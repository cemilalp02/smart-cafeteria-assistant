"""
Ortak dependency'ler, yardımcı fonksiyonlar, Pydantic şemaları
ve lazy model loader'lar.

Tüm route modülleri buradaki sembolleri import eder —
böylece circular import riski ortadan kalkar.
"""

import os
import re
import hashlib
import hmac

from fastapi import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config import active_config
from models import (
    get_db,          # noqa: F401  — re-export for routes
    Yemek,           # noqa: F401
    Menu,            # noqa: F401
    MenuPuanlama,    # noqa: F401
    Alert,           # noqa: F401
    UretimLog,       # noqa: F401
)
from modules.chatbot import init_chatbot
from modules.menu_optimizer import load_trained_model


# ═══════════════════════════════════════════════════════════════════
# Jinja2 Templates
# ═══════════════════════════════════════════════════════════════════
os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")


# ═══════════════════════════════════════════════════════════════════
# ADMIN AUTH YARDIMCILARI
# ═══════════════════════════════════════════════════════════════════

def _make_admin_token() -> str:
    """Admin oturumu için imzalı token oluşturur."""
    secret = active_config.SECRET_KEY
    return hmac.new(secret.encode(), b"admin_session", hashlib.sha256).hexdigest()


def _is_admin(request: Request) -> bool:
    """İstekte geçerli admin cookie'si var mı kontrol eder."""
    token = request.cookies.get("admin_token")
    return token == _make_admin_token()


# ═══════════════════════════════════════════════════════════════════
# LAZY MODEL LOADER'LAR
# ═══════════════════════════════════════════════════════════════════

chatbot_model = None
menu_ml_model = None
menu_encoders = None
menu_feature_cols = None


def get_chatbot_model():
    global chatbot_model
    if chatbot_model is None:
        chatbot_model = init_chatbot()
    return chatbot_model


def get_menu_model():
    global menu_ml_model, menu_encoders, menu_feature_cols
    if menu_ml_model is None:
        menu_ml_model, menu_encoders, menu_feature_cols = load_trained_model()
    return menu_ml_model, menu_encoders, menu_feature_cols


# ═══════════════════════════════════════════════════════════════════
# PYDANTIC ŞEMALARI
# ═══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str


class MenuPredictRequest(BaseModel):
    baslangic_tarihi: str | None = None


class RateMealRequest(BaseModel):
    tarih: str
    yemek_adi: str
    kategori: str
    puan: int = Field(..., ge=1, le=5)
    yorum: str | None = None
    israf_self_report: int | None = Field(default=None, ge=0, le=3)


class WasteModelTrainRequest(BaseModel):
    min_samples: int = Field(default=8, ge=4, le=10000)


class ProductionLogRequest(BaseModel):
    tarih: str
    yemek_adi: str
    kategori: str
    uretilen: float = Field(..., gt=0)
    kalan: float = Field(..., ge=0)
    notlar: str | None = None


class BulkProductionLogRequest(BaseModel):
    tarih: str
    girisler: list[dict]


class PushTokenRequest(BaseModel):
    token: str = Field(..., description="Expo Push Token")


class CustomNotificationRequest(BaseModel):
    title: str = Field(..., description="Bildirim başlığı", min_length=1)
    body: str = Field(..., description="Bildirim metni", min_length=1)


# ═══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def _canonicalize_meal_name(name: str) -> str:
    """Yemek adını standart forma çevirir: trim + tek boşluk + title-case."""
    normalized = re.sub(r"\s+", " ", (name or "").strip())
    if not normalized:
        return ""
    return normalized.title()


def _meal_group_key(name: str) -> str:
    """Case-insensitive ve boşluk normalize edilmiş grup anahtarı üretir."""
    normalized = re.sub(r"\s+", " ", (name or "").strip())
    return normalized.casefold()


def _merge_meal_rating_aggregates(rows):
    """
    SQL'den gelen satırları (yemek_adi, kategori, ortalama, toplam_oy)
    yemek adı normalizasyonu ile birleştirir.
    """
    merged = {}

    for row in rows:
        canonical_name = _canonicalize_meal_name(row.yemek_adi)
        key = _meal_group_key(canonical_name)

        if key not in merged:
            merged[key] = {
                "yemek_adi": canonical_name,
                "toplam_oy": 0,
                "puan_toplami": 0.0,
                "kategori_oylari": {},
            }

        oy_sayisi = int(row.toplam_oy or 0)
        merged[key]["toplam_oy"] += oy_sayisi
        merged[key]["puan_toplami"] += float(row.ortalama or 0) * oy_sayisi
        merged[key]["kategori_oylari"][row.kategori] = (
            merged[key]["kategori_oylari"].get(row.kategori, 0) + oy_sayisi
        )

    result = []
    for item in merged.values():
        toplam_oy = item["toplam_oy"]
        ortalama = (item["puan_toplami"] / toplam_oy) if toplam_oy else 0.0

        kategori = "diger"
        if item["kategori_oylari"]:
            kategori_adaylari = set(item["kategori_oylari"].keys())
            if "icecek" in kategori_adaylari and kategori_adaylari.issubset({"salata", "icecek"}):
                kategori = "icecek"
            else:
                kategori = sorted(
                    item["kategori_oylari"].items(),
                    key=lambda x: (x[1], x[0] == "icecek"),
                    reverse=True,
                )[0][0]

        result.append(
            {
                "yemek_adi": item["yemek_adi"],
                "kategori": kategori,
                "ortalama": ortalama,
                "toplam_oy": toplam_oy,
            }
        )

    return result
