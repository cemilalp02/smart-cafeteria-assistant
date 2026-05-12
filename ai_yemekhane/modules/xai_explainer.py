"""
Explainable AI (XAI) modülü — SHAP tabanlı model açıklamaları.

Fonksiyonlar:
  - get_global_explanation()  → Tüm feature'ların genel önem sıralaması
  - get_single_explanation()  → Tek bir yemek tahmini için SHAP açıklaması
"""

import logging
import os
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# SHAP opsiyonel
try:
    import shap
    _HAS_SHAP = True
except ImportError:
    _HAS_SHAP = False
    logger.info("SHAP kütüphanesi bulunamadı. XAI açıklamaları devre dışı.")

from modules.waste_analyzer import (
    load_waste_model,
    WASTE_FEATURE_COLUMNS,
    _get_mevsim,
    _get_gun_tipi,
    _get_ogrenci_katilim_tahmini,
    _canonicalize_meal_name,
    _build_training_dataframe,
    SessionLocal,
)

# Feature Türkçe etiketleri (admin dashboard için)
FEATURE_LABELS = {
    "yemek_adi": "Yemek Adı",
    "kategori": "Kategori",
    "gun_hafta": "Haftanın Günü",
    "ay": "Ay",
    "uretilen_porsiyon": "Üretilen Porsiyon",
    "rating_avg": "Ortalama Puan",
    "rating_count": "Toplam Oy Sayısı",
    "onceki_hafta_israf": "Önceki Hafta İsrafı",
    "populerlik_skoru": "Popülerlik Skoru",
    "mevsim": "Mevsim",
    "hafta_ici_mi": "Hafta İçi mi",
    "son_3_gun_ort_israf": "Son 3 Gün Ort. İsraf",
    "kategori_ort_israf": "Kategori Ort. İsraf",
    "rating_std": "Puan Std. Sapma",
    "menu_cesitlilik": "Menü Çeşitlilik",
    "ogrenci_sayisi_tahmini": "Öğrenci Katılım Tahmini",
    "menu_cekiciligi": "Menü Çekiciliği",
    "gun_tipi": "Gün Tipi",
    "onceki_gun_israf": "Önceki Gün İsrafı",
    "self_report_avg": "Self-Report Ortalaması",
}


def _get_shap_explainer(pipeline, X_sample: pd.DataFrame):
    """
    Pipeline için SHAP Explainer oluşturur.
    TreeExplainer (hızlı) → fallback: KernelExplainer.
    """
    preprocessor = pipeline.named_steps["preprocessor"]
    regressor = pipeline.named_steps["regressor"]

    X_transformed = preprocessor.transform(X_sample)
    if hasattr(X_transformed, "toarray"):
        X_transformed = X_transformed.toarray()

    # Ensemble'ın alt modellerinden birini kullan (TreeExplainer daha hızlı)
    sub_model = None
    if hasattr(regressor, "estimators_"):
        for est in regressor.estimators_:
            if hasattr(est, "feature_importances_"):
                sub_model = est
                break

    if sub_model is not None:
        try:
            explainer = shap.TreeExplainer(sub_model)
            return explainer, X_transformed
        except Exception:
            pass

    # Fallback: KernelExplainer
    bg_size = min(50, X_transformed.shape[0])
    bg_data = shap.kmeans(X_transformed, bg_size)
    explainer = shap.KernelExplainer(regressor.predict, bg_data)
    return explainer, X_transformed


def _get_transformed_feature_names(pipeline) -> list[str]:
    """Pipeline'ın preprocessor'undan feature isimlerini çıkarır."""
    preprocessor = pipeline.named_steps["preprocessor"]
    try:
        # Doğrudan preprocessor'un çıktı isimlerini al — en güvenilir yol
        return list(preprocessor.get_feature_names_out())
    except Exception:
        pass
    # Fallback: manuel hesapla
    try:
        ohe = preprocessor.named_transformers_["cat"]
        cat_names = list(ohe.get_feature_names_out())
    except Exception:
        cat_names = []
    num_names = [c for c in WASTE_FEATURE_COLUMNS if c not in ("yemek_adi", "kategori")]
    return cat_names + num_names


