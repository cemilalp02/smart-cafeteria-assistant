"""
Modül 1: Menü Optimizasyonu
─────────────────────────────────────────────
Makine öğrenimi ile yemek popülerlik tahmini ve
haftalık menü önerisi oluşturma modülü.

Kullanılan teknolojiler:
  - scikit-learn (RandomForest, vb.)
  - pandas (veri işleme)
  - numpy (sayısal hesaplamalar)
"""

import random
from datetime import date, timedelta
from typing import Any

# ─── Sabitler ──────────────────────────────────────────────────────
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]

KATEGORILER = {
    "corba": "Çorba",
    "ana_yemek": "Ana Yemek",
    "pilav": "Pilav / Makarna",
    "tatli": "Tatlı",
    "salata": "Salata",
}


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Popülerlik Modeli Eğitimi
# ═══════════════════════════════════════════════════════════════════
def train_popularity_model(historical_data: list[dict]) -> Any:
    """
    Geçmiş yemekhane verilerini kullanarak bir popülerlik
    tahmin modeli eğitir.

    Args:
        historical_data: Geçmiş yemek tüketim verileri.
            Her bir dict şunları içermeli:
            - yemek_id (int)
            - tarih (str)
            - tuketim_sayisi (int)
            - hava_durumu (str, opsiyonel)
            - gun (str)

    Returns:
        Eğitilmiş model nesnesi (şu an placeholder olarak None).

    TODO:
        - pandas DataFrame'e dönüştürme
        - Feature engineering (gün, mevsim, hava durumu)
        - scikit-learn RandomForestRegressor ile eğitim
        - Model değerlendirme (MAE, RMSE)
        - Model kaydetme (joblib)
    """
    # Placeholder
    print("⏳ Popülerlik modeli eğitiliyor...")
    print(f"   Toplam {len(historical_data)} kayıt ile eğitim yapılacak.")

    # TODO: Gerçek model eğitimi
    model = None

    print("✅ Model eğitimi tamamlandı (placeholder).")
    return model


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Popülerlik Tahmini
# ═══════════════════════════════════════════════════════════════════
def predict_popularity(model: Any, yemek_adi: str, gun: str) -> float:
    """
    Verilen yemeğin belirtilen gündeki tahmini popülerlik
    skorunu döndürür.

    Args:
        model: Eğitilmiş popülerlik modeli.
        yemek_adi: Yemeğin adı.
        gun: Haftanın günü.

    Returns:
        float: 0.0 - 1.0 arası popülerlik skoru.

    TODO:
        - Modelden gerçek tahmin çıktısı alma
        - Feature vektörü oluşturma
    """
    # Placeholder: rastgele skor döndür
    skor = round(random.uniform(0.3, 1.0), 2)
    print(f"📊 {yemek_adi} ({gun}): Popülerlik skoru = {skor}")
    return skor


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Haftalık Menü Oluştur
# ═══════════════════════════════════════════════════════════════════
def generate_weekly_menu(
    yemek_listesi: list[dict],
    baslangic_tarihi: date | None = None,
) -> list[dict]:
    """
    Popülerlik skorlarına ve dengeye dayalı olarak
    haftalık menü önerisi oluşturur.

    Args:
        yemek_listesi: Veritabanındaki tüm yemeklerin listesi.
            Her dict: {"id", "ad", "kategori", "kalori", ...}
        baslangic_tarihi: Menünün başlangıç tarihi
            (varsayılan: gelecek Pazartesi).

    Returns:
        list[dict]: Her gün için menü önerisi.
            {
                "tarih": "2026-03-02",
                "gun": "Pazartesi",
                "corba": "Mercimek Çorbası",
                "ana_yemek": "Tavuk Sote",
                "pilav": "Pirinç Pilavı",
                "tatli": "Sütlaç",
                "salata": "Mevsim Salata",
            }

    TODO:
        - Popülerlik modeli entegrasyonu
        - Kalori dengesi kontrolü
        - Tekrar yemek yazma önleme
        - Kısıt optimizasyonu (örn. haftada max 2 kez kızartma)
    """
    if baslangic_tarihi is None:
        bugun = date.today()
        # Gelecek Pazartesi
        gun_fark = (7 - bugun.weekday()) % 7
        if gun_fark == 0:
            gun_fark = 7
        baslangic_tarihi = bugun + timedelta(days=gun_fark)

    # Kategoriye göre grupla
    kategoriler_dict: dict[str, list[dict]] = {
        "corba": [],
        "ana_yemek": [],
        "pilav": [],
        "tatli": [],
        "salata": [],
    }

    for yemek in yemek_listesi:
        kat = yemek.get("kategori", "")
        if kat in kategoriler_dict:
            kategoriler_dict[kat].append(yemek)

    # Haftalık menü oluştur
    haftalik_menu = []
    for i, gun in enumerate(GUNLER):
        tarih = baslangic_tarihi + timedelta(days=i)
        gun_menusu = {
            "tarih": str(tarih),
            "gun": gun,
        }

        for kategori_key in kategoriler_dict:
            secenekler = kategoriler_dict[kategori_key]
            if secenekler:
                secilen = random.choice(secenekler)
                gun_menusu[kategori_key] = secilen["ad"]
            else:
                gun_menusu[kategori_key] = "Belirtilmedi"

        haftalik_menu.append(gun_menusu)

    print(f"📅 {len(haftalik_menu)} günlük menü önerisi oluşturuldu.")
    return haftalik_menu


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Menü Skoru Hesapla
# ═══════════════════════════════════════════════════════════════════
def calculate_menu_score(menu: dict, yemek_listesi: list[dict]) -> dict:
    """
    Bir günlük menünün besin değeri dengesini skorlar.

    Args:
        menu: Bir günlük menü dict'i.
        yemek_listesi: Besin değerleri bilgisi içeren yemek listesi.

    Returns:
        dict: {"toplam_kalori": float, "denge_skoru": float}

    TODO:
        - Gerçek besin değeri hesaplaması
        - WHO / Türkiye Beslenme Rehberi standartlarına göre değerlendirme
    """
    # Placeholder
    return {
        "toplam_kalori": round(random.uniform(800, 1200), 0),
        "denge_skoru": round(random.uniform(0.6, 1.0), 2),
    }
