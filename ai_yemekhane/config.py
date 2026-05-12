"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - Konfigürasyon Dosyası
"""

import logging
import os
import sys
from dotenv import load_dotenv

# .env dosyasını yükle (son güncelleme: 2026-05-11)
load_dotenv()

logger = logging.getLogger(__name__)

# Güvensiz varsayılan değerler (prod'da bunlar kullanılırsa fail-fast)
_INSECURE_SECRET_KEYS = {"dev-secret-key-degistir", "buraya-guclu-bir-anahtar-yazin", ""}
_INSECURE_ADMIN_PASSWORDS = {"admin123", "admin", "password", ""}


class Config:
    """Temel konfigürasyon sınıfı."""

    # Flask / Uygulama ayarları
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-degistir")
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Veritabanı ayarları
    # SQLite (varsayılan):  sqlite:///yemekhane.db
    # PostgreSQL:           postgresql://user:pass@localhost:5432/yemekhane
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'yemekhane.db')}"
    )

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    # API anahtarları
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Admin şifresi
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # Uygulama ayarları
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8001"))


class DevelopmentConfig(Config):
    """Geliştirme ortamı konfigürasyonu."""


class ProductionConfig(Config):
    """Üretim ortamı konfigürasyonu."""
    DEBUG = False


# Aktif konfigürasyon
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}

_active_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))
active_config = config_map.get(_active_env, DevelopmentConfig)()


# ═══════════════════════════════════════════════════════════════════
# GÜVENLİK KONTROLÜ
# ═══════════════════════════════════════════════════════════════════
def _validate_production_secrets():
    """Production ortamında zayıf default'lar varsa fail-fast."""
    errors = []
    if active_config.SECRET_KEY in _INSECURE_SECRET_KEYS:
        errors.append(
            "SECRET_KEY production'da varsayılan/boş olamaz. .env dosyasında güçlü bir değer atayın."
        )
    if active_config.ADMIN_PASSWORD in _INSECURE_ADMIN_PASSWORDS:
        errors.append(
            "ADMIN_PASSWORD production'da varsayılan/boş olamaz. .env dosyasında güçlü bir değer atayın."
        )
    if errors:
        for e in errors:
            logger.error("[GÜVENLİK] %s", e)
        print("\n[GÜVENLİK HATASI] Production ortamı güvensiz yapılandırmayla başlatılamaz:\n  - "
              + "\n  - ".join(errors), file=sys.stderr)
        sys.exit(1)


def _warn_dev_secrets():
    """Development'ta zayıf default varsa uyarı logla (fail etme)."""
    if active_config.SECRET_KEY in _INSECURE_SECRET_KEYS:
        logger.warning(
            "[GÜVENLİK UYARISI] SECRET_KEY varsayılan değerde. Production'a geçmeden önce .env'de değiştirin."
        )
    if active_config.ADMIN_PASSWORD in _INSECURE_ADMIN_PASSWORDS:
        logger.warning(
            "[GÜVENLİK UYARISI] ADMIN_PASSWORD varsayılan değerde ('admin123'). Production'a geçmeden önce .env'de değiştirin."
        )


if _active_env == "production":
    _validate_production_secrets()
else:
    _warn_dev_secrets()
