"""
Model Performans Tracking
═══════════════════════════════════════════════════════════════

Her model eğitiminde metrikleri (MAE, RMSE, R², F1, accuracy)
JSON dosyasına kaydeder. Metrik geçmişi API ile sorgulanabilir.
Performans degradation tespiti yapar.

Kullanım:
    from modules.model_tracker import log_metrics, get_metrics_history, get_latest_metrics
    log_metrics("waste", {"mae": 5.2, "rmse": 7.1, "r2": 0.85})
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models_data")
METRICS_FILE = os.path.join(MODELS_DIR, "model_metrics.json")


# ═══════════════════════════════════════════════════════════════════
# METRICS STORE
# ═══════════════════════════════════════════════════════════════════

def _load_metrics() -> list[dict]:
    """Metrik geçmişini dosyadan okur."""
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_metrics(data: list[dict]):
    """Metrik geçmişini dosyaya yazar."""
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════
# ANA FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def log_metrics(
    model_name: str,
    metrics: dict[str, float],
    extra: dict[str, Any] | None = None,
) -> dict:
    """
    Bir model eğitimi sonrası metrikleri kaydeder.

    Args:
        model_name: "waste" | "menu" | "sentiment"
        metrics: {"mae": 5.2, "rmse": 7.1, "r2": 0.85, ...}
        extra: Opsiyonel ek bilgi (sample_count, duration vb.)

    Returns:
        Kaydedilen entry dict
    """
    history = _load_metrics()

    entry = {
        "model": model_name,
        "trained_at": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "extra": extra or {},
    }

    history.append(entry)

    # Son 100 kayıt tut (dosya çok büyümesin)
    if len(history) > 100:
        history = history[-100:]

    _save_metrics(history)
    logger.info("[ModelTracker] %s metrikleri kaydedildi: %s", model_name, metrics)
    return entry


def get_metrics_history(
    model_name: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Metrik geçmişini döndürür.

    Args:
        model_name: None ise tüm modeller, aksi halde filtrelenir.
        limit: Son N kayıt.
    """
    history = _load_metrics()

    if model_name:
        history = [h for h in history if h.get("model") == model_name]

    return list(reversed(history[-limit:]))


def get_latest_metrics() -> list[dict]:
    """Her model için en son metrik kaydını döndürür."""
    history = _load_metrics()

    latest: dict[str, dict] = {}
    for entry in history:
        model = entry.get("model", "unknown")
        latest[model] = entry  # Son gelen kazanır

    return list(latest.values())


def check_degradation(model_name: str, threshold: float = 0.1) -> dict:
    """
    Son iki eğitim arasında performans düşüşü var mı kontrol eder.

    Karşılaştırma metriği:
      - r2 için: yeni < eski - threshold → degradation
      - mae/rmse için: yeni > eski * (1 + threshold) → degradation

    Returns:
        {"degraded": bool, "details": {...}}
    """
    history = _load_metrics()
    model_history = [h for h in history if h.get("model") == model_name]

    if len(model_history) < 2:
        return {
            "degraded": False,
            "message": "Karşılaştırma için yeterli geçmiş yok (en az 2 eğitim gerekli).",
            "model": model_name,
        }

    prev = model_history[-2]["metrics"]
    curr = model_history[-1]["metrics"]

    alerts = []

    # R² düşüşü
    if "r2" in prev and "r2" in curr:
        if curr["r2"] < prev["r2"] - threshold:
            alerts.append(
                f"R² düştü: {prev['r2']:.4f} → {curr['r2']:.4f} (fark: {curr['r2'] - prev['r2']:.4f})"
            )

    # MAE artışı
    if "mae" in prev and "mae" in curr:
        if prev["mae"] > 0 and curr["mae"] > prev["mae"] * (1 + threshold):
            alerts.append(
                f"MAE arttı: {prev['mae']:.4f} → {curr['mae']:.4f}"
            )

    # RMSE artışı
    if "rmse" in prev and "rmse" in curr:
        if prev["rmse"] > 0 and curr["rmse"] > prev["rmse"] * (1 + threshold):
            alerts.append(
                f"RMSE arttı: {prev['rmse']:.4f} → {curr['rmse']:.4f}"
            )

    # Accuracy düşüşü
    if "accuracy" in prev and "accuracy" in curr:
        if curr["accuracy"] < prev["accuracy"] - threshold:
            alerts.append(
                f"Accuracy düştü: {prev['accuracy']:.4f} → {curr['accuracy']:.4f}"
            )

    # F1 düşüşü
    if "f1" in prev and "f1" in curr:
        if curr["f1"] < prev["f1"] - threshold:
            alerts.append(
                f"F1 düştü: {prev['f1']:.4f} → {curr['f1']:.4f}"
            )

    return {
        "degraded": len(alerts) > 0,
        "model": model_name,
        "alerts": alerts,
        "previous": prev,
        "current": curr,
        "trained_at_prev": model_history[-2].get("trained_at"),
        "trained_at_curr": model_history[-1].get("trained_at"),
    }
