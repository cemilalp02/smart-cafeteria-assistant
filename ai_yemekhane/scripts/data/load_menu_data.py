"""
CSV Verilerini Veritabanına Yükleme Scripti
════════════════════════════════════════════
data/menu_data.csv      → Menu + Yemek tabloları
data/nutrition_data.csv → Yemek tablosu (besin değerleri)
"""

import csv
import os
import sys
from datetime import datetime

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from models import init_db, SessionLocal, Yemek, Menu


# ─── Sabitler ──────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
MENU_CSV = os.path.join(DATA_DIR, "menu_data.csv")
NUTRITION_CSV = os.path.join(DATA_DIR, "nutrition_data.csv")

# Yemek adından kategoriye eşleştirme (270 yemek - gerçek üniversite menü verisi)
KATEGORI_MAP = {
    # Çorbalar
    "Alaca Çorba": "corba",
    "Arabaşı Çorba": "corba",
    "Ayranaşı Çorba": "corba",
    "Brokoli Çorba": "corba",
    "Domates Çorba": "corba",
    "Düğün Çorba": "corba",
    "Ezogelin Çorba": "corba",
    "Hanımağa Çorba": "corba",
    "Kabak Çorbası": "corba",
    "Kremalı Mantar Çorba": "corba",
    "Kremalı Sebze Çorba": "corba",
    "Kru. Domates Çorba": "corba",
    "Krut. Domates Çorba": "corba",
    "Krutonlu Domates Çorba": "corba",
    "Köylüm Çorba": "corba",
    "Köz Biber Çorba": "corba",
    "Lebeniye Çorba": "corba",
    "Mahluta Çorba": "corba",
    "Mercimek Çorba": "corba",
    "Minestrone Çorba": "corba",
    "Pirinç Çorba": "corba",
    "Saray Çorba": "corba",
    "Sebze Çorba": "corba",
    "Sebzeli Şehriye Çorba": "corba",
    "Süzme Mercimek Çorba": "corba",
    "Tandır Çorba": "corba",
    "Tarhana Çorba": "corba",
    "Tarhana Çorbası": "corba",
    "Tavuk Suyu Çorba": "corba",
    "Tavuk Çorba": "corba",
    "Tel Şehriye Çorba": "corba",
    "Terbiyeli Tavuk Çorba": "corba",
    "Toyga Çorba": "corba",
    "Yayla Çorba": "corba",
    "Yeşil Mercimek Çorba": "corba",
    "Yoğurt Çorba": "corba",
    "Şehriye Çorba": "corba",
    # Ana Yemekler
    "Adana Köfte (lavaş)": "ana_yemek",
    "Akdeniz Usulü Ispanak": "ana_yemek",
    "Ankara Tava": "ana_yemek",
    "Arnavut Ciğer /May. Roka Soğan Söğüş": "ana_yemek",
    "Babagannuş": "ana_yemek",
    "Bahçıvan Kebabı": "ana_yemek",
    "Barbekü Soslu Tavuk": "ana_yemek",
    "Bezelye Yemeği": "ana_yemek",
    "Beğendili Misket Köfte": "ana_yemek",
    "Beşamelli Fırın Patates": "ana_yemek",
    "Dana Navarin": "ana_yemek",
    "Dürüm Tavuk Tantuni": "ana_yemek",
    "Ekmek arası Balık/Soğan Söğüş": "ana_yemek",
    "Et Döner": "ana_yemek",
    "Et Fajita": "ana_yemek",
    "Et Haşlama": "ana_yemek",
    "Et Sote": "ana_yemek",
    "Et Stroganoff": "ana_yemek",
    "Etli Barbunya": "ana_yemek",
    "Etli Nohut": "ana_yemek",
    "Etli Taze Fasulye": "ana_yemek",
    "Etli Türlü": "ana_yemek",
    "Etli Yaz Türlüsü": "ana_yemek",
    "Fırın Köfte": "ana_yemek",
    "Fırın Tavuk (Brokoli, Kırmızı Biber)": "ana_yemek",
    "Fırında Patatesli Hamsi": "ana_yemek",
    "Fırında Tavuk Pirzola/Brokoli, Kırmızı Biber,Mısır Garnitür": "ana_yemek",
    "Hamburger": "ana_yemek",
    "Hamburger (Patates Kızartması)": "ana_yemek",
    "Hamburger /Patates Kızartma": "ana_yemek",
    "Hamburger/Patates Kızartması": "ana_yemek",
    "Hasanpaşa Köfte (Püreli)": "ana_yemek",
    "Hünkar Beğendi": "ana_yemek",
    "Ispanak Kavurma": "ana_yemek",
    "Ispanak Yemeği / Yoğurt": "ana_yemek",
    "Izgara Kanat / Brokoli Karnabahar Haşlama": "ana_yemek",
    "Izgara Köfte / Elma Dilim Patates": "ana_yemek",
    "Izgara Tavuk Kanat / Elma Dilim Patates": "ana_yemek",
    "Kabak Dolma": "ana_yemek",
    "Kabak Mücver (domates,biber)": "ana_yemek",
    "Kapuska": "ana_yemek",
    "Karnabahar Pane": "ana_yemek",
    "Karnabahar Pane (yoğurt)": "ana_yemek",
    "Karnabahar Pane / Yoğurt": "ana_yemek",
    "Karnıyarık": "ana_yemek",
    "Karışık Dolma (yoğurt)": "ana_yemek",
    "Kekikli Fırın Tavuk Pirzola": "ana_yemek",
    "Kremalı Köri Soslu Tavuk": "ana_yemek",
    "Kuru Fasulye": "ana_yemek",
    "Köfteli Avcı Kebabı": "ana_yemek",
    "Köri Soslu Tavuk": "ana_yemek",
    "Kıymalı Bezelye": "ana_yemek",
    "Kıymalı Biber Dolma (Yoğurt)": "ana_yemek",
    "Kıymalı Ispanak / Yoğurt": "ana_yemek",
    "Kıymalı Karnabahar Yemeği": "ana_yemek",
    "Kıymalı Patates Oturtma": "ana_yemek",
    "Kıymalı Pırasa": "ana_yemek",
    "Lahana Kapama/ Yoğurt": "ana_yemek",
    "Lavaşlı Et Tantuni": "ana_yemek",
    "Lavaşlı Tavuk Tantuni": "ana_yemek",
    "Macar Gulaş": "ana_yemek",
    "Mantarlı Tavuk Sote": "ana_yemek",
    "Meksika Soslu Tavuk": "ana_yemek",
    "Mevsim Türlü": "ana_yemek",
    "Nohut Kavurma": "ana_yemek",
    "Nohut Yemeği": "ana_yemek",
    "Nohutlu Pirinç Pilavı": "ana_yemek",
    "Nohutlu, Portakallı Kereviz": "ana_yemek",
    "Orman Kebabı": "ana_yemek",
    "Paris Soslu Tavuk": "ana_yemek",
    "Patates Oturtma": "ana_yemek",
    "Patlıcan Musakka": "ana_yemek",
    "Patlıcanlı Fırın Köfte": "ana_yemek",
    "Pideli Köfte": "ana_yemek",
    "Pideli Parmak Köfte": "ana_yemek",
    "Pideli Tavuk Kebabı": "ana_yemek",
    "Pilav Üstü Kavurma": "ana_yemek",
    "Portakallı Noh.Kereviz": "ana_yemek",
    "Püreli Hasan Paşa Köfte": "ana_yemek",
    "Püreli Misket Köfte": "ana_yemek",
    "Püreli Rosto Köfte": "ana_yemek",
    "Sahan Köfte": "ana_yemek",
    "Sebze Graten": "ana_yemek",
    "Sebze Şöleni": "ana_yemek",
    "Sebzeli Tavuk Sote": "ana_yemek",
    "Sebzeli Çanak Köfte": "ana_yemek",
    "Soslu Köfte(Patates Kzt)": "ana_yemek",
    "Soslu Misket Köfte": "ana_yemek",
    "Soslu Tavuk Kanat / Sebze Garnitür (patates, havuç, bezelye)": "ana_yemek",
    "Soslu Tavuk Külbastı / Elma Dilim Patates": "ana_yemek",
    "Tas Kebabı": "ana_yemek",
    "Tavuk But/Pat. Kızartma": "ana_yemek",
    "Tavuk Büryan": "ana_yemek",
    "Tavuk Döner": "ana_yemek",
    "Tavuk Döner / Elma Dilim Patates": "ana_yemek",
    "Tavuk Fajita": "ana_yemek",
    "Tavuk Fajıta": "ana_yemek",
    "Tavuk Haşlama": "ana_yemek",
    "Tavuk Külbastı": "ana_yemek",
    "Tavuk Pane / Elma Dilim Patates": "ana_yemek",
    "Tavuk Pane / ElmaDilim Patates": "ana_yemek",
    "Tavuk Pirzola/ Sebze Haşlama": "ana_yemek",
    "Tavuk Şiş ( Elma Dili Patates)": "ana_yemek",
    "Taze Fasulye": "ana_yemek",
    "Tepsi Köfte / Brokoli Karnabahar Havuç Haşlama": "ana_yemek",
    "Uskumru Fileto Kızartma / Roka,Tere, Soğan Söğüş": "ana_yemek",
    "Yufkalı Tavuk Sarma": "ana_yemek",
    "Yumurtalı Ispanak": "ana_yemek",
    "Zyt Barbunya": "ana_yemek",
    "Zyt. Bamya": "ana_yemek",
    "Zyt. Barbunya": "ana_yemek",
    "Zyt. Taze Fasulye": "ana_yemek",
    "Zyt.Barbunya": "ana_yemek",
    "Zyt.Taze Fasulye": "ana_yemek",
    "Çiftlik Kebabı": "ana_yemek",
    "Çiftlik Kebap": "ana_yemek",
    "Çiftlik Köfte": "ana_yemek",
    "Çoban Kavurma": "ana_yemek",
    "Çökertme Kebabı": "ana_yemek",
    "Çıtır Tavuk Paget / Baharatlı Patates": "ana_yemek",
    "İslim Köfte": "ana_yemek",
    "İsveç Köfte / Sebze Garnitür": "ana_yemek",
    "İzmir Köfte": "ana_yemek",
    "İçli Köfte": "ana_yemek",
    "Şakşuka": "ana_yemek",
    "Şinitzel Burger": "ana_yemek",
    "Şinitzel/ Patates Kızartma": "ana_yemek",
    "Fırında Sebzeli Special But": "ana_yemek",
    "Püreli Dalyan Köfte": "ana_yemek",
    "Tatlı, Acı Soslu Tavuk": "ana_yemek",
    "Tavuk Baget/ Dom,Biber": "ana_yemek",
    "Tavuk Döner / Fırında Patates": "ana_yemek",
    "Tavuk Kavurma": "ana_yemek",
    "Tavuk Pane / Baharatlı Patates": "ana_yemek",
    "Tavuk Külbastı / Sebze Sote": "ana_yemek",
    "Lavaşlı Adana Köfte": "ana_yemek",
    "Kaşarlı Domates Çorba": "corba",
    "Tavuklu Şehriye Çorba": "corba",
    # Pilav / Makarna / Börek
    "Bolonez Soslu Makarna": "yan_yemek",
    "Bulgur Pilavı": "yan_yemek",
    "Cevizli Erişte": "yan_yemek",
    "Dom. Bulgur Pilavı": "yan_yemek",
    "Erişte": "yan_yemek",
    "Fesleğen Soslu Makarna": "yan_yemek",
    "Fırın Makarna": "yan_yemek",
    "Hav. Pirinç Pilavı": "yan_yemek",
    "Kuskus Pilavı": "yan_yemek",
    "Mıs. Pirinç Pilavı": "yan_yemek",
    "Mısırlı Pirinç Pilavı": "yan_yemek",
    "Nap. Soslu Makarna": "yan_yemek",
    "Napoliten Soslu Makarna": "yan_yemek",
    "Patatesli Gül Böreği": "yan_yemek",
    "Patatesli Kol Böreği": "yan_yemek",
    "Peynirli Börek": "yan_yemek",
    "Peynirli Gül Böreği": "yan_yemek",
    "Patates ve Soğan Halkası": "yan_yemek",
    "Pilav Üstü Dana Tandır": "yan_yemek",
    "Pirinç Pilavı": "yan_yemek",
    "Sebzeli Makarna": "yan_yemek",
    "Soslu Makarna": "yan_yemek",
    "Su Böreği": "yan_yemek",
    "Yeşil Mercimekli Bulgur Pilavı": "yan_yemek",
    "Yoğurtlu Mantı Makarna": "yan_yemek",
    "İç Pilav": "yan_yemek",
    "Şeh Pirinç Pilavı": "yan_yemek",
    "Şeh. Bulgur Pilavı": "yan_yemek",
    "Şeh. Pirinç Pilavı": "yan_yemek",
    "Şehriye Pilavı": "yan_yemek",
    "Şehriyeli Bulgur Pilavı": "yan_yemek",
    "Şehriyeli Kuskus Pilavı": "yan_yemek",
    "Şehriyeli Pirinç Pilavı": "yan_yemek",
    # Tatlılar
    "Baklava": "tatli",
    "Balbadem Tatlısı": "tatli",
    "Brownie": "tatli",
    "Cevizli Baklava": "tatli",
    "Cevizli Kabak Tatlısı": "tatli",
    "Cevizli Kalburabastı": "tatli",
    "Ekler": "tatli",
    "Havuç Dilim Baklava": "tatli",
    "Helva": "tatli",
    "Islak Kek": "tatli",
    "Kakaolu Puding": "tatli",
    "Kayısı / Üzüm Komposto": "tatli",
    "Keşkül": "tatli",
    "Komposto": "tatli",
    "Komposto / Meyve Suyu": "tatli",
    "Komposto /Meyve Suyu": "tatli",
    "Komposto/ Meyve Suyu": "tatli",
    "Kıbrıs Tatlısı": "tatli",
    "Muhallebili Kemalpaşa": "tatli",
    "Muzlu Keşkül": "tatli",
    "Pembe Sultan": "tatli",
    "Sarışınım Tatlısı": "tatli",
    "Sevgi Tatlısı": "tatli",
    "Soslu Brownie": "tatli",
    "Soğuk Baklava": "tatli",
    "Sütlü İrmik Tatlısı": "tatli",
    "Tiramisu": "tatli",
    "Trileçe": "tatli",
    "İncirli Keşkül": "tatli",
    "İrmik Helvası": "tatli",
    "Kalburabastı": "tatli",
    "Kazandibi": "tatli",
    "Komposto / Şalgam": "tatli",
    "Vezir Parmağı": "tatli",
    "Şekerpare": "tatli",
    # Meyveler
    "Elma": "tatli",
    "Mandalina": "tatli",
    "Meyve": "tatli",
    "Meyve ( Üzüm)": "tatli",
    "Meyve (Armut)": "tatli",
    "Meyve (Elma)": "tatli",
    "Meyve (kavun)": "tatli",
    "Meyve (üzüm)": "tatli",
    "Meyve(Portakal)": "tatli",
    "Muz": "tatli",
    "Portakal": "tatli",
    # Salatalar / Mezeler
    "Biber Borani": "salata",
    "Cacık": "salata",
    "Coleslow Salata": "salata",
    "Ezme": "salata",
    "Havuç Tarator": "salata",
    "Haydari": "salata",
    "Kabak Tarator": "salata",
    "Karışık Salata": "salata",
    "Kısır": "salata",
    "Kış Salata": "salata",
    "Mercimek Salata": "salata",
    "Mevsim Salata": "salata",
    "Mevsim salata": "salata",
    "Mıs Börülce Salata": "salata",
    "Mıs. Iceberg Salata": "salata",
    "Mıs. Pancar Salata": "salata",
    "Mısır, Havuç, Kırmızı Lahana Salata": "salata",
    "Patates Salatası": "salata",
    "Piyaz": "salata",
    "Salata": "salata",
    "Turşu": "salata",
    "Yoğ. Semizotu Salata": "salata",
    "Yoğurt": "salata",
    "Yoğurtlu Semizotu Salata": "salata",
    "Çin Salatası": "salata",
    "Çoban Salata": "salata",
    # İçecekler
    "Ayran": "salata",
    "Bardak Limonata": "salata",
    "Şalgam/ Meyve Suyu": "salata",
}


