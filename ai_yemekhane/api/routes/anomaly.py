"""
Anomali Tespiti API Endpoint'leri — Öneri 4B
Prefix: /api/v1/anomaly
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db

router = APIRouter(prefix="/api/v1/anomaly", tags=["Anomali Tespiti"])


@router.post("/detect")
async def detect_anomalies(
    tarih: Optional[str] = Query(None, description="Tarih (YYYY-MM-DD), varsayılan: bugün"),
    use_isolation_forest: bool = Query(True, description="Isolation Forest kullan"),
):
    """
    Verilen tarih için anomali tespiti çalıştır.
    Tespit edilen anomalileri DB'ye kaydeder.
    """
    from modules.anomaly_detector import detect_and_save

    target_date = None
    if tarih:
        try:
            target_date = date.fromisoformat(tarih)
        except ValueError:
            return {"success": False, "error": "Geçersiz tarih formatı. YYYY-MM-DD kullanın."}

    return detect_and_save(target_date=target_date, use_isolation_forest=use_isolation_forest)


@router.get("/list")
async def list_anomalies(
    limit: int = Query(50, ge=1, le=500),
    cozulmus_dahil: bool = Query(False, description="Çözülmüş anomalileri de dahil et"),
    siddet: Optional[str] = Query(None, description="Filtre: KRITIK | YUKSEK | ORTA | DUSUK"),
):
    """Kayıtlı anomali listesini döndür."""
    from modules.anomaly_detector import list_anomalies as _list

    return _list(
        limit=limit,
        cozulmus_dahil=cozulmus_dahil,
        siddet_filtre=siddet,
    )


@router.get("/stats")
async def anomaly_stats(
    gun: int = Query(30, ge=7, le=365, description="Geriye dönük gün sayısı"),
):
    """
    Pattern analizi istatistikleri:
    en sık anomali yaşayan yemekler, şiddet/tip dağılımı, günlük trend.
    """
    from modules.anomaly_detector import get_pattern_stats
    return get_pattern_stats(gun_sayisi=gun)


@router.post("/{anomali_id}/resolve")
async def resolve_anomaly(
    anomali_id: int,
    payload: dict = Body(default_factory=dict),
):
    """Bir anomali kaydını 'çözüldü' olarak işaretle."""
    from modules.anomaly_detector import resolve_anomaly as _resolve

    cozum_notu = payload.get("cozum_notu") if isinstance(payload, dict) else None
    return _resolve(anomali_id=anomali_id, cozum_notu=cozum_notu)


@router.get("/explain/{anomali_id}")
async def explain_anomaly(
    anomali_id: int,
    db: Session = Depends(get_db),
):
    """
    Anomali için XAI (SHAP) açıklaması.
    4A entegrasyonu — anomalinin neden oluştuğunu SHAP ile açıkla.
    """
    from models import AnomaliKaydi
    from modules.xai_explainer import get_single_explanation

    kayit = db.query(AnomaliKaydi).filter(AnomaliKaydi.id == anomali_id).first()
    if not kayit:
        return {"success": False, "error": "Anomali kaydı bulunamadı."}

    if not kayit.yemek_adi:
        return {
            "success": False,
            "error": "Bu kategori-bazlı anomali için XAI açıklaması yok (yemek belirsiz).",
        }

    explanation = get_single_explanation(
        yemek_adi=kayit.yemek_adi,
        kategori=kayit.kategori or "diger",
        tarih=kayit.tarih,
    )

    return {
        "success": True,
        "anomali": kayit.to_dict(),
        "shap_explanation": explanation,
    }
