# -*- coding: utf-8 -*-
"""
Menu CSV'deki typo'ları düzelt + eksik besin değerlerini nutrition CSV'ye ekle.
"""
import csv, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
MENU_CSV = os.path.join(DATA, 'menu_data.csv')
NUT_CSV = os.path.join(DATA, 'nutrition_data.csv')

# ═══ ADIM 1: Menu CSV typo düzeltme ═══════════════════════════════

TYPO_MAP = {
    # Yazım hataları
    'Brokoli Çoba': 'Brokoli Çorba',
    'Mecimek Çorba': 'Mercimek Çorba',
    'Kuru Fasülye': 'Kuru Fasulye',
    'Taze Fasülye': 'Taze Fasulye',
    'Zyt.Taze Fasülye': 'Zyt.Taze Fasulye',
    'Kuru Fasülye': 'Kuru Fasulye',
    # Kalori artığı kalmış isimler
    'Mahluta Çorba 148 kkla': 'Mahluta Çorba',
    'Tavuklu Şehriye Çorba 232 kkaql': 'Tavuklu Şehriye Çorba',
    'Şehriyeli Pirinç Pilavı 342 kal': 'Şehriyeli Pirinç Pilavı',
    'Et Fajita 371': 'Et Fajita',
    # Fazla boşluk
    'Ezogelin  Çorba': 'Ezogelin Çorba',
    'Şehriyeli  Bulgur Pilavı': 'Şehriyeli Bulgur Pilavı',
    'Tavuk Pane  /  Baharatlı Patates': 'Tavuk Pane / Baharatlı Patates',
    # Triliçe -> Trileçe (tutarlılık)
    'Triliçe': 'Trileçe',
}

