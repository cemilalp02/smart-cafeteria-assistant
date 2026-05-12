"""
Rapor ve PDF indirme + tahminsel analiz endpoint'leri.
"""

import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.dependencies import get_db
from modules.pdf_report import generate_weekly_pdf, generate_monthly_pdf, generate_excel_report
from modules.predictive_analyzer import (
    predict_next_week_waste,
    predict_dish_risk,
    generate_predictive_alerts,
)

router = APIRouter(prefix="/api/v1", tags=["reports"])


# ──────────────────────────────────────────────────────────────────
# PDF RAPOR İNDİRME
# ──────────────────────────────────────────────────────────────────

@router.get("/report/pdf")
async def download_pdf_report(
    period: str = Query("weekly", description="weekly veya monthly"),
    db: Session = Depends(get_db),
):
    """Haftalık veya aylık raporu PDF olarak indirir."""
    try:
        if period == "monthly":
            pdf_bytes = generate_monthly_pdf(db)
            filename = f"aylik_rapor_{date.today().strftime('%Y%m%d')}.pdf"
        else:
            pdf_bytes = generate_weekly_pdf(db)
            filename = f"haftalik_rapor_{date.today().strftime('%Y%m%d')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/excel")
async def download_excel_report(
    gun: int = Query(default=30, ge=7, le=365, description="Son kaç günün verisi"),
    db: Session = Depends(get_db),
):
    """Puanlama, günlük detay, kategori ve israf verilerini Excel olarak indirir."""
    try:
        excel_bytes = generate_excel_report(db, gun=gun)
        filename = f"yemekhane_rapor_{date.today().strftime('%Y%m%d')}.xlsx"
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl kurulu değil. pip install openpyxl")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────
# TAHMİNSEL ANALİZ
# ──────────────────────────────────────────────────────────────────

@router.get("/predictions/weekly")
async def weekly_prediction(db: Session = Depends(get_db)):
    """Gelecek haftaya ait israf tahmini ve riskli yemekler."""
    try:
        result = predict_next_week_waste(db)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/predictions/dish/{yemek_adi}")
async def dish_prediction(yemek_adi: str, db: Session = Depends(get_db)):
    """Belirli bir yemeğin israf risk tahmini."""
    try:
        result = predict_dish_risk(yemek_adi, db)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/predictions/alerts")
async def predictive_alerts(db: Session = Depends(get_db)):
    """Tahmine dayalı uyarılar."""
    try:
        alerts = generate_predictive_alerts(db)
        return {"success": True, "alerts": alerts, "toplam": len(alerts)}
    except Exception as e:
        return {"success": False, "message": str(e)}