def load_nutrition_data(db):
    """nutrition_data.csv dosyasından besin verilerini yükler."""
    if not os.path.exists(NUTRITION_CSV):
        print(f"❌ Dosya bulunamadı: {NUTRITION_CSV}")
        return 0

    print(f"\n📦 Besin değerleri yükleniyor: {NUTRITION_CSV}")
    eklenen = 0
    guncellenen = 0

    with open(NUTRITION_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yemek_adi = row["yemek_adi"].strip()
            kategori = KATEGORI_MAP.get(yemek_adi, "diger")

            # Mevcut kaydı kontrol et
            mevcut = db.query(Yemek).filter(Yemek.ad == yemek_adi).first()

            if mevcut:
                # Besin değerlerini güncelle
                mevcut.kalori = float(row["kalori"])
                mevcut.protein = float(row["protein_g"])
                mevcut.karbonhidrat = float(row["karbonhidrat_g"])
                mevcut.yag = float(row["yag_g"])
                guncellenen += 1
            else:
                # Yeni yemek ekle
                yemek = Yemek(
                    ad=yemek_adi,
                    kategori=kategori,
                    kalori=float(row["kalori"]),
                    protein=float(row["protein_g"]),
                    karbonhidrat=float(row["karbonhidrat_g"]),
                    yag=float(row["yag_g"]),
                )
                db.add(yemek)
                eklenen += 1

    db.commit()
    print(f"   ✅ {eklenen} yeni yemek eklendi, {guncellenen} güncellendi.")
    return eklenen + guncellenen


def load_menu_data(db):
    """menu_data.csv dosyasından menü verilerini yükler."""
    if not os.path.exists(MENU_CSV):
        print(f"❌ Dosya bulunamadı: {MENU_CSV}")
        return 0

    print(f"\n📅 Menü verileri yükleniyor: {MENU_CSV}")
    eklenen = 0
    atlanan = 0

    # Önce menüdeki tüm yemekleri Yemek tablosuna ekle
    benzersiz_yemekler = set()
    with open(MENU_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for kolon in ["corba", "ana_yemek", "pilav_makarna", "tatli", "salata"]:
                yemek_adi = row.get(kolon, "").strip()
                if yemek_adi:
                    benzersiz_yemekler.add(yemek_adi)

    # Eksik yemekleri ekle
    yemek_eklenen = 0
    for yemek_adi in benzersiz_yemekler:
        mevcut = db.query(Yemek).filter(Yemek.ad == yemek_adi).first()
        if not mevcut:
            kategori = KATEGORI_MAP.get(yemek_adi, "diger")
            yemek = Yemek(
                ad=yemek_adi,
                kategori=kategori,
                kalori=0, protein=0, karbonhidrat=0, yag=0,
            )
            db.add(yemek)
            yemek_eklenen += 1
    db.commit()
    if yemek_eklenen:
        print(f"   ℹ️  {yemek_eklenen} eksik yemek Yemek tablosuna eklendi (besin değeri 0).")

    # Menüleri yükle
    with open(MENU_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tarih_str = row["tarih"].strip()
            tarih = datetime.strptime(tarih_str, "%Y-%m-%d").date()

            # Aynı tarihte menü var mı kontrol et
            mevcut_menu = db.query(Menu).filter(Menu.tarih == tarih).first()
            if mevcut_menu:
                atlanan += 1
                continue

            menu = Menu(
                tarih=tarih,
                gun=row["gun"].strip(),
                corba=row.get("corba", "").strip() or None,
                ana_yemek=row.get("ana_yemek", "").strip() or None,
                yan_yemek=row.get("pilav_makarna", "").strip() or None,
                tatli=row.get("tatli", "").strip() or None,
                salata=row.get("salata", "").strip() or None,
            )
            db.add(menu)
            eklenen += 1

    db.commit()
    print(f"   ✅ {eklenen} günlük menü eklendi, {atlanan} zaten mevcuttu.")
    return eklenen


def main():
    """Ana yükleme fonksiyonu."""
    print("=" * 60)
    print("  CSV → Veritabanı Yükleme Scripti")
    print("=" * 60)

    # Veritabanını başlat
    init_db()
    db = SessionLocal()

    try:
        # 1) Besin verilerini yükle (önce bu, çünkü yemek tablosunu doldurur)
        load_nutrition_data(db)

        # 2) Menü verilerini yükle
        load_menu_data(db)

        # Özet
        print("\n" + "=" * 60)
        print("  📊 Yükleme Özeti")
        print("=" * 60)
        print(f"  Toplam yemek sayısı : {db.query(Yemek).count()}")
        print(f"  Toplam menü sayısı  : {db.query(Menu).count()}")
        print("=" * 60)
        print("  🎉 Tüm veriler başarıyla yüklendi!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Hata: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
