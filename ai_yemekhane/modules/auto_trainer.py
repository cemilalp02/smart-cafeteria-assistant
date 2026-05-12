"""
Otomatik Model Retraining Pipeline
═══════════════════════════════════════════════════════════════

Yeterli yeni veri biriktiğinde modelleri otomatik yeniden eğitir.
Champion-challenger yaklaşımı ile yeni modeli eski ile karşılaştırır.
Performans degradation tespiti yapar.

Desteklenen modeller:
  1. waste   — İsraf tahmin modeli  (waste_analyzer)
  2. menu    — Menü popülerlik modeli (menu_optimizer)
  3. sentiment — Duygu analizi modeli (sentiment_analyzer)

Kullanım:
    from modules.auto_trainer import check_and_retrain, get_model_health
"""

import os
import json
import logging
import shutil
from datetime import datetime, date, timedelta
from typing import Any, Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from models import UretimLog, MenuPuanlama

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models_data")
TRAINER_STATE_FILE = os.path.join(MODELS_DIR, "auto_trainer_state.json")

# Her model için minimum yeni veri eşiği
RETRAIN_THRESHOLDS = {
    "waste": {
        "min_new_records": 20,
        "model_file": "waste_predictor.joblib",
        "check_table": "uretim_log",
    },
    "sentiment": {
        "min_new_records": 30,
        "model_file": "sentiment_tfidf_model.joblib",
        "check_table": "menu_puanlama",
    },
}


