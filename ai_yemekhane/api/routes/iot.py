"""
IoT Tartı Entegrasyonu API Endpoint'leri
─────────────────────────────────────────
- POST /api/v1/iot/weight-data   → Tartı verisini kaydet
- POST /api/v1/iot/simulate      → Simülasyon çalıştır
- GET  /api/v1/iot/status         → IoT durum özeti
- GET  /api/v1/iot/daily          → Günlük tartı verileri

Silme: Bu dosyayı silip main.py'den import'u kaldırmak yeterlidir.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from api.dependencies import get_db, UretimLog

router = APIRouter(prefix="/api/v1/iot", tags=["iot"])


# ── Request / Response Modelleri ──────────────────────────────────

class WeightDataRequest(BaseModel):
    tarih: str
    yemek_adi: str
    tartilan_israf_kg: float = Field(..., ge=0, le=500)
    kaynak: str = Field(default="iot_tarti", pattern="^(iot_tarti|simulasyon|manuel)$")


class SimulateRequest(BaseModel):
    tarih: str | None = None
    gun_sayisi: int = Field(default=1, ge=1, le=90)
    overwrite: bool = False


# ═══════════════════════════════════════════════════════════════════
# TARTI VERİSİ KAYDET
# ═══════════════════════════════════════════════════════════════════

@router.post("/weight-data")
async def record_weight_data(
    body: WeightDataRequest,
    db: Session = Depends(get_db),
):
    """IoT tartı veya manuel girişten gelen israf ağırlığını kaydeder."""
    try:
        tarih = date.fromisoformat(body.tarih)
    except ValueError:
        return {"success": False, "message": "Geçersiz tarih formatı. YYYY-MM-DD olmalı."}

    # Eşleşen UretimLog kaydını bul
    log = (
        db.query(UretimLog)
        .filter(
            UretimLog.tarih == tarih,
            UretimLog.yemek_adi.ilike(f"%{body.yemek_adi}%"),
        )
        .first()
    )

    if not log:
        return {
            "success": False,
            "message": f"'{body.yemek_adi}' için {body.tarih} tarihinde üretim kaydı bulunamadı.",
        }

    log.tartilan_israf_kg = body.tartilan_israf_kg
    log.tartilan_israf_kaynagi = body.kaynak
    db.commit()

    return {
        "success": True,
        "message": f"Tartı verisi kaydedildi: {body.yemek_adi} → {body.tartilan_israf_kg} kg ({body.kaynak})",
        "data": log.to_dict(),
    }


# ═══════════════════════════════════════════════════════════════════
# SİMÜLASYON ÇALIŞTIR
# ═══════════════════════════════════════════════════════════════════

@router.post("/simulate")
async def run_simulation_endpoint(
    body: SimulateRequest,
    db: Session = Depends(get_db),
):
    """Simülasyon modunu çalıştırarak tutarlı tartı verisi üretir."""
    from modules.iot_simulator import run_simulation, run_bulk_simulation

    try:
        if body.gun_sayisi > 1:
            result = run_bulk_simulation(
                db=db,
                gun_sayisi=body.gun_sayisi,
                overwrite=body.overwrite,
            )
        else:
            tarih = date.fromisoformat(body.tarih) if body.tarih else date.today()
            result = run_simulation(db=db, tarih=tarih, overwrite=body.overwrite)

        return result

    except Exception as e:
        return {"success": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# IoT DURUM ÖZETİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/status")
async def iot_status(db: Session = Depends(get_db)):
    """IoT tartı sistemi durum özeti."""
    bugun = date.today()
    son_30_gun = bugun - timedelta(days=30)

    # Bugünün tartı verileri
    bugun_count = (
        db.query(sqla_func.count(UretimLog.id))
        .filter(
            UretimLog.tarih == bugun,
            UretimLog.tartilan_israf_kg.isnot(None),
        )
        .scalar() or 0
    )

    bugun_toplam_kg = (
        db.query(sqla_func.sum(UretimLog.tartilan_israf_kg))
        .filter(
            UretimLog.tarih == bugun,
            UretimLog.tartilan_israf_kg.isnot(None),
        )
        .scalar() or 0.0
    )

    # Son 30 gün özet
    son30_toplam = (
        db.query(sqla_func.sum(UretimLog.tartilan_israf_kg))
        .filter(
            UretimLog.tarih >= son_30_gun,
            UretimLog.tartilan_israf_kg.isnot(None),
        )
        .scalar() or 0.0
    )

    son30_count = (
        db.query(sqla_func.count(UretimLog.id))
        .filter(
            UretimLog.tarih >= son_30_gun,
            UretimLog.tartilan_israf_kg.isnot(None),
        )
        .scalar() or 0
    )

    # Kaynak dağılımı
    kaynak_dagilim = {}
    kaynak_rows = (
        db.query(
            UretimLog.tartilan_israf_kaynagi,
            sqla_func.count(UretimLog.id).label("sayi"),
        )
        .filter(
            UretimLog.tarih >= son_30_gun,
            UretimLog.tartilan_israf_kg.isnot(None),
        )
        .group_by(UretimLog.tartilan_israf_kaynagi)
        .all()
    )
    for r in kaynak_rows:
        kaynak_dagilim[r.tartilan_israf_kaynagi or "bilinmeyen"] = int(r.sayi)

    return {
        "success": True,
        "bugun": {
            "tarih": str(bugun),
            "olcum_sayisi": bugun_count,
            "toplam_israf_kg": round(float(bugun_toplam_kg), 2),
        },
        "son_30_gun": {
            "toplam_israf_kg": round(float(son30_toplam), 2),
            "olcum_sayisi": son30_count,
            "ort_gunluk_kg": round(float(son30_toplam) / 30, 2) if son30_toplam else 0,
        },
        "kaynak_dagilim": kaynak_dagilim,
    }


# ═══════════════════════════════════════════════════════════════════
# GÜNLÜK TARTI VERİLERİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/daily")
async def iot_daily_data(
    tarih: str | None = None,
    db: Session = Depends(get_db),
):
    """Belirli bir günün tartı verilerini yemek bazında döndürür."""
    hedef = date.fromisoformat(tarih) if tarih else date.today()

    logs = (
        db.query(UretimLog)
        .filter(
            UretimLog.tarih == hedef,
            UretimLog.tartilan_israf_kg.isnot(None),
        )
        .all()
    )

    yemekler = []
    for log in logs:
        uretilen_kg = (log.uretilen_porsiyon or 0) * 0.35
        yemekler.append({
            "yemek_adi": log.yemek_adi,
            "kategori": log.kategori,
            "uretilen_porsiyon": log.uretilen_porsiyon,
            "uretilen_kg_tahmini": round(uretilen_kg, 2),
            "tartilan_israf_kg": log.tartilan_israf_kg,
            "israf_orani_hesaplanan": round(
                (log.tartilan_israf_kg / uretilen_kg * 100) if uretilen_kg > 0 else 0, 1
            ),
            "israf_orani_yonetici": log.israf_orani,
            "kaynak": log.tartilan_israf_kaynagi,
        })

    toplam_israf = sum(y["tartilan_israf_kg"] or 0 for y in yemekler)
    toplam_uretim = sum(y["uretilen_kg_tahmini"] or 0 for y in yemekler)

    return {
        "success": True,
        "tarih": str(hedef),
        "toplam_israf_kg": round(toplam_israf, 2),
        "toplam_uretim_kg": round(toplam_uretim, 2),
        "genel_israf_orani": round(
            (toplam_israf / toplam_uretim * 100) if toplam_uretim > 0 else 0, 1
        ),
        "yemekler": yemekler,
    }


# ═══════════════════════════════════════════════════════════════════
# TARTI TREND VERİSİ (Son N gün)
# ═══════════════════════════════════════════════════════════════════

@router.get("/trend")
async def iot_trend(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Son N günün günlük toplam tartı israf trendi."""
    baslangic = date.today() - timedelta(days=gun)

    rows = (
        db.query(
            UretimLog.tarih,
            sqla_func.sum(UretimLog.tartilan_israf_kg).label("toplam_kg"),
            sqla_func.count(UretimLog.id).label("olcum_sayisi"),
        )
        .filter(
            UretimLog.tarih >= baslangic,
            UretimLog.tartilan_israf_kg.isnot(None),
        )
        .group_by(UretimLog.tarih)
        .order_by(UretimLog.tarih)
        .all()
    )

    trend = [
        {
            "tarih": str(r.tarih),
            "toplam_israf_kg": round(float(r.toplam_kg), 2),
            "olcum_sayisi": int(r.olcum_sayisi),
        }
        for r in rows
    ]

    return {
        "success": True,
        "gun": gun,
        "trend": trend,
    }