def _consolidate_shap_values(
    shap_vals: np.ndarray,
    feature_names: list[str],
) -> dict[str, float]:
    """
    OHE genişletilmiş SHAP değerlerini orijinal feature'lara geri toplar.
    Preprocessor prefix'lerini (cat__, num__) temizler.
    """
    consolidated: dict[str, float] = {}
    for i, fname in enumerate(feature_names):
        # Prefix temizle: num__rating_avg → rating_avg, cat__yemek_adi_X → yemek_adi
        clean = fname
        if clean.startswith("num__"):
            clean = clean[5:]
        elif clean.startswith("cat__"):
            clean = clean[5:]
            # OHE: cat__yemek_adi_Mercimek → yemek_adi
            for col in ("yemek_adi", "kategori"):
                if clean.startswith(col + "_") or clean == col:
                    clean = col
                    break
        consolidated[clean] = consolidated.get(clean, 0.0) + float(shap_vals[i])
    return consolidated


def get_global_explanation(max_features: int = 15) -> dict[str, Any]:
    """
    SHAP ile global feature importance hesaplar.
    Model yoksa veya SHAP yoksa mevcut feature_importance'a fallback yapar.
    """
    model_bundle = load_waste_model()
    if model_bundle is None:
        return {"success": False, "error": "Model yüklü değil. Önce modeli eğitin."}

    # 1) Mevcut feature importance (her zaman döndür — hızlı)
    existing_importance = model_bundle.get("feature_importance", [])

    # Türkçe etiket ekle
    for item in existing_importance:
        item["label"] = FEATURE_LABELS.get(item["feature"], item["feature"])

    result = {
        "success": True,
        "model_type": model_bundle.get("model_type", "Bilinmiyor"),
        "trained_at": model_bundle.get("trained_at"),
        "sample_count": model_bundle.get("sample_count", 0),
        "feature_importance": existing_importance[:max_features],
        "shap_available": _HAS_SHAP,
        "shap_global": None,
    }

    # 2) SHAP global (varsa)
    if _HAS_SHAP:
        try:
            pipeline = model_bundle["pipeline"]
            db = SessionLocal()
            try:
                df = _build_training_dataframe(db)
            finally:
                db.close()

            if df.empty or len(df) < 5:
                result["shap_error"] = "Yeterli eğitim verisi yok."
                return result

            X = df[WASTE_FEATURE_COLUMNS]
            # Performans için max 100 örnek
            sample_size = min(100, len(X))
            X_sample = X.sample(n=sample_size, random_state=42)

            explainer, X_transformed = _get_shap_explainer(pipeline, X_sample)
            feature_names = _get_transformed_feature_names(pipeline)

            # SHAP değerlerini hesapla (tüm örnekler üzerinden)
            shap_values = explainer.shap_values(X_transformed)

            # Ortalama mutlak SHAP
            mean_abs_shap = np.abs(shap_values).mean(axis=0)

            # Orijinal feature'lara geri topla
            consolidated = _consolidate_shap_values(mean_abs_shap, feature_names)

            # Sırala ve normalize et
            total = sum(abs(v) for v in consolidated.values()) or 1.0
            shap_global = [
                {
                    "feature": k,
                    "label": FEATURE_LABELS.get(k, k),
                    "shap_importance": round(abs(v) / total, 4),
                    "shap_raw": round(float(v), 6),
                }
                for k, v in consolidated.items()
            ]
            shap_global.sort(key=lambda x: x["shap_importance"], reverse=True)
            result["shap_global"] = shap_global[:max_features]

        except Exception as e:
            logger.warning("SHAP global açıklama hatası: %s", e)
            result["shap_error"] = str(e)

    return result


