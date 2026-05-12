"""
Üretim planlama, tüketim takip ve manuel üretim veri girişi endpoint'leri.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.dependencies import (
    get_db,
    ProductionLogRequest,
    BulkProductionLogRequest,
    UretimLog,
)
from modules.consumption_tracker import (
    save_production_log,
    save_bulk_production_log,
    get_daily_consumption,
    get_weekly_consumption,
    get_dish_consumption_history,
)
from modules.production_planner import (
    get_dish_recommendation,
    generate_production_plan,
)

router = APIRouter(prefix="/api/v1", tags=["production"])


# ═══════════════════════════════════════════════════════════════════
# TÜKETİM TAKİP — MANUEL ÜRETİM VERİ GİRİŞİ
# ═══════════════════════════════════════════════════════════════════

@router.post("/production-log")
async def add_production_log(
    request_body: ProductionLogRequest,
    db: Session = Depends(get_db),
):
    """Tek bir yemek için üretim/kalan verisi kaydeder."""
    try:
        tarih = date.fromisoformat(request_body.tarih)
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "message": "Geçersiz tarih."})

    result = save_production_log(
        tarih=tarih,
        yemek_adi=request_body.yemek_adi,
        kategori=request_body.kategori,
        uretilen=request_body.uretilen,
        kalan=request_body.kalan,
        notlar=request_body.notlar,
        db=db,
    )
    return result


@router.post("/production-log/bulk")
async def add_bulk_production_log(
    request_body: BulkProductionLogRequest,
    db: Session = Depends(get_db),
):
    """Birden fazla yemek için toplu üretim verisi kaydeder."""
    try:
        tarih = date.fromisoformat(request_body.tarih)
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "message": "Geçersiz tarih."})

    result = save_bulk_production_log(tarih=tarih, girisler=request_body.girisler, db=db)
    return result


@router.get("/production-log/today")
async def get_today_production(db: Session = Depends(get_db)):
    """Bugün için girilmiş üretim verilerini döndürür."""
    bugun = date.today()
    kayitlar = (
        db.query(UretimLog)
        .filter(UretimLog.tarih == bugun)
        .order_by(UretimLog.kategori)
        .all()
    )
    return {
        "success": True,
        "tarih": str(bugun),
        "kayitlar": [k.to_dict() for k in kayitlar],
    }


@router.get("/consumption/daily")
async def consumption_daily(
    tarih: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Günlük tüketim/israf raporu."""
    t = date.fromisoformat(tarih) if tarih else None
    return get_daily_consumption(tarih=t, db=db)


@router.get("/consumption/weekly")
async def consumption_weekly(db: Session = Depends(get_db)):
    """Haftalık tüketim özeti."""
    return get_weekly_consumption(db=db)


@router.get("/consumption/by-dish/{yemek_adi}")
async def consumption_by_dish(
    yemek_adi: str,
    gun: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Belirli bir yemeğin tüketim geçmişi."""
    return get_dish_consumption_history(yemek_adi, gun=gun, db=db)


# ═══════════════════════════════════════════════════════════════════
# ÜRETİM PLANLAMA
# ═══════════════════════════════════════════════════════════════════

@router.get("/production/plan")
async def production_plan(db: Session = Depends(get_db)):
    """Geçmiş verilere dayalı üretim planı önerisi."""
    return generate_production_plan(db=db)


@router.get("/production/dish-recommendation/{yemek_adi}")
async def dish_recommendation(
    yemek_adi: str,
    db: Session = Depends(get_db),
):
    """Belirli bir yemek için üretim önerisi."""
    return get_dish_recommendation(yemek_adi, db=db)
