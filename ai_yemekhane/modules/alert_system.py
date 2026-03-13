"""
AI Akıllı Yemekhane Asistan Sistemi — Otomatik İsraf Uyarı Sistemi

Kurallar:
  - 3 hafta üst üste ort puan < 2.5 → KRİTİK: Menüden çıkarılmalı
  - 2 hafta üst üste ort puan < 3.0 → UYARI: İzlemeye alındı
  - Puan %30+ ani düşüş → DİKKAT: Ani düşüş tespit edildi
  - Kategori genelinde düşüş → BİLGİ: Kategoride genel düşüş

Seviyeler: KRİTİK (kırmızı), UYARI (turuncu), DİKKAT (sarı), BİLGİ (mavi)
"""

from datetime import date, timedelta

from sqlalchemy import func as sqla_func

from models import SessionLocal, MenuPuanlama, Alert


SEVIYE_RENK = {
    "KRITIK": "red",
    "UYARI": "orange",
    "DIKKAT": "yellow",
    "BILGI": "blue",
}


def _get_weekly_averages(yemek_adi: str, hafta_sayisi: int, db) -> list:
    """Son N hafta için yemek bazında haftalık ortalama puanları döndürür."""
    bugun = date.today()
    hafta_ortalamalari = []

    for i in range(hafta_sayisi):
        hafta_sonu = bugun - timedelta(days=i * 7)
        hafta_basi = hafta_sonu - timedelta(days=7)

        result = (
            db.query(sqla_func.avg(MenuPuanlama.puan).label("ort"))
            .filter(
                MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
                MenuPuanlama.tarih >= hafta_basi,
                MenuPuanlama.tarih < hafta_sonu,
            )
            .scalar()
        )

        hafta_ortalamalari.append(float(result) if result else None)

    return hafta_ortalamalari  # [bu_hafta, geçen_hafta, 2_hafta_önce, ...]


def _get_unique_meals(gun: int, db) -> list:
    """Son N gün içinde puanlanan benzersiz yemek isimlerini döndürür."""
    baslangic = date.today() - timedelta(days=gun)
    result = (
        db.query(MenuPuanlama.yemek_adi)
        .filter(MenuPuanlama.tarih >= baslangic)
        .distinct()
        .all()
    )
    return [row.yemek_adi for row in result]


