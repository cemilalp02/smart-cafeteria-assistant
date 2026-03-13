"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - Konfigürasyon Dosyası
"""

import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()


class Config:
    """Temel konfigürasyon sınıfı."""

    # Flask / Uygulama ayarları
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-degistir")
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Veritabanı ayarları
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'yemekhane.db')}"
    )

    # API anahtarları
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Admin şifresi
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # Dosya yükleme ayarları
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # YOLO model ayarları
    YOLO_MODEL_PATH = os.getenv(
        "YOLO_MODEL_PATH",
        # combined model eğitilince otomatik o kullanılır (load_model sırası)
        # Şimdilik çalışan Food101 modeli varsayılan
        os.path.join(BASE_DIR, "models_data", "food_yolov8s_best.pt")
    )

    # Uygulama ayarları
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))


class DevelopmentConfig(Config):
    """Geliştirme ortamı konfigürasyonu."""
    DEBUG = True


class ProductionConfig(Config):
    """Üretim ortamı konfigürasyonu."""
    DEBUG = False


# Aktif konfigürasyon
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}

active_config = config_map.get(
    os.getenv("FLASK_ENV", "development"),
    DevelopmentConfig
)