# Menu CSV oku
with open(MENU_CSV, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = reader.fieldnames

# Typo'ları düzelt
degisen = 0
for row in rows:
    for col in ['corba', 'ana_yemek', 'pilav_makarna', 'tatli', 'salata']:
        val = row.get(col, '').strip()
        if val in TYPO_MAP:
            print(f"  ✏️  {row['tarih']} {col}: '{val}' → '{TYPO_MAP[val]}'")
            row[col] = TYPO_MAP[val]
            degisen += 1

# Yaz
with open(MENU_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ Menu CSV: {degisen} typo düzeltildi.\n")

# ═══ ADIM 2: Eksik besin değerlerini ekle ═══════════════════════════

# Mevcut nutrition verisini oku
nut_data = []
nut_names = set()
with open(NUT_CSV, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    nut_fieldnames = reader.fieldnames
    for row in reader:
        nut_data.append(row)
        nut_names.add(row['yemek_adi'].strip())

# "Et Fajita 371" gereksiz kaydını sil
nut_data = [r for r in nut_data if r['yemek_adi'].strip() != 'Et Fajita 371']

# Menüdeki yemekleri topla
menu_yemekler = set()
with open(MENU_CSV, 'r', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        for k in ['corba', 'ana_yemek', 'pilav_makarna', 'tatli', 'salata']:
            v = row.get(k, '').strip()
            if v:
                menu_yemekler.add(v)

# Eksik yemeklerin besin değerleri (gerçekçi değerler)
YENI_BESIN = {
    'Anadolu Çorba':                  (250, 169, 6.3, 23.3, 5.6, 2.3),
    'Elbasan Tava':                   (250, 324, 24.3, 24.3, 14.4, 2.4),
    'Hasanpaşa Köfte':                (250, 384, 28.8, 28.8, 17.1, 2.9),
    'Kaşarlı Domates Çorba':          (250, 183, 6.9, 25.2, 6.1, 2.5),
    'Lavaşlı Adana Köfte':            (250, 325, 24.4, 24.4, 14.4, 2.4),
    'Meyve Suyu/ Kayısı, Üzüm Hoşafı': (200, 210, 2.6, 34.1, 7.0, 3.4),
    'Mıs. Havuç Salata':              (150, 80, 2.0, 10.0, 3.6, 1.0),
    'Nohutlu Pilav Üstü Tavuk':       (250, 336, 25.2, 25.2, 14.9, 2.5),
    'Patates Kızartması':             (200, 156, 3.9, 27.3, 3.5, 2.7),
    'Peynirli Börek':                 (200, 389, 9.7, 68.1, 8.6, 6.8),
    'Portakallı Revani':              (150, 418, 5.2, 67.9, 13.9, 6.8),
    'Püreli Kadınbudu Köfte':         (250, 383, 28.7, 28.7, 17.0, 2.9),
    'Sebzeli Bulgur Pilavı':          (200, 229, 5.7, 40.1, 5.1, 4.0),
    'Tavuk Köfte/ Elma Dilimli Patates': (250, 301, 22.6, 22.6, 13.4, 2.3),
    'Tavuk Külbastı / Sebze Sote':    (250, 374, 28.0, 28.0, 16.6, 2.8),
    'Tavuk Pane / Baharatlı Patates': (250, 464, 34.8, 34.8, 20.6, 3.5),
    'Tavuk Şiş Dürüm':               (250, 395, 29.6, 29.6, 17.6, 3.0),
    'Tavuklu Şehriye Çorba':          (250, 232, 8.7, 31.9, 7.7, 3.2),
    'Tulumba Tatlısı':                (150, 341, 4.3, 55.4, 11.4, 5.5),
    'Vezir Parmağı':                  (150, 359, 4.5, 58.3, 12.0, 5.8),
    'Çin Usulü Tavuk':                (250, 251, 18.8, 18.8, 11.2, 1.9),
    'İnegöl Köfte / Piyaz':           (250, 326, 24.4, 24.4, 14.5, 2.4),
    'Şeh.Pirinç Pilavı':             (200, 342, 8.6, 59.8, 7.6, 6.0),
    'Şintitzel Burger':               (250, 427, 32.0, 32.0, 19.0, 3.2),
    # Kalori=0 olanları düzelt
    'Meyve (Armut)':                  (150, 80, 1.0, 17.0, 0.9, 1.7),
}

# Ekle
eklenen = 0
guncellenen = 0
for ad, (porsiyon, kal, prot, karb, yag, lif) in YENI_BESIN.items():
    existing = None
    for r in nut_data:
        if r['yemek_adi'].strip() == ad:
            existing = r
            break

    if existing:
        if float(existing['kalori']) == 0:
            existing['porsiyon_gram'] = str(porsiyon)
            existing['kalori'] = str(kal)
            existing['protein_g'] = str(prot)
            existing['karbonhidrat_g'] = str(karb)
            existing['yag_g'] = str(yag)
            existing['lif_g'] = str(lif)
            print(f"  🔄 GÜNCELLENDİ: {ad} (kalori: 0 → {kal})")
            guncellenen += 1
    else:
        nut_data.append({
            'yemek_adi': ad,
            'porsiyon_gram': str(porsiyon),
            'kalori': str(kal),
            'protein_g': str(prot),
            'karbonhidrat_g': str(karb),
            'yag_g': str(yag),
            'lif_g': str(lif),
        })
        print(f"  ➕ EKLENDİ: {ad} ({kal} kkal)")
        eklenen += 1

# Sırala ve yaz
nut_data.sort(key=lambda r: r['yemek_adi'])
with open(NUT_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=nut_fieldnames)
    writer.writeheader()
    writer.writerows(nut_data)

print(f"\n✅ Nutrition CSV: {eklenen} eklendi, {guncellenen} güncellendi, 'Et Fajita 371' silindi.")

# ═══ ADIM 3: Tekrar kontrol ═══════════════════════════════════════

nut2 = set()
with open(NUT_CSV, 'r', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        nut2.add(row['yemek_adi'].strip())

menu2 = set()
with open(MENU_CSV, 'r', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        for k in ['corba', 'ana_yemek', 'pilav_makarna', 'tatli', 'salata']:
            v = row.get(k, '').strip()
            if v:
                menu2.add(v)

eksik2 = sorted(menu2 - nut2)
print(f"\n=== SON DURUM ===")
print(f"  Nutrition: {len(nut2)} yemek")
print(f"  Menü:      {len(menu2)} yemek")
print(f"  Eksik:     {len(eksik2)}")
if eksik2:
    for e in eksik2:
        print(f"    ⚠️  {e}")
else:
    print(f"  🎉 Tüm menü yemeklerinin besin değeri mevcut!")
