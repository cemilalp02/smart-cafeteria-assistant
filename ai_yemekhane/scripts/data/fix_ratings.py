# -*- coding: utf-8 -*-
"""Bugün yanlış menü için girilen puanları sil."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import date
from models import SessionLocal, MenuPuanlama

db = SessionLocal()
bugun = date.today()

# Bugün için girilen tüm puanları göster
puanlar = db.query(MenuPuanlama).filter(MenuPuanlama.tarih == bugun).all()
print(f"Bugün ({bugun}) için {len(puanlar)} puan kaydı bulundu:\n")
for p in puanlar:
    print(f"  ID:{p.id} | {p.yemek_adi:40s} | {p.kategori:12s} | Puan:{p.puan} | {p.yorum or ''}")

# Yanlış menü yemekleri (eski yanlış menü)
yanlis_yemekler = [
    'Karnabahar Pane / Yoğurt',
    'Karnabahar Pane',
    'Komposto / Meyve Suyu',
    'Mahluta Çorba',
    'Su Böreği',
]

# Bugün için bu yemeklerin puanlarını sil
silinen = 0
for p in puanlar:
    if p.yemek_adi in yanlis_yemekler:
        print(f"  🗑️ SİLİNİYOR: {p.yemek_adi} (Puan:{p.puan})")
        db.delete(p)
        silinen += 1

db.commit()
print(f"\n✅ {silinen} yanlış puan kaydı silindi.")

# Kalan puanları göster
kalan = db.query(MenuPuanlama).filter(MenuPuanlama.tarih == bugun).all()
print(f"📊 Bugün için kalan puan sayısı: {len(kalan)}")
for p in kalan:
    print(f"  ID:{p.id} | {p.yemek_adi:40s} | Puan:{p.puan}")

db.close()
