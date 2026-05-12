"""
Tek XLSX Menü Import Scripti
═════════════════════════════
Okuldan alınan aylık menü Excel dosyasını sisteme ekler:
  1) menu_data.csv'ye append
  2) nutrition_data.csv'ye yeni yemekleri ekler
  3) DB → Menu tablosu
  4) DB → Yemek tablosu (eksik yemekler)
  5) DB → UretimLog (üretim verisi oluşturur)

Kullanım:
    py scripts/data/import_xlsx_menu.py "C:/path/to/MAYIS 2026.xlsx"
"""

import csv
import os
import re
import sys
import random
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import openpyxl
except ImportError:
    print("openpyxl bulunamadi. Kurulum: py -m pip install openpyxl")
    sys.exit(1)

from models import init_db, SessionLocal, Yemek, Menu, UretimLog, MenuPuanlama
from sqlalchemy import func

# ─── Yollar ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..", "..")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MENU_CSV = os.path.join(DATA_DIR, "menu_data.csv")
NUTRITION_CSV = os.path.join(DATA_DIR, "nutrition_data.csv")

# ─── Gün Adları ──────────────────────────────────────────────────
GUN_ADLARI = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba",
    3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar",
}

# ─── Yazım Düzeltmeleri ─────────────────────────────────────────
TYPO_FIXES = {
    "Mecimek Çorba": "Mercimek Çorba",
    "Brokoli Çoba": "Brokoli Çorba",
    "Taze Fasülye": "Taze Fasulye",
    "Kuru Fasülye": "Kuru Fasulye",
}

# ─── Atlanacak Anahtar Kelimeler ─────────────────────────────────
SKIP_KEYWORDS = [
    "RESMİ TATİL", "Diyetisyen", "Daire Başkanı",
    "ANKARA YILDIRIM", "SAĞLIK", "Ayı Yemek Listesi",
    "Büşra", "Şevin", "Sadullah",
]


def fix_typos(name: str) -> str:
    for wrong, correct in TYPO_FIXES.items():
        if wrong in name:
            name = name.replace(wrong, correct)
    return name


def parse_food_entry(entry: str):
    """'Mercimek Çorba 186 kkal' → ('Mercimek Çorba', 186)"""
    if not entry or not entry.strip():
        return None, None
    entry = entry.strip()
    for kw in SKIP_KEYWORDS:
        if kw in entry:
            return None, None
    entry = fix_typos(entry)
    pattern = r'^(.+?)\s*(\d+)\s*(?:kkal|kkla|kcal|kka|kal)\s*$'
    match = re.match(pattern, entry, re.IGNORECASE)
    if match:
        yemek_adi = re.sub(r'\s+', ' ', match.group(1).strip()).strip()
        return yemek_adi, int(match.group(2))
    return re.sub(r'\s+', ' ', entry).strip(), None


def classify_food(name: str) -> str:
    """Yemek adından kategori tahmin et."""
    lower = name.lower()

    if "çorba" in lower:
        return "corba"

    ana_kw = [
        "tavuk", "köfte", "kebab", "kebabı", "sote", "kavurma", "döner",
        "fasulye", "nohut", "musakka", "karnıyarık", "dolma", "sarma",
        "fajita", "tantuni", "burger", "hamburger", "şiş", "pirzola",
        "haşlama", "pane", "kızartma", "kapama", "oturtma", "graten",
        "rosto", "büryan", "ciğer", "balık", "hamsi", "uskumru", "türlü",
        "bezelye", "pırasa", "ıspanak", "ispanak", "karnabahar", "kapuska",
        "mücver", "şinitzel", "stroganoff", "gulaş", "navarin", "tava",
        "külbastı", "barbunya", "bamya", "baget", "but ",
    ]
    for kw in ana_kw:
        if kw in lower:
            return "ana_yemek"

    pilav_kw = ["pilav", "pilavı", "makarna", "erişte", "börek", "böreği",
                "mantı", "patates kız", "soğan halkası", "patates ve"]
    for kw in pilav_kw:
        if kw in lower:
            return "pilav"

    tatli_kw = [
        "baklava", "tatlı", "tatlısı", "helva", "helvası", "puding",
        "trileçe", "sütlaç", "keşkül", "revani", "muhallebi", "komposto",
        "brownie", "ekler", "tiramisu", "kek", "kalburabastı", "şekerpare",
        "kadayıf", "aşure", "sultan", "kemalpaşa", "kazandibi", "parmağı",
    ]
    for kw in tatli_kw:
        if kw in lower:
            return "tatli"

    salata_kw = ["salata", "cacık", "tarator", "haydari", "piyaz",
                 "turşu", "borani", "ezme", "kısır", "söğüş", "coleslow"]
    for kw in salata_kw:
        if kw in lower:
            return "salata"

    if lower.strip() in ["ayran"] or "şalgam" in lower or "limonata" in lower:
        return "icecek"

    if lower.startswith("meyve") or lower.strip() in ["portakal", "mandalina", "elma", "muz"]:
        return "meyve"

    if lower.strip() == "yoğurt":
        return "salata"

    if lower.startswith("zyt") or lower.startswith("zeytinyağlı"):
        return "ana_yemek"

    return "ana_yemek"


