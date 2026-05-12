"""
Asenkron görev yönetimi — BackgroundTasks ile model eğitimi,
PDF üretimi gibi uzun süren işlemleri arka planda çalıştırır.
İşlem durumu polling ile takip edilir.
"""

import uuid
import time
import traceback
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db

router = APIRouter(prefix="/api/v1", tags=["tasks"])

# ═══════════════════════════════════════════════════════════════════
# IN-MEMORY TASK STORE (TTL + MAX SIZE)
# ═══════════════════════════════════════════════════════════════════

_task_store: dict[str, dict[str, Any]] = {}

# Temizlik politikası
TASK_TTL_HOURS = 24          # Tamamlanmış taskları 24 saat sonra sil
MAX_TASKS = 500              # Store'da en fazla bu kadar task tutulur
CLEANUP_EVERY_N_CREATE = 20  # Her N yeni task'ta cleanup çalıştır

_create_counter = 0


def _cleanup_old_tasks() -> int:
    """Eski veya fazla task'ları temizler. Silinen sayısını döner."""
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=TASK_TTL_HOURS)

    # 1) TTL: eski + tamamlanmış taskları sil
    to_delete = []
    for tid, t in _task_store.items():
        if t.get("status") in ("completed", "failed"):
            finished_str = t.get("finished_at")
            if finished_str:
                try:
                    finished_dt = datetime.fromisoformat(finished_str)
                    if finished_dt < cutoff:
                        to_delete.append(tid)
                except ValueError:
                    pass

    for tid in to_delete:
        _task_store.pop(tid, None)

    silinen = len(to_delete)

    # 2) Max size: hala fazlaysa en eskileri sil
    if len(_task_store) > MAX_TASKS:
        sorted_tasks = sorted(
            _task_store.items(),
            key=lambda kv: kv[1].get("started_at", ""),
        )
        fazla = len(_task_store) - MAX_TASKS
        for tid, _ in sorted_tasks[:fazla]:
            _task_store.pop(tid, None)
            silinen += 1

    return silinen


def _create_task(task_type: str) -> str:
    """Yeni bir görev kaydı oluşturur, task_id döner."""
    global _create_counter
    _create_counter += 1
    if _create_counter % CLEANUP_EVERY_N_CREATE == 0:
        _cleanup_old_tasks()

    task_id = str(uuid.uuid4())[:8]
    _task_store[task_id] = {
        "task_id": task_id,
        "type": task_type,
        "status": "running",
        "progress": 0,
        "message": "Görev başlatıldı...",
        "result": None,
        "error": None,
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }
    return task_id


def _update_task(task_id: str, **kwargs):
    """Görev durumunu günceller."""
    if task_id in _task_store:
        _task_store[task_id].update(kwargs)


def _finish_task(task_id: str, result: Any = None, error: str | None = None):
    """Görevi tamamlanmış olarak işaretle."""
    if task_id in _task_store:
        _task_store[task_id].update({
            "status": "failed" if error else "completed",
            "progress": 100 if not error else _task_store[task_id]["progress"],
            "result": result,
            "error": error,
            "finished_at": datetime.utcnow().isoformat(),
        })


# ═══════════════════════════════════════════════════════════════════
# BACKGROUND WORKER FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════

def _bg_train_waste_model(task_id: str, min_samples: int):
    """İsraf modelini arka planda eğitir."""
    from models import SessionLocal
    try:
        _update_task(task_id, progress=10, message="Veritabanı bağlantısı kuruluyor...")
        db = SessionLocal()
        try:
            _update_task(task_id, progress=20, message="Model eğitimi başlatılıyor...")
            from modules.waste_analyzer import train_waste_model_from_db
            result = train_waste_model_from_db(db=db, min_samples=min_samples)
            _update_task(task_id, progress=90, message="Model kaydediliyor...")
            _finish_task(task_id, result=result)
        finally:
            db.close()
    except Exception as e:
        _finish_task(task_id, error=f"{type(e).__name__}: {e}")


def _bg_train_sentiment_model(task_id: str):
    """Sentiment modelini arka planda eğitir."""
    from models import SessionLocal
    try:
        _update_task(task_id, progress=10, message="Veritabanı bağlantısı kuruluyor...")
        db = SessionLocal()
        try:
            _update_task(task_id, progress=20, message="TF-IDF model eğitimi başlatılıyor...")
            from modules.sentiment_analyzer import train_sentiment_model
            result = train_sentiment_model(db=db)
            _finish_task(task_id, result=result)
        finally:
            db.close()
    except Exception as e:
        _finish_task(task_id, error=f"{type(e).__name__}: {e}")


