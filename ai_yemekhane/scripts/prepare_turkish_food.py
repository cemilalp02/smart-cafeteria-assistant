"""
Türk Yemekleri Archive Dataset → YOLO Classification Format
═══════════════════════════════════════════════════════════════
archive/Turkish Food/ dizinindeki 102 sınıf Türk yemekleri
datasetini YOLOv8 classification eğitimine uygun formata
dönüştürür.

Yapı:
  archive/Turkish Food/<sinif-adi>/*.jpg
    →
  datasets/turkish_food/train/<sinif-adi>/*.jpg
  datasets/turkish_food/val/<sinif-adi>/*.jpg

Kullanım:
  python scripts/prepare_turkish_food.py
  python scripts/prepare_turkish_food.py --ratio 0.85
"""

import os
import sys
import shutil
import random
import argparse
from pathlib import Path
from datetime import datetime

# Proje kök dizinini path'e ekle
PROJE_KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJE_KOK)

# ─── Varsayılan Ayarlar ──────────────────────────────────────────
ARCHIVE_DIR = os.path.abspath(os.path.join(PROJE_KOK, "..", "archive", "Turkish Food"))
OUTPUT_DIR = os.path.join(PROJE_KOK, "datasets", "turkish_food")
TRAIN_RATIO = 0.80  # %80 train, %20 val
RANDOM_SEED = 42
IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    """Komut satırı argümanlarını okur."""
    parser = argparse.ArgumentParser(
        description="Türk Yemekleri Dataset Hazırlayıcı",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--archive", type=str, default=ARCHIVE_DIR,
                        help="Archive/Turkish Food dizini yolu")
    parser.add_argument("--output", type=str, default=OUTPUT_DIR,
                        help="Çıktı dizini (YOLO format)")
    parser.add_argument("--ratio", type=float, default=TRAIN_RATIO,
                        help="Train oranı (0.0 - 1.0)")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED,
                        help="Random seed")
    parser.add_argument("--copy", action="store_true", default=True,
                        help="Dosyaları kopyala (varsayılan)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Dosya kopyalamadan sadece plan göster")
    return parser.parse_args()


def discover_classes(archive_dir: str) -> list[str]:
    """
    Archive dizinindeki tüm yemek sınıflarını keşfeder.
    
    Returns:
        Sıralı sınıf adları listesi
    """
    if not os.path.exists(archive_dir):
        print(f"❌ Archive dizini bulunamadı: {archive_dir}")
        sys.exit(1)

    classes = sorted([
        d for d in os.listdir(archive_dir)
        if os.path.isdir(os.path.join(archive_dir, d))
    ])

    if not classes:
        print(f"❌ Archive dizininde sınıf klasörü bulunamadı: {archive_dir}")
        sys.exit(1)

    return classes


def get_class_images(archive_dir: str, class_name: str) -> list[str]:
    """Bir sınıfa ait tüm görüntü dosyalarını getirir."""
    class_dir = os.path.join(archive_dir, class_name)
    images = [
        f for f in os.listdir(class_dir)
        if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS
    ]
    return sorted(images)


def split_images(images: list[str], train_ratio: float, seed: int) -> tuple[list[str], list[str]]:
    """Görüntüleri train/val olarak böler."""
    rng = random.Random(seed)
    shuffled = images.copy()
    rng.shuffle(shuffled)

    split_idx = int(len(shuffled) * train_ratio)
    train = shuffled[:split_idx]
    val = shuffled[split_idx:]

    return train, val


def create_directory_structure(output_dir: str, classes: list[str]):
    """YOLO classification dizin yapısını oluşturur."""
    for split in ["train", "val"]:
        for cls in classes:
            dir_path = os.path.join(output_dir, split, cls)
            os.makedirs(dir_path, exist_ok=True)


def copy_images(
    archive_dir: str,
    output_dir: str,
    class_name: str,
    train_images: list[str],
    val_images: list[str],
) -> tuple[int, int]:
    """
    Görüntüleri archive'dan YOLO dizinine kopyalar.
    
    Returns:
        (train_count, val_count) kopyalanan dosya sayıları
    """
    train_count = 0
    val_count = 0
    src_dir = os.path.join(archive_dir, class_name)

    for img in train_images:
        src = os.path.join(src_dir, img)
        dst = os.path.join(output_dir, "train", class_name, img)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        train_count += 1

    for img in val_images:
        src = os.path.join(src_dir, img)
        dst = os.path.join(output_dir, "val", class_name, img)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        val_count += 1

    return train_count, val_count


