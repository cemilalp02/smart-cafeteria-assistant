"""
Yemek Tanıma Test Scripti
══════════════════════════
Eğitilmiş YOLOv8 modelini test eder.

Kullanım:
  python scripts/test_food_recognition.py
  python scripts/test_food_recognition.py --image path/to/food.jpg
  python scripts/test_food_recognition.py --dir path/to/images/
"""

import os
import sys
import json
import argparse
import random
from pathlib import Path

# Proje kök dizinini path'e ekle
PROJE_KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJE_KOK)

from modules.food_recognizer import (
    load_model, load_ensemble_models,
    recognize_food, recognize_food_ensemble,
    analyze_food_photo, get_nutrition_info,
)


def find_sample_images(num_samples: int = 5) -> list[str]:
    """
    Food-101 dataset'inden rastgele örnek görüntüler seçer.
    """
    images_dir = os.path.join(PROJE_KOK, "datasets", "turkish_food", "val")
    if not os.path.exists(images_dir):
        # Eski dataset'ten dene
        images_dir = os.path.join(PROJE_KOK, "datasets", "food101_yolo", "val")

    if not os.path.exists(images_dir):
        print("⚠️ Örnek görüntü dizini bulunamadı.")
        return []

    all_images = []
    for class_dir in os.listdir(images_dir):
        class_path = os.path.join(images_dir, class_dir)
        if os.path.isdir(class_path):
            for img_file in os.listdir(class_path):
                if img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                    all_images.append(os.path.join(class_path, img_file))

    if not all_images:
        print("⚠️ Hiç görüntü bulunamadı.")
        return []

    # Rastgele seç
    random.seed(42)
    samples = random.sample(all_images, min(num_samples, len(all_images)))
    return samples


def test_single_image(model, image_path: str, db_session=None):
    """Tek bir görüntü ile test yapar."""
    print(f"\n{'═' * 60}")
    print(f"  📸 Test: {os.path.basename(image_path)}")
    print(f"{'═' * 60}")

    # Tam analiz
    sonuc = analyze_food_photo(model, image_path, db_session)

    # JSON format göster
    print(f"\n📋 Sonuç (JSON):")
    print(json.dumps(sonuc, indent=2, ensure_ascii=False))

    # Özet
    if sonuc["en_olasi_yemek"]:
        ey = sonuc["en_olasi_yemek"]
        print(f"\n  🏆 En olası: {ey['yemek']} ({ey['yemek_en']})")
        print(f"     Güven  : %{ey['guven']*100:.1f}")
        print(f"     Kalori : {ey['kalori']} kcal")
        print(f"     Protein: {ey['protein']}g")
        print(f"     Karb.  : {ey['karbonhidrat']}g")
        print(f"     Yağ    : {ey['yag']}g")

    return sonuc


def test_directory(model, dir_path: str, max_images: int = 10, db_session=None):
    """Bir dizindeki tüm görüntüleri test eder."""
    images = []
    for f in os.listdir(dir_path):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            images.append(os.path.join(dir_path, f))

    if not images:
        print(f"⚠️ Dizinde görüntü bulunamadı: {dir_path}")
        return

    print(f"📁 {len(images)} görüntü bulundu, {min(max_images, len(images))} tanesi test edilecek.")

    correct = 0
    total = 0

    for img_path in images[:max_images]:
        sonuc = test_single_image(model, img_path, db_session)
        total += 1

        # Eğer dosya adında sınıf adı varsa, doğruluğu kontrol et
        parent_dir = os.path.basename(os.path.dirname(img_path))
        if sonuc["en_olasi_yemek"] and parent_dir == sonuc["en_olasi_yemek"]["yemek_en"]:
            correct += 1
            print(f"  ✅ DOĞRU!")
        elif sonuc["en_olasi_yemek"]:
            print(f"  ❓ Gerçek: {parent_dir}")

    if total > 0:
        print(f"\n{'═' * 60}")
        print(f"  📊 Doğruluk: {correct}/{total} (%{correct/total*100:.1f})")
        print(f"{'═' * 60}")


def test_api_format(model, image_path: str):
    """API response formatını test eder."""
    print(f"\n{'═' * 60}")
    print(f"  🌐 API Response Testi")
    print(f"{'═' * 60}")

    sonuc = analyze_food_photo(model, image_path)

    # API'nin döneceği format (main.py'deki gibi)
    api_response = {
        "success": True,
        "message": "Yemek tanıma tamamlandı.",
        "dosya": os.path.basename(image_path),
        "data": sonuc,
    }

    print(f"\n📋 API Response:")
    print(json.dumps(api_response, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Yemek Tanıma Test Scripti")
    parser.add_argument("--image", type=str, help="Test edilecek görüntü yolu")
    parser.add_argument("--dir", type=str, help="Test edilecek görüntü dizini")
    parser.add_argument("--model", type=str, help="Model dosyası (.pt)")
    parser.add_argument("--samples", type=int, default=5, help="Örnek görüntü sayısı")
    parser.add_argument("--ensemble", action="store_true", help="Ensemble modeli kullan (hem Turkish Food hem Food101)")
    parser.add_argument("--no-tta", action="store_true", help="TTA (Test-Time Augmentation) kapatır")
    args = parser.parse_args()

    print("=" * 60)
    print("  🍽️  Yemek Tanıma Test Scripti")
    print("=" * 60)

    # Model yükle
    if args.ensemble:
        print("\n📦 Ensemble mod: Birden fazla model yükleniyor...")
        models = load_ensemble_models()
        model = models[0]  # Tek model gereken testler için
        print(f"✅ {len(models)} model yüklendi.")
    else:
        model = load_model(args.model)
        models = [model]

    # DB session (opsiyonel)
    db_session = None
    try:
        from models import SessionLocal
        db_session = SessionLocal()
        print("✅ Veritabanı bağlantısı kuruldu.")
    except Exception as e:
        print(f"⚠️ Veritabanı bağlantısı kurulamadı: {e}")
        print("   Sabit besin tablosu kullanılacak.")

    try:
        if args.image:
            # Tek görüntü testi
            if not os.path.exists(args.image):
                print(f"❌ Dosya bulunamadı: {args.image}")
                sys.exit(1)
            test_single_image(model, args.image, db_session)
            test_api_format(model, args.image)

        elif args.dir:
            # Dizin testi
            if not os.path.exists(args.dir):
                print(f"❌ Dizin bulunamadı: {args.dir}")
                sys.exit(1)
            test_directory(model, args.dir, db_session=db_session)

        else:
            # Otomatik örnek test
            print(f"\n🔍 Food-101'den {args.samples} örnek görüntü seçiliyor...")
            samples = find_sample_images(args.samples)

            if not samples:
                print("❌ Test görüntüsü bulunamadı.")
                print("   --image veya --dir parametresi ile belirtin.")
                sys.exit(1)

            for img_path in samples:
                test_single_image(model, img_path, db_session)

            # Son görüntü ile API format testi
            if samples:
                test_api_format(model, samples[0])

    finally:
        if db_session:
            db_session.close()

    print(f"\n{'=' * 60}")
    print(f"  ✅ Test tamamlandı!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