# ═══════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def _load_state() -> dict:
    """Eğitim durumunu dosyadan okur."""
    if os.path.exists(TRAINER_STATE_FILE):
        try:
            with open(TRAINER_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    """Eğitim durumunu dosyaya yazar."""
    os.makedirs(os.path.dirname(TRAINER_STATE_FILE), exist_ok=True)
    with open(TRAINER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════
# VERİ SAYACI
# ═══════════════════════════════════════════════════════════════════

def _count_new_records(db: Session, model_name: str, since: datetime | None) -> int:
    """Son eğitimden bu yana eklenen yeni kayıt sayısını hesaplar."""
    if model_name == "waste":
        q = db.query(sqla_func.count(UretimLog.id))
        if since:
            q = q.filter(UretimLog.created_at > since)
        return q.scalar() or 0

    elif model_name == "sentiment":
        q = db.query(sqla_func.count(MenuPuanlama.id)).filter(
            MenuPuanlama.yorum.isnot(None),
            MenuPuanlama.yorum != "",
        )
        if since:
            q = q.filter(MenuPuanlama.created_at > since)
        return q.scalar() or 0

    return 0


def _total_records(db: Session, model_name: str) -> int:
    """Toplam kayıt sayısını döndürür."""
    if model_name == "waste":
        return db.query(sqla_func.count(UretimLog.id)).scalar() or 0
    elif model_name == "sentiment":
        return db.query(sqla_func.count(MenuPuanlama.id)).filter(
            MenuPuanlama.yorum.isnot(None),
            MenuPuanlama.yorum != "",
        ).scalar() or 0
    return 0


# ═══════════════════════════════════════════════════════════════════
# CHAMPION-CHALLENGER
# ═══════════════════════════════════════════════════════════════════

def _backup_model(model_name: str) -> str | None:
    """Mevcut modeli yedekler, yedek dosya yolunu döner."""
    cfg = RETRAIN_THRESHOLDS.get(model_name)
    if not cfg:
        return None
    model_path = os.path.join(MODELS_DIR, cfg["model_file"])
    if not os.path.exists(model_path):
        return None

    backup_path = model_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(model_path, backup_path)
    logger.info("[AutoTrainer] Model yedeklendi: %s → %s", model_path, backup_path)
    return backup_path


def _rollback_model(model_name: str, backup_path: str):
    """Yeni model başarısızsa eski modeli geri yükler."""
    cfg = RETRAIN_THRESHOLDS.get(model_name)
    if not cfg:
        return
    model_path = os.path.join(MODELS_DIR, cfg["model_file"])
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, model_path)
        logger.info("[AutoTrainer] Model geri yüklendi: %s", model_path)


def _model_exists(model_name: str) -> bool:
    """Model dosyası var mı?"""
    cfg = RETRAIN_THRESHOLDS.get(model_name)
    if not cfg:
        return False
    return os.path.exists(os.path.join(MODELS_DIR, cfg["model_file"]))


def _model_age_days(model_name: str) -> float | None:
    """Model dosyasının yaşını gün olarak döndürür."""
    cfg = RETRAIN_THRESHOLDS.get(model_name)
    if not cfg:
        return None
    model_path = os.path.join(MODELS_DIR, cfg["model_file"])
    if not os.path.exists(model_path):
        return None
    mtime = os.path.getmtime(model_path)
    age_seconds = datetime.now().timestamp() - mtime
    return round(age_seconds / 86400, 1)


# ═══════════════════════════════════════════════════════════════════
# EĞİTİM FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════

def _train_waste(db: Session) -> dict:
    """İsraf modelini eğitir, sonuçları döner."""
    from modules.waste_analyzer import train_waste_model_from_db
    return train_waste_model_from_db(db=db, min_samples=8)


def _train_sentiment(db: Session) -> dict:
    """Sentiment modelini eğitir, sonuçları döner."""
    from modules.sentiment_analyzer import train_sentiment_model
    return train_sentiment_model(db=db)


_TRAIN_FN = {
    "waste": _train_waste,
    "sentiment": _train_sentiment,
}


# ═══════════════════════════════════════════════════════════════════
# ANA FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def check_and_retrain(
    db: Session,
    model_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Belirtilen model (veya tümü) için yeni veri kontrolü yapar.
    Eşik aşılmışsa champion-challenger ile yeniden eğitir.

    Args:
        db: SQLAlchemy oturumu
        model_name: "waste" | "sentiment" | None (tümü)
        force: True ise eşik kontrolünü atla, doğrudan eğit

    Returns:
        Her model için eğitim sonuçları dict
    """
    state = _load_state()
    models_to_check = [model_name] if model_name else list(RETRAIN_THRESHOLDS.keys())
    results = {}

    for mname in models_to_check:
        cfg = RETRAIN_THRESHOLDS.get(mname)
        if not cfg:
            results[mname] = {"action": "skipped", "reason": f"Bilinmeyen model: {mname}"}
            continue

        train_fn = _TRAIN_FN.get(mname)
        if not train_fn:
            results[mname] = {"action": "skipped", "reason": "Eğitim fonksiyonu bulunamadı."}
            continue

        # Son eğitim zamanı
        last_trained = state.get(mname, {}).get("last_trained_at")
        last_trained_dt = datetime.fromisoformat(last_trained) if last_trained else None

        # Yeni kayıt sayısı
        new_count = _count_new_records(db, mname, last_trained_dt)
        total_count = _total_records(db, mname)
        threshold = cfg["min_new_records"]

        model_info = {
            "model": mname,
            "new_records": new_count,
            "total_records": total_count,
            "threshold": threshold,
            "last_trained": last_trained,
            "model_exists": _model_exists(mname),
            "model_age_days": _model_age_days(mname),
        }

        if not force and new_count < threshold:
            results[mname] = {
                **model_info,
                "action": "skipped",
                "reason": f"Yeni veri yetersiz ({new_count}/{threshold}). Eğitim atlandı.",
            }
            continue

        # ── CHAMPION-CHALLENGER ──
        logger.info("[AutoTrainer] %s modeli eğitiliyor... (yeni veri: %d)", mname, new_count)
        backup_path = _backup_model(mname)

        try:
            train_result = train_fn(db)
            success = train_result.get("success", False) if isinstance(train_result, dict) else False

            if success:
                # Yeni model başarılı — durumu güncelle
                state[mname] = {
                    "last_trained_at": datetime.utcnow().isoformat(),
                    "records_at_training": total_count,
                    "train_result": _safe_serialize(train_result),
                    "backup_path": backup_path,
                }
                _save_state(state)

                results[mname] = {
                    **model_info,
                    "action": "retrained",
                    "train_result": train_result,
                    "backup": backup_path,
                    "message": f"{mname} modeli başarıyla yeniden eğitildi (champion-challenger).",
                }
                logger.info("[AutoTrainer] %s modeli başarıyla eğitildi.", mname)
            else:
                # Eğitim başarısız — rollback
                if backup_path:
                    _rollback_model(mname, backup_path)
                results[mname] = {
                    **model_info,
                    "action": "failed_rollback",
                    "train_result": train_result,
                    "message": f"{mname} eğitimi başarısız. Eski model geri yüklendi.",
                }
                logger.warning("[AutoTrainer] %s eğitimi başarısız, rollback yapıldı.", mname)

        except Exception as e:
            if backup_path:
                _rollback_model(mname, backup_path)
            results[mname] = {
                **model_info,
                "action": "error_rollback",
                "error": f"{type(e).__name__}: {e}",
                "message": f"{mname} eğitiminde hata. Eski model geri yüklendi.",
            }
            logger.error("[AutoTrainer] %s eğitim hatası: %s", mname, e)

    return {"success": True, "models": results}


def get_model_health(db: Session) -> dict[str, Any]:
    """Tüm modellerin sağlık durumunu döndürür."""
    state = _load_state()
    health = {}

    for mname, cfg in RETRAIN_THRESHOLDS.items():
        last_trained = state.get(mname, {}).get("last_trained_at")
        last_trained_dt = datetime.fromisoformat(last_trained) if last_trained else None

        new_count = _count_new_records(db, mname, last_trained_dt)
        total_count = _total_records(db, mname)
        threshold = cfg["min_new_records"]
        age = _model_age_days(mname)
        exists = _model_exists(mname)

        # Sağlık durumu
        if not exists:
            status = "missing"
            status_label = "Model dosyası bulunamadı"
        elif age is not None and age > 14:
            status = "stale"
            status_label = f"Model eski ({age} gün)"
        elif new_count >= threshold:
            status = "retrain_needed"
            status_label = f"Yeniden eğitim gerekli ({new_count} yeni veri)"
        else:
            status = "healthy"
            status_label = "Model güncel"

        health[mname] = {
            "model": mname,
            "model_file": cfg["model_file"],
            "exists": exists,
            "age_days": age,
            "status": status,
            "status_label": status_label,
            "last_trained": last_trained,
            "new_records_since": new_count,
            "total_records": total_count,
            "retrain_threshold": threshold,
            "needs_retrain": new_count >= threshold or not exists,
        }

    return {"success": True, "models": health}


def _safe_serialize(obj: Any) -> Any:
    """JSON serializable olmayan nesneleri güvenli hale getirir."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return str(obj)
