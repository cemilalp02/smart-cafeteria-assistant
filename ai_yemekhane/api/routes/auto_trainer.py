"""
Otomatik model retraining endpoint'leri — model sağlık durumu,
yeniden eğitim tetikleme ve champion-challenger karşılaştırması.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db
from modules.auto_trainer import check_and_retrain, get_model_health

router = APIRouter(prefix="/api/v1", tags=["auto_trainer"])


@router.get("/models/health")
async def model_health(db: Session = Depends(get_db)):
    """
    Tüm ML modellerinin sağlık durumunu döndürür.
    - healthy: Model güncel
    - stale: Model eski (>14 gün)
    - retrain_needed: Yeterli yeni veri birikmiş
    - missing: Model dosyası yok
    """
    return get_model_health(db)


@router.post("/models/retrain")
async def retrain_models(
    background_tasks: BackgroundTasks,
    model: str = Query(default=None, description="waste | sentiment | None (tümü)"),
    force: bool = Query(default=False, description="Eşik kontrolünü atla"),
    db: Session = Depends(get_db),
):
    """
    Belirtilen modeli (veya tümünü) yeniden eğitir.
    Champion-challenger: eski model yedeklenir, başarısızsa geri yüklenir.
    """
    return check_and_retrain(db, model_name=model, force=force)


@router.post("/models/retrain-async")
async def retrain_models_async(
    background_tasks: BackgroundTasks,
    model: str = Query(default=None, description="waste | sentiment | None (tümü)"),
    force: bool = Query(default=False),
):
    """
    Modeli arka planda yeniden eğitir (non-blocking).
    Görev durumu /api/tasks/{task_id} ile takip edilir.
    """
    from api.routes.tasks import _create_task, _update_task, _finish_task
    from models import SessionLocal

    task_id = _create_task(f"auto_retrain_{model or 'all'}")

    def _bg_retrain(tid: str, mname: str | None, do_force: bool):
        try:
            _update_task(tid, progress=10, message="Veritabanı bağlantısı kuruluyor...")
            session = SessionLocal()
            try:
                _update_task(tid, progress=20, message="Model kontrol ve eğitim başlıyor...")
                result = check_and_retrain(session, model_name=mname, force=do_force)
                _finish_task(tid, result=result)
            finally:
                session.close()
        except Exception as e:
            _finish_task(tid, error=f"{type(e).__name__}: {e}")

    background_tasks.add_task(_bg_retrain, task_id, model, force)

    return {
        "success": True,
        "message": "Model retraining arka planda başlatıldı.",
        "task_id": task_id,
        "status_url": f"/api/tasks/{task_id}",
    }
