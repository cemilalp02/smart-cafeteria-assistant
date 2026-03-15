"""
AI Akıllı Yemekhane Asistan Sistemi — Tahminsel Analiz Modülü
═════════════════════════════════════════════════════════════
Geçmiş israf ve puanlama verilerinden gelecek haftanın
israf trendini ve riskli yemekleri tahmin eder.

Yöntemler:
  - Ağırlıklı Hareketli Ortalama (WMA): Son haftalara daha çok ağırlık
  - Trend Yönü: Artış/azalış/stabil
  - Risk Skorlama: Düşük puan + yüksek israf = yüksek risk
"""

from __future__ import annotations

from datetime import date, timedelta
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session
from models import SessionLocal, MenuPuanlama, Alert


# ═══════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ═══════════════════════════════════════════════════════════════════

def _weighted_moving_average(values: list[float], weights: Optional[list[int]] = None) -> float:
    """Ağırlıklı hareketli ortalama hesaplar."""
    if not values:
        return 0
    if weights is None:
        # Son değere daha çok ağırlık ver
        n = len(values)
        weights = list(range(1, n + 1))
    total_weight = sum(weights[:len(values)])
    if total_weight == 0:
        return 0
    return sum(v * w for v, w in zip(values, weights[:len(values)])) / total_weight


def _trend_direction(values: list[float]) -> tuple[str, float]:
    """Basit trend yönü: artış/azalış/stabil."""
    if len(values) < 2:
        return "stabil", 0

    # Basit regresyon eğimi
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denom = sum((i - x_mean) ** 2 for i in range(n))

    if denom == 0:
        return "stabil", 0

    slope = num / denom

    if slope > 0.05:
        return "artış", slope
    elif slope < -0.05:
        return "azalış", slope
    return "stabil", slope


# ═══════════════════════════════════════════════════════════════════
# HAFTALIK TAHMİN
# ═══════════════════════════════════════════════════════════════════

# Puandan israf oranına dönüşüm
ISRAF_MAP = {1: 80, 2: 65, 3: 35, 4: 12, 5: 5}


def _puan_to_israf(puan: float) -> float:
    """Puanı tahmini israf yüzdesine çevirir."""
    if puan <= 1:
        return 80
    if puan >= 5:
        return 5
    lower = int(puan)
    upper = lower + 1
    frac = puan - lower
    return ISRAF_MAP[lower] * (1 - frac) + ISRAF_MAP[upper] * frac


