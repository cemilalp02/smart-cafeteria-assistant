"""
AI Akıllı Yemekhane Asistan Sistemi - Örnek Veri Yükleyici
═══════════════════════════════════════════════════════════
Veritabanına Türk yemekhane yemekleri, örnek menüler ve
test kullanıcıları ekler.
"""

from datetime import date, timedelta

from models import init_db, SessionLocal, Yemek, Menu, Kullanici, KullaniciYemekLog

# ─── Yemek Verileri ────────────────────────────────────────────────
YEMEKLER = [
    # Çorbalar
    {"ad": "Mercimek Çorbası", "kategori": "corba", "kalori": 139, "protein": 9.0, "karbonhidrat": 20.0, "yag": 3.5},
    {"ad": "Ezogelin Çorbası", "kategori": "corba", "kalori": 120, "protein": 5.0, "karbonhidrat": 18.0, "yag": 3.0},
    {"ad": "Domates Çorbası", "kategori": "corba", "kalori": 95, "protein": 3.0, "karbonhidrat": 15.0, "yag": 2.5},
    {"ad": "Tavuk Suyu Çorbası", "kategori": "corba", "kalori": 85, "protein": 6.0, "karbonhidrat": 8.0, "yag": 3.0},
    {"ad": "Yayla Çorbası", "kategori": "corba", "kalori": 110, "protein": 4.0, "karbonhidrat": 12.0, "yag": 5.0},
    {"ad": "Tarhana Çorbası", "kategori": "corba", "kalori": 105, "protein": 5.0, "karbonhidrat": 16.0, "yag": 2.0},
    {"ad": "İşkembe Çorbası", "kategori": "corba", "kalori": 150, "protein": 12.0, "karbonhidrat": 5.0, "yag": 9.0},
    # Ana Yemekler
    {"ad": "Tavuk Sote", "kategori": "ana_yemek", "kalori": 220, "protein": 25.0, "karbonhidrat": 8.0, "yag": 10.0},
    {"ad": "Karnıyarık", "kategori": "ana_yemek", "kalori": 280, "protein": 12.0, "karbonhidrat": 15.0, "yag": 18.0},
    {"ad": "Etli Nohut", "kategori": "ana_yemek", "kalori": 310, "protein": 18.0, "karbonhidrat": 30.0, "yag": 12.0},
    {"ad": "Köfte", "kategori": "ana_yemek", "kalori": 295, "protein": 22.0, "karbonhidrat": 10.0, "yag": 18.0},
    {"ad": "Tavuk Izgara", "kategori": "ana_yemek", "kalori": 190, "protein": 30.0, "karbonhidrat": 2.0, "yag": 7.0},
    {"ad": "Kuru Fasulye", "kategori": "ana_yemek", "kalori": 260, "protein": 14.0, "karbonhidrat": 35.0, "yag": 8.0},
    {"ad": "Musakka", "kategori": "ana_yemek", "kalori": 275, "protein": 15.0, "karbonhidrat": 12.0, "yag": 19.0},
    {"ad": "İzmir Köfte", "kategori": "ana_yemek", "kalori": 305, "protein": 20.0, "karbonhidrat": 14.0, "yag": 19.0},
    {"ad": "Tas Kebabı", "kategori": "ana_yemek", "kalori": 320, "protein": 24.0, "karbonhidrat": 10.0, "yag": 20.0},
    # Pilavlar / Makarnalar
    {"ad": "Pirinç Pilavı", "kategori": "yan_yemek", "kalori": 180, "protein": 4.0, "karbonhidrat": 38.0, "yag": 2.0},
    {"ad": "Bulgur Pilavı", "kategori": "yan_yemek", "kalori": 160, "protein": 5.0, "karbonhidrat": 32.0, "yag": 2.5},
    {"ad": "Makarna", "kategori": "yan_yemek", "kalori": 200, "protein": 7.0, "karbonhidrat": 35.0, "yag": 4.0},
    {"ad": "Erişte", "kategori": "yan_yemek", "kalori": 190, "protein": 6.0, "karbonhidrat": 33.0, "yag": 3.5},
    {"ad": "Nohutlu Pirinç Pilavı", "kategori": "yan_yemek", "kalori": 210, "protein": 7.0, "karbonhidrat": 36.0, "yag": 4.0},
    # Tatlılar
    {"ad": "Sütlaç", "kategori": "tatli", "kalori": 180, "protein": 5.0, "karbonhidrat": 30.0, "yag": 5.0},
    {"ad": "Revani", "kategori": "tatli", "kalori": 250, "protein": 4.0, "karbonhidrat": 42.0, "yag": 8.0},
    {"ad": "Muhallebi", "kategori": "tatli", "kalori": 150, "protein": 4.0, "karbonhidrat": 25.0, "yag": 4.0},
    {"ad": "Keşkül", "kategori": "tatli", "kalori": 170, "protein": 5.0, "karbonhidrat": 28.0, "yag": 5.0},
    {"ad": "Komposto", "kategori": "tatli", "kalori": 100, "protein": 0.5, "karbonhidrat": 25.0, "yag": 0.2},
    {"ad": "Aşure", "kategori": "tatli", "kalori": 190, "protein": 4.0, "karbonhidrat": 38.0, "yag": 3.0},
    # Salatalar
    {"ad": "Mevsim Salata", "kategori": "salata", "kalori": 45, "protein": 2.0, "karbonhidrat": 6.0, "yag": 1.5},
    {"ad": "Çoban Salata", "kategori": "salata", "kalori": 50, "protein": 1.5, "karbonhidrat": 7.0, "yag": 2.0},
    {"ad": "Cacık", "kategori": "salata", "kalori": 60, "protein": 3.0, "karbonhidrat": 4.0, "yag": 3.5},
    {"ad": "Piyaz", "kategori": "salata", "kalori": 120, "protein": 6.0, "karbonhidrat": 18.0, "yag": 3.0},
    {"ad": "Havuç Tarator", "kategori": "salata", "kalori": 70, "protein": 2.0, "karbonhidrat": 8.0, "yag": 3.0},
]


