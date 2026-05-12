"""
XLSX → CSV Dönüştürme Scripti
══════════════════════════════
'aylara göre yemek listeleri' klasöründeki tüm xlsx dosyalarını
okuyarak data/menu_data.csv ve data/nutrition_data.csv dosyalarını üretir.

Kullanım:
    py scripts/convert_xlsx_to_csv.py
"""

import csv
import os
import re
import sys
from datetime import datetime

try:
    import openpyxl
except ImportError:
    print("openpyxl bulunamadı. Kurulum: py -m pip install openpyxl")
    sys.exit(1)

# ─── Yollar ───────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
XLSX_DIR = os.path.join(PROJECT_ROOT, "..", "aylara göre yemek listeleri")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MENU_CSV = os.path.join(DATA_DIR, "menu_data.csv")
NUTRITION_CSV = os.path.join(DATA_DIR, "nutrition_data.csv")

# ─── Gün adları ───────────────────────────────────────────────────
GUN_ADLARI = {
    0: "Pazartesi",
    1: "Salı",
    2: "Çarşamba",
    3: "Perşembe",
    4: "Cuma",
    5: "Cumartesi",
    6: "Pazar",
}

# ─── Yazım düzeltmeleri ──────────────────────────────────────────
TYPO_FIXES = {
    "Mecimek Çorba": "Mercimek Çorba",
    "Brokoli Çoba": "Brokoli Çorba",
    "Taze Fasülye": "Taze Fasulye",
    "Kuru Fasülye": "Kuru Fasulye",
}

# ─── Kategori tahmini (yemek adından) ────────────────────────────
# Her satır bir kategoriyi temsil eder: corba, ana_yemek, pilav_makarna, tatli, salata
# Excel'de sıralama: Satır 1=Çorba, Satır 2=Ana Yemek, Satır 3=Pilav/Makarna, Satır 4=Tatlı/Salata
# Bazı dosyalarda 5 satır olabilir (ek yan yemek)
ROW_CATEGORY_MAP = {
    0: "corba",
    1: "ana_yemek",
    2: "pilav_makarna",
    3: "tatli",
    4: "salata",   # 5. satır varsa ek
}


def fix_typos(name: str) -> str:
    """Bilinen yazım hatalarını düzelt."""
    for wrong, correct in TYPO_FIXES.items():
        if wrong in name:
            name = name.replace(wrong, correct)
    return name


def parse_food_entry(entry: str):
    """
    'Mercimek Çorba 186 kkal' → ('Mercimek Çorba', 186)
    'Soslu Makarna' → ('Soslu Makarna', None)
    'RESMİ TATİL' → (None, None)
    
    Returns: (yemek_adi, kalori) or (None, None)
    """
    if not entry or not entry.strip():
        return None, None
    
    entry = entry.strip()
    
    # Resmi tatil veya meta satır kontrolü
    skip_keywords = ["RESMİ TATİL", "Diyetisyen", "Daire Başkanı", 
                     "ANKARA YILDIRIM", "SAĞLIK", "Ayı Yemek Listesi",
                     "Büşra", "Şevin", "Sadullah"]
    for kw in skip_keywords:
        if kw in entry:
            return None, None
    
    entry = fix_typos(entry)
    
    # Kalori bilgisini parse et: "Yemek Adı XXX kkal" veya "Yemek Adı XXX kcal"
    # Bazen "kkal" yerine "kkla" veya boşluksuz "162kkal" olabilir
    pattern = r'^(.+?)\s*(\d+)\s*(?:kkal|kkla|kcal|kal)\s*$'
    match = re.match(pattern, entry, re.IGNORECASE)
    
    if match:
        yemek_adi = match.group(1).strip()
        kalori = int(match.group(2))
        # Sonundaki fazla boşlukları temizle
        yemek_adi = re.sub(r'\s+', ' ', yemek_adi).strip()
        return yemek_adi, kalori
    
    # Kalori bilgisi yok
    yemek_adi = re.sub(r'\s+', ' ', entry).strip()
    return yemek_adi, None


def is_date_row(row):
    """Satırın tarih satırı olup olmadığını kontrol et."""
    for cell in row:
        if cell and isinstance(cell, datetime):
            return True
        if cell and isinstance(cell, str) and re.match(r'\d{4}-\d{2}-\d{2}', str(cell)):
            return True
    return False