def predict_next_week_waste(db: Optional[Session] = None) -> dict[str, Any]:
    """
    Son 4 haftanın verilerinden gelecek haftanın israf trendini tahmin eder.

    Returns:
        dict: {
            "tahmin_israf_skoru": float,
            "trend_yon": str,
            "guven": str,
            "haftalik_gecmis": [...],
            "riskli_yemekler": [...],
            "oneriler": [...]
        }
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        today = date.today()
        weekly_scores = []

        # Son 4 haftanın verilerini al
        for week in range(4):
            week_end = today - timedelta(days=week * 7)
            week_start = week_end - timedelta(days=6)

            records = db.query(
                sqla_func.avg(MenuPuanlama.puan).label("avg_puan"),
                sqla_func.count(MenuPuanlama.id).label("count"),
            ).filter(
                MenuPuanlama.tarih >= week_start,
                MenuPuanlama.tarih <= week_end,
            ).first()

            if records and records.avg_puan and records.count > 0:
                israf = _puan_to_israf(float(records.avg_puan))
                weekly_scores.append({
                    "hafta": f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}",
                    "ort_puan": round(float(records.avg_puan), 1),
                    "israf_skoru": round(israf, 1),
                    "veri_sayisi": records.count,
                })

        # Tahmin yap
        if not weekly_scores:
            return {
                "success": False,
                "message": "Yeterli veri yok (en az 1 haftalık veri gerekli).",
            }

        # Kronolojik sırala (eskiden yeniye)
        weekly_scores.reverse()
        israf_values = [w["israf_skoru"] for w in weekly_scores]

        # WMA ile tahmin
        predicted_waste = _weighted_moving_average(israf_values)

        # Trend yönü
        trend, slope = _trend_direction(israf_values)

        # Trend'e göre tahmin düzeltme
        if trend == "artış":
            predicted_waste = min(100, predicted_waste + abs(slope) * 5)
        elif trend == "azalış":
            predicted_waste = max(0, predicted_waste - abs(slope) * 5)

        # Güven seviyesi
        n = len(weekly_scores)
        if n >= 4:
            confidence = "Yüksek"
        elif n >= 2:
            confidence = "Orta"
        else:
            confidence = "Düşük"

        # Seviye
        if predicted_waste >= 50:
            seviye = "KRİTİK"
        elif predicted_waste >= 30:
            seviye = "UYARI"
        elif predicted_waste >= 15:
            seviye = "DİKKAT"
        else:
            seviye = "İYİ"

        # Riskli yemekleri bul (son 2 haftada ort puan < 2.5)
        risk_start = today - timedelta(days=13)
        riskli = db.query(
            MenuPuanlama.yemek_adi,
            sqla_func.avg(MenuPuanlama.puan).label("ort"),
            sqla_func.count(MenuPuanlama.id).label("cnt"),
        ).filter(
            MenuPuanlama.tarih >= risk_start,
        ).group_by(
            MenuPuanlama.yemek_adi,
        ).having(
            sqla_func.avg(MenuPuanlama.puan) < 2.5,
        ).order_by(
            sqla_func.avg(MenuPuanlama.puan),
        ).limit(5).all()

        riskli_list = [
            {
                "yemek_adi": r.yemek_adi,
                "ort_puan": round(float(r.ort), 1),
                "tahmini_israf": round(_puan_to_israf(float(r.ort)), 1),
                "risk": "Yüksek" if r.ort < 2.0 else "Orta",
            }
            for r in riskli
        ]

        # Öneriler
        oneriler = []
        if predicted_waste >= 50:
            oneriler.append("🔴 İsraf kritik seviyede! Menüde düşük puanlı yemekleri değiştirin.")
        if predicted_waste >= 30:
            oneriler.append("🟠 Riskli yemekleri menüden çıkarmayı veya tariflerini değiştirmeyi düşünün.")
        if trend == "artış":
            oneriler.append("📈 İsraf trendi artıyor. Öğrenci geri bildirimlerini incelemeniz önerilir.")
        if trend == "azalış":
            oneriler.append("📉 İsraf trendi düşüyor — mevcut menü stratejisi işe yarıyor!")
        if riskli_list:
            oneriler.append(f"⚠️ {len(riskli_list)} riskli yemek tespit edildi. Detayları kontrol edin.")
        if not oneriler:
            oneriler.append("✅ Her şey yolunda! Mevcut performansı koruyun.")

        return {
            "success": True,
            "tahmin_israf_skoru": round(predicted_waste, 1),
            "tahmin_seviye": seviye,
            "trend_yon": trend,
            "trend_yon_tr": {
                "artış": "📈 Artıyor",
                "azalış": "📉 Azalıyor",
                "stabil": "➡️ Stabil",
            }.get(trend, trend),
            "guven": confidence,
            "haftalik_gecmis": weekly_scores,
            "riskli_yemekler": riskli_list,
            "oneriler": oneriler,
        }

    finally:
        if close_db:
            db.close()


def predict_dish_risk(yemek_adi: str, db: Optional[Session] = None) -> dict[str, Any]:
    """
    Belirli bir yemeğin israf riskini tahmin eder.

    Args:
        yemek_adi: Yemek adı.

    Returns:
        dict: Risk bilgileri.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        today = date.today()
        weekly_avgs = []

        for week in range(4):
            week_end = today - timedelta(days=week * 7)
            week_start = week_end - timedelta(days=6)

            avg = db.query(
                sqla_func.avg(MenuPuanlama.puan),
            ).filter(
                MenuPuanlama.yemek_adi == yemek_adi,
                MenuPuanlama.tarih >= week_start,
                MenuPuanlama.tarih <= week_end,
            ).scalar()

            if avg is not None:
                weekly_avgs.append(float(avg))

        if not weekly_avgs:
            return {"success": False, "message": f"'{yemek_adi}' için veri bulunamadı."}

        weekly_avgs.reverse()
        avg_puan = _weighted_moving_average(weekly_avgs)
        israf = _puan_to_israf(avg_puan)
        trend, _ = _trend_direction(weekly_avgs)

        if israf >= 50:
            risk = "Yüksek"
        elif israf >= 25:
            risk = "Orta"
        else:
            risk = "Düşük"

        return {
            "success": True,
            "yemek_adi": yemek_adi,
            "tahmini_puan": round(avg_puan, 1),
            "tahmini_israf": round(israf, 1),
            "risk_seviye": risk,
            "trend": trend,
            "haftalik_puanlar": weekly_avgs,
        }

    finally:
        if close_db:
            db.close()


def generate_predictive_alerts(db: Optional[Session] = None) -> list[dict[str, Any]]:
    """
    Tahmine dayalı uyarılar oluşturur.

    Returns:
        list[dict]: Uyarı listesi.
    """
    prediction = predict_next_week_waste(db)
    if not prediction.get("success"):
        return []

    alerts = []

    # Genel israf tahmini
    waste = prediction["tahmin_israf_skoru"]
    if waste >= 50:
        alerts.append({
            "seviye": "KRITIK",
            "mesaj": f"🔮 Tahmin: Gelecek hafta israf oranı %{waste:.0f} olabilir! Menüyü gözden geçirin.",
            "tip": "tahmin",
        })
    elif waste >= 30:
        alerts.append({
            "seviye": "UYARI",
            "mesaj": f"🔮 Tahmin: Gelecek hafta israf %{waste:.0f} civarında. Dikkatli olun.",
            "tip": "tahmin",
        })

    # Trend uyarısı
    if prediction["trend_yon"] == "artış":
        alerts.append({
            "seviye": "DIKKAT",
            "mesaj": "📈 İsraf trendi son haftalarda artış gösteriyor. Önlem alın.",
            "tip": "tahmin",
        })

    # Riskli yemekler
    for r in prediction.get("riskli_yemekler", [])[:3]:
        alerts.append({
            "seviye": "DIKKAT",
            "mesaj": f"⚠️ '{r['yemek_adi']}' riskli: ort. puan {r['ort_puan']}/5, "
                     f"tahmini israf %{r['tahmini_israf']:.0f}",
            "tip": "tahmin",
        })

    return alerts