def seed_database():
    """Veritabanına örnek veri yükler."""
    init_db()
    db = SessionLocal()

    try:
        # ── Yemekler ──────────────────────────────────────────────
        print("🍽️  Yemekler ekleniyor...")
        yemek_objeleri = []
        for y in YEMEKLER:
            mevcut = db.query(Yemek).filter(Yemek.ad == y["ad"]).first()
            if not mevcut:
                yemek = Yemek(**y)
                db.add(yemek)
                yemek_objeleri.append(yemek)
        db.commit()
        print(f"   ✅ {len(yemek_objeleri)} yeni yemek eklendi.")

        # ── Menüler (bu hafta) ────────────────────────────────────
        print("📅 Menüler ekleniyor...")
        bugun = date.today()
        # Bu haftanın Pazartesi'si
        pazartesi = bugun - timedelta(days=bugun.weekday())
        gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]

        haftalik_menuler = [
            {"corba": "Mercimek Çorbası", "ana_yemek": "Tavuk Sote", "yan_yemek": "Pirinç Pilavı", "tatli": "Sütlaç", "salata": "Mevsim Salata"},
            {"corba": "Ezogelin Çorbası", "ana_yemek": "Karnıyarık", "yan_yemek": "Bulgur Pilavı", "tatli": "Revani", "salata": "Çoban Salata"},
            {"corba": "Domates Çorbası", "ana_yemek": "Etli Nohut", "yan_yemek": "Makarna", "tatli": "Muhallebi", "salata": "Cacık"},
            {"corba": "Tavuk Suyu Çorbası", "ana_yemek": "Köfte", "yan_yemek": "Pirinç Pilavı", "tatli": "Keşkül", "salata": "Piyaz"},
            {"corba": "Yayla Çorbası", "ana_yemek": "Tavuk Izgara", "yan_yemek": "Bulgur Pilavı", "tatli": "Komposto", "salata": "Havuç Tarator"},
        ]

        menu_sayac = 0
        for i, gun in enumerate(gunler):
            tarih = pazartesi + timedelta(days=i)
            mevcut = db.query(Menu).filter(Menu.tarih == tarih).first()
            if not mevcut:
                menu = Menu(
                    tarih=tarih,
                    gun=gun,
                    **haftalik_menuler[i],
                )
                db.add(menu)
                menu_sayac += 1
        db.commit()
        print(f"   ✅ {menu_sayac} günlük menü eklendi.")

        # ── Kullanıcılar ──────────────────────────────────────────
        print("👤 Kullanıcılar ekleniyor...")
        test_kullanicilar = [
            {"ad": "Ahmet Yılmaz", "email": "ahmet@university.edu.tr", "gunluk_kalori_hedefi": 2200},
            {"ad": "Fatma Demir", "email": "fatma@university.edu.tr", "gunluk_kalori_hedefi": 1800},
            {"ad": "Mehmet Kaya", "email": "mehmet@university.edu.tr", "gunluk_kalori_hedefi": 2500},
        ]

        kullanici_sayac = 0
        for k in test_kullanicilar:
            mevcut = db.query(Kullanici).filter(Kullanici.email == k["email"]).first()
            if not mevcut:
                kullanici = Kullanici(**k)
                db.add(kullanici)
                kullanici_sayac += 1
        db.commit()
        print(f"   ✅ {kullanici_sayac} kullanıcı eklendi.")

        print("\n🎉 Tüm örnek veriler başarıyla yüklendi!")
        print(f"   Toplam yemek: {db.query(Yemek).count()}")
        print(f"   Toplam menü : {db.query(Menu).count()}")
        print(f"   Toplam kullanıcı: {db.query(Kullanici).count()}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Hata oluştu: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
