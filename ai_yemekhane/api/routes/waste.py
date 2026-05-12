"""
İsraf analizi endpoint'leri — günlük/haftalık raporlar,
yemek bazlı israf geçmişi, ML model durumu ve eğitimi.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from api.dependencies import get_db, WasteModelTrainRequest, UretimLog
from modules.waste_analyzer import (
    get_daily_waste_report,
    get_weekly_waste_report,
    get_dish_waste_history,
    train_waste_model_from_db,
    get_waste_model_status,
    get_feature_importance_report,
)

router = APIRouter(prefix="/api/v1", tags=["waste"])


@router.get("/waste/daily")
async def waste_daily(db: Session = Depends(get_db)):
    """Bugünün tahmini israf raporunu döndürür."""
    return get_daily_waste_report(db=db)


@router.get("/waste/weekly")
async def waste_weekly(db: Session = Depends(get_db)):
    """Haftalık israf özetini döndürür."""
    return get_weekly_waste_report(db=db)


@router.get("/waste/by-dish/{yemek_adi}")
async def waste_by_dish(
    yemek_adi: str,
    gun: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Belirli bir yemeğin israf geçmişini döndürür."""
    return get_dish_waste_history(yemek_adi, gun=gun, db=db)


@router.get("/waste/model-status")
async def waste_model_status(db: Session = Depends(get_db)):
    """Israf ML modelinin dosya/veri durumunu dondurur."""
    return get_waste_model_status(db=db)


@router.get("/waste/feature-importance")
async def waste_feature_importance():
    """Israf modelinin feature importance raporunu dondurur (admin dashboard icin)."""
    return get_feature_importance_report()


@router.post("/waste/train-model")
async def waste_train_model(
    request_body: WasteModelTrainRequest,
    db: Session = Depends(get_db),
):
    """
    Gercek uretim + puan sinyali ile israf modelini yeniden egitir.
    Veri yetersizse fallback devam eder.
    """
    return train_waste_model_from_db(db=db, min_samples=request_body.min_samples)


@router.get("/waste/production-summary")
async def waste_production_summary(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Son N gunun uretim ve israf trend verisini dondurur."""
    try:
        baslangic = date.today() - timedelta(days=gun)
        gunluk = (
            db.query(
                UretimLog.tarih,
                sqla_func.sum(UretimLog.uretilen_porsiyon).label("toplam_uretilen"),
                sqla_func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            )
            .filter(UretimLog.tarih >= baslangic)
            .group_by(UretimLog.tarih)
            .order_by(UretimLog.tarih)
            .all()
        )

        gunluk_trend = [
            {
                "tarih": str(g.tarih),
                "toplam_uretilen": int(g.toplam_uretilen or 0),
                "toplam_kalan": int(g.toplam_kalan or 0),
                "ort_israf": round(float(g.ort_israf or 0), 1),
            }
            for g in gunluk
        ]

        return {"success": True, "gunluk_trend": gunluk_trend}
    except Exception as e:
        return {"success": False, "error": str(e)}