def get_single_explanation(
    yemek_adi: str,
    kategori: str,
    tarih: Optional[date] = None,
    uretilen_porsiyon: float = 100.0,
    rating_avg: float = 3.0,
    rating_count: int = 10,
) -> dict[str, Any]:
    """
    Tek bir yemek için SHAP açıklaması — "Bu tahmini ne etkiliyor?"
    """
    model_bundle = load_waste_model()
    if model_bundle is None:
        return {"success": False, "error": "Model yüklü değil."}

    if not _HAS_SHAP:
        return {"success": False, "error": "SHAP kütüphanesi yüklü değil. pip install shap"}

    if tarih is None:
        tarih = date.today()

    pipeline = model_bundle["pipeline"]

    # Eğitim verisini arka plan olarak kullan
    db = SessionLocal()
    try:
        df = _build_training_dataframe(db)
    finally:
        db.close()

    if df.empty or len(df) < 5:
        return {"success": False, "error": "Yeterli eğitim verisi yok."}

    X_train = df[WASTE_FEATURE_COLUMNS]
    sample_size = min(50, len(X_train))
    X_bg = X_train.sample(n=sample_size, random_state=42)

    # Tahmin satırını oluştur
    mevsim = _get_mevsim(tarih)
    hafta_ici = 1 if tarih.weekday() < 5 else 0

    row_data = {
        "yemek_adi": _canonicalize_meal_name(yemek_adi) or yemek_adi,
        "kategori": kategori or "diger",
        "gun_hafta": int(tarih.weekday()),
        "ay": int(tarih.month),
        "uretilen_porsiyon": float(uretilen_porsiyon),
        "rating_avg": float(rating_avg),
        "rating_count": int(rating_count),
        "onceki_hafta_israf": -1.0,
        "populerlik_skoru": 0.5,
        "mevsim": mevsim,
        "hafta_ici_mi": hafta_ici,
        "son_3_gun_ort_israf": -1.0,
        "kategori_ort_israf": 20.0,
        "rating_std": 0.0,
        "menu_cesitlilik": 5,
        "ogrenci_sayisi_tahmini": _get_ogrenci_katilim_tahmini(tarih),
        "menu_cekiciligi": 0.5,
        "gun_tipi": _get_gun_tipi(tarih),
        "onceki_gun_israf": -1.0,
        "self_report_avg": -1.0,
    }

    # DB'den gerçek değerleri çek
    try:
        from modules.menu_optimizer import YEMEK_BAZI_POPULERLIK
        row_data["populerlik_skoru"] = YEMEK_BAZI_POPULERLIK.get(
            row_data["yemek_adi"], 0.5
        )
    except ImportError:
        pass

    try:
        db2 = SessionLocal()
        from sqlalchemy import func as sqla_func
        from models import UretimLog, MenuPuanlama

        # Son 3 gün israf ortalaması
        uc_gun = tarih - timedelta(days=3)
        s3 = db2.query(sqla_func.avg(UretimLog.israf_orani)).filter(
            UretimLog.tarih >= uc_gun, UretimLog.tarih < tarih,
            UretimLog.israf_orani.isnot(None),
        ).scalar()
        if s3 is not None:
            row_data["son_3_gun_ort_israf"] = float(s3)

        # Kategori ort israf
        ko = db2.query(sqla_func.avg(UretimLog.israf_orani)).filter(
            UretimLog.kategori == kategori, UretimLog.israf_orani.isnot(None),
        ).scalar()
        if ko is not None:
            row_data["kategori_ort_israf"] = float(ko)

        # Önceki hafta israf
        prev = db2.query(UretimLog).filter(
            UretimLog.yemek_adi.ilike(f"%{yemek_adi}%"),
            UretimLog.tarih == tarih - timedelta(days=7),
            UretimLog.israf_orani.isnot(None),
        ).first()
        if prev and prev.israf_orani is not None:
            row_data["onceki_hafta_israf"] = float(prev.israf_orani)

        # Önceki gün israf
        lag1 = db2.query(sqla_func.avg(UretimLog.israf_orani)).filter(
            UretimLog.tarih == tarih - timedelta(days=1),
            UretimLog.israf_orani.isnot(None),
        ).scalar()
        if lag1 is not None:
            row_data["onceki_gun_israf"] = float(lag1)

        # Self-report
        sr = db2.query(sqla_func.avg(MenuPuanlama.israf_self_report)).filter(
            MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
            MenuPuanlama.israf_self_report.isnot(None),
        ).scalar()
        if sr is not None:
            row_data["self_report_avg"] = float(sr)

        db2.close()
    except Exception:
        pass

    X_single = pd.DataFrame([row_data])

    try:
        preprocessor = pipeline.named_steps["preprocessor"]
        regressor = pipeline.named_steps["regressor"]
        feature_names = _get_transformed_feature_names(pipeline)

        # Tek tahmin transform
        X_single_transformed = preprocessor.transform(X_single)
        if hasattr(X_single_transformed, "toarray"):
            X_single_transformed = X_single_transformed.toarray()

        # Tahmin değeri
        prediction = float(pipeline.predict(X_single)[0])

        # TreeExplainer (hızlı) kullan
        sub_model = None
        if hasattr(regressor, "estimators_"):
            for est in regressor.estimators_:
                if hasattr(est, "feature_importances_"):
                    sub_model = est
                    break

        if sub_model is not None:
            explainer = shap.TreeExplainer(sub_model)
        else:
            X_bg_transformed = preprocessor.transform(X_bg)
            if hasattr(X_bg_transformed, "toarray"):
                X_bg_transformed = X_bg_transformed.toarray()
            bg_data = shap.kmeans(X_bg_transformed, min(30, len(X_bg_transformed)))
            explainer = shap.KernelExplainer(regressor.predict, bg_data)

        # SHAP değerleri
        shap_values = explainer.shap_values(X_single_transformed)
        sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values

        # Orijinal feature'lara geri topla
        consolidated = _consolidate_shap_values(sv, feature_names)

        # Sırala (mutlak değere göre)
        explanations = []
        for feat, val in consolidated.items():
            direction = "artırıyor" if val > 0 else "azaltıyor"
            abs_val = abs(val)
            explanations.append({
                "feature": feat,
                "label": FEATURE_LABELS.get(feat, feat),
                "shap_value": round(float(val), 4),
                "abs_shap": round(abs_val, 4),
                "direction": direction,
                "input_value": row_data.get(feat, "—"),
            })
        explanations.sort(key=lambda x: x["abs_shap"], reverse=True)

        # Özet metin oluştur
        top3 = explanations[:3]
        summary_parts = []
        for e in top3:
            summary_parts.append(
                f"{e['label']} tahmini {e['direction']} (etki: {e['abs_shap']:.2f})"
            )
        summary = f"{yemek_adi} için israf tahmini: %{prediction:.1f}. " + "; ".join(summary_parts) + "."

        return {
            "success": True,
            "yemek_adi": yemek_adi,
            "kategori": kategori,
            "tarih": tarih.isoformat(),
            "prediction": round(prediction, 2),
            "base_value": round(float(explainer.expected_value), 2),
            "explanations": explanations[:12],
            "summary": summary,
            "input_values": row_data,
        }

    except Exception as e:
        logger.warning("SHAP tek tahmin açıklama hatası: %s", e)
        return {"success": False, "error": str(e)}


def get_xai_status() -> dict[str, Any]:
    """XAI modülünün durumunu döndürür."""
    model_bundle = load_waste_model()
    return {
        "shap_installed": _HAS_SHAP,
        "model_loaded": model_bundle is not None,
        "model_type": (model_bundle or {}).get("model_type"),
        "sample_count": (model_bundle or {}).get("sample_count", 0),
        "feature_count": len(WASTE_FEATURE_COLUMNS),
        "has_importance": bool((model_bundle or {}).get("feature_importance")),
    }
