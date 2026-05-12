"""
AI Akilli Yemekhane Asistan Sistemi - Israf Analizi Modulu

Bu modul iki sekilde calisir:
1) Egitilmis israf modeli varsa: puan + uretim sinyallerinden ML tahmini
2) Model yoksa: kural tabanli fallback (puan -> israf)

Not: ML modeli gercek hedef olarak UretimLog.israf_orani kullanir.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

try:
    from xgboost import XGBRegressor
    _HAS_XGBOOST = True
except ImportError:
    _HAS_XGBOOST = False

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    _HAS_OPTUNA = True
except ImportError:
    _HAS_OPTUNA = False

from models import MenuPuanlama, SessionLocal, UretimLog

logger = logging.getLogger(__name__)

# -------------------- Kural tabanli fallback --------------------
ISRAF_MAP = {
    1: 80,  # Puan 1 -> %80 israf
    2: 65,  # Puan 2 -> %65 israf
    3: 35,  # Puan 3 -> %35 israf
    4: 12,  # Puan 4 -> %12 israf
    5: 5,   # Puan 5 -> %5 israf
}


def puan_to_israf_orani(puan: float) -> float:
    """Puani tahmini israf oranina (%0-100) donusturur."""
    if puan <= 1:
        return 80.0
    if puan <= 2:
        return 65.0 + (2 - puan) * 15  # 65-80
    if puan <= 3:
        return 35.0 + (3 - puan) * 30  # 35-65
    if puan <= 4:
        return 12.0 + (4 - puan) * 23  # 12-35
    return max(0.0, 5.0 + (5 - puan) * 7)  # 0-12


# -------------------- ML model sabitleri --------------------
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models_data")
WASTE_MODEL_PATH = os.path.join(MODEL_DIR, "waste_predictor.joblib")
WASTE_METRICS_PATH = os.path.join(MODEL_DIR, "waste_metrics.json")
WASTE_FEATURE_COLUMNS = [
    "yemek_adi",
    "kategori",
    "gun_hafta",
    "ay",
    "uretilen_porsiyon",
    "rating_avg",
    "rating_count",
    "onceki_hafta_israf",
    "populerlik_skoru",
    # ── Mevcut Ek Feature'lar ──
    "mevsim",              # 0=kış, 1=ilkbahar, 2=yaz, 3=sonbahar
    "hafta_ici_mi",        # 1=hafta içi, 0=hafta sonu
    "son_3_gun_ort_israf", # Son 3 günün genel israf ortalaması
    "kategori_ort_israf",  # Bu kategorinin genel ortalama israfı
    "rating_std",          # Puanlama standart sapması
    "menu_cesitlilik",     # O gün menüde kaç farklı yemek var
    # ── Plan 1.2 Yeni Feature'lar ──
    "ogrenci_sayisi_tahmini",  # Akademik takvime göre tahmini katılım (0-1)
    "menu_cekiciligi",     # O günkü menünün ortalama popülerlik skoru
    "gun_tipi",            # 0=normal, 1=hafta sonu, 2=tatil/sınav haftası
    "onceki_gun_israf",    # Lag-1 — bir önceki günün genel israf ortalaması
    # ── Self-Report Feature ──
    "self_report_avg",     # Öğrenci israf self-report ortalaması (0-3, -1=veri yok)
]

# ── Akademik takvim tahmini katılım oranları ──
_GUN_TIPI_KATILIM = {
    0: 1.0,   # Normal gün
    1: 0.3,   # Hafta sonu
    2: 0.5,   # Tatil / sınav haftası
}

WASTE_IMPORTANCE_PATH = os.path.join(MODEL_DIR, "waste_feature_importance.json")
DEFAULT_RATING_AVG = 3.0
DEFAULT_PRODUCTION = 100.0
MIN_TRAIN_SAMPLES = 8

_cached_waste_model: dict[str, Any] | None = None


def _clip_israf(score: float | None) -> float | None:
    if score is None:
        return None
    return max(0.0, min(100.0, float(score)))


def _waste_level(score: float | None) -> str:
    if score is None:
        return "Veri yok"
    if score >= 50:
        return "Yuksek"
    if score >= 25:
        return "Orta"
    return "Dusuk"


def _canonicalize_meal_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", (name or "").strip())
    return normalized.title()


def _meal_group_key(name: str) -> str:
    normalized = re.sub(r"\s+", " ", (name or "").strip())
    return normalized.casefold()


# -------------------- Yeni Feature Hesaplama Yardımcıları --------------------

_MEVSIM_NUM = {1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3, 12: 0}

# Türkiye resmi tatil günleri (ay, gün) — yaygın olanlar
_RESMI_TATILLER: set[tuple[int, int]] = {
    (1, 1), (4, 23), (5, 1), (5, 19), (7, 15), (8, 30), (10, 29),
}

# Üniversite sınav haftaları (yaklaşık): Ocak 2. yarı, Haziran 1. yarı
_SINAV_HAFTALARI: list[tuple[int, int, int]] = [
    (1, 13, 31),   # Ocak 13–31 final
    (6, 1, 15),    # Haziran 1–15 final
]


def _get_mevsim(tarih: date) -> int:
    return _MEVSIM_NUM.get(tarih.month, 0)


def _get_gun_tipi(tarih: date) -> int:
    """0=normal, 1=hafta sonu, 2=tatil/sınav haftası"""
    if (tarih.month, tarih.day) in _RESMI_TATILLER:
        return 2
    for ay, gun_bas, gun_son in _SINAV_HAFTALARI:
        if tarih.month == ay and gun_bas <= tarih.day <= gun_son:
            return 2
    if tarih.weekday() >= 5:
        return 1
    return 0


def _get_ogrenci_katilim_tahmini(tarih: date) -> float:
    """Akademik takvime göre 0-1 arası tahmini katılım oranı."""
    gun_tipi = _get_gun_tipi(tarih)
    baz = _GUN_TIPI_KATILIM.get(gun_tipi, 1.0)
    # Yaz aylarında (Temmuz-Ağustos) düşük katılım
    if tarih.month in (7, 8):
        baz *= 0.4
    return round(baz, 2)


def _build_rating_maps(
    db: Session,
) -> tuple[dict[tuple[date, str], dict[str, float]], dict[str, dict[str, float]]]:
    """
    Puanlamayi iki seviyede mapler:
    - (tarih, yemek_key) -> gunluk ortalama puan / oy
    - yemek_key -> tum zaman ortalama puan / oy
    """
    rows = (
        db.query(
            MenuPuanlama.tarih,
            MenuPuanlama.yemek_adi,
            sqla_func.avg(MenuPuanlama.puan).label("ort_puan"),
            sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .group_by(MenuPuanlama.tarih, MenuPuanlama.yemek_adi)
        .all()
    )

    day_map: dict[tuple[date, str], dict[str, float]] = {}
    meal_acc: dict[str, dict[str, float]] = {}

    for row in rows:
        key = _meal_group_key(row.yemek_adi)
        oy = int(row.toplam_oy or 0)
        ort = float(row.ort_puan or 0.0)

        day_map[(row.tarih, key)] = {"rating_avg": ort, "rating_count": oy}

        if key not in meal_acc:
            meal_acc[key] = {"puan_toplam": 0.0, "oy_toplam": 0.0}
        meal_acc[key]["puan_toplam"] += ort * oy
        meal_acc[key]["oy_toplam"] += oy

    meal_map: dict[str, dict[str, float]] = {}
    for key, item in meal_acc.items():
        oy_toplam = int(item["oy_toplam"])
        if oy_toplam <= 0:
            continue
        meal_map[key] = {
            "rating_avg": item["puan_toplam"] / oy_toplam,
            "rating_count": oy_toplam,
        }

    return day_map, meal_map


def _build_production_maps(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[dict[tuple[date, str], dict[str, float]], dict[str, dict[str, float]]]:
    """
    Uretim sinyalini iki seviyede mapler:
    - (tarih, yemek_key) -> ortalama uretilen / ortalama israf
    - yemek_key -> tum donem ortalama uretilen / ortalama israf
    """
    query = db.query(
        UretimLog.tarih,
        UretimLog.yemek_adi,
        sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
        sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
        sqla_func.count(UretimLog.id).label("kayit_sayisi"),
    ).filter(UretimLog.uretilen_porsiyon > 0)

    if start_date is not None:
        query = query.filter(UretimLog.tarih >= start_date)
    if end_date is not None:
        query = query.filter(UretimLog.tarih <= end_date)

    rows = query.group_by(UretimLog.tarih, UretimLog.yemek_adi).all()

    day_map: dict[tuple[date, str], dict[str, float]] = {}
    meal_acc: dict[str, dict[str, float]] = {}

    for row in rows:
        key = _meal_group_key(row.yemek_adi)
        kayit_sayisi = int(row.kayit_sayisi or 1)
        ort_uretilen = float(row.ort_uretilen or 0.0)
        ort_israf = _clip_israf(float(row.ort_israf)) if row.ort_israf is not None else None

        day_map[(row.tarih, key)] = {
            "uretilen_porsiyon": ort_uretilen,
            "israf_orani": ort_israf if ort_israf is not None else 0.0,
            "has_israf": 1 if ort_israf is not None else 0,
        }

        if key not in meal_acc:
            meal_acc[key] = {
                "uretilen_toplam": 0.0,
                "israf_toplam": 0.0,
                "israf_kayit": 0.0,
                "kayit_sayisi": 0.0,
            }
        meal_acc[key]["uretilen_toplam"] += ort_uretilen * kayit_sayisi
        meal_acc[key]["kayit_sayisi"] += kayit_sayisi
        if ort_israf is not None:
            meal_acc[key]["israf_toplam"] += ort_israf * kayit_sayisi
            meal_acc[key]["israf_kayit"] += kayit_sayisi

    meal_map: dict[str, dict[str, float]] = {}
    for key, item in meal_acc.items():
        kayit_sayisi = item["kayit_sayisi"] or 1.0
        israf_kayit = item["israf_kayit"] or 0.0
        meal_map[key] = {
            "uretilen_porsiyon": item["uretilen_toplam"] / kayit_sayisi,
            "israf_orani": (
                item["israf_toplam"] / israf_kayit
                if israf_kayit > 0
                else None
            ),
        }

    return day_map, meal_map


def _resolve_rating_signal(
    tarih: date,
    meal_key: str,
    rating_day_map: dict[tuple[date, str], dict[str, float]],
    rating_meal_map: dict[str, dict[str, float]],
) -> tuple[float, int]:
    by_day = rating_day_map.get((tarih, meal_key))
    if by_day:
        return float(by_day["rating_avg"]), int(by_day["rating_count"])

    by_meal = rating_meal_map.get(meal_key)
    if by_meal:
        return float(by_meal["rating_avg"]), int(by_meal["rating_count"])

    return DEFAULT_RATING_AVG, 0


def _resolve_production_signal(
    tarih: date,
    meal_key: str,
    prod_day_map: dict[tuple[date, str], dict[str, float]],
    prod_meal_map: dict[str, dict[str, float]],
) -> tuple[float, float | None]:
    by_day = prod_day_map.get((tarih, meal_key))
    if by_day:
        israf = by_day["israf_orani"] if by_day.get("has_israf") else None
        return float(by_day["uretilen_porsiyon"]), israf

    by_meal = prod_meal_map.get(meal_key)
    if by_meal:
        return float(by_meal["uretilen_porsiyon"]), _clip_israf(by_meal.get("israf_orani"))

    return DEFAULT_PRODUCTION, None


def _build_training_dataframe(db: Session) -> pd.DataFrame:
    """UretimLog (hedef) + puanlama + temporal + populerlik + yeni sinyaller ile egitim dataframe'i uretir."""
    rating_day_map, rating_meal_map = _build_rating_maps(db)
    prod_day_map, prod_meal_map = _build_production_maps(db)

    # Populerlik skorlari (menu_optimizer'dan)
    try:
        from modules.menu_optimizer import YEMEK_BAZI_POPULERLIK
    except ImportError:
        YEMEK_BAZI_POPULERLIK = {}

    logs = (
        db.query(UretimLog)
        .filter(UretimLog.uretilen_porsiyon > 0, UretimLog.israf_orani.isnot(None))
        .all()
    )

    # Onceki hafta israf lookup: (yemek_adi, tarih) -> onceki hafta ayni yemegin israf orani
    israf_lookup: dict[tuple[str, date], float] = {}
    for log in logs:
        key = (_canonicalize_meal_name(log.yemek_adi), log.tarih)
        israf_lookup[key] = float(log.israf_orani or 0.0)

    # Tarih bazli israf ortalamalari (son 3 gun icin)
    tarih_israf: dict[date, list[float]] = {}
    for log in logs:
        tarih_israf.setdefault(log.tarih, []).append(float(log.israf_orani or 0.0))

    # Kategori bazli israf ortalamalari
    kategori_israf_acc: dict[str, list[float]] = {}
    for log in logs:
        kat = log.kategori or "diger"
        kategori_israf_acc.setdefault(kat, []).append(float(log.israf_orani or 0.0))
    kategori_ort_israf_map = {k: sum(v)/len(v) for k, v in kategori_israf_acc.items() if v}

    # Tarih bazli menu cesitliligi
    tarih_cesitlilik: dict[date, int] = {}
    for log in logs:
        tarih_cesitlilik[log.tarih] = tarih_cesitlilik.get(log.tarih, 0) + 1

    # Rating standart sapma (yemek bazli)
    from collections import defaultdict
    rating_values: dict[str, list[float]] = defaultdict(list)
    rating_rows = db.query(MenuPuanlama.yemek_adi, MenuPuanlama.puan).all()
    for row in rating_rows:
        key = _meal_group_key(row.yemek_adi)
        rating_values[key].append(float(row.puan))
    rating_std_map = {
        k: float(np.std(v)) if len(v) > 1 else 0.0
        for k, v in rating_values.items()
    }

    # Tarih bazli genel israf ortalamasi (onceki_gun_israf - Lag-1 icin)
    tarih_ort_israf: dict[date, float] = {}
    for t, vals in tarih_israf.items():
        tarih_ort_israf[t] = sum(vals) / len(vals) if vals else 0.0

    # Self-report ortalamaları: (tarih, yemek_key) -> ort self-report
    self_report_map: dict[tuple[date, str], float] = {}
    sr_rows = (
        db.query(
            MenuPuanlama.tarih,
            MenuPuanlama.yemek_adi,
            sqla_func.avg(MenuPuanlama.israf_self_report).label("ort_sr"),
        )
        .filter(MenuPuanlama.israf_self_report.isnot(None))
        .group_by(MenuPuanlama.tarih, MenuPuanlama.yemek_adi)
        .all()
    )
    for sr in sr_rows:
        key = _meal_group_key(sr.yemek_adi)
        self_report_map[(sr.tarih, key)] = float(sr.ort_sr) if sr.ort_sr is not None else -1.0

    # Yemek bazli genel self-report ortalamasi (fallback)
    sr_meal_acc: dict[str, list[float]] = defaultdict(list)
    for sr in sr_rows:
        key = _meal_group_key(sr.yemek_adi)
        if sr.ort_sr is not None:
            sr_meal_acc[key].append(float(sr.ort_sr))
    sr_meal_map: dict[str, float] = {
        k: sum(v) / len(v) for k, v in sr_meal_acc.items() if v
    }

    # Menu cekiciligi: o gunku menunun ortalama populerlik skoru
    tarih_menu_cekicilik: dict[date, float] = {}
    for log in logs:
        meal_name_tmp = _canonicalize_meal_name(log.yemek_adi)
        pop = YEMEK_BAZI_POPULERLIK.get(meal_name_tmp, 0.5)
        tarih_menu_cekicilik.setdefault(log.tarih, []).append(pop)  # type: ignore[arg-type]
    tarih_menu_cekicilik = {
        t: sum(v) / len(v) for t, v in tarih_menu_cekicilik.items() if v  # type: ignore[union-attr]
    }

    records: list[dict[str, Any]] = []
    for log in logs:
        meal_name = _canonicalize_meal_name(log.yemek_adi)
        meal_key = _meal_group_key(meal_name)

        rating_avg, rating_count = _resolve_rating_signal(
            tarih=log.tarih,
            meal_key=meal_key,
            rating_day_map=rating_day_map,
            rating_meal_map=rating_meal_map,
        )
        uretilen_porsiyon, _ = _resolve_production_signal(
            tarih=log.tarih,
            meal_key=meal_key,
            prod_day_map=prod_day_map,
            prod_meal_map=prod_meal_map,
        )

        # --- Mevcut Feature: onceki_hafta_israf ---
        onceki_hafta_tarih = log.tarih - timedelta(days=7)
        onceki_israf = israf_lookup.get((meal_name, onceki_hafta_tarih), -1.0)

        # --- Mevcut Feature: populerlik_skoru ---
        pop_skor = YEMEK_BAZI_POPULERLIK.get(meal_name, 0.5)

        # --- Mevcut Ek Feature: mevsim ---
        mevsim = _get_mevsim(log.tarih)

        # --- Yeni Feature: hafta_ici_mi ---
        hafta_ici = 1 if log.tarih.weekday() < 5 else 0

        # --- Yeni Feature: son_3_gun_ort_israf ---
        son_3_gun_israflar = []
        for delta in range(1, 4):
            onceki_tarih = log.tarih - timedelta(days=delta)
            if onceki_tarih in tarih_israf:
                son_3_gun_israflar.extend(tarih_israf[onceki_tarih])
        son_3_gun_ort = sum(son_3_gun_israflar) / len(son_3_gun_israflar) if son_3_gun_israflar else -1.0

        # --- Yeni Feature: kategori_ort_israf ---
        kat_ort_israf = kategori_ort_israf_map.get(log.kategori or "diger", 20.0)

        # --- Yeni Feature: rating_std ---
        r_std = rating_std_map.get(meal_key, 0.0)

        # --- Yeni Feature: menu_cesitlilik ---
        cesitlilik = tarih_cesitlilik.get(log.tarih, 5)

        records.append(
            {
                "yemek_adi": meal_name or "Bilinmeyen",
                "kategori": log.kategori or "diger",
                "gun_hafta": int(log.tarih.weekday()),
                "ay": int(log.tarih.month),
                "uretilen_porsiyon": float(uretilen_porsiyon),
                "rating_avg": float(rating_avg),
                "rating_count": int(rating_count),
                "onceki_hafta_israf": float(onceki_israf),
                "populerlik_skoru": float(pop_skor),
                # Yeni feature'lar
                "mevsim": mevsim,
                "hafta_ici_mi": hafta_ici,
                "son_3_gun_ort_israf": son_3_gun_ort,
                "kategori_ort_israf": kat_ort_israf,
                "rating_std": r_std,
                "menu_cesitlilik": cesitlilik,
                # Plan 1.2 yeni feature'lar
                "ogrenci_sayisi_tahmini": _get_ogrenci_katilim_tahmini(log.tarih),
                "menu_cekiciligi": tarih_menu_cekicilik.get(log.tarih, 0.5),
                "gun_tipi": _get_gun_tipi(log.tarih),
                "onceki_gun_israf": tarih_ort_israf.get(
                    log.tarih - timedelta(days=1), -1.0
                ),
                # Self-report feature
                "self_report_avg": self_report_map.get(
                    (log.tarih, meal_key),
                    sr_meal_map.get(meal_key, -1.0),
                ),
                # Hedef + sıralama
                "target_israf": float(log.israf_orani or 0.0),
                "_tarih": log.tarih,  # time-series CV icin sıralama
            }
        )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["target_israf"] = df["target_israf"].clip(lower=0, upper=100)
    # Kronolojik siralama (time-series CV icin)
    df = df.sort_values("_tarih").reset_index(drop=True)
    return df