def verify_dataset(output_dir: str, classes: list[str]):
    """Oluşturulan dataset'i doğrular."""
    print(f"\n{'═' * 60}")
    print(f"  📊 Dataset Doğrulama Raporu")
    print(f"{'═' * 60}")

    total_train = 0
    total_val = 0
    min_train = float("inf")
    max_train = 0
    min_val = float("inf")
    max_val = 0
    min_train_cls = ""
    max_train_cls = ""

    for cls in classes:
        train_dir = os.path.join(output_dir, "train", cls)
        val_dir = os.path.join(output_dir, "val", cls)

        train_count = len([f for f in os.listdir(train_dir)
                          if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS]) if os.path.exists(train_dir) else 0
        val_count = len([f for f in os.listdir(val_dir)
                        if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS]) if os.path.exists(val_dir) else 0

        total_train += train_count
        total_val += val_count

        if train_count < min_train:
            min_train = train_count
            min_train_cls = cls
        if train_count > max_train:
            max_train = train_count
            max_train_cls = cls

    print(f"\n  ✅ Sınıf Sayısı : {len(classes)}")
    print(f"  📁 Train Toplam : {total_train:,} görüntü")
    print(f"  📁 Val Toplam   : {total_val:,} görüntü")
    print(f"  📊 Toplam       : {total_train + total_val:,} görüntü")
    print(f"\n  📈 Train sınıf başına:")
    print(f"     Min: {min_train} ({min_train_cls})")
    print(f"     Max: {max_train} ({max_train_cls})")
    print(f"     Ort: {total_train / len(classes):.0f}")

    # Sınıf listesini kaydet
    class_list_path = os.path.join(output_dir, "classes.txt")
    with open(class_list_path, "w", encoding="utf-8") as f:
        for i, cls in enumerate(classes):
            f.write(f"{i}: {cls}\n")
    print(f"\n  📝 Sınıf listesi: {class_list_path}")

    return total_train, total_val


def main():
    args = parse_args()

    print("=" * 60)
    print("  🍽️  Türk Yemekleri Dataset Hazırlayıcı")
    print("=" * 60)
    print(f"  Kaynak   : {args.archive}")
    print(f"  Çıktı    : {args.output}")
    print(f"  Oran     : %{args.ratio*100:.0f} train / %{(1-args.ratio)*100:.0f} val")
    print(f"  Seed     : {args.seed}")
    print(f"  Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Sınıfları keşfet
    print(f"\n{'─' * 60}")
    print("  📂 Sınıflar keşfediliyor...")
    classes = discover_classes(args.archive)
    print(f"  ✅ {len(classes)} sınıf bulundu:")
    for i, cls in enumerate(classes):
        print(f"     {i+1:3d}. {cls}")

    # 2. Dizin yapısını oluştur
    if not args.dry_run:
        print(f"\n{'─' * 60}")
        print("  📁 Dizin yapısı oluşturuluyor...")
        create_directory_structure(args.output, classes)
        print("  ✅ Dizin yapısı hazır.")

    # 3. Her sınıf için görüntüleri böl ve kopyala
    print(f"\n{'─' * 60}")
    print("  📸 Görüntüler bölünüyor ve kopyalanıyor...")

    grand_train = 0
    grand_val = 0

    for i, cls in enumerate(classes):
        images = get_class_images(args.archive, cls)
        train_imgs, val_imgs = split_images(images, args.ratio, args.seed)

        if args.dry_run:
            print(f"  [{i+1:3d}/{len(classes)}] {cls}: {len(images)} → "
                  f"train={len(train_imgs)}, val={len(val_imgs)}")
            grand_train += len(train_imgs)
            grand_val += len(val_imgs)
        else:
            tc, vc = copy_images(args.archive, args.output, cls, train_imgs, val_imgs)
            grand_train += tc
            grand_val += vc
            pct = (i + 1) / len(classes) * 100
            print(f"  [{i+1:3d}/{len(classes)}] {cls}: {tc} train + {vc} val = {tc+vc} "
                  f"({pct:.0f}%)")

    print(f"\n  📊 Özet: {grand_train:,} train + {grand_val:,} val = "
          f"{grand_train + grand_val:,} toplam")

    if args.dry_run:
        print("\n  ⚠️ DRY RUN — dosya kopyalanmadı.")
        return

    # 4. Doğrulama
    verify_dataset(args.output, classes)

    print(f"\n{'=' * 60}")
    print(f"  🎉 Dataset hazırlığı tamamlandı!")
    print(f"  ⏱️ Bitiş: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")
    print(f"\n  Sonraki adım — eğitimi başlatmak için:")
    print(f"  python scripts/train_yolo.py")


if __name__ == "__main__":
    main()
