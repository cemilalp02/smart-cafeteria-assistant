"""
Food-101 Dataset → YOLO Format Dönüştürücü
═══════════════════════════════════════════
Food-101 sınıflandırma veri setini YOLOv8
sınıflandırma (classification) formatına çevirir.

ÖNEMLİ NOT:
  Food-101 bir sınıflandırma veri setidir (her resimde tek yemek).
  Bounding-box annotation içermez.
  Bu yüzden YOLOv8 classification (cls) modu için hazırlanır.
  Format: datasets/food101_yolo/train/<class_name>/image.jpg
          datasets/food101_yolo/val/<class_name>/image.jpg

Kullanım:
  python scripts/convert_food101_to_yolo.py
"""

import os
import sys
import shutil
import random
import yaml
from pathlib import Path
from PIL import Image

# Proje kök dizinini path'e ekle
PROJE_KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJE_KOK)

# ─── Ayarlar ──────────────────────────────────────────────────────
FOOD101_DIR = os.path.join(PROJE_KOK, "data", "food-101", "food-101")
OUTPUT_DIR = os.path.join(PROJE_KOK, "datasets", "food101_yolo")
TRAIN_RATIO = 0.80  # %80 train, %20 val
RANDOM_SEED = 42
IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_classes(food101_dir: str) -> list[str]:
    """Food-101 sınıf listesini yükler."""
    classes_file = os.path.join(food101_dir, "meta", "classes.txt")
    if not os.path.exists(classes_file):
        raise FileNotFoundError(f"classes.txt bulunamadı: {classes_file}")

    with open(classes_file, "r", encoding="utf-8") as f:
        classes = [line.strip() for line in f if line.strip()]

    print(f"📋 {len(classes)} sınıf yüklendi.")
    return classes


def load_split_files(food101_dir: str) -> tuple[list[str], list[str]]:
    """
    Food-101 train/test split dosyalarını yükler.
    Her satır: class_name/image_id formatında.
    """
    train_file = os.path.join(food101_dir, "meta", "train.txt")
    test_file = os.path.join(food101_dir, "meta", "test.txt")

    train_list = []
    test_list = []

    if os.path.exists(train_file):
        with open(train_file, "r", encoding="utf-8") as f:
            train_list = [line.strip() for line in f if line.strip()]
        print(f"📁 Train listesi: {len(train_list)} görüntü")

    if os.path.exists(test_file):
        with open(test_file, "r", encoding="utf-8") as f:
            test_list = [line.strip() for line in f if line.strip()]
        print(f"📁 Test listesi : {len(test_list)} görüntü")

    return train_list, test_list


def create_directory_structure(output_dir: str, classes: list[str]):
    """YOLO classification format için dizin yapısını oluşturur."""
    for split in ["train", "val"]:
        for cls in classes:
            dir_path = os.path.join(output_dir, split, cls)
            os.makedirs(dir_path, exist_ok=True)

    print(f"📂 Dizin yapısı oluşturuldu: {output_dir}")


def copy_images(
    food101_dir: str,
    output_dir: str,
    image_list: list[str],
    split: str,
    classes: list[str],
) -> int:
    """
    Görüntüleri Food-101 dizininden YOLO classification dizinine kopyalar.

    Args:
        food101_dir: Food-101 kök dizini
        output_dir: YOLO çıktı dizini
        image_list: class/image_id formatında görüntü listesi
        split: "train" veya "val"
        classes: Kullanılacak sınıf listesi

    Returns:
        Kopyalanan görüntü sayısı
    """
    copied = 0
    skipped = 0
    class_set = set(classes)

    for i, entry in enumerate(image_list):
        # class_name/image_id formatını ayır
        parts = entry.split("/")
        if len(parts) != 2:
            skipped += 1
            continue

        class_name, image_id = parts

        # Sınıf filtreleme
        if class_name not in class_set:
            skipped += 1
            continue

        # Kaynak dosya
        src = os.path.join(food101_dir, "images", class_name, f"{image_id}.jpg")
        if not os.path.exists(src):
            skipped += 1
            continue

        # Hedef dosya
        dst_dir = os.path.join(output_dir, split, class_name)
        dst = os.path.join(dst_dir, f"{image_id}.jpg")

        # Kopyala (zaten varsa atla)
        if not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                print(f"  ⚠️ Kopyalama hatası: {src} → {e}")
                skipped += 1
        else:
            copied += 1  # Zaten mevcut

        # İlerleme göster
        if (i + 1) % 5000 == 0:
            print(f"  📦 {split}: {i + 1}/{len(image_list)} işlendi ({copied} kopyalandı)")

    return copied


