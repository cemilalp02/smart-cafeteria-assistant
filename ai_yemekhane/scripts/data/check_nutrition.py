# -*- coding: utf-8 -*-
"""Nutrition data analiz: eksik, hatalı, duplikat kontrolü."""
import csv, sys, os
sys.stdout.reconfigure(encoding='utf-8')

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')

# Nutrition data oku
nut = {}
with open(os.path.join(DATA, 'nutrition_data.csv'), 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        ad = row['yemek_adi'].strip()
        kal = float(row['kalori'])
        nut[ad] = kal

# Menu data - tum yemek adlarini topla
menu_yemekler = set()
with open(os.path.join(DATA, 'menu_data.csv'), 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        for k in ['corba', 'ana_yemek', 'pilav_makarna', 'tatli', 'salata']:
            v = row.get(k, '').strip()
            if v:
                menu_yemekler.add(v)

# 1) Kalori 0 olan yemekler
print('=== SORUN 1: Kalori 0 olan yemekler ===')
sifir = []
for ad, kal in sorted(nut.items()):
    if kal == 0:
        sifir.append(ad)
        print(f'  ❌ {ad}: kalori=0')
print(f'  Toplam: {len(sifir)}\n')

# 2) Menu'de olup nutrition'da olmayan
eksik = sorted(menu_yemekler - set(nut.keys()))
print(f'=== SORUN 2: Menüde olup nutrition\'da OLMAYAN yemekler ===')
for e in eksik:
    print(f'  ⚠️  {e}')
print(f'  Toplam: {len(eksik)}\n')

# 3) Nutrition'da olup menüde olmayan (gereksiz)
gereksiz = sorted(set(nut.keys()) - menu_yemekler)
print(f'=== BİLGİ: Nutrition\'da olup menüde olmayan ({len(gereksiz)}) ===')
for g in gereksiz[:10]:
    print(f'  ℹ️  {g}')
if len(gereksiz) > 10:
    print(f'  ... ve {len(gereksiz)-10} tane daha')

print(f'\n=== ÖZET ===')
print(f'  Nutrition kayıt: {len(nut)}')
print(f'  Menü yemek:      {len(menu_yemekler)}')
print(f'  Eksik besin:     {len(eksik)}')
print(f'  Kalori=0:        {len(sifir)}')
