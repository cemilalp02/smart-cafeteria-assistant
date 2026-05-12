"""
Model performans tracking endpoint'leri — metrik geçmişi,
degradation tespiti ve en son metrikler.
"""

from fastapi import APIRouter, Query

from modules.model_tracker import (
    get_metrics_history,
    get_latest_metrics,
    check_degradation,
)

router = APIRouter(prefix="/api/v1", tags=["model_tracker"])


@router.get("/models/metrics")
async def model_metrics(
    model: str = Query(default=None, description="waste | menu | sentiment | None (tümü)"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Model eğitim metrik geçmişini döndürür."""
    return {
        "success": True,
        "history": get_metrics_history(model_name=model, limit=limit),
    }


@router.get("/models/metrics/latest")
async def model_metrics_latest():
    """Her model için en son metrikleri döndürür."""
    return {
        "success": True,
        "latest": get_latest_metrics(),
    }


@router.get("/models/metrics/degradation")
async def model_degradation(
    model: str = Query(description="waste | menu | sentiment"),
    threshold: float = Query(default=0.1, ge=0.01, le=0.5),
):
    """Son iki eğitim arasında performans düşüşü olup olmadığını kontrol eder."""
    result = check_degradation(model, threshold=threshold)
    return {"success": True, **result}