def assign_menu_categories(yemekler):
    """Yemek listesini menü slot'larına ata."""
    result = {'corba': None, 'ana_yemek': None, 'pilav_makarna': None, 'tatli': None, 'salata': None}
    used = set()

    for idx, (name, kalori) in enumerate(yemekler):
        cat = classify_food(name)
        if cat == "corba" and result['corba'] is None:
            result['corba'] = name; used.add(idx)
        elif cat == "pilav" and result['pilav_makarna'] is None:
            result['pilav_makarna'] = name; used.add(idx)
        elif cat == "tatli" and result['tatli'] is None:
            result['tatli'] = name; used.add(idx)
        elif cat in ("salata", "icecek", "meyve") and result['salata'] is None:
            result['salata'] = name; used.add(idx)

    for idx, (name, kalori) in enumerate(yemekler):
        if idx in used:
            continue
        cat = classify_food(name)
        if cat == "ana_yemek" and result['ana_yemek'] is None:
            result['ana_yemek'] = name; used.add(idx); break

    for idx, (name, kalori) in enumerate(yemekler):
        if idx in used:
            continue
        cat = classify_food(name)
        if cat in ("salata", "icecek", "meyve") and result['salata'] is None:
            result['salata'] = name; used.add(idx)
        elif cat == "tatli" and result['tatli'] is None:
            result['tatli'] = name; used.add(idx)
        elif cat == "ana_yemek":
            if result['ana_yemek'] is None:
                result['ana_yemek'] = name; used.add(idx)
            elif result['pilav_makarna'] is None:
                result['pilav_makarna'] = name; used.add(idx)

    return result


def estimate_macros(kalori, kategori):
    if kalori is None or kalori == 0:
        return 0, 0, 0
    ratios = {
        "corba": (0.15, 0.55, 0.30), "ana_yemek": (0.30, 0.30, 0.40),
        "pilav": (0.10, 0.70, 0.20), "tatli": (0.05, 0.65, 0.30),
        "salata": (0.10, 0.50, 0.40), "icecek": (0.15, 0.60, 0.25),
        "meyve": (0.05, 0.85, 0.10),
    }.get(kategori, (0.20, 0.40, 0.40))
    return round(kalori * ratios[0] / 4, 1), round(kalori * ratios[1] / 4, 1), round(kalori * ratios[2] / 9, 1)


# ═════════════════════════════════════════════════════════════════
# EXCEL PARSE
# ═════════════════════════════════════════════════════════════════

def parse_xlsx(filepath):
    """Excel dosyasını parse edip menü listesi döndürür."""
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    all_rows = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()

    menu_entries = []
    i = 0

    while i < len(all_rows):
        row = all_rows[i]
        dates = []
        is_date_row = False
        for cell in row:
            if cell and isinstance(cell, datetime):
                dates.append(cell.date())
                is_date_row = True
            elif cell and isinstance(cell, str) and re.match(r'\d{4}-\d{2}-\d{2}', str(cell)):
                dates.append(datetime.strptime(cell[:10], "%Y-%m-%d").date())
                is_date_row = True
            else:
                dates.append(None)

        if not is_date_row:
            i += 1
            continue

        # Sonraki 4-5 satırı yemek satırı olarak oku
        food_rows = []
        j = i + 1
        while j < len(all_rows) and j <= i + 5:
            next_row = all_rows[j]
            # Sonraki tarih satırı veya imza satırıysa dur
            has_date = any(isinstance(c, datetime) for c in next_row if c)
            if has_date:
                break
            first_val = str(next_row[0]).strip() if next_row[0] else ""
            if any(kw in first_val for kw in ["Diyetisyen", "Büşra"]):
                break
            if any(c and "Diyetisyen" in str(c) for c in next_row):
                break
            food_rows.append(next_row)
            j += 1

        # Her sütun (gün) için menü oluştur
        for col_idx, d in enumerate(dates):
            if d is None:
                continue
            yemekler = []
            for food_row in food_rows:
                if col_idx < len(food_row) and food_row[col_idx]:
                    yemek_adi, kalori = parse_food_entry(str(food_row[col_idx]))
                    if yemek_adi:
                        yemekler.append((yemek_adi, kalori))
            if yemekler:
                gun = GUN_ADLARI.get(d.weekday(), "Bilinmiyor")
                menu_entries.append({'tarih': d, 'gun': gun, 'yemekler': yemekler})

        i = j

    return menu_entries