def _bg_train_menu_model(task_id: str):
    """Menü popülerlik modelini arka planda eğitir."""
    from models import SessionLocal
    try:
        _update_task(task_id, progress=10, message="Veritabanı bağlantısı kuruluyor...")
        db = SessionLocal()
        try:
            _update_task(task_id, progress=20, message="Menu model eğitimi başlatılıyor...")
            from modules.menu_optimizer import train_model
            result = train_model(db=db)
            _finish_task(task_id, result=result)
        finally:
            db.close()
    except Exception as e:
        _finish_task(task_id, error=f"{type(e).__name__}: {e}")


def _bg_generate_pdf(task_id: str, period: str):
    """PDF raporu arka planda üretir."""
    import os
    from models import SessionLocal
    try:
        _update_task(task_id, progress=10, message="Veritabanı sorgulanıyor...")
        db = SessionLocal()
        try:
            _update_task(task_id, progress=30, message="PDF oluşturuluyor...")
            from modules.pdf_report import generate_weekly_pdf, generate_monthly_pdf
            from datetime import date

            if period == "monthly":
                pdf_bytes = generate_monthly_pdf(db)
                filename = f"aylik_rapor_{date.today().strftime('%Y%m%d')}.pdf"
            else:
                pdf_bytes = generate_weekly_pdf(db)
                filename = f"haftalik_rapor_{date.today().strftime('%Y%m%d')}.pdf"

            # PDF'i geçici dosyaya kaydet
            os.makedirs("static/reports", exist_ok=True)
            filepath = os.path.join("static", "reports", filename)
            with open(filepath, "wb") as f:
                f.write(pdf_bytes)

            _finish_task(task_id, result={
                "filename": filename,
                "download_url": f"/static/reports/{filename}",
                "size_kb": round(len(pdf_bytes) / 1024, 1),
            })
        finally:
            db.close()
    except Exception as e:
        _finish_task(task_id, error=f"{type(e).__name__}: {e}")


# ═══════════════════════════════════════════════════════════════════
# API ENDPOINT'LERİ
# ═══════════════════════════════════════════════════════════════════

@router.post("/tasks/train-waste-model")
async def async_train_waste_model(
    background_tasks: BackgroundTasks,
    min_samples: int = Query(default=8, ge=4, le=10000),
):
    """İsraf modelini arka planda eğitir. Hemen task_id döner."""
    task_id = _create_task("train_waste_model")
    background_tasks.add_task(_bg_train_waste_model, task_id, min_samples)
    return {
        "success": True,
        "message": "İsraf model eğitimi arka planda başlatıldı.",
        "task_id": task_id,
        "status_url": f"/api/tasks/{task_id}",
    }


@router.post("/tasks/train-sentiment-model")
async def async_train_sentiment_model(background_tasks: BackgroundTasks):
    """Sentiment modelini arka planda eğitir."""
    task_id = _create_task("train_sentiment_model")
    background_tasks.add_task(_bg_train_sentiment_model, task_id)
    return {
        "success": True,
        "message": "Sentiment model eğitimi arka planda başlatıldı.",
        "task_id": task_id,
        "status_url": f"/api/tasks/{task_id}",
    }


@router.post("/tasks/train-menu-model")
async def async_train_menu_model(background_tasks: BackgroundTasks):
    """Menü popülerlik modelini arka planda eğitir."""
    task_id = _create_task("train_menu_model")
    background_tasks.add_task(_bg_train_menu_model, task_id)
    return {
        "success": True,
        "message": "Menü model eğitimi arka planda başlatıldı.",
        "task_id": task_id,
        "status_url": f"/api/tasks/{task_id}",
    }


@router.post("/tasks/generate-pdf")
async def async_generate_pdf(
    background_tasks: BackgroundTasks,
    period: str = Query(default="weekly", description="weekly veya monthly"),
):
    """PDF raporu arka planda üretir."""
    task_id = _create_task(f"generate_pdf_{period}")
    background_tasks.add_task(_bg_generate_pdf, task_id, period)
    return {
        "success": True,
        "message": f"{period} PDF raporu arka planda oluşturuluyor.",
        "task_id": task_id,
        "status_url": f"/api/tasks/{task_id}",
    }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Görev durumunu sorgular (polling)."""
    task = _task_store.get(task_id)
    if not task:
        return {"success": False, "message": f"Görev bulunamadı: {task_id}"}
    return {"success": True, **task}


@router.get("/tasks")
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
):
    """Son görevleri listeler."""
    tasks = sorted(
        _task_store.values(),
        key=lambda t: t["started_at"],
        reverse=True,
    )[:limit]
    return {
        "success": True,
        "tasks": tasks,
        "toplam": len(_task_store),
    }


@router.post("/tasks/cleanup")
async def cleanup_tasks():
    """Eski task kayıtlarını manuel olarak temizler."""
    silinen = _cleanup_old_tasks()
    return {
        "success": True,
        "silinen": silinen,
        "kalan": len(_task_store),
        "ttl_hours": TASK_TTL_HOURS,
        "max_tasks": MAX_TASKS,
    }