def parse_date(val):
    """Hücredeki tarih değerini date nesnesine çevir."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        match = re.match(r'(\d{4}-\d{2}-\d{2})', val)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    return None


def parse_xlsx_file(filepath):
    """
    Bir Excel dosyasını parse edip günlük menü listesi döndürür.
    
    Returns: list of dict, her biri:
        {
            'tarih': date,
            'gun': str,
            'yemekler': [('yemek_adi', kalori), ...]  # satır sırasına göre
        }
    """
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    
    all_rows = []
    for row in ws.iter_rows(values_only=True):
        all_rows.append(list(row))
    
    menu_entries = []
    i = 0
    
    while i < len(all_rows):
        row = all_rows[i]
        
        # Tarih satırı bul
        if is_date_row(row):
            dates = []
            for cell in row:
                d = parse_date(cell) if cell else None
                dates.append(d)
            
            # Sonraki 4-5 satır yemek satırları
            food_rows = []
            j = i + 1
            while j < len(all_rows) and j <= i + 5:
                next_row = all_rows[j]
                # Eğer sonraki satır bir tarih satırı ise dur
                if is_date_row(next_row):
                    break
                # Eğer "Diyetisyen" gibi imza satırı ise dur
                first_val = str(next_row[0]).strip() if next_row[0] else ""
                if first_val in ["Diyetisyen", "Büşra TEKİN", ""]:
                    skip = False
                    for cell in next_row:
                        if cell and "Diyetisyen" in str(cell):
                            skip = True
                            break
                    if skip:
                        break
                food_rows.append(next_row)
                j += 1
            
            # Her tarih sütunu için menü oluştur
            for col_idx, d in enumerate(dates):
                if d is None:
                    continue
                
                yemekler = []
                for food_row in food_rows:
                    if col_idx < len(food_row):
                        cell_val = food_row[col_idx]
                        if cell_val:
                            yemek_adi, kalori = parse_food_entry(str(cell_val))
                            if yemek_adi:
                                yemekler.append((yemek_adi, kalori))
                
                if yemekler:  # En az bir yemek varsa
                    gun = GUN_ADLARI.get(d.weekday(), "Bilinmiyor")
                    menu_entries.append({
                        'tarih': d,
                        'gun': gun,
                        'yemekler': yemekler,
                    })
            
            i = j  # Yemek satırlarını atla
        else:
            i += 1
    
    wb.close()
    return menu_entries


def classify_food(name: str) -> str:
    """
    Yemek adından kategorisini tahmin et.
    """
    lower = name.lower()
    
    # Çorba
    if "çorba" in lower:
        return "corba"
    
    # Ana yemek kesin anahtar kelimeler (tatlı/pilav'dan ÖNCE kontrol et)
    ana_yemek_keywords = [
        "tavuk", "köfte", "kebab", "kebabı", "sote", "kavurma", "döner",
        "köfte", "fasulye", "fasülye", "nohut", "musakka", "karnıyarık",
        "dolma", "sarma", "fajita", "fajıta", "tantuni", "burger", "hamburger",
        "şiş", "pirzola", "haşlama", "pane", "kızartma", "kapama",
        "oturtma", "graten", "rosto", "büryan", "ciğer", "balık", "hamsi",
        "uskumru", "türlü", "bezelye", "pırasa", "ıspanak", "ispanak",
        "karnabahar", "kapuska", "mücver", "şinitzel", "schnitzel",
        "stroganoff", "gulaş", "navarin", "tava", "külbastı",
        "barbunya", "bamya",
    ]
    for kw in ana_yemek_keywords:
        if kw in lower:
            return "ana_yemek"
    
    # Pilav / Makarna / Börek türevleri
    pilav_keywords = ["pilav", "pilavı", "makarna", "erişte", "börek", "böreği",
                       "mantı", "patates kız", "soğan halkası"]
    for kw in pilav_keywords:
        if kw in lower:
            return "pilav"
    
    # Tatlı
    tatli_keywords = ["baklava", "tatlı", "tatlısı", "helva", "helvası", "puding",
                       "trileçe", "sütlaç", "keşkül", "revani", "muhallebi",
                       "komposto", "brownie", "ekler", "tiramisu", "kek", 
                       "kalburabastı", "şekerpare", "kadayıf", "aşure",
                       "sultan", "kemalpaşa"]
    for kw in tatli_keywords:
        if kw in lower:
            return "tatli"
    
    # Salata / Meze / Yan yemek
    salata_keywords = ["salata", "cacık", "tarator", "haydari", "piyaz",
                        "turşu", "borani", "ezme", "kısır", "söğüş",
                        "coleslow"]
    for kw in salata_keywords:
        if kw in lower:
            return "salata"
    
    # İçecek
    if lower.strip() in ["ayran"] or "şalgam" in lower:
        return "icecek"
    
    # Meyve
    if (lower.startswith("meyve") or 
        lower.strip() in ["portakal", "mandalina", "elma", "muz"]):
        return "meyve"
    
    # Yoğurt tek başına
    if lower.strip() == "yoğurt":
        return "salata"
    
    # Zyt. ile başlayan yemekler (Zeytinyağlı) genellikle ana yemek veya pilav yanı
    if lower.startswith("zyt") or lower.startswith("zeytinyağlı"):
        return "ana_yemek"
    
    # Geri kalan her şey ana yemek
    return "ana_yemek"


def assign_menu_categories(yemekler):
    """
    Yemek listesini menü kategorilerine ata.
    Excel'deki sıralama genellikle: çorba, ana yemek, pilav/makarna, tatlı/salata, ek
    Akıllı atama + Excel sıralamasını ipucu olarak kullan.
    """
    result = {
        'corba': None,
        'ana_yemek': None,
        'pilav_makarna': None,
        'tatli': None,
        'salata': None,
    }
    
    used = set()
    
    # İlk geçiş: kesin kategoriler (çorba, pilav, tatlı, salata)
    for idx, (name, kalori) in enumerate(yemekler):
        cat = classify_food(name)
        
        if cat == "corba" and result['corba'] is None:
            result['corba'] = name
            used.add(idx)
        elif cat == "pilav" and result['pilav_makarna'] is None:
            result['pilav_makarna'] = name
            used.add(idx)
        elif cat == "tatli" and result['tatli'] is None:
            result['tatli'] = name
            used.add(idx)
        elif cat in ("salata", "icecek", "meyve") and result['salata'] is None:
            result['salata'] = name
            used.add(idx)
    
    # İkinci geçiş: ana yemek (kalan ana_yemek'leri ata)
    for idx, (name, kalori) in enumerate(yemekler):
        if idx in used:
            continue
        cat = classify_food(name)
        if cat == "ana_yemek" and result['ana_yemek'] is None:
            result['ana_yemek'] = name
            used.add(idx)
            break
    
    # Üçüncü geçiş: kalan boş slotlara ata
    for idx, (name, kalori) in enumerate(yemekler):
        if idx in used:
            continue
        cat = classify_food(name)
        if cat in ("salata", "icecek", "meyve") and result['salata'] is None:
            result['salata'] = name
            used.add(idx)
        elif cat == "tatli" and result['tatli'] is None:
            result['tatli'] = name
            used.add(idx)
        elif cat == "ana_yemek":
            # İkinci ana yemek, boş olan herhangi bir slota koy
            if result['ana_yemek'] is None:
                result['ana_yemek'] = name
                used.add(idx)
            elif result['pilav_makarna'] is None:
                result['pilav_makarna'] = name  # Yan yemek olarak pilav slotuna
                used.add(idx)
    
    return result


def estimate_macros(kalori, kategori):
    """
    Kalori değerinden tahmini makro besin değerleri hesapla.
    Kategoriye göre makro dağılımı.
    """
    if kalori is None or kalori == 0:
        return 0, 0, 0, 0
    
    # Kategoriye göre tahmini makro yüzdeleri (protein%, karb%, fat%)
    macro_ratios = {
        "corba":       (0.15, 0.55, 0.30),
        "ana_yemek":   (0.30, 0.30, 0.40),
        "pilav":       (0.10, 0.70, 0.20),
        "tatli":       (0.05, 0.65, 0.30),
        "salata":      (0.10, 0.50, 0.40),
        "icecek":      (0.15, 0.60, 0.25),
        "meyve":       (0.05, 0.85, 0.10),
        "diger":       (0.20, 0.40, 0.40),
    }
    
    ratios = macro_ratios.get(kategori, macro_ratios["diger"])
    protein_cal = kalori * ratios[0]
    carb_cal = kalori * ratios[1]
    fat_cal = kalori * ratios[2]
    
    protein_g = round(protein_cal / 4, 1)   # 4 cal/g protein
    carb_g = round(carb_cal / 4, 1)         # 4 cal/g karbonhidrat
    fat_g = round(fat_cal / 9, 1)           # 9 cal/g yağ
    lif_g = round(carb_g * 0.1, 1)          # Tahmini lif
    
    return protein_g, carb_g, fat_g, lif_g


def estimate_portion(kategori):
    """Kategoriye göre tahmini porsiyon gramı."""
    portions = {
        "corba": 250,
        "ana_yemek": 250,
        "pilav": 200,
        "tatli": 150,
        "salata": 150,
        "icecek": 200,
        "meyve": 150,
        "diger": 200,
    }
    return portions.get(kategori, 200)


def main():
    print("=" * 60)
    print("  XLSX → CSV Dönüştürme Scripti")
    print("=" * 60)
    
    # XLSX dosyalarını bul
    if not os.path.isdir(XLSX_DIR):
        print(f"❌ XLSX klasörü bulunamadı: {XLSX_DIR}")
        sys.exit(1)
    
    xlsx_files = sorted([f for f in os.listdir(XLSX_DIR) if f.endswith('.xlsx')])
    print(f"\n📂 {len(xlsx_files)} Excel dosyası bulundu:")
    for f in xlsx_files:
        print(f"   📄 {f}")
    
    # Tüm dosyaları parse et
    all_menus = []
    all_foods = {}  # yemek_adi -> {kalori, kategori}
    
    for f in xlsx_files:
        filepath = os.path.join(XLSX_DIR, f)
        print(f"\n🔄 İşleniyor: {f}")
        
        entries = parse_xlsx_file(filepath)
        print(f"   ✅ {len(entries)} gün menü bulundu")
        
        for entry in entries:
            all_menus.append(entry)
            
            # Besin bilgilerini topla
            for yemek_adi, kalori in entry['yemekler']:
                kategori = classify_food(yemek_adi)
                if yemek_adi not in all_foods:
                    all_foods[yemek_adi] = {'kalori': kalori, 'kategori': kategori}
                elif kalori and (all_foods[yemek_adi]['kalori'] is None):
                    all_foods[yemek_adi]['kalori'] = kalori
    
    # Tarihe göre sırala
    all_menus.sort(key=lambda x: x['tarih'])
    
    # Duplicate tarihleri temizle (aynı tarih birden fazla dosyada olabilir)
    seen_dates = set()
    unique_menus = []
    for m in all_menus:
        if m['tarih'] not in seen_dates:
            seen_dates.add(m['tarih'])
            unique_menus.append(m)
    
    print(f"\n📊 Toplam: {len(unique_menus)} benzersiz gün, {len(all_foods)} benzersiz yemek")
    
    # ─── menu_data.csv oluştur ────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print(f"\n📝 menu_data.csv yazılıyor...")
    with open(MENU_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['tarih', 'gun', 'corba', 'ana_yemek', 'pilav_makarna', 'tatli', 'salata', 'ek_bilgi'])
        
        for m in unique_menus:
            cats = assign_menu_categories(m['yemekler'])
            writer.writerow([
                m['tarih'].strftime('%Y-%m-%d'),
                m['gun'],
                cats['corba'] or '',
                cats['ana_yemek'] or '',
                cats['pilav_makarna'] or '',
                cats['tatli'] or '',
                cats['salata'] or '',
                '',  # ek_bilgi
            ])
    
    print(f"   ✅ {len(unique_menus)} satır yazıldı")
    
    # ─── nutrition_data.csv oluştur ───────────────────────────────
    print(f"\n📝 nutrition_data.csv yazılıyor...")
    with open(NUTRITION_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['yemek_adi', 'porsiyon_gram', 'kalori', 'protein_g', 'karbonhidrat_g', 'yag_g', 'lif_g'])
        
        food_count = 0
        for yemek_adi in sorted(all_foods.keys()):
            info = all_foods[yemek_adi]
            kalori = info['kalori'] or 0
            kategori = info['kategori']
            porsiyon = estimate_portion(kategori)
            protein, karb, yag, lif = estimate_macros(kalori, kategori)
            
            writer.writerow([
                yemek_adi,
                porsiyon,
                kalori,
                protein,
                karb,
                yag,
                lif,
            ])
            food_count += 1
    
    print(f"   ✅ {food_count} yemek yazıldı")
    
    # ─── Özet ─────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  📊 Dönüştürme Özeti")
    print(f"{'=' * 60}")
    print(f"  📅 Tarih aralığı   : {unique_menus[0]['tarih']} → {unique_menus[-1]['tarih']}")
    print(f"  📅 Toplam gün      : {len(unique_menus)}")
    print(f"  🍽️  Benzersiz yemek : {len(all_foods)}")
    print(f"  📂 menu_data.csv   : {MENU_CSV}")
    print(f"  📂 nutrition_data  : {NUTRITION_CSV}")
    print(f"{'=' * 60}")
    
    # ─── Kategori istatistikleri ──────────────────────────────────
    cat_counts = {}
    for name, info in all_foods.items():
        cat = info['kategori']
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    print(f"\n  📊 Kategori Dağılımı:")
    for cat, count in sorted(cat_counts.items()):
        print(f"     {cat:15s} → {count:3d} yemek")
    
    # ─── KATEGORI_MAP ve POPULERLIK sözlükleri için çıktı ────────
    print(f"\n  📋 KATEGORI_MAP için yemek listesi (load_menu_data.py'ye eklenecek):")
    for cat in sorted(cat_counts.keys()):
        foods_in_cat = [(n, i) for n, i in all_foods.items() if i['kategori'] == cat]
        print(f"\n  # {cat}")
        for name, _ in sorted(foods_in_cat):
            print(f'    "{name}": "{cat}",')
    
    print(f"\n  🎉 Dönüştürme başarıyla tamamlandı!")


if __name__ == "__main__":
    main()