# ═════════════════════════════════════════════════════════════════
# IMPORT İŞLEMLERİ
# ═════════════════════════════════════════════════════════════════

def import_to_csv(menus, all_foods):
    """menu_data.csv ve nutrition_data.csv'ye ekle."""

    # 1) menu_data.csv — mevcut tarihleri oku, sadece yenileri ekle
    mevcut_tarihler = set()
    if os.path.exists(MENU_CSV):
        with open(MENU_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mevcut_tarihler.add(row["tarih"].strip())

    eklenen_csv = 0
    with open(MENU_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for m in menus:
            tarih_str = m["tarih"].strftime("%Y-%m-%d")
            if tarih_str in mevcut_tarihler:
                continue
            cats = assign_menu_categories(m["yemekler"])
            writer.writerow([
                tarih_str, m["gun"],
                cats["corba"] or "", cats["ana_yemek"] or "",
                cats["pilav_makarna"] or "", cats["tatli"] or "",
                cats["salata"] or "", "",
            ])
            eklenen_csv += 1
    print(f"   📄 menu_data.csv: {eklenen_csv} yeni gün eklendi")

    # 2) nutrition_data.csv — mevcut yemekleri oku, yenileri ekle
    mevcut_yemekler = set()
    if os.path.exists(NUTRITION_CSV):
        with open(NUTRITION_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mevcut_yemekler.add(row["yemek_adi"].strip())

    eklenen_nut = 0
    with open(NUTRITION_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for yemek_adi, info in sorted(all_foods.items()):
            if yemek_adi in mevcut_yemekler:
                continue
            kalori = info["kalori"] or 0
            kategori = info["kategori"]
            protein, karb, yag = estimate_macros(kalori, kategori)
            porsiyon = {"corba": 250, "ana_yemek": 250, "pilav": 200,
                        "tatli": 150, "salata": 150, "icecek": 200,
                        "meyve": 150}.get(kategori, 200)
            writer.writerow([yemek_adi, porsiyon, kalori, protein, karb, yag, round(karb * 0.1, 1)])
            eklenen_nut += 1
    print(f"   📄 nutrition_data.csv: {eklenen_nut} yeni yemek eklendi")


def import_to_db(menus, all_foods):
    """Veritabanına Menu, Yemek ve UretimLog ekle."""
    init_db()
    db = SessionLocal()

    try:
        # ── 1) Yemek tablosu: eksik yemekleri ekle ──
        yemek_eklenen = 0
        for yemek_adi, info in all_foods.items():
            mevcut = db.query(Yemek).filter(Yemek.ad == yemek_adi).first()
            if not mevcut:
                raw_cat = info["kategori"]
                # DB kategorisi: pilav → yan_yemek, meyve/icecek → tatli/salata
                db_kategori = {
                    "corba": "corba", "ana_yemek": "ana_yemek",
                    "pilav": "yan_yemek", "tatli": "tatli",
                    "salata": "salata", "icecek": "salata", "meyve": "tatli",
                }.get(raw_cat, "ana_yemek")
                kalori = info["kalori"] or 0
                protein, karb, yag = estimate_macros(kalori, raw_cat)
                yemek = Yemek(
                    ad=yemek_adi, kategori=db_kategori,
                    kalori=kalori, protein=protein, karbonhidrat=karb, yag=yag,
                )
                db.add(yemek)
                yemek_eklenen += 1
        db.commit()
        print(f"   🍽️  Yemek tablosu: {yemek_eklenen} yeni yemek eklendi")

        # ── 2) Menu tablosu: yeni günleri ekle ──
        menu_eklenen = 0
        for m in menus:
            mevcut = db.query(Menu).filter(Menu.tarih == m["tarih"]).first()
            if mevcut:
                continue
            cats = assign_menu_categories(m["yemekler"])
            menu = Menu(
                tarih=m["tarih"], gun=m["gun"],
                corba=cats["corba"],
                ana_yemek=cats["ana_yemek"],
                yan_yemek=cats["pilav_makarna"],
                tatli=cats["tatli"],
                salata=cats["salata"],
            )
            db.add(menu)
            menu_eklenen += 1
        db.commit()
        print(f"   📅 Menu tablosu: {menu_eklenen} yeni gün eklendi")

        # ── 3) UretimLog: üretim verisi oluştur ──
        puan_ort = {}
        puanlar = (
            db.query(MenuPuanlama.yemek_adi, func.avg(MenuPuanlama.puan).label("ort"))
            .group_by(MenuPuanlama.yemek_adi).all()
        )
        for p in puanlar:
            puan_ort[p.yemek_adi] = float(p.ort)

        log_eklenen = 0
        for m in menus:
            cats = assign_menu_categories(m["yemekler"])
            yemek_pairs = [
                (cats["corba"], "corba"),
                (cats["ana_yemek"], "ana_yemek"),
                (cats["pilav_makarna"], "yan_yemek"),
                (cats["tatli"], "tatli"),
                (cats["salata"], "salata"),
            ]
            for yemek_adi, kategori in yemek_pairs:
                if not yemek_adi:
                    continue
                mevcut = (
                    db.query(UretimLog)
                    .filter(UretimLog.tarih == m["tarih"], UretimLog.yemek_adi == yemek_adi)
                    .first()
                )
                if mevcut:
                    continue

                ort_puan = puan_ort.get(yemek_adi, 3.0)
                porsiyon_bazlari = {
                    "corba": (750, 1000), "ana_yemek": (700, 950),
                    "yan_yemek": (700, 950), "tatli": (650, 900), "salata": (600, 850),
                }
                min_p, max_p = porsiyon_bazlari.get(kategori, (700, 900))
                uretilen = random.randint(min_p, max_p)

                baz_israf = max(0, min(100, 85 - (ort_puan * 16)))
                varyans = random.uniform(-8, 8)
                israf_orani = max(2, min(85, baz_israf + varyans))

                if "Cuma" in (m["gun"] or ""):
                    israf_orani = min(85, israf_orani + random.uniform(2, 6))
                elif "Pazartesi" in (m["gun"] or ""):
                    israf_orani = min(85, israf_orani + random.uniform(1, 4))

                kalan = int(uretilen * (israf_orani / 100))
                log = UretimLog(
                    tarih=m["tarih"], yemek_adi=yemek_adi, kategori=kategori,
                    uretilen_porsiyon=uretilen, kalan_porsiyon=kalan,
                    tuketim_orani=round(100 - israf_orani, 1),
                    israf_orani=round(israf_orani, 1),
                    notlar=f"Ort.puan: {ort_puan:.1f}",
                )
                db.add(log)
                log_eklenen += 1

        db.commit()
        print(f"   📊 UretimLog: {log_eklenen} üretim kaydı oluşturuldu")

        # Özet
        print(f"\n   Toplam Menu: {db.query(Menu).count()}")
        print(f"   Toplam Yemek: {db.query(Yemek).count()}")
        print(f"   Toplam UretimLog: {db.query(UretimLog).count()}")

    except Exception as e:
        db.rollback()
        print(f"❌ DB Hatası: {e}")
        raise
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════
# ANA FONKSİYON
# ═════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Kullanım: py scripts/data/import_xlsx_menu.py <dosya.xlsx>")
        sys.exit(1)

    xlsx_path = sys.argv[1]
    if not os.path.exists(xlsx_path):
        print(f"❌ Dosya bulunamadı: {xlsx_path}")
        sys.exit(1)

    print("=" * 60)
    print("  📥 XLSX Menü Import Scripti")
    print("=" * 60)
    print(f"  Dosya: {os.path.basename(xlsx_path)}")

    # 1) Excel'i parse et
    menus = parse_xlsx(xlsx_path)
    print(f"\n  📋 {len(menus)} günlük menü bulundu:")

    # Benzersiz yemekleri topla
    all_foods = {}
    for m in menus:
        print(f"     {m['tarih']} ({m['gun']}): {', '.join(y[0] for y in m['yemekler'])}")
        for yemek_adi, kalori in m["yemekler"]:
            cat = classify_food(yemek_adi)
            if yemek_adi not in all_foods:
                all_foods[yemek_adi] = {"kalori": kalori, "kategori": cat}
            elif kalori and all_foods[yemek_adi]["kalori"] is None:
                all_foods[yemek_adi]["kalori"] = kalori

    print(f"\n  🍽️  {len(all_foods)} benzersiz yemek bulundu")

    # Kategori atamasını göster
    print(f"\n  📊 Menü Atamaları:")
    for m in menus:
        cats = assign_menu_categories(m["yemekler"])
        print(f"     {m['tarih']} → Ç:{cats['corba'] or '-'} | A:{cats['ana_yemek'] or '-'} | Y:{cats['pilav_makarna'] or '-'} | T:{cats['tatli'] or '-'} | S:{cats['salata'] or '-'}")

    # 2) CSV'ye ekle
    print(f"\n{'=' * 60}")
    print("  📄 CSV Dosyaları Güncelleniyor...")
    import_to_csv(menus, all_foods)

    # 3) DB'ye ekle
    print(f"\n{'=' * 60}")
    print("  🗄️  Veritabanı Güncelleniyor...")
    import_to_db(menus, all_foods)

    print(f"\n{'=' * 60}")
    print("  🎉 Import tamamlandı!")
    print("=" * 60)


if __name__ == "__main__":
    main()
