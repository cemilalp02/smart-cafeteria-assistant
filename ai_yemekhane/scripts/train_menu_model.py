"""
Menü Popülerlik Modeli Eğitim Scripti
══════════════════════════════════════
data/menu_data.csv dosyasını kullanarak:
  1. Feature engineering
  2. Sentetik popülerlik skoru üretimi
  3. ML model eğitimi (GradientBoosting)
  4. Metrikleri yazdırma
  5. Modeli models_data/ altına kaydetme
  6. Örnek haftalık menü optimizasyonu

Kullanım:
  python scripts/train_menu_model.py
  python scripts/train_menu_model.py --model random_forest
"""

import argparse
import os
import sys
from datetime import date, timedelta

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.menu_optimizer import (
    train_model,
    save_model,
    load_trained_model,
    generate_weekly_menu,
    calculate_menu_score,
)


def main():
    parser = argparse.ArgumentParser(description="Menü Popülerlik Modeli Eğitimi")
    parser.add_argument(
        "--model",
        choices=["gradient_boosting", "random_forest"],
        default="gradient_boosting",
        help="Model tipi (varsayılan: gradient_boosting)",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.20,
        help="Test set oranı (varsayılan: 0.20)",
    )
    parser.add_argument(
        "--cv",
        type=int,
        default=5,
        help="Cross-validation fold sayısı (varsayılan: 5)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Modeli kaydetme",
    )
    args = parser.parse_args()

    # CSV yolu
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "menu_data.csv")
    if not os.path.exists(csv_path):
        print(f"❌ CSV dosyası bulunamadı: {csv_path}")
        print("   Önce data/menu_data.csv dosyasını oluşturun.")
        sys.exit(1)

    # ── Model eğitimi ─────────────────────────────────────────────
    result = train_model(
        csv_path=csv_path,
        model_type=args.model,
        test_size=args.test_size,
        cv_folds=args.cv,
        verbose=True,
    )

    model = result["model"]
    encoders = result["encoders"]
    feature_cols = result["feature_cols"]
    metrics = result["metrics"]

    # ── Modeli kaydet ─────────────────────────────────────────────
    if not args.no_save:
        save_model(model, encoders, feature_cols)

    # ── Doğrulama: modeli yükle ve test et ────────────────────────
    print("\n" + "=" * 60)
    print("  🔄 Model Yükleme Doğrulaması")
    print("=" * 60)
    loaded_model, loaded_enc, loaded_cols = load_trained_model()
    if loaded_model is not None:
        print("   ✅ Model başarıyla yüklendi ve kullanıma hazır.")

    # ── Örnek haftalık menü ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("  📅 Örnek Haftalık Menü Optimizasyonu")
    print("=" * 60)

    # DB'den yemek listesi simülasyonu
    yemek_havuzu = []
    df_scored = result["df_scored"]
    for yemek_adi in df_scored["yemek_adi"].unique():
        kategori = df_scored[df_scored["yemek_adi"] == yemek_adi]["kategori"].iloc[0]
        yemek_havuzu.append({"ad": yemek_adi, "kategori": kategori})

    # Gelecek Pazartesi
    bugun = date.today()
    gun_fark = (7 - bugun.weekday()) % 7
    if gun_fark == 0:
        gun_fark = 7
    pazartesi = bugun + timedelta(days=gun_fark)

    haftalik = generate_weekly_menu(
        yemek_listesi=yemek_havuzu,
        baslangic_tarihi=pazartesi,
        model=model,
        encoders=encoders,
        feature_cols=feature_cols,
    )

    for gun_menu in haftalik:
        print(f"\n  📌 {gun_menu['gun']} ({gun_menu['tarih']})")
        for kat in ["corba", "ana_yemek", "pilav", "tatli", "salata"]:
            yemek = gun_menu.get(kat, "-")
            skor = gun_menu.get(f"{kat}_skor", "-")
            emoji = {"corba": "🥣", "ana_yemek": "🍖", "pilav": "🍚",
                     "tatli": "🍰", "salata": "🥗"}.get(kat, "🍽️")
            print(f"     {emoji} {kat:12s}: {yemek:25s} (skor: {skor})")

    # Toplam skor
    toplam = calculate_menu_score(haftalik)
    print(f"\n  📊 Menü Toplam Skor: {toplam['toplam']:.3f}")
    print(f"     Ortalama: {toplam['ortalama']:.3f} | "
          f"Min: {toplam['min']:.3f} | Max: {toplam['max']:.3f}")

    print("\n" + "=" * 60)
    print("  🎉 Eğitim ve optimizasyon tamamlandı!")
    print("=" * 60)


if __name__ == "__main__":
    main()