def load_waste_model(force_reload: bool = False) -> dict[str, Any] | None:
    """Kayitli israf modelini yukler."""
    global _cached_waste_model

    if _cached_waste_model is not None and not force_reload:
        return _cached_waste_model

    if not os.path.exists(WASTE_MODEL_PATH):
        _cached_waste_model = None
        return None

    try:
        model_bundle = joblib.load(WASTE_MODEL_PATH)
        if not isinstance(model_bundle, dict) or "pipeline" not in model_bundle:
            _cached_waste_model = None
            return None
        _cached_waste_model = model_bundle
        return _cached_waste_model
    except Exception:
        _cached_waste_model = None
        return None


def _optuna_tune(
    X: pd.DataFrame,
    y: pd.Series,
    preprocessor: ColumnTransformer,
    sample_count: int,
    n_trials: int = 30,
) -> dict[str, Any]:
    """
    Optuna ile Bayesian hyperparameter tuning.
    Optuna yoksa veya veri yetersizse bos dict dondurur (varsayilanlar kullanilir).
    """
    if not _HAS_OPTUNA or sample_count < 20:
        return {}

    try:
        def objective(trial: "optuna.Trial") -> float:
            params = {
                "rf_n_estimators": trial.suggest_int("rf_n_estimators", 100, 600, step=50),
                "rf_max_depth": trial.suggest_int("rf_max_depth", 5, 25),
                "rf_min_samples_leaf": trial.suggest_int("rf_min_samples_leaf", 1, 8),
                "gbr_n_estimators": trial.suggest_int("gbr_n_estimators", 100, 500, step=50),
                "gbr_max_depth": trial.suggest_int("gbr_max_depth", 3, 15),
                "gbr_learning_rate": trial.suggest_float("gbr_learning_rate", 0.01, 0.2, log=True),
                "gbr_min_samples_leaf": trial.suggest_int("gbr_min_samples_leaf", 1, 8),
            }
            if _HAS_XGBOOST:
                params["xgb_n_estimators"] = trial.suggest_int("xgb_n_estimators", 100, 500, step=50)
                params["xgb_max_depth"] = trial.suggest_int("xgb_max_depth", 3, 12)
                params["xgb_learning_rate"] = trial.suggest_float("xgb_learning_rate", 0.01, 0.2, log=True)

            rf = RandomForestRegressor(
                n_estimators=params["rf_n_estimators"],
                max_depth=params["rf_max_depth"],
                min_samples_leaf=params["rf_min_samples_leaf"],
                random_state=42, n_jobs=-1,
            )
            gbr = GradientBoostingRegressor(
                n_estimators=params["gbr_n_estimators"],
                max_depth=params["gbr_max_depth"],
                learning_rate=params["gbr_learning_rate"],
                subsample=0.85,
                min_samples_leaf=params["gbr_min_samples_leaf"],
                random_state=42,
            )
            ests = [("rf", rf), ("gbr", gbr)]
            if _HAS_XGBOOST:
                xgb = XGBRegressor(
                    n_estimators=params["xgb_n_estimators"],
                    max_depth=params["xgb_max_depth"],
                    learning_rate=params["xgb_learning_rate"],
                    subsample=0.85, colsample_bytree=0.8,
                    random_state=42, verbosity=0,
                )
                ests.append(("xgb", xgb))

            pipe = Pipeline([
                ("preprocessor", preprocessor),
                ("regressor", VotingRegressor(estimators=ests)),
            ])

            n_sp = min(3, sample_count // 5)
            tscv = TimeSeriesSplit(n_splits=max(2, n_sp))
            scores = []
            for tr_idx, te_idx in tscv.split(X):
                pipe.fit(X.iloc[tr_idx], y.iloc[tr_idx])
                pred = pipe.predict(X.iloc[te_idx])
                scores.append(mean_absolute_error(y.iloc[te_idx], pred))
            return float(np.mean(scores))

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="minimize")
        logger.info("Optuna tuning basliyor: %d trial, timeout=120s ...", n_trials)
        study.optimize(objective, n_trials=n_trials, timeout=120, show_progress_bar=False)
        logger.info("Optuna best MAE: %.3f, params: %s", study.best_value, study.best_params)
        return dict(study.best_params)
    except Exception as e:
        logger.warning("Optuna tuning basarisiz, varsayilan parametreler kullanilacak: %s", e)
        return {}


