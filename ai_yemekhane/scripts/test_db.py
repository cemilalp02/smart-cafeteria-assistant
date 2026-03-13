"""
Veritabanı Test Scripti
════════════════════════
Veritabanı bağlantısını, menü ve besin değeri
sorgularını test eder.
"""

import os
import sys
from datetime import date

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import SessionLocal, Yemek, Menu, Kullanici, KullaniciYemekLog


def test_connection(db):
    """Veritabanı bağlantısını test eder."""
    print("─" * 50)
    print("1️⃣  Veritabanı Bağlantı Testi")
    print("─" * 50)
    try:
        yemek_sayisi = db.query(Yemek).count()
        menu_sayisi = db.query(Menu).count()
        kullanici_sayisi = db.query(Kullanici).count()

        print(f"   ✅ Bağlantı başarılı!")
        print(f"   📊 Yemek sayısı    : {yemek_sayisi}")
        print(f"   📅 Menü sayısı     : {menu_sayisi}")
        print(f"   👤 Kullanıcı sayısı: {kullanici_sayisi}")
        return True
    except Exception as e:
        print(f"   ❌ Bağlantı hatası: {e}")
        return False


def test_today_menu(db):
    """Bugünün menüsünü sorgular."""
    print("\n" + "─" * 50)
    print("2️⃣  Bugünün Menüsü")
    print("─" * 50)

    bugun = date.today()
    menu = db.query(Menu).filter(Menu.tarih == bugun).first()

    if menu:
        print(f"   📅 Tarih    : {menu.tarih} ({menu.gun})")
        print(f"   🥣 Çorba    : {menu.corba or '-'}")
        print(f"   🍖 Ana Yemek: {menu.ana_yemek or '-'}")
        print(f"   🍚 Pilav    : {menu.pilav or '-'}")
        print(f"   🍰 Tatlı    : {menu.tatli or '-'}")
        print(f"   🥗 Salata   : {menu.salata or '-'}")
    else:
        print(f"   ⚠️  Bugün ({bugun}) için menü bulunamadı.")
        # En yakın menüyü göster
        en_yakin = db.query(Menu).order_by(Menu.tarih.desc()).first()
        if en_yakin:
            print(f"   ℹ️  En son menü: {en_yakin.tarih} ({en_yakin.gun})")
            print(f"       🥣 {en_yakin.corba} | 🍖 {en_yakin.ana_yemek}")

    return menu


def test_nutrition_query(db):
    """Bir yemeğin besin değerini sorgular."""
    print("\n" + "─" * 50)
    print("3️⃣  Besin Değeri Sorgusu")
    print("─" * 50)

    # Birkaç yemek sorgula
    test_yemekler = ["Mercimek Çorbası", "Köfte", "Pirinç Pilavı", "Sütlaç", "Mevsim Salata"]

    for yemek_adi in test_yemekler:
        yemek = db.query(Yemek).filter(Yemek.ad == yemek_adi).first()
        if yemek:
            print(f"\n   🍽️  {yemek.ad} ({yemek.kategori})")
            print(f"       🔥 Kalori      : {yemek.kalori} kcal")
            print(f"       💪 Protein     : {yemek.protein}g")
            print(f"       🌾 Karbonhidrat: {yemek.karbonhidrat}g")
            print(f"       🧈 Yağ         : {yemek.yag}g")
        else:
            print(f"\n   ⚠️  '{yemek_adi}' bulunamadı.")


def test_category_summary(db):
    """Kategori bazlı yemek özeti."""
    print("\n" + "─" * 50)
    print("4️⃣  Kategori Bazlı Özet")
    print("─" * 50)

    kategoriler = db.query(Yemek.kategori).distinct().all()
    for (kat,) in kategoriler:
        sayi = db.query(Yemek).filter(Yemek.kategori == kat).count()
        ort_kalori = (
            db.query(Yemek.kalori)
            .filter(Yemek.kategori == kat, Yemek.kalori > 0)
            .all()
        )
        if ort_kalori:
            ortalama = sum(k[0] for k in ort_kalori) / len(ort_kalori)
        else:
            ortalama = 0
        print(f"   📂 {kat:12s} → {sayi:2d} yemek | Ort. kalori: {ortalama:.0f} kcal")


def test_menu_range(db):
    """Menü tarih aralığını gösterir."""
    print("\n" + "─" * 50)
    print("5️⃣  Menü Tarih Aralığı")
    print("─" * 50)

    ilk = db.query(Menu).order_by(Menu.tarih.asc()).first()
    son = db.query(Menu).order_by(Menu.tarih.desc()).first()

    if ilk and son:
        gun_fark = (son.tarih - ilk.tarih).days
        print(f"   📅 İlk menü : {ilk.tarih} ({ilk.gun})")
        print(f"   📅 Son menü  : {son.tarih} ({son.gun})")
        print(f"   📊 Toplam    : {gun_fark} günlük aralık, {db.query(Menu).count()} menü kaydı")
    else:
        print("   ⚠️  Menü verisi bulunamadı.")


def main():
    """Tüm testleri çalıştırır."""
    print("=" * 50)
    print("  🧪 Veritabanı Test Scripti")
    print("=" * 50)

    db = SessionLocal()
    try:
        ok = test_connection(db)
        if not ok:
            print("\n❌ Veritabanı bağlantısı kurulamadı. Çıkılıyor.")
            return

        test_today_menu(db)
        test_nutrition_query(db)
        test_category_summary(db)
        test_menu_range(db)

        print("\n" + "=" * 50)
        print("  ✅ Tüm testler tamamlandı!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Test hatası: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
