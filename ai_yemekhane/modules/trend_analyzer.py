"""
AI Akıllı Yemekhane Asistan Sistemi — Uzun Vadeli Trend Analizi Modülü

Puanlama verisinden tüketim trendleri, mevsimsel analiz,
trend yönü hesaplama ve anomali tespiti yapar.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from models import SessionLocal, MenuPuanlama


# ─── Sabitler ──────────────────────────────────────────────────────
MEVSIM_MAP = {
    12: "Kış", 1: "Kış", 2: "Kış",
    3: "İlkbahar", 4: "İlkbahar", 5: "İlkbahar",
    6: "Yaz", 7: "Yaz", 8: "Yaz",
    9: "Sonbahar", 10: "Sonbahar", 11: "Sonbahar",
}


def _get_trend_direction(values: list) -> str:
    """Basit doğrusal regresyon ile trend yönünü belirler."""
    if len(values) < 3:
        return "Yetersiz Veri"

    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "Sabit"

    slope = numerator / denominator

    if slope > 0.05:
        return "Yükselen"
    elif slope < -0.05:
        return "Düşen"
    else:
        return "Sabit"


def get_monthly_trends(gun: int = 30, db: Optional[Session] = None) -> dict[str, Any]:
    """Son N günlük genel tüketim trendlerini döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        baslangic = bugun - timedelta(days=gun)

        # Günlük genel ortalama
        gunluk = (
            db.query(
                MenuPuanlama.tarih,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih >= baslangic)
            .group_by(MenuPuanlama.tarih)
            .order_by(MenuPuanlama.tarih)
            .all()
        )

        gunluk_trend = [
            {
                "tarih": str(row.tarih),
                "ortalama": round(float(row.ortalama), 2),
                "toplam_oy": row.toplam_oy,
            }
            for row in gunluk
        ]

        values = [row.ortalama for row in gunluk if row.ortalama is not None]
        trend_yon = _get_trend_direction([float(v) for v in values])

        # Yemek bazında trendler
        yemek_ort = (
            db.query(
                MenuPuanlama.yemek_adi,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih >= baslangic)
            .group_by(MenuPuanlama.yemek_adi)
            .order_by(sqla_func.avg(MenuPuanlama.puan).desc())
            .all()
        )

        yemekler = [
            {
                "yemek_adi": row.yemek_adi,
                "ortalama": round(float(row.ortalama), 2),
                "toplam_oy": row.toplam_oy,
            }
            for row in yemek_ort
        ]

        genel_ort = round(float(sum(v for v in values) / len(values)), 2) if values else 0

        return {
            "success": True,
            "donem_gun": gun,
            "donem": {"baslangic": str(baslangic), "bitis": str(bugun)},
            "genel_ortalama": genel_ort,
            "trend_yon": trend_yon,
            "gunluk_trend": gunluk_trend,
            "yemekler": yemekler,
        }
    finally:
        if close_db:
            db.close()


def get_seasonal_analysis(db: Optional[Session] = None) -> dict[str, Any]:
    """Mevsimsel popülerlik analizini döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Tüm puanlama verisini çek
        tumveri = (
            db.query(
                MenuPuanlama.tarih,
                MenuPuanlama.yemek_adi,
                MenuPuanlama.kategori,
                MenuPuanlama.puan,
            )
            .all()
        )

        if not tumveri:
            return {"success": True, "mesaj": "Henüz yeterli veri yok.", "mevsimler": {}}

        # Mevsim bazında grupla
        mevsim_data = {}
        for row in tumveri:
            ay = row.tarih.month
            mevsim = MEVSIM_MAP.get(ay, "Bilinmiyor")

            if mevsim not in mevsim_data:
                mevsim_data[mevsim] = {}

            yemek = row.yemek_adi
            if yemek not in mevsim_data[mevsim]:
                mevsim_data[mevsim][yemek] = {"puanlar": [], "kategori": row.kategori}

            mevsim_data[mevsim][yemek]["puanlar"].append(row.puan)

        # Özet oluştur
        mevsimler = {}
        for mevsim, yemekler in mevsim_data.items():
            yemek_list = []
            for yemek, data in yemekler.items():
                ort = sum(data["puanlar"]) / len(data["puanlar"])
                yemek_list.append({
                    "yemek_adi": yemek,
                    "kategori": data["kategori"],
                    "ortalama": round(ort, 2),
                    "oy_sayisi": len(data["puanlar"]),
                })

            yemek_list.sort(key=lambda x: x["ortalama"], reverse=True)
            genel = sum(y["ortalama"] for y in yemek_list) / len(yemek_list) if yemek_list else 0

            mevsimler[mevsim] = {
                "genel_ortalama": round(genel, 2),
                "en_populer": yemek_list[:5],
                "en_az_populer": list(reversed(yemek_list[-3:])) if len(yemek_list) >= 3 else [],
                "toplam_yemek_sayisi": len(yemek_list),
            }

        return {
            "success": True,
            "mevsimler": mevsimler,
        }
    finally:
        if close_db:
            db.close()


def get_dish_trend(yemek_adi: str, gun: int = 90, db: Optional[Session] = None) -> dict[str, Any]:
    """Belirli bir yemeğin uzun vadeli trendini ve yönünü döndürür."""
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
                "ortalama": round(float(row.ortalama), 2),
                "toplam_oy": row.toplam_oy,
            }
            for row in gunluk
        ]

        values = [float(row.ortalama) for row in gunluk]
        trend_yon = _get_trend_direction(values)

        genel = (
            db.query(sqla_func.avg(MenuPuanlama.puan).label("ort"))
            .filter(
                MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
                MenuPuanlama.tarih >= baslangic,
            )
            .scalar()
        )

        return {
            "success": True,
            "yemek_adi": yemek_adi,
            "donem_gun": gun,
            "genel_ortalama": round(float(genel), 2) if genel else 0,
            "trend_yon": trend_yon,
            "trend": trend,
        }
    finally:
        if close_db:
            db.close()


def detect_anomalies(gun: int = 30, db: Optional[Session] = None) -> dict[str, Any]:
    """Normalden çok farklı puanlanan günleri tespit eder."""
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
            .filter(MenuPuanlama.tarih >= baslangic)
            .group_by(MenuPuanlama.tarih)
            .order_by(MenuPuanlama.tarih)
            .all()
        )

        if len(gunluk) < 5:
            return {"success": True, "anomaliler": [], "mesaj": "Yetersiz veri."}

        values = [float(row.ortalama) for row in gunluk]
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5

        anomaliler = []
        for row, val in zip(gunluk, values):
            if std_dev > 0:
                z_score = abs(val - mean_val) / std_dev
                if z_score > 1.5:  # 1.5 standart sapmadan fazla
                    anomaliler.append({
                        "tarih": str(row.tarih),
                        "ortalama": round(val, 2),
                        "beklenen": round(mean_val, 2),
                        "sapma": round(z_score, 2),
                        "yon": "Düşük" if val < mean_val else "Yüksek",
                        "toplam_oy": row.toplam_oy,
                    })

        return {
            "success": True,
            "donem_gun": gun,
            "ortalama": round(mean_val, 2),
            "standart_sapma": round(std_dev, 2),
            "anomaliler": anomaliler,
        }
    finally:
        if close_db:
            db.close()