def _extract_feature_importance(
    pipeline: Pipeline,
    X: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Egitilmis pipeline'dan feature importance cikarir.
    Her model icin ayri, sonra ensemble ortalamasi.
    Admin dashboard'da gosterilmek uzere JSON-friendly liste dondurur.
    """
    try:
        preprocessor: ColumnTransformer = pipeline.named_steps["preprocessor"]
        regressor: VotingRegressor = pipeline.named_steps["regressor"]

        # OHE sonrasi feature isimleri
        try:
            ohe = preprocessor.named_transformers_["cat"]
            cat_feature_names = list(ohe.get_feature_names_out())
        except Exception:
            cat_feature_names = []
        num_feature_names = [c for c in WASTE_FEATURE_COLUMNS if c not in ("yemek_adi", "kategori")]
        all_feature_names = cat_feature_names + num_feature_names

        # Her alt modelden importance topla
        importances_sum = np.zeros(len(all_feature_names))
        model_count = 0
        for estimator in regressor.estimators_:
            imp = None
            if hasattr(estimator, "feature_importances_"):
                imp = estimator.feature_importances_
            if imp is not None and len(imp) == len(all_feature_names):
                importances_sum += imp
                model_count += 1

        if model_count == 0:
            return []

        avg_importance = importances_sum / model_count

        # OHE feature'lari orijinal kategorik sutuna geri topla
        consolidated: dict[str, float] = {}
        for i, fname in enumerate(all_feature_names):
            # OHE feature'lari "cat__yemek_adi_XXX" seklinde
            original_col = fname
            for prefix in ("cat__yemek_adi_", "cat__kategori_"):
                if fname.startswith(prefix):
                    original_col = prefix.replace("cat__", "").rstrip("_")
                    break
            consolidated[original_col] = consolidated.get(original_col, 0.0) + float(avg_importance[i])

        # Normalize ve sirala
        total = sum(consolidated.values()) or 1.0
        result = [
            {"feature": k, "importance": round(v / total, 4), "importance_raw": round(v, 6)}
            for k, v in consolidated.items()
        ]
        result.sort(key=lambda x: x["importance"], reverse=True)
        return result
    except Exception as e:
        logger.warning("Feature importance cikarimi basarisiz: %s", e)
        return []


def train_waste_model_from_db(
    db: Optional[Session] = None,
    min_samples: int = MIN_TRAIN_SAMPLES,
) -> dict[str, Any]:
    """
    Gercek israf hedefiyle modeli egitir ve diske kaydeder.

    Hedef:
      - UretimLog.israf_orani (gercek saha verisi)
    Ozellikler:
      - 20 feature: temel + temporal + populerlik + hava/takvim/cekicilik/lag-1
    Model:
      - Ensemble (RandomForest + GradientBoosting + XGBoost)
      - Optuna Bayesian Hyperparameter Tuning
      - Time-Series Cross-Validation
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        min_samples = max(4, int(min_samples))
        df = _build_training_dataframe(db)

        if df.empty:
            return {
                "success": False,
                "message": "Egitim icin uygun UretimLog verisi bulunamadi.",
                "sample_count": 0,
                "min_samples": min_samples,
            }

        sample_count = int(len(df))
        if sample_count < min_samples:
            return {
                "success": False,
                "message": (
                    f"Egitim icin veri yetersiz. Gerekli >= {min_samples}, mevcut = {sample_count}."
                ),
                "sample_count": sample_count,
                "min_samples": min_samples,
            }

        # _tarih kolonu sadece siralama icin — modele verilmez
        X = df[WASTE_FEATURE_COLUMNS]
        y = df["target_israf"]

        cat_cols = ["yemek_adi", "kategori"]
        num_cols = [c for c in WASTE_FEATURE_COLUMNS if c not in cat_cols]

        preprocessor = ColumnTransformer(
            transformers=[
                ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
                ("num", "passthrough", num_cols),
            ]
        )

        # ── Optuna Bayesian Hyperparameter Tuning ──
        best_params = _optuna_tune(X, y, preprocessor, sample_count)

        # ── Ensemble: RandomForest + GradientBoosting + XGBoost ──
        rf = RandomForestRegressor(
            n_estimators=best_params.get("rf_n_estimators", 400),
            max_depth=best_params.get("rf_max_depth", 15),
            min_samples_leaf=best_params.get("rf_min_samples_leaf", 2),
            min_samples_split=4,
            random_state=42,
            n_jobs=-1,
        )
        gbr = GradientBoostingRegressor(
            n_estimators=best_params.get("gbr_n_estimators", 350),
            max_depth=best_params.get("gbr_max_depth", 10),
            learning_rate=best_params.get("gbr_learning_rate", 0.05),
            subsample=0.85,
            min_samples_leaf=best_params.get("gbr_min_samples_leaf", 3),
            random_state=42,
        )

        estimators = [("rf", rf), ("gbr", gbr)]
        model_type_label = "Ensemble(RF+GBR"

        if _HAS_XGBOOST:
            xgb = XGBRegressor(
                n_estimators=best_params.get("xgb_n_estimators", 300),
                max_depth=best_params.get("xgb_max_depth", 8),
                learning_rate=best_params.get("xgb_learning_rate", 0.05),
                subsample=0.85,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0,
            )
            estimators.append(("xgb", xgb))
            model_type_label += "+XGBoost"

        model_type_label += ")"
        ensemble = VotingRegressor(estimators=estimators)

        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("regressor", ensemble),
            ]
        )

        # ── Time-Series Cross-Validation (kronolojik split) ──
        metrics: dict[str, float | str]
        if sample_count >= 12:
            n_splits = min(5, sample_count // 4)
            tscv = TimeSeriesSplit(n_splits=max(2, n_splits))
            cv_mae, cv_rmse, cv_r2 = [], [], []
            for train_idx, test_idx in tscv.split(X):
                X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
                y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
                pipeline.fit(X_tr, y_tr)
                y_p = pipeline.predict(X_te)
                cv_mae.append(mean_absolute_error(y_te, y_p))
                cv_rmse.append(math.sqrt(mean_squared_error(y_te, y_p)))
                r2_val = r2_score(y_te, y_p) if len(y_te) > 1 else 0.0
                cv_r2.append(r2_val)

            # Final fit on all data
            pipeline.fit(X, y)

            metrics = {
                "mae_cv": round(float(np.mean(cv_mae)), 3),
                "rmse_cv": round(float(np.mean(cv_rmse)), 3),
                "r2_cv": round(float(np.mean(cv_r2)), 3),
                "cv_folds": len(cv_mae),
                "validation": "TimeSeriesSplit",
            }
        else:
            pipeline.fit(X, y)
            y_pred = pipeline.predict(X)
            metrics = {
                "mae_train": round(float(mean_absolute_error(y, y_pred)), 3),
                "rmse_train": round(float(math.sqrt(mean_squared_error(y, y_pred))), 3),
                "r2_train": round(float(r2_score(y, y_pred)), 3),
                "note": "Veri az oldugu icin train metrikleri raporlandi.",
            }

        # ── Feature Importance Raporu ──
        importance_report = _extract_feature_importance(pipeline, X)

        os.makedirs(MODEL_DIR, exist_ok=True)
        model_bundle = {
            "pipeline": pipeline,
            "feature_columns": list(WASTE_FEATURE_COLUMNS),
            "trained_at": datetime.utcnow().isoformat() + "Z",
            "sample_count": sample_count,
            "model_type": model_type_label,
            "feature_importance": importance_report,
            "optuna_params": best_params,
        }
        joblib.dump(model_bundle, WASTE_MODEL_PATH)

        global _cached_waste_model
        _cached_waste_model = model_bundle

        # Metrikleri JSON dosyasina kaydet
        metrics_data = {
            "trained_at": model_bundle["trained_at"],
            "sample_count": sample_count,
            "model_type": model_type_label,
            **metrics,
        }
        try:
            with open(WASTE_METRICS_PATH, "w", encoding="utf-8") as f:
                json.dump(metrics_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Feature importance ayri JSON olarak kaydet (admin dashboard icin)
        try:
            with open(WASTE_IMPORTANCE_PATH, "w", encoding="utf-8") as f:
                json.dump(importance_report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return {
            "success": True,
            "message": "Israf ML modeli basariyla egitildi.",
            "model_path": WASTE_MODEL_PATH,
            "sample_count": sample_count,
            "metrics": metrics,
            "model_type": model_type_label,
            "feature_importance": importance_report,
            "optuna_tuned": bool(best_params),
        }
    finally:
        if close_db:
            db.close()


def get_waste_model_status(db: Optional[Session] = None) -> dict[str, Any]:
    """Israf modelinin dosya ve veri durumunu dondurur."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        model_bundle = load_waste_model()
        training_data_count = (
            db.query(sqla_func.count(UretimLog.id))
            .filter(UretimLog.uretilen_porsiyon > 0, UretimLog.israf_orani.isnot(None))
            .scalar()
        ) or 0

        # Kaydedilmis metrikleri oku
        saved_metrics = {}
        try:
            if os.path.exists(WASTE_METRICS_PATH):
                with open(WASTE_METRICS_PATH, "r", encoding="utf-8") as f:
                    saved_metrics = json.load(f)
        except Exception:
            pass

        # Feature importance bilgisi
        has_importance = os.path.exists(WASTE_IMPORTANCE_PATH)

        return {
            "success": True,
            "model_yuklu": model_bundle is not None,
            "model_tipi": (model_bundle or {}).get("model_type", "Bilinmiyor"),
            "model_path": WASTE_MODEL_PATH,
            "son_egitim_tarihi": saved_metrics.get("trained_at") or (model_bundle or {}).get("trained_at"),
            "egitim_veri_sayisi": saved_metrics.get("sample_count") or (model_bundle or {}).get("sample_count"),
            "mae": saved_metrics.get("mae_cv", saved_metrics.get("mae_test", saved_metrics.get("mae_train", "-"))),
            "rmse": saved_metrics.get("rmse_cv", saved_metrics.get("rmse_test", saved_metrics.get("rmse_train", "-"))),
            "r2": saved_metrics.get("r2_cv", saved_metrics.get("r2_test", saved_metrics.get("r2_train", "-"))),
            "validation_method": saved_metrics.get("validation", "train_test_split"),
            "cv_folds": saved_metrics.get("cv_folds"),
            "training_data_count": int(training_data_count),
            "fallback_active": model_bundle is None,
            "feature_count": len(WASTE_FEATURE_COLUMNS),
            "xgboost_active": _HAS_XGBOOST,
            "optuna_active": _HAS_OPTUNA,
            "feature_importance_available": has_importance,
        }
    finally:
        if close_db:
            db.close()


def get_feature_importance_report() -> dict[str, Any]:
    """
    Admin dashboard icin feature importance raporu dondurur.
    Egitilmis modelden veya kaydedilmis JSON'dan okur.
    """
    # Oncelik 1: Bellekteki modelden
    model_bundle = load_waste_model()
    if model_bundle and model_bundle.get("feature_importance"):
        return {
            "success": True,
            "source": "model_bundle",
            "model_type": model_bundle.get("model_type", "Bilinmiyor"),
            "trained_at": model_bundle.get("trained_at"),
            "features": model_bundle["feature_importance"],
        }

    # Oncelik 2: Kaydedilmis JSON dosyasindan
    if os.path.exists(WASTE_IMPORTANCE_PATH):
        try:
            with open(WASTE_IMPORTANCE_PATH, "r", encoding="utf-8") as f:
                features = json.load(f)
            return {
                "success": True,
                "source": "saved_file",
                "features": features,
            }
        except Exception:
            pass

    return {
        "success": False,
        "message": "Feature importance raporu bulunamadi. Once modeli egitin.",
        "features": [],
    }


def _predict_waste_with_ml(
    yemek_adi: str,
    kategori: str,
    tarih: date,
    ortalama_puan: float,
    toplam_oy: int,
    uretilen_porsiyon: float,
    onceki_hafta_israf: float = -1.0,
    populerlik_skoru: float = 0.5,
) -> float | None:
    model_bundle = load_waste_model()
    if model_bundle is None:
        return None

    # Model yeterli veri ile egitilmemisse guvenilir degil → fallback kullan
    sample_count = model_bundle.get("sample_count", 0)
    if sample_count < 20:
        return None

    pipeline = model_bundle.get("pipeline")
    if pipeline is None:
        return None

    # Mevcut ek feature'lar icin runtime hesaplamalar
    mevsim = _get_mevsim(tarih)
    hafta_ici = 1 if tarih.weekday() < 5 else 0

    # DB'den runtime sinyalleri cek
    son_3_gun_ort = -1.0
    kategori_ort = 20.0
    rating_std = 0.0
    menu_cesitlilik = 5
    onceki_gun_israf_val = -1.0
    menu_cekiciligi_val = 0.5
    self_report_avg_val = -1.0
    try:
        db_temp = SessionLocal()

        # Son 3 gun genel israf ortalamasi
        uc_gun_once = tarih - timedelta(days=3)
        son3 = db_temp.query(sqla_func.avg(UretimLog.israf_orani)).filter(
            UretimLog.tarih >= uc_gun_once,
            UretimLog.tarih < tarih,
            UretimLog.israf_orani.isnot(None),
        ).scalar()
        if son3 is not None:
            son_3_gun_ort = float(son3)

        # Kategori ortalama israfi
        kat_ort = db_temp.query(sqla_func.avg(UretimLog.israf_orani)).filter(
            UretimLog.kategori == (kategori or "diger"),
            UretimLog.israf_orani.isnot(None),
        ).scalar()
        if kat_ort is not None:
            kategori_ort = float(kat_ort)

        # Rating standart sapmasi
        puanlar = [float(r.puan) for r in db_temp.query(MenuPuanlama.puan).filter(
            MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%")
        ).all()]
        if len(puanlar) > 1:
            rating_std = float(np.std(puanlar))

        # Bugunun menu cesitliligi
        cesit = db_temp.query(sqla_func.count(UretimLog.id)).filter(
            UretimLog.tarih == tarih,
        ).scalar()
        if cesit and cesit > 0:
            menu_cesitlilik = int(cesit)

        # ── Plan 1.2: onceki_gun_israf (Lag-1) ──
        onceki_gun = tarih - timedelta(days=1)
        lag1 = db_temp.query(sqla_func.avg(UretimLog.israf_orani)).filter(
            UretimLog.tarih == onceki_gun,
            UretimLog.israf_orani.isnot(None),
        ).scalar()
        if lag1 is not None:
            onceki_gun_israf_val = float(lag1)

        # ── Self-report ortalamasi ──
        sr_val = db_temp.query(sqla_func.avg(MenuPuanlama.israf_self_report)).filter(
            MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
            MenuPuanlama.israf_self_report.isnot(None),
        ).scalar()
        if sr_val is not None:
            self_report_avg_val = float(sr_val)

        # ── Plan 1.2: menu_cekiciligi ──
        try:
            from modules.menu_optimizer import YEMEK_BAZI_POPULERLIK
            bugun_yemekler = db_temp.query(UretimLog.yemek_adi).filter(
                UretimLog.tarih == tarih,
            ).distinct().all()
            if bugun_yemekler:
                pops = [YEMEK_BAZI_POPULERLIK.get(
                    _canonicalize_meal_name(r.yemek_adi), 0.5
                ) for r in bugun_yemekler]
                menu_cekiciligi_val = sum(pops) / len(pops)
        except ImportError:
            pass

        db_temp.close()
    except Exception:
        pass

    row = pd.DataFrame(
        [
            {
                "yemek_adi": _canonicalize_meal_name(yemek_adi) or "Bilinmeyen",
                "kategori": kategori or "diger",
                "gun_hafta": int(tarih.weekday()),
                "ay": int(tarih.month),
                "uretilen_porsiyon": float(max(1.0, uretilen_porsiyon)),
                "rating_avg": float(ortalama_puan),
                "rating_count": int(max(0, toplam_oy)),
                "onceki_hafta_israf": float(onceki_hafta_israf),
                "populerlik_skoru": float(populerlik_skoru),
                # Mevcut ek feature'lar
                "mevsim": mevsim,
                "hafta_ici_mi": hafta_ici,
                "son_3_gun_ort_israf": son_3_gun_ort,
                "kategori_ort_israf": kategori_ort,
                "rating_std": rating_std,
                "menu_cesitlilik": menu_cesitlilik,
                # Plan 1.2 yeni feature'lar
                "ogrenci_sayisi_tahmini": _get_ogrenci_katilim_tahmini(tarih),
                "menu_cekiciligi": menu_cekiciligi_val,
                "gun_tipi": _get_gun_tipi(tarih),
                "onceki_gun_israf": onceki_gun_israf_val,
                # Self-report feature
                "self_report_avg": self_report_avg_val,
            }
        ]
    )

    try:
        pred = float(pipeline.predict(row)[0])
        return _clip_israf(pred)
    except Exception:
        return None


def estimate_waste_ratio(
    *,
    yemek_adi: str,
    kategori: str,
    tarih: date,
    ortalama_puan: float | None,
    toplam_oy: int | None,
    uretilen_porsiyon: float | None,
    uretim_israf_orani: float | None,
    onceki_hafta_israf: float | None = None,
    populerlik_skoru: float | None = None,
) -> tuple[float | None, str]:
    """
    Sirali karar:
      1) ML model (ensemble)
      2) Gercek uretim israf ortalamasi
      3) Kural tabanli puan -> israf
      4) Veri yok
    """
    rating_avg = float(ortalama_puan) if ortalama_puan is not None else DEFAULT_RATING_AVG
    rating_count = int(toplam_oy or 0)
    production = float(uretilen_porsiyon) if uretilen_porsiyon and uretilen_porsiyon > 0 else DEFAULT_PRODUCTION

    # Onceki hafta israf verisini otomatik bul (verilmemisse)
    prev_israf = float(onceki_hafta_israf) if onceki_hafta_israf is not None else -1.0
    if prev_israf < 0:
        try:
            db_temp = SessionLocal()
            onceki_tarih = tarih - timedelta(days=7)
            prev_log = (
                db_temp.query(UretimLog)
                .filter(
                    UretimLog.yemek_adi.ilike(f"%{yemek_adi}%"),
                    UretimLog.tarih == onceki_tarih,
                    UretimLog.israf_orani.isnot(None),
                )
                .first()
            )
            if prev_log and prev_log.israf_orani is not None:
                prev_israf = float(prev_log.israf_orani)
            db_temp.close()
        except Exception:
            pass

    # Populerlik skorunu otomatik bul (verilmemisse)
    pop_skor = float(populerlik_skoru) if populerlik_skoru is not None else 0.5
    if populerlik_skoru is None:
        try:
            from modules.menu_optimizer import YEMEK_BAZI_POPULERLIK
            pop_skor = YEMEK_BAZI_POPULERLIK.get(yemek_adi, 0.5)
        except ImportError:
            pass

    ml_pred = _predict_waste_with_ml(
        yemek_adi=yemek_adi,
        kategori=kategori,
        tarih=tarih,
        ortalama_puan=rating_avg,
        toplam_oy=rating_count,
        uretilen_porsiyon=production,
        onceki_hafta_israf=prev_israf,
        populerlik_skoru=pop_skor,
    )
    if ml_pred is not None:
        return ml_pred, "ml_model"

    if uretim_israf_orani is not None:
        return _clip_israf(float(uretim_israf_orani)), "uretim_gercek"

    if ortalama_puan is not None:
        return _clip_israf(puan_to_israf_orani(float(ortalama_puan))), "kural_puan"

    return None, "veri_yok"


def _method_counter() -> dict[str, int]:
    return {
        "ml_model": 0,
        "uretim_gercek": 0,
        "kural_puan": 0,
        "veri_yok": 0,
    }


def _resolve_meal_category(yemek_adi: str, db: Session) -> str:
    """Yemek icin en olasi kategoriyi bulur."""
    category_votes: dict[str, int] = {}

    rating_rows = (
        db.query(
            MenuPuanlama.kategori,
            sqla_func.count(MenuPuanlama.id).label("adet"),
        )
        .filter(MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"))
        .group_by(MenuPuanlama.kategori)
        .all()
    )
    for row in rating_rows:
        category_votes[row.kategori] = category_votes.get(row.kategori, 0) + int(row.adet or 0)

    production_rows = (
        db.query(
            UretimLog.kategori,
            sqla_func.count(UretimLog.id).label("adet"),
        )
        .filter(UretimLog.yemek_adi.ilike(f"%{yemek_adi}%"))
        .group_by(UretimLog.kategori)
        .all()
    )
    for row in production_rows:
        category_votes[row.kategori] = category_votes.get(row.kategori, 0) + int(row.adet or 0)

    if not category_votes:
        return "diger"

    return sorted(category_votes.items(), key=lambda x: x[1], reverse=True)[0][0]


def _sort_by_waste(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda x: (x.get("israf_skoru") is not None, x.get("israf_skoru") or -1),
        reverse=True,
    )


def calculate_waste_score(yemek_adi: str, db: Optional[Session] = None) -> dict[str, Any]:
    """
    Belirli bir yemegin israf skorunu hesaplar (0-100).
    100 = en cok israf edilen.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        rating_result = (
            db.query(
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"))
            .first()
        )
        production_result = (
            db.query(
                sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                sqla_func.count(UretimLog.id).label("kayit_sayisi"),
            )
            .filter(UretimLog.yemek_adi.ilike(f"%{yemek_adi}%"))
            .first()
        )

        ort_puan = None
        toplam_oy = 0
        if rating_result and rating_result.toplam_oy and rating_result.toplam_oy > 0:
            ort_puan = float(rating_result.ortalama)
            toplam_oy = int(rating_result.toplam_oy)

        ort_uretilen = None
        ort_israf = None
        uretim_kayit = 0
        if production_result and production_result.kayit_sayisi and production_result.kayit_sayisi > 0:
            ort_uretilen = float(production_result.ort_uretilen or 0.0)
            ort_israf = (
                float(production_result.ort_israf)
                if production_result.ort_israf is not None
                else None
            )
            uretim_kayit = int(production_result.kayit_sayisi)

        kategori = _resolve_meal_category(yemek_adi, db)
        israf_orani, method = estimate_waste_ratio(
            yemek_adi=yemek_adi,
            kategori=kategori,
            tarih=date.today(),
            ortalama_puan=ort_puan,
            toplam_oy=toplam_oy,
            uretilen_porsiyon=ort_uretilen,
            uretim_israf_orani=ort_israf,
        )

        if israf_orani is None:
            return {
                "yemek_adi": yemek_adi,
                "ortalama_puan": None,
                "toplam_oy": 0,
                "israf_skoru": None,
                "israf_seviye": "Veri yok",
                "tahmin_metodu": "veri_yok",
            }

        return {
            "yemek_adi": yemek_adi,
            "ortalama_puan": round(ort_puan, 2) if ort_puan is not None else None,
            "toplam_oy": toplam_oy,
            "uretim_kayit_sayisi": uretim_kayit,
            "israf_skoru": round(israf_orani, 1),
            "israf_seviye": _waste_level(israf_orani),
            "tahmin_metodu": method,
        }
    finally:
        if close_db:
            db.close()


def get_daily_waste_report(db: Optional[Session] = None) -> dict[str, Any]:
    """Bugunun tahmini/olculen israf raporunu dondurur."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        method_counts = _method_counter()

        rating_rows = (
            db.query(
                MenuPuanlama.yemek_adi,
                MenuPuanlama.kategori,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih == bugun)
            .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
            .all()
        )

        prod_day_map, prod_meal_map = _build_production_maps(
            db=db,
            start_date=bugun,
            end_date=bugun,
        )

        yemekler: list[dict[str, Any]] = []

        for row in rating_rows:
            meal_key = _meal_group_key(row.yemek_adi)
            prod_uretilen, prod_israf = _resolve_production_signal(
                tarih=bugun,
                meal_key=meal_key,
                prod_day_map=prod_day_map,
                prod_meal_map=prod_meal_map,
            )
            israf, method = estimate_waste_ratio(
                yemek_adi=row.yemek_adi,
                kategori=row.kategori,
                tarih=bugun,
                ortalama_puan=float(row.ortalama) if row.ortalama is not None else None,
                toplam_oy=int(row.toplam_oy or 0),
                uretilen_porsiyon=prod_uretilen,
                uretim_israf_orani=prod_israf,
            )
            method_counts[method] = method_counts.get(method, 0) + 1

            yemekler.append(
                {
                    "yemek_adi": row.yemek_adi,
                    "kategori": row.kategori,
                    "ortalama_puan": round(float(row.ortalama), 2) if row.ortalama is not None else None,
                    "toplam_oy": int(row.toplam_oy or 0),
                    "israf_skoru": round(israf, 1) if israf is not None else None,
                    "israf_seviye": _waste_level(israf),
                    "tahmin_metodu": method,
                }
            )

        # Puan yoksa ama uretim varsa gene de rapor dondur.
        if not yemekler:
            production_rows = (
                db.query(
                    UretimLog.yemek_adi,
                    UretimLog.kategori,
                    sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                    sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
                    sqla_func.count(UretimLog.id).label("kayit_sayisi"),
                )
                .filter(UretimLog.tarih == bugun)
                .group_by(UretimLog.yemek_adi, UretimLog.kategori)
                .all()
            )
            for row in production_rows:
                israf, method = estimate_waste_ratio(
                    yemek_adi=row.yemek_adi,
                    kategori=row.kategori,
                    tarih=bugun,
                    ortalama_puan=None,
                    toplam_oy=0,
                    uretilen_porsiyon=float(row.ort_uretilen or 0.0),
                    uretim_israf_orani=float(row.ort_israf) if row.ort_israf is not None else None,
                )
                method_counts[method] = method_counts.get(method, 0) + 1
                yemekler.append(
                    {
                        "yemek_adi": row.yemek_adi,
                        "kategori": row.kategori,
                        "ortalama_puan": None,
                        "toplam_oy": 0,
                        "israf_skoru": round(israf, 1) if israf is not None else None,
                        "israf_seviye": _waste_level(israf),
                        "tahmin_metodu": method,
                    }
                )

        skorlar = [float(y["israf_skoru"]) for y in yemekler if y.get("israf_skoru") is not None]
        genel_israf = round(sum(skorlar) / len(skorlar), 1) if skorlar else 0.0

        return {
            "success": True,
            "tarih": str(bugun),
            "genel_israf_skoru": genel_israf,
            "genel_israf_seviye": _waste_level(genel_israf),
            "yemekler": _sort_by_waste(yemekler),
            "model_durumu": "ML model aktif" if load_waste_model() else "Fallback (kural/uretim)",
            "tahmin_ozet": method_counts,
        }
    finally:
        if close_db:
            db.close()


def get_weekly_waste_report(db: Optional[Session] = None) -> dict[str, Any]:
    """Haftalik israf ozetini dondurur."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        hafta_basi = bugun - timedelta(days=7)
        method_counts = _method_counter()

        rating_rows = (
            db.query(
                MenuPuanlama.yemek_adi,
                MenuPuanlama.kategori,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih >= hafta_basi)
            .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
            .all()
        )

        _, prod_meal_map = _build_production_maps(
            db=db,
            start_date=hafta_basi,
            end_date=bugun,
        )

        yemekler: list[dict[str, Any]] = []

        for row in rating_rows:
            meal_key = _meal_group_key(row.yemek_adi)
            prod_info = prod_meal_map.get(meal_key, {})
            israf, method = estimate_waste_ratio(
                yemek_adi=row.yemek_adi,
                kategori=row.kategori,
                tarih=bugun,
                ortalama_puan=float(row.ortalama) if row.ortalama is not None else None,
                toplam_oy=int(row.toplam_oy or 0),
                uretilen_porsiyon=float(prod_info.get("uretilen_porsiyon") or DEFAULT_PRODUCTION),
                uretim_israf_orani=_clip_israf(prod_info.get("israf_orani")),
            )
            method_counts[method] = method_counts.get(method, 0) + 1
            yemekler.append(
                {
                    "yemek_adi": row.yemek_adi,
                    "kategori": row.kategori,
                    "ortalama_puan": round(float(row.ortalama), 2) if row.ortalama is not None else None,
                    "toplam_oy": int(row.toplam_oy or 0),
                    "israf_skoru": round(israf, 1) if israf is not None else None,
                    "tahmin_metodu": method,
                }
            )

        # Rating yoksa production'dan doldur.
        if not yemekler:
            production_rows = (
                db.query(
                    UretimLog.yemek_adi,
                    UretimLog.kategori,
                    sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                    sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
                )
                .filter(UretimLog.tarih >= hafta_basi)
                .group_by(UretimLog.yemek_adi, UretimLog.kategori)
                .all()
            )
            for row in production_rows:
                israf, method = estimate_waste_ratio(
                    yemek_adi=row.yemek_adi,
                    kategori=row.kategori,
                    tarih=bugun,
                    ortalama_puan=None,
                    toplam_oy=0,
                    uretilen_porsiyon=float(row.ort_uretilen or 0.0),
                    uretim_israf_orani=float(row.ort_israf) if row.ort_israf is not None else None,
                )
                method_counts[method] = method_counts.get(method, 0) + 1
                yemekler.append(
                    {
                        "yemek_adi": row.yemek_adi,
                        "kategori": row.kategori,
                        "ortalama_puan": None,
                        "toplam_oy": 0,
                        "israf_skoru": round(israf, 1) if israf is not None else None,
                        "tahmin_metodu": method,
                    }
                )

        yemekler = _sort_by_waste(yemekler)

        # Gunluk trend
        gunluk_rating_rows = (
            db.query(
                MenuPuanlama.tarih,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih >= hafta_basi)
            .group_by(MenuPuanlama.tarih)
            .order_by(MenuPuanlama.tarih)
            .all()
        )
        gunluk_prod_rows = (
            db.query(
                UretimLog.tarih,
                sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            )
            .filter(UretimLog.tarih >= hafta_basi)
            .group_by(UretimLog.tarih)
            .all()
        )
        gunluk_prod_map = {
            row.tarih: {
                "uretilen": float(row.ort_uretilen or 0.0),
                "israf": float(row.ort_israf) if row.ort_israf is not None else None,
            }
            for row in gunluk_prod_rows
        }

        gunluk_trend: list[dict[str, Any]] = []
        for row in gunluk_rating_rows:
            prod = gunluk_prod_map.get(row.tarih, {})
            israf, method = estimate_waste_ratio(
                yemek_adi="Gunluk Ortalama",
                kategori="genel",
                tarih=row.tarih,
                ortalama_puan=float(row.ortalama) if row.ortalama is not None else None,
                toplam_oy=int(row.toplam_oy or 0),
                uretilen_porsiyon=float(prod.get("uretilen") or DEFAULT_PRODUCTION),
                uretim_israf_orani=_clip_israf(prod.get("israf")),
            )
            gunluk_trend.append(
                {
                    "tarih": str(row.tarih),
                    "ortalama_puan": round(float(row.ortalama), 2) if row.ortalama is not None else None,
                    "israf_skoru": round(israf, 1) if israf is not None else None,
                    "tahmin_metodu": method,
                }
            )

        # Kategori bazinda
        kategori_rating_rows = (
            db.query(
                MenuPuanlama.kategori,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.tarih >= hafta_basi)
            .group_by(MenuPuanlama.kategori)
            .all()
        )
        kategori_prod_rows = (
            db.query(
                UretimLog.kategori,
                sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            )
            .filter(UretimLog.tarih >= hafta_basi)
            .group_by(UretimLog.kategori)
            .all()
        )
        kategori_prod_map = {
            row.kategori: {
                "uretilen": float(row.ort_uretilen or 0.0),
                "israf": float(row.ort_israf) if row.ort_israf is not None else None,
            }
            for row in kategori_prod_rows
        }

        kategori_israf: dict[str, Any] = {}
        for row in kategori_rating_rows:
            prod = kategori_prod_map.get(row.kategori, {})
            israf, method = estimate_waste_ratio(
                yemek_adi=f"Kategori {row.kategori}",
                kategori=row.kategori,
                tarih=bugun,
                ortalama_puan=float(row.ortalama) if row.ortalama is not None else None,
                toplam_oy=int(row.toplam_oy or 0),
                uretilen_porsiyon=float(prod.get("uretilen") or DEFAULT_PRODUCTION),
                uretim_israf_orani=_clip_israf(prod.get("israf")),
            )
            kategori_israf[row.kategori] = {
                "ortalama_puan": round(float(row.ortalama), 2) if row.ortalama is not None else None,
                "israf_skoru": round(israf, 1) if israf is not None else None,
                "tahmin_metodu": method,
            }

        skorlar = [float(y["israf_skoru"]) for y in yemekler if y.get("israf_skoru") is not None]
        genel = round(sum(skorlar) / len(skorlar), 1) if skorlar else 0.0

        return {
            "success": True,
            "donem": {"baslangic": str(hafta_basi), "bitis": str(bugun)},
            "genel_israf_skoru": genel,
            "genel_israf_seviye": _waste_level(genel),
            "en_cok_israf": yemekler[:5],
            "en_az_israf": list(reversed(yemekler[-5:])) if len(yemekler) >= 5 else list(reversed(yemekler)),
            "gunluk_trend": gunluk_trend,
            "kategori_israf": kategori_israf,
            "tum_yemekler": yemekler,
            "model_durumu": "ML model aktif" if load_waste_model() else "Fallback (kural/uretim)",
            "tahmin_ozet": method_counts,
        }
    finally:
        if close_db:
            db.close()


def get_dish_waste_history(
    yemek_adi: str,
    gun: int = 30,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """Belirli bir yemegin israf gecmisini dondurur."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        baslangic = bugun - timedelta(days=gun)

        gunluk_rating = (
            db.query(
                MenuPuanlama.tarih,
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(
                MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
                MenuPuanlama.tarih >= baslangic,
            )
            .group_by(MenuPuanlama.tarih)
            .order_by(MenuPuanlama.tarih)
            .all()
        )

        gunluk_production = (
            db.query(
                UretimLog.tarih,
                sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            )
            .filter(
                UretimLog.yemek_adi.ilike(f"%{yemek_adi}%"),
                UretimLog.tarih >= baslangic,
            )
            .group_by(UretimLog.tarih)
            .order_by(UretimLog.tarih)
            .all()
        )
        production_map = {
            row.tarih: {
                "uretilen": float(row.ort_uretilen or 0.0),
                "israf": float(row.ort_israf) if row.ort_israf is not None else None,
            }
            for row in gunluk_production
        }

        kategori = _resolve_meal_category(yemek_adi, db)
        trend: list[dict[str, Any]] = []

        for row in gunluk_rating:
            prod = production_map.get(row.tarih, {})
            israf, method = estimate_waste_ratio(
                yemek_adi=yemek_adi,
                kategori=kategori,
                tarih=row.tarih,
                ortalama_puan=float(row.ortalama) if row.ortalama is not None else None,
                toplam_oy=int(row.toplam_oy or 0),
                uretilen_porsiyon=float(prod.get("uretilen") or DEFAULT_PRODUCTION),
                uretim_israf_orani=_clip_israf(prod.get("israf")),
            )
            trend.append(
                {
                    "tarih": str(row.tarih),
                    "ortalama_puan": round(float(row.ortalama), 2) if row.ortalama is not None else None,
                    "israf_skoru": round(israf, 1) if israf is not None else None,
                    "toplam_oy": int(row.toplam_oy or 0),
                    "tahmin_metodu": method,
                }
            )

        # Puan trendi yoksa production trendini dondur.
        if not trend:
            for row in gunluk_production:
                israf, method = estimate_waste_ratio(
                    yemek_adi=yemek_adi,
                    kategori=kategori,
                    tarih=row.tarih,
                    ortalama_puan=None,
                    toplam_oy=0,
                    uretilen_porsiyon=float(row.ort_uretilen or 0.0),
                    uretim_israf_orani=float(row.ort_israf) if row.ort_israf is not None else None,
                )
                trend.append(
                    {
                        "tarih": str(row.tarih),
                        "ortalama_puan": None,
                        "israf_skoru": round(israf, 1) if israf is not None else None,
                        "toplam_oy": 0,
                        "tahmin_metodu": method,
                    }
                )

        genel = calculate_waste_score(yemek_adi, db)
        return {
            "success": True,
            "yemek_adi": yemek_adi,
            "donem_gun": gun,
            "genel_israf_skoru": genel["israf_skoru"],
            "genel_israf_seviye": genel["israf_seviye"],
            "ortalama_puan": genel["ortalama_puan"],
            "tahmin_metodu": genel.get("tahmin_metodu"),
            "trend": trend,
        }
    finally:
        if close_db:
            db.close()
