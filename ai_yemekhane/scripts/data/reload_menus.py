# -*- coding: utf-8 -*-
"""
Eski yanlış menüleri sil, doğru olanları yükle.
Nisan 2026'dan itibaren (değişen) kayıtları günceller.
"""
import sys, os, csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, date
from models import init_db, SessionLocal, Menu, Yemek

MENU_CSV = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'menu_data.csv')

# Kategori map (basit)
def guess_kategori(ad):
    al = ad.lower()
    if 'çorba' in al: return 'corba'
    if any(k in al for k in ['pilav', 'makarna', 'erişte', 'börek', 'kuskus', 'bulgur']): return 'yan_yemek'
    if any(k in al for k in ['salata', 'cacık', 'ayran', 'yoğurt', 'turşu', 'haydari', 'tarator', 'piyaz']): return 'salata'
    if any(k in al for k in ['komposto', 'baklava', 'kek', 'tatlı', 'helva', 'puding', 'trileçe', 'tiramisu',
                              'keşkül', 'brownie', 'sultan', 'ekler', 'şekerpare', 'revani', 'tulumba',
                              'vezir', 'irmik', 'meyve suyu', 'hoşaf']): return 'tatli'
    if any(k in al for k in ['meyve', 'portakal', 'elma', 'armut', 'muz']): return 'tatli'
    return 'ana_yemek'

def main():
    init_db()
    db = SessionLocal()

    try:
        # 1) TÜM mevcut menüleri sil
        count = db.query(Menu).count()
        db.query(Menu).delete()
        db.commit()
        print(f"🗑️  {count} eski menü kaydı silindi.")

        # 2) CSV'den tüm menüleri yükle
        benzersiz_yemekler = set()
        with open(MENU_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Yemek tablosuna eksik yemekleri ekle
        for row in rows:
            for kolon in ['corba', 'ana_yemek', 'yan_yemek', 'tatli', 'salata']:
                adi = row.get(kolon, '').strip()
                if adi:
                    benzersiz_yemekler.add(adi)

        yemek_eklenen = 0
        for adi in benzersiz_yemekler:
            mevcut = db.query(Yemek).filter(Yemek.ad == adi).first()
            if not mevcut:
                db.add(Yemek(ad=adi, kategori=guess_kategori(adi), kalori=0, protein=0, karbonhidrat=0, yag=0))
                yemek_eklenen += 1
        db.commit()
        if yemek_eklenen:
            print(f"🍽️  {yemek_eklenen} yeni yemek eklendi (besin değeri 0).")

        # 3) Menüleri yükle
        menu_eklenen = 0
        for row in rows:
            tarih_str = row['tarih'].strip()
            tarih = datetime.strptime(tarih_str, '%Y-%m-%d').date()

            menu = Menu(
                tarih=tarih,
                gun=row['gun'].strip(),
                corba=row.get('corba', '').strip() or None,
                ana_yemek=row.get('ana_yemek', '').strip() or None,
                yan_yemek=row.get('yan_yemek', '').strip() or row.get('pilav_makarna', '').strip() or row.get('pilav', '').strip() or None,
                tatli=row.get('tatli', '').strip() or None,
                salata=row.get('salata', '').strip() or None,
            )
            db.add(menu)
            menu_eklenen += 1

        db.commit()
        print(f"✅ {menu_eklenen} günlük menü yüklendi.")

        # 4) Bugünü kontrol et
        bugun = date.today()
        menu = db.query(Menu).filter(Menu.tarih == bugun).first()
        if menu:
            print(f"\n📅 BUGÜN ({bugun}, {menu.gun}):")
            print(f"   Çorba:     {menu.corba}")
            print(f"   Ana Yemek: {menu.ana_yemek}")
            print(f"   Yan Yemek: {menu.yan_yemek}")
            print(f"   Tatlı:     {menu.tatli}")
            print(f"   Salata:    {menu.salata}")
        else:
            print(f"\n❌ Bugün ({bugun}) için menü bulunamadı!")

        # Özet
        print(f"\n📊 Toplam yemek: {db.query(Yemek).count()}")
        print(f"📊 Toplam menü:  {db.query(Menu).count()}")

    except Exception as e:
        db.rollback()
        print(f"❌ Hata: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    main()
