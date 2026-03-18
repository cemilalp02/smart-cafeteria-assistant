"""
AI Akilli Yemekhane Asistan Sistemi - Israf Analizi Modulu

Bu modul iki sekilde calisir:
1) Egitilmis israf modeli varsa: puan + uretim sinyallerinden ML tahmini
2) Model yoksa: kural tabanli fallback (puan -> israf)

Not: ML modeli gercek hedef olarak UretimLog.israf_orani kullanir.
"""

from __future__ import annotations

import math
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from models import MenuPuanlama, SessionLocal, UretimLog

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
WASTE_FEATURE_COLUMNS = [
    "yemek_adi",
    "kategori",
    "gun_hafta",
    "ay",
    "uretilen_porsiyon",
    "rating_avg",
    "rating_count",
]
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
    """UretimLog (hedef) + puanlama sinyalleri ile egitim dataframe'i uretir."""
    rating_day_map, rating_meal_map = _build_rating_maps(db)
    prod_day_map, prod_meal_map = _build_production_maps(db)

    logs = (
        db.query(UretimLog)
        .filter(UretimLog.uretilen_porsiyon > 0, UretimLog.israf_orani.isnot(None))
        .all()
    )

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

        records.append(
            {
                "yemek_adi": meal_name or "Bilinmeyen",
                "kategori": log.kategori or "diger",
                "gun_hafta": int(log.tarih.weekday()),
                "ay": int(log.tarih.month),
                "uretilen_porsiyon": float(uretilen_porsiyon),
                "rating_avg": float(rating_avg),
                "rating_count": int(rating_count),
                "target_israf": float(log.israf_orani or 0.0),
            }
        )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["target_israf"] = df["target_israf"].clip(lower=0, upper=100)
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


def train_waste_model_from_db(
    db: Optional[Session] = None,
    min_samples: int = MIN_TRAIN_SAMPLES,
) -> dict[str, Any]:
    """
    Gercek israf hedefiyle modeli egitir ve diske kaydeder.

    Hedef:
      - UretimLog.israf_orani (gercek saha verisi)
    Ozellikler:
      - yemek_adi, kategori, gun/ay, uretilen_porsiyon, puan ortalamasi, oy sayisi
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

        X = df[WASTE_FEATURE_COLUMNS]
        y = df["target_israf"]

        cat_cols = ["yemek_adi", "kategori"]
        num_cols = [
            "gun_hafta",
            "ay",
            "uretilen_porsiyon",
            "rating_avg",
            "rating_count",
        ]

        preprocessor = ColumnTransformer(
            transformers=[
                ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
                ("num", "passthrough", num_cols),
            ]
        )
        regressor = RandomForestRegressor(
            n_estimators=250,
            max_depth=12,
            min_samples_leaf=1,
            random_state=42,
            n_jobs=-1,
        )
        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("regressor", regressor),
            ]
        )

        metrics: dict[str, float | str]
        if sample_count >= 12:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=0.2,
                random_state=42,
            )
            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)

            metrics = {
                "mae_test": round(float(mean_absolute_error(y_test, y_pred)), 3),
                "rmse_test": round(float(math.sqrt(mean_squared_error(y_test, y_pred))), 3),
                "r2_test": round(float(r2_score(y_test, y_pred)), 3),
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

        os.makedirs(MODEL_DIR, exist_ok=True)
        model_bundle = {
            "pipeline": pipeline,
            "feature_columns": list(WASTE_FEATURE_COLUMNS),
            "trained_at": datetime.utcnow().isoformat() + "Z",
            "sample_count": sample_count,
            "model_type": "RandomForestRegressor",
        }
        joblib.dump(model_bundle, WASTE_MODEL_PATH)

        global _cached_waste_model
        _cached_waste_model = model_bundle

        return {
            "success": True,
            "message": "Israf ML modeli basariyla egitildi.",
            "model_path": WASTE_MODEL_PATH,
            "sample_count": sample_count,
            "metrics": metrics,
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

        return {
            "success": True,
            "model_exists": model_bundle is not None,
            "model_path": WASTE_MODEL_PATH,
            "trained_at": (model_bundle or {}).get("trained_at"),
            "model_sample_count": (model_bundle or {}).get("sample_count"),
            "training_data_count": int(training_data_count),
            "fallback_active": model_bundle is None,
        }
    finally:
        if close_db:
            db.close()


def _predict_waste_with_ml(
    yemek_adi: str,
    kategori: str,
    tarih: date,
    ortalama_puan: float,
    toplam_oy: int,
    uretilen_porsiyon: float,
) -> float | None:
    model_bundle = load_waste_model()
    if model_bundle is None:
        return None

    pipeline = model_bundle.get("pipeline")
    if pipeline is None:
        return None

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
) -> tuple[float | None, str]:
    """
    Sirali karar:
      1) ML model
      2) Gercek uretim israf ortalamasi
      3) Kural tabanli puan -> israf
      4) Veri yok
    """
    rating_avg = float(ortalama_puan) if ortalama_puan is not None else DEFAULT_RATING_AVG
    rating_count = int(toplam_oy or 0)
    production = float(uretilen_porsiyon) if uretilen_porsiyon and uretilen_porsiyon > 0 else DEFAULT_PRODUCTION

    ml_pred = _predict_waste_with_ml(
        yemek_adi=yemek_adi,
        kategori=kategori,
        tarih=tarih,
        ortalama_puan=rating_avg,
        toplam_oy=rating_count,
        uretilen_porsiyon=production,
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
