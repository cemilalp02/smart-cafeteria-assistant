"""
Uretim Logu Olusturucu
======================
Mevcut puanlama ve menu verilerinden gercekci uretim logları olusturur.
Bu veriler israf modelinin (GradientBoosting) egitimi icin kullanilir.
"""

import random
from datetime import date, timedelta
from models import init_db, SessionLocal, Menu, MenuPuanlama, UretimLog
from sqlalchemy import func

def generate_production_logs():
    """Mevcut menu ve puanlama verisinden gercekci uretim loglari uretir."""
    init_db()
    db = SessionLocal()

    try:
        # Mevcut menu tarihlerini al
        menuler = db.query(Menu).order_by(Menu.tarih).all()
        if not menuler:
            print("Menu verisi bulunamadi!")
            return

        # Yemek bazli ortalama puanlari hesapla
        puan_ortalama = {}
        puanlar = (
            db.query(
                MenuPuanlama.yemek_adi,
                func.avg(MenuPuanlama.puan).label("ort"),
            )
            .group_by(MenuPuanlama.yemek_adi)
            .all()
        )
        for p in puanlar:
            puan_ortalama[p.yemek_adi] = float(p.ort)

        eklenen = 0

        for menu in menuler:
            # Her menudeki 5 kategori icin uretim logu olustur
            yemekler = [
                (menu.corba, "corba"),
                (menu.ana_yemek, "ana_yemek"),
                (menu.yan_yemek, "yan_yemek"),
                (menu.tatli, "tatli"),
                (menu.salata, "salata"),
            ]

            for yemek_adi, kategori in yemekler:
                if not yemek_adi:
                    continue

                # Zaten bu tarih + yemek icin log var mi?
                mevcut = (
                    db.query(UretimLog)
                    .filter(
                        UretimLog.tarih == menu.tarih,
                        UretimLog.yemek_adi == yemek_adi,
                    )
                    .first()
                )
                if mevcut:
                    continue

                # Puan bilgisi varsa kullan, yoksa varsayilan 3.0
                ort_puan = puan_ortalama.get(yemek_adi, 3.0)

                # Kategoriye gore uretilen porsiyon ayarla
                porsiyon_bazlari = {
                    "corba": (900, 1200),
                    "ana_yemek": (900, 1200),
                    "yan_yemek": (900, 1200),
                    "tatli": (900, 1200),
                    "salata": (900, 1200),
                }
                min_p, max_p = porsiyon_bazlari.get(kategori, (900, 1200))
                uretilen = random.randint(min_p, max_p)

                # Puanadan israf orani hesapla (gercekci varyans ekle)
                # Dusuk puan = yuksek israf, yuksek puan = dusuk israf
                # Gercekci: 5 puan=%5 israf, 3 puan=%17, 1 puan=%29
                baz_israf = max(3, min(40, 35 - (ort_puan * 6)))
                # Gercekci varyans: +/- %5
                varyans = random.uniform(-5, 5)
                israf_orani = max(2, min(40, baz_israf + varyans))

                kalan = int(uretilen * (israf_orani / 100))
                tuketim_orani = round(100 - israf_orani, 1)
                israf_orani = round(israf_orani, 1)

                log = UretimLog(
                    tarih=menu.tarih,
                    yemek_adi=yemek_adi,
                    kategori=kategori,
                    uretilen_porsiyon=uretilen,
                    kalan_porsiyon=kalan,
                    tuketim_orani=tuketim_orani,
                    israf_orani=israf_orani,
                    notlar=f"Ort.puan: {ort_puan:.1f}",
                )
                db.add(log)
                eklenen += 1

        db.commit()
        print(f"[OK] {eklenen} uretim logu olusturuldu.")
        print(f"Toplam uretim logu: {db.query(UretimLog).count()}")

        # Israf modelini yeniden egit
        print("\nIsraf modeli egitiliyor...")
        try:
            from modules.waste_analyzer import train_waste_model_from_db
            result = train_waste_model_from_db(db)
            if result.get("success"):
                print(f"[OK] Model egitildi! MAE: {result.get('mae', '?')}, R2: {result.get('r2', '?')}")
            else:
                print(f"Model egitim notu: {result.get('message', 'Bilinmiyor')}")
        except Exception as e:
            print(f"Model egitim hatasi: {e}")

    except Exception as e:
        db.rollback()
        print(f"Hata: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_production_logs()
