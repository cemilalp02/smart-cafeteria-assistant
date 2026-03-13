"""
AI Akıllı Yemekhane Asistan Sistemi — İsraf Analizi Modülü

Anonim puanlama ve tüketim verilerinden israf oranı türetir.
  - Puan 1-2 → yüksek israf (%60-80 artık)
  - Puan 3   → orta israf  (%30-40 artık)
  - Puan 4-5 → düşük israf (%0-15 artık)
"""

from datetime import date, timedelta

from sqlalchemy import func as sqla_func

from models import SessionLocal, MenuPuanlama, KullaniciYemekLog, Yemek


# ─── Sabitler ──────────────────────────────────────────────────────
ISRAF_MAP = {
    1: 80,  # Puan 1 → %80 israf
    2: 65,  # Puan 2 → %65 israf
    3: 35,  # Puan 3 → %35 israf
    4: 12,  # Puan 4 → %12 israf
    5: 5,   # Puan 5 → %5 israf
}


def puan_to_israf_orani(puan: float) -> float:
    """Puanı tahmini israf oranına (%0-100) dönüştürür."""
    if puan <= 1:
        return 80.0
    elif puan <= 2:
        return 65.0 + (2 - puan) * 15  # 65-80
    elif puan <= 3:
        return 35.0 + (3 - puan) * 30  # 35-65
    elif puan <= 4:
        return 12.0 + (4 - puan) * 23  # 12-35
    else:
        return max(0, 5.0 + (5 - puan) * 7)  # 0-12


def calculate_waste_score(yemek_adi: str, db=None) -> dict:
    """
    Belirli bir yemeğin israf skorunu hesaplar (0-100).
    100 = en çok israf edilen.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        result = (
            db.query(
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"))
            .first()
        )

        if result and result.toplam_oy and result.toplam_oy > 0:
            ort_puan = float(result.ortalama)
            israf_orani = puan_to_israf_orani(ort_puan)
            return {
                "yemek_adi": yemek_adi,
                "ortalama_puan": round(ort_puan, 2),
                "toplam_oy": result.toplam_oy,
                "israf_skoru": round(israf_orani, 1),
                "israf_seviye": (
                    "Yüksek" if israf_orani >= 50 else
                    "Orta" if israf_orani >= 25 else
                    "Düşük"
                ),
            }

        return {
            "yemek_adi": yemek_adi,
            "ortalama_puan": None,
            "toplam_oy": 0,
            "israf_skoru": None,
            "israf_seviye": "Veri yok",
        }
    finally:
        if close_db:
            db.close()


def get_daily_waste_report(db=None) -> dict:
    """Bugünün tahmini israf raporunu döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()

        sonuclar = (
            db.query(
                MenuPuanlama.yemek_adi,
                MenuPuanlama.kategori,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih == bugun)
            .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
            .all()
        )

        yemekler = []
        toplam_israf = 0
        for row in sonuclar:
            ort = float(row.ortalama)
            israf = puan_to_israf_orani(ort)
            yemekler.append({
                "yemek_adi": row.yemek_adi,
                "kategori": row.kategori,
                "ortalama_puan": round(ort, 2),
                "toplam_oy": row.toplam_oy,
                "israf_skoru": round(israf, 1),
                "israf_seviye": (
                    "Yüksek" if israf >= 50 else
                    "Orta" if israf >= 25 else
                    "Düşük"
                ),
            })
            toplam_israf += israf

        genel_israf = round(toplam_israf / len(yemekler), 1) if yemekler else 0

        return {
            "success": True,
            "tarih": str(bugun),
            "genel_israf_skoru": genel_israf,
            "genel_israf_seviye": (
                "Yüksek" if genel_israf >= 50 else
                "Orta" if genel_israf >= 25 else
                "Düşük"
            ),
            "yemekler": sorted(yemekler, key=lambda x: x["israf_skoru"], reverse=True),
        }
    finally:
        if close_db:
            db.close()


def get_weekly_waste_report(db=None) -> dict:
    """Haftalık israf özetini döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        hafta_basi = bugun - timedelta(days=7)

        # Yemek bazında israf
        sonuclar = (
            db.query(
                MenuPuanlama.yemek_adi,
                MenuPuanlama.kategori,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih >= hafta_basi)
            .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
            .all()
        )

        yemekler = []
        for row in sonuclar:
            ort = float(row.ortalama)
            israf = puan_to_israf_orani(ort)
            yemekler.append({
                "yemek_adi": row.yemek_adi,
                "kategori": row.kategori,
                "ortalama_puan": round(ort, 2),
                "toplam_oy": row.toplam_oy,
                "israf_skoru": round(israf, 1),
            })

        yemekler.sort(key=lambda x: x["israf_skoru"], reverse=True)

        # Günlük trend
        gunluk = (
            db.query(
                MenuPuanlama.tarih,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
            )
            .filter(MenuPuanlama.tarih >= hafta_basi)
            .group_by(MenuPuanlama.tarih)
            .order_by(MenuPuanlama.tarih)
            .all()
        )

        gunluk_trend = [
            {
                "tarih": str(row.tarih),
                "ortalama_puan": round(float(row.ortalama), 2),
                "israf_skoru": round(puan_to_israf_orani(float(row.ortalama)), 1),
            }
            for row in gunluk
        ]

        # Kategori bazında
        kategori_ort = (
            db.query(
                MenuPuanlama.kategori,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
            )
            .filter(MenuPuanlama.tarih >= hafta_basi)
            .group_by(MenuPuanlama.kategori)
            .all()
        )

        kategori_israf = {
            row.kategori: {
                "ortalama_puan": round(float(row.ortalama), 2),
                "israf_skoru": round(puan_to_israf_orani(float(row.ortalama)), 1),
            }
            for row in kategori_ort
        }

        genel = sum(y["israf_skoru"] for y in yemekler) / len(yemekler) if yemekler else 0

        return {
            "success": True,
            "donem": {"baslangic": str(hafta_basi), "bitis": str(bugun)},
            "genel_israf_skoru": round(genel, 1),
            "en_cok_israf": yemekler[:5],
            "en_az_israf": list(reversed(yemekler[-5:])) if len(yemekler) >= 5 else list(reversed(yemekler)),
            "gunluk_trend": gunluk_trend,
            "kategori_israf": kategori_israf,
            "tum_yemekler": yemekler,
        }
    finally:
        if close_db:
            db.close()


def get_dish_waste_history(yemek_adi: str, gun: int = 30, db=None) -> dict:
    """Belirli bir yemeğin israf geçmişini döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        baslangic = bugun - timedelta(days=gun)

        gunluk = (
            db.query(
                MenuPuanlama.tarih,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(
                MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
                MenuPuanlama.tarih >= baslangic,
            )
            .group_by(MenuPuanlama.tarih)
            .order_by(MenuPuanlama.tarih)
            .all()
        )

        trend = [
            {
                "tarih": str(row.tarih),
                "ortalama_puan": round(float(row.ortalama), 2),
                "israf_skoru": round(puan_to_israf_orani(float(row.ortalama)), 1),
                "toplam_oy": row.toplam_oy,
            }
            for row in gunluk
        ]

        # Genel
        genel = calculate_waste_score(yemek_adi, db)

        return {
            "success": True,
            "yemek_adi": yemek_adi,
            "donem_gun": gun,
            "genel_israf_skoru": genel["israf_skoru"],
            "genel_israf_seviye": genel["israf_seviye"],
            "ortalama_puan": genel["ortalama_puan"],
            "trend": trend,
        }
    finally:
        if close_db:
            db.close()
