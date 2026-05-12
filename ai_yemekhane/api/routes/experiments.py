"""
A/B Test ve Deney endpoint'leri — AI menü vs gerçek menü karşılaştırması,
istatistiksel anlamlılık testleri ve haftalık deney raporları.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db
from modules.experiment_engine import run_ab_experiment, get_experiment_summary

router = APIRouter(prefix="/api/v1", tags=["experiments"])


@router.get("/experiments/ab-test")
async def ab_test_experiment(
    hafta_baslangic: str = Query(default=None, description="YYYY-MM-DD (varsayılan: 4 hafta önce)"),
    hafta_sayisi: int = Query(default=4, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """
    A/B deneyi çalıştırır:
    - A grubu = Gerçek menü (mutfağın uyguladığı)
    - B grubu = AI önerisi (MenuOneriLog'daki)
    
    İsraf ve puan metrikleri karşılaştırılır, t-test uygulanır.
    """
    try:
        bas = date.fromisoformat(hafta_baslangic) if hafta_baslangic else None
    except ValueError:
        return {"success": False, "message": "Geçersiz tarih formatı. YYYY-MM-DD kullanın."}

    return run_ab_experiment(db, hafta_baslangic=bas, hafta_sayisi=hafta_sayisi)


@router.get("/experiments/summary")
async def experiment_summary(
    son_hafta: int = Query(default=8, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """Son N haftanın haftalık A/B test özet raporunu döndürür."""
    return get_experiment_summary(db, son_hafta=son_hafta)