def check_and_generate_alerts(db=None) -> list:
    """
    Tüm uyarı kurallarını çalıştırır, yeni uyarılar oluşturur.
    Mevcut aktif uyarıları günceller.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        yeni_uyarilar = []
        bugun = date.today()

        # Benzersiz yemekleri al
        yemekler = _get_unique_meals(gun=30, db=db)

        for yemek in yemekler:
            hafta_ort = _get_weekly_averages(yemek, 3, db)

            # ─── KURAL 1: 3 hafta üst üste < 2.5 → KRİTİK ──────
            valid_weeks = [h for h in hafta_ort if h is not None]
            if len(valid_weeks) >= 3 and all(h < 2.5 for h in valid_weeks[:3]):
                mesaj = (
                    f"KRİTİK: '{yemek}' son 3 haftada sürekli düşük puan aldı "
                    f"(ort: {round(sum(valid_weeks[:3])/3, 1)}). "
                    f"Menüden çıkarılması önerilir."
                )
                _create_alert_if_new(db, "KRITIK", yemek, mesaj, bugun)
                yeni_uyarilar.append({"seviye": "KRITIK", "yemek": yemek, "mesaj": mesaj})

            # ─── KURAL 2: 2 hafta üst üste < 3.0 → UYARI ────────
            elif len(valid_weeks) >= 2 and all(h < 3.0 for h in valid_weeks[:2]):
                mesaj = (
                    f"UYARI: '{yemek}' son 2 haftada düşük puan aldı "
                    f"(ort: {round(sum(valid_weeks[:2])/2, 1)}). "
                    f"İzlemeye alındı."
                )
                _create_alert_if_new(db, "UYARI", yemek, mesaj, bugun)
                yeni_uyarilar.append({"seviye": "UYARI", "yemek": yemek, "mesaj": mesaj})

            # ─── KURAL 3: Ani %30+ düşüş → DİKKAT ───────────────
            if len(valid_weeks) >= 2 and valid_weeks[1] is not None and valid_weeks[1] > 0:
                if valid_weeks[0] is not None:
                    degisim = (valid_weeks[1] - valid_weeks[0]) / valid_weeks[1]
                    if degisim >= 0.30:
                        mesaj = (
                            f"DİKKAT: '{yemek}' puanında ani düşüş tespit edildi. "
                            f"Önceki: {round(valid_weeks[1], 1)}, "
                            f"Şimdi: {round(valid_weeks[0], 1)} "
                            f"(%{round(degisim*100)} düşüş)."
                        )
                        _create_alert_if_new(db, "DIKKAT", yemek, mesaj, bugun)
                        yeni_uyarilar.append({"seviye": "DIKKAT", "yemek": yemek, "mesaj": mesaj})

        # ─── KURAL 4: Kategori genelinde düşüş → BİLGİ ──────────
        kategoriler = ["corba", "ana_yemek", "pilav", "tatli", "salata"]
        kat_labels = {
            "corba": "Çorba", "ana_yemek": "Ana Yemek", "pilav": "Yan Yemek",
            "tatli": "Tatlı", "salata": "Salata",
        }

        for kat in kategoriler:
            # Bu hafta vs geçen hafta
            bu_hafta_ort = (
                db.query(sqla_func.avg(MenuPuanlama.puan))
                .filter(
                    MenuPuanlama.kategori == kat,
                    MenuPuanlama.tarih >= bugun - timedelta(days=7),
                )
                .scalar()
            )
            gecen_hafta_ort = (
                db.query(sqla_func.avg(MenuPuanlama.puan))
                .filter(
                    MenuPuanlama.kategori == kat,
                    MenuPuanlama.tarih >= bugun - timedelta(days=14),
                    MenuPuanlama.tarih < bugun - timedelta(days=7),
                )
                .scalar()
            )

            if bu_hafta_ort and gecen_hafta_ort:
                bu = float(bu_hafta_ort)
                gecen = float(gecen_hafta_ort)
                if gecen > 0 and (gecen - bu) / gecen >= 0.15:
                    mesaj = (
                        f"BİLGİ: {kat_labels.get(kat, kat)} kategorisinde genel düşüş. "
                        f"Geçen hafta: {round(gecen, 1)}, Bu hafta: {round(bu, 1)}."
                    )
                    _create_alert_if_new(db, "BILGI", None, mesaj, bugun, kategori=kat)
                    yeni_uyarilar.append({"seviye": "BILGI", "kategori": kat, "mesaj": mesaj})

        db.commit()
        return yeni_uyarilar

    finally:
        if close_db:
            db.close()


def _create_alert_if_new(db, seviye: str, yemek_adi: str, mesaj: str, tarih, kategori: str = None):
    """Aynı uyarı bugün oluşturulmadıysa yeni uyarı ekler."""
    mevcut = (
        db.query(Alert)
        .filter(
            Alert.seviye == seviye,
            Alert.tarih == tarih,
        )
    )
    if yemek_adi:
        mevcut = mevcut.filter(Alert.yemek_adi == yemek_adi)
    else:
        mevcut = mevcut.filter(Alert.kategori == kategori)

    if mevcut.first():
        return  # Zaten var

    yeni = Alert(
        tarih=tarih,
        seviye=seviye,
        yemek_adi=yemek_adi,
        kategori=kategori,
        mesaj=mesaj,
        aktif=True,
    )
    db.add(yeni)


def get_active_alerts(db=None) -> dict:
    """Aktif uyarıları döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Önce kuralları çalıştır
        check_and_generate_alerts(db=db)

        alerts = (
            db.query(Alert)
            .filter(Alert.aktif == True)
            .order_by(
                # KRİTİK en üstte
                sqla_func.case(
                    (Alert.seviye == "KRITIK", 1),
                    (Alert.seviye == "UYARI", 2),
                    (Alert.seviye == "DIKKAT", 3),
                    (Alert.seviye == "BILGI", 4),
                    else_=5,
                ),
                Alert.created_at.desc(),
            )
            .all()
        )

        return {
            "success": True,
            "toplam": len(alerts),
            "alerts": [a.to_dict() for a in alerts],
            "ozet": {
                "kritik": sum(1 for a in alerts if a.seviye == "KRITIK"),
                "uyari": sum(1 for a in alerts if a.seviye == "UYARI"),
                "dikkat": sum(1 for a in alerts if a.seviye == "DIKKAT"),
                "bilgi": sum(1 for a in alerts if a.seviye == "BILGI"),
            },
        }
    finally:
        if close_db:
            db.close()


def get_alert_history(limit: int = 50, db=None) -> dict:
    """Geçmiş uyarıları döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        alerts = (
            db.query(Alert)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .all()
        )

        return {
            "success": True,
            "toplam": len(alerts),
            "alerts": [a.to_dict() for a in alerts],
        }
    finally:
        if close_db:
            db.close()
