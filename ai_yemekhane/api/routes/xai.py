"""
XAI (Explainable AI) API endpoint'leri.
Prefix: /api/v1/xai
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/xai", tags=["XAI - Explainable AI"])


@router.get("/status")
async def xai_status():
    """XAI modülü durum bilgisi."""
    from modules.xai_explainer import get_xai_status
    return get_xai_status()


@router.get("/global")
async def xai_global(
    max_features: int = Query(15, ge=3, le=25, description="Gösterilecek max feature sayısı"),
):
    """
    Global feature importance — tüm modelin genel açıklaması.
    Hem mevcut importance hem SHAP (varsa) döndürür.
    """
    from modules.xai_explainer import get_global_explanation
    return get_global_explanation(max_features=max_features)


@router.get("/explain")
async def xai_explain(
    yemek_adi: str = Query(..., description="Yemek adı"),
    kategori: str = Query("diger", description="Kategori (corba, ana_yemek, yan_yemek, tatli, salata)"),
    tarih: Optional[str] = Query(None, description="Tarih (YYYY-MM-DD), varsayılan: bugün"),
    uretilen_porsiyon: float = Query(100.0, description="Üretilen porsiyon"),
    rating_avg: float = Query(3.0, description="Ortalama puan"),
    rating_count: int = Query(10, description="Toplam oy sayısı"),
):
    """
    Tek bir yemek için SHAP açıklaması.
    "Bu yemekte israf neden yüksek/düşük?" sorusuna cevap verir.
    """
    from modules.xai_explainer import get_single_explanation

    if tarih:
        try:
            tarih_date = date.fromisoformat(tarih)
        except ValueError:
            return {"success": False, "error": "Geçersiz tarih formatı. YYYY-MM-DD kullanın."}
    else:
        tarih_date = date.today()

    return get_single_explanation(
        yemek_adi=yemek_adi,
        kategori=kategori,
        tarih=tarih_date,
        uretilen_porsiyon=uretilen_porsiyon,
        rating_avg=rating_avg,
        rating_count=rating_count,
    )
