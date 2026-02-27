"""
Modül 2: Yemek Fotoğrafından Tanıma + Besin Analizi
─────────────────────────────────────────────────────
Kullanıcının yüklediği fotoğraftan yemeği tanıyıp
besin değeri analizi yapan modül.

Kullanılan teknolojiler:
  - YOLO (ultralytics) — nesne tespiti
  - Food-101 dataset — yemek sınıflandırma
  - Pillow — görüntü işleme
"""

from pathlib import Path
from typing import Any

# ─── Sabitler ──────────────────────────────────────────────────────
# Food-101 veya Türk yemekleri sınıf listesi (placeholder)
YEMEK_SINIFLARI = [
    "mercimek_corbasi",
    "tavuk_sote",
    "pirinc_pilavi",
    "sutlac",
    "mevsim_salata",
    "karniyarik",
    "iskender",
    "lahmacun",
    "pide",
    "baklava",
    "corba",
    "kofte",
    "makarna",
    "pizza",
    "hamburger",
]


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Model Yükleme
# ═══════════════════════════════════════════════════════════════════
def load_model(model_path: str | None = None) -> Any:
    """
    YOLO veya özel eğitilmiş yemek tanıma modelini yükler.

    Args:
        model_path: Model dosyasının yolu.
            None ise varsayılan model kullanılır.

    Returns:
        Yüklenen model nesnesi (şu an placeholder olarak None).

    TODO:
        - ultralytics.YOLO ile model yükleme
        - Özel eğitilmiş Food-101 fine-tuned model desteği
        - Model cache mekanizması
    """
    print(f"⏳ Yemek tanıma modeli yükleniyor: {model_path or 'varsayılan'}")

    # TODO: Gerçek model yükleme
    # from ultralytics import YOLO
    # model = YOLO(model_path or "yolov8n.pt")
    model = None

    print("✅ Model yüklendi (placeholder).")
    return model


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Yemek Tanıma
# ═══════════════════════════════════════════════════════════════════
def recognize_food(
    model: Any,
    image_path: str,
    confidence_threshold: float = 0.5,
) -> list[dict]:
    """
    Verilen fotoğraftan yemekleri tanıyıp sınıflandırır.

    Args:
        model: Yüklü yemek tanıma modeli.
        image_path: Fotoğraf dosyasının yolu.
        confidence_threshold: Minimum güven eşiği (0.0 - 1.0).

    Returns:
        list[dict]: Tanınan yemekler listesi.
            Her dict:
            {
                "yemek_adi": str,
                "guven_skoru": float,
                "bbox": [x1, y1, x2, y2]  (opsiyonel)
            }

    TODO:
        - YOLO inference çalıştırma
        - Bounding box çıkarma
        - Sınıf adını Türkçe'ye çevirme
        - Birden fazla yemek tespiti
    """
    print(f"🔍 Yemek tanıma yapılıyor: {image_path}")

    # Dosya kontrolü
    if not Path(image_path).exists():
        print(f"❌ Dosya bulunamadı: {image_path}")
        return []

    # TODO: Gerçek inference
    # results = model(image_path)

    # Placeholder sonuç
    placeholder_sonuc = [
        {
            "yemek_adi": "Mercimek Çorbası",
            "guven_skoru": 0.87,
            "bbox": [10, 20, 200, 180],
        }
    ]

    print(f"✅ {len(placeholder_sonuc)} yemek tespit edildi (placeholder).")
    return placeholder_sonuc


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Besin Değeri Sorgula
# ═══════════════════════════════════════════════════════════════════
def get_nutrition_info(yemek_adi: str, db_session=None) -> dict | None:
    """
    Yemek adına göre besin değeri bilgisini veritabanından
    veya sabit listeden getirir.

    Args:
        yemek_adi: Sorgulanan yemeğin adı.
        db_session: SQLAlchemy oturum nesnesi (opsiyonel).

    Returns:
        dict | None: Besin değerleri veya bulunamazsa None.
            {
                "ad": str,
                "kalori": float,
                "protein": float,
                "karbonhidrat": float,
                "yag": float,
            }

    TODO:
        - Veritabanı sorgusu (Yemek tablosu)
        - Fuzzy matching (benzer isim arama)
        - Harici API entegrasyonu (USDA, vb.)
    """
    print(f"🥗 Besin değeri sorgulanıyor: {yemek_adi}")

    # TODO: Gerçek veritabanı sorgusu
    # if db_session:
    #     from models import Yemek
    #     yemek = db_session.query(Yemek).filter(
    #         Yemek.ad.ilike(f"%{yemek_adi}%")
    #     ).first()
    #     if yemek:
    #         return yemek.to_dict()

    # Placeholder
    placeholder_veritabani = {
        "mercimek çorbası": {
            "ad": "Mercimek Çorbası",
            "kalori": 139.0,
            "protein": 9.0,
            "karbonhidrat": 20.0,
            "yag": 3.5,
        },
        "tavuk sote": {
            "ad": "Tavuk Sote",
            "kalori": 220.0,
            "protein": 25.0,
            "karbonhidrat": 8.0,
            "yag": 10.0,
        },
        "pirinç pilavı": {
            "ad": "Pirinç Pilavı",
            "kalori": 180.0,
            "protein": 4.0,
            "karbonhidrat": 38.0,
            "yag": 2.0,
        },
    }

    sonuc = placeholder_veritabani.get(yemek_adi.lower())
    if sonuc:
        print(f"✅ Besin değeri bulundu: {sonuc['ad']}")
    else:
        print(f"⚠️ Besin değeri bulunamadı: {yemek_adi}")

    return sonuc


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Fotoğraftan Tam Analiz
# ═══════════════════════════════════════════════════════════════════
def analyze_food_photo(model: Any, image_path: str, db_session=None) -> dict:
    """
    Fotoğraftan yemek tanıma + besin değeri analizini
    birleştiren üst düzey fonksiyon.

    Args:
        model: Yüklü model nesnesi.
        image_path: Fotoğraf yolu.
        db_session: SQLAlchemy oturumu (opsiyonel).

    Returns:
        dict: {
            "taninan_yemekler": [...],
            "toplam_besin_degeri": {
                "kalori": float,
                "protein": float,
                ...
            }
        }
    """
    taninan = recognize_food(model, image_path)
    toplam = {"kalori": 0, "protein": 0, "karbonhidrat": 0, "yag": 0}

    for yemek in taninan:
        besin = get_nutrition_info(yemek["yemek_adi"], db_session)
        if besin:
            yemek["besin_degeri"] = besin
            toplam["kalori"] += besin.get("kalori", 0)
            toplam["protein"] += besin.get("protein", 0)
            toplam["karbonhidrat"] += besin.get("karbonhidrat", 0)
            toplam["yag"] += besin.get("yag", 0)

    return {
        "taninan_yemekler": taninan,
        "toplam_besin_degeri": toplam,
    }