def create_data_yaml(output_dir: str, classes: list[str]):
    """
    YOLO classification eğitimi için data.yaml dosyasını oluşturur.
    """
    data_config = {
        "path": output_dir.replace("\\", "/"),
        "train": "train",
        "val": "val",
        "nc": len(classes),
        "names": classes,
    }

    yaml_path = os.path.join(output_dir, "data.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_config, f, default_flow_style=False, allow_unicode=True)

    print(f"\n📄 data.yaml oluşturuldu: {yaml_path}")
    print(f"   Sınıf sayısı: {len(classes)}")
    return yaml_path


def verify_dataset(output_dir: str, classes: list[str]):
    """Oluşturulan dataset'i doğrular."""
    print("\n" + "═" * 60)
    print("  📊 Dataset Doğrulama")
    print("═" * 60)

    total_train = 0
    total_val = 0
    class_stats = []

    for cls in classes:
        train_dir = os.path.join(output_dir, "train", cls)
        val_dir = os.path.join(output_dir, "val", cls)

        train_count = len([f for f in os.listdir(train_dir) if f.endswith(".jpg")]) if os.path.exists(train_dir) else 0
        val_count = len([f for f in os.listdir(val_dir) if f.endswith(".jpg")]) if os.path.exists(val_dir) else 0

        total_train += train_count
        total_val += val_count
        class_stats.append((cls, train_count, val_count))

    # Özet
    print(f"\n  📁 Train toplam : {total_train:,} görüntü")
    print(f"  📁 Val toplam   : {total_val:,} görüntü")
    print(f"  📁 Genel toplam : {total_train + total_val:,} görüntü")
    print(f"  📋 Sınıf sayısı : {len(classes)}")

    if total_train > 0 and total_val > 0:
        ratio = total_train / (total_train + total_val) * 100
        print(f"  📊 Train/Val oranı: %{ratio:.1f} / %{100 - ratio:.1f}")

    # İlk ve son 5 sınıf
    print(f"\n  {'Sınıf':<30} {'Train':>8} {'Val':>8}")
    print(f"  {'─' * 48}")
    for cls, tc, vc in class_stats[:5]:
        print(f"  {cls:<30} {tc:>8} {vc:>8}")
    if len(class_stats) > 10:
        print(f"  {'...':<30} {'...':>8} {'...':>8}")
    for cls, tc, vc in class_stats[-5:]:
        print(f"  {cls:<30} {tc:>8} {vc:>8}")


def main():
    """Ana dönüştürme fonksiyonu."""
    print("=" * 60)
    print("  🍽️  Food-101 → YOLO Classification Dönüştürücü")
    print("=" * 60)

    # 1. Kontrol: Food-101 dizini
    if not os.path.exists(FOOD101_DIR):
        print(f"\n❌ Food-101 dizini bulunamadı: {FOOD101_DIR}")
        print("   Lütfen Food-101 dataset'ini data/food-101/ altına indirin.")
        sys.exit(1)

    images_dir = os.path.join(FOOD101_DIR, "images")
    if not os.path.exists(images_dir):
        print(f"\n❌ images dizini bulunamadı: {images_dir}")
        sys.exit(1)

    # 2. Sınıfları yükle
    classes = load_classes(FOOD101_DIR)

    # 3. Train/Test listelerini yükle
    train_list, test_list = load_split_files(FOOD101_DIR)

    # 4. Kendi train/val split'imizi oluştur
    # Food-101'in kendi train listesini (750/class) train+val olarak kullanıyoruz
    # Food-101'in test listesini (250/class) de ekliyoruz → toplam 1000/class
    # Sonra %80/%20 split yapıyoruz
    print(f"\n🔀 Tüm görüntüler birleştiriliyor ve %{int(TRAIN_RATIO*100)}/%{int((1-TRAIN_RATIO)*100)} split yapılıyor...")

    all_images = train_list + test_list
    print(f"   Toplam görüntü: {len(all_images):,}")

    # Sınıf bazlı split yap (her sınıftan eşit oranda)
    random.seed(RANDOM_SEED)
    our_train = []
    our_val = []

    class_images = {}
    for entry in all_images:
        cls = entry.split("/")[0]
        if cls not in class_images:
            class_images[cls] = []
        class_images[cls].append(entry)

    for cls in classes:
        imgs = class_images.get(cls, [])
        random.shuffle(imgs)
        split_idx = int(len(imgs) * TRAIN_RATIO)
        our_train.extend(imgs[:split_idx])
        our_val.extend(imgs[split_idx:])

    print(f"   Train: {len(our_train):,} görüntü")
    print(f"   Val  : {len(our_val):,} görüntü")

    # 5. Çıktı dizin yapısını oluştur
    if os.path.exists(OUTPUT_DIR):
        print(f"\n⚠️  Mevcut çıktı dizini siliniyor: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    create_directory_structure(OUTPUT_DIR, classes)

    # 6. Görüntüleri kopyala
    print(f"\n📦 Train görüntüleri kopyalanıyor...")
    train_copied = copy_images(FOOD101_DIR, OUTPUT_DIR, our_train, "train", classes)
    print(f"   ✅ {train_copied:,} train görüntü kopyalandı.")

    print(f"\n📦 Val görüntüleri kopyalanıyor...")
    val_copied = copy_images(FOOD101_DIR, OUTPUT_DIR, our_val, "val", classes)
    print(f"   ✅ {val_copied:,} val görüntü kopyalandı.")

    # 7. data.yaml oluştur
    yaml_path = create_data_yaml(OUTPUT_DIR, classes)

    # 8. Doğrulama
    verify_dataset(OUTPUT_DIR, classes)

    print("\n" + "=" * 60)
    print("  ✅ Dönüştürme tamamlandı!")
    print("=" * 60)
    print(f"\n  📁 Çıktı dizini : {OUTPUT_DIR}")
    print(f"  📄 data.yaml    : {yaml_path}")
    print(f"\n  Eğitimi başlatmak için:")
    print(f"  python scripts/train_yolo.py")


if __name__ == "__main__":
    main()
