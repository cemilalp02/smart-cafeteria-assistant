"""
Birleşik Dataset Hazırlığı
══════════════════════════
Food101 (101 sınıf) + Turkish Food (102 sınıf) datasetlerini
tek bir "combined_food" klasöründe birleştirir.

Örtüşen sınıflar (baklava, omelette vb.) birleştirilir.
Sonuç: ~200 sınıflık tek dataset.

Kullanım:
  python scripts/prepare_combined_dataset.py
"""

import os
import sys
import shutil
from pathlib import Path
from collections import defaultdict

PROJE_KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FOOD101_DIR = os.path.join(PROJE_KOK, "datasets", "food101_yolo")
TURKISH_DIR = os.path.join(PROJE_KOK, "datasets", "turkish_food")
OUTPUT_DIR = os.path.join(PROJE_KOK, "datasets", "combined_food")

# Örtüşen sınıfları eşleştir (Food101 adı → Turkish Food adı)
# Bu sınıflar aynı yemek, sadece farklı isimle
OVERLAP_MAP = {
    "baklava": "baklava",           # Aynı isim
    "omelette": "omlet",            # Food101: omelette → Turkish: omlet
    "ice_cream": "dondurma",        # Food101: ice_cream → Turkish: dondurma
    "french_fries": "patates-kizartmasi",  # Benzer
}


def count_images(directory):
    """Bir dizindeki resim sayısını döndürür."""
    count = 0
    if os.path.exists(directory):
        for f in os.listdir(directory):
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                count += 1
    return count


def copy_images(src_dir, dst_dir, prefix=""):
    """Resimleri kaynak dizinden hedef dizine kopyalar."""
    os.makedirs(dst_dir, exist_ok=True)
    copied = 0
    if not os.path.exists(src_dir):
        return 0

    for f in os.listdir(src_dir):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            src = os.path.join(src_dir, f)
            # Çakışma olmaması için prefix ekle
            if prefix:
                dst = os.path.join(dst_dir, f"{prefix}_{f}")
            else:
                dst = os.path.join(dst_dir, f)

            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                copied += 1
    return copied


def main():
    print("=" * 60)
    print("  🍽️  Birleşik Dataset Hazırlama")
    print("  Food101 + Turkish Food → combined_food")
    print("=" * 60)

    # Kaynak datasetleri kontrol et
    if not os.path.exists(FOOD101_DIR):
        print(f"❌ Food101 dataset bulunamadı: {FOOD101_DIR}")
        sys.exit(1)

    if not os.path.exists(TURKISH_DIR):
        print(f"❌ Turkish Food dataset bulunamadı: {TURKISH_DIR}")
        sys.exit(1)

    # Çıktı dizinini oluştur
    if os.path.exists(OUTPUT_DIR):
        print(f"⚠️ Eski combined_food dizini siliniyor...")
        shutil.rmtree(OUTPUT_DIR)

    os.makedirs(os.path.join(OUTPUT_DIR, "train"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "val"), exist_ok=True)

    # Turkish Food sınıflarını listele
    turkish_classes = set()
    turkish_train = os.path.join(TURKISH_DIR, "train")
    for d in os.listdir(turkish_train):
        if os.path.isdir(os.path.join(turkish_train, d)):
            turkish_classes.add(d)

    # Food101 sınıflarını listele
    food101_classes = set()
    food101_train = os.path.join(FOOD101_DIR, "train")
    for d in os.listdir(food101_train):
        if os.path.isdir(os.path.join(food101_train, d)):
            food101_classes.add(d)

    print(f"\n📊 Kaynak Bilgileri:")
    print(f"   Turkish Food: {len(turkish_classes)} sınıf")
    print(f"   Food101     : {len(food101_classes)} sınıf")

    # Örtüşen sınıfları bul
    overlap_food101 = set(OVERLAP_MAP.keys())
    overlap_turkish = set(OVERLAP_MAP.values())

    # Tüm sınıfları birleştir
    combined_classes = set()
    class_stats = defaultdict(lambda: {"train": 0, "val": 0})

    # 1. TURKISH FOOD sınıflarını kopyala (öncelikli)
    print(f"\n📁 Turkish Food sınıfları kopyalanıyor...")
    for split in ["train", "val"]:
        src_base = os.path.join(TURKISH_DIR, split)
        for class_name in sorted(turkish_classes):
            src = os.path.join(src_base, class_name)
            dst = os.path.join(OUTPUT_DIR, split, class_name)
            copied = copy_images(src, dst)
            class_stats[class_name][split] += copied
            combined_classes.add(class_name)

    turkish_copied = len(turkish_classes)
    print(f"   ✅ {turkish_copied} sınıf kopyalandı")

    # 2. FOOD101 sınıflarını kopyala
    print(f"\n📁 Food101 sınıfları kopyalanıyor...")
    food101_new = 0
    food101_merged = 0
    for split in ["train", "val"]:
        src_base = os.path.join(FOOD101_DIR, split)
        for class_name in sorted(food101_classes):
            src = os.path.join(src_base, class_name)

            if class_name in OVERLAP_MAP:
                # Örtüşen sınıf → Turkish Food sınıfına ekle
                target_name = OVERLAP_MAP[class_name]
                dst = os.path.join(OUTPUT_DIR, split, target_name)
                copied = copy_images(src, dst, prefix="f101")
                class_stats[target_name][split] += copied
                if split == "train":
                    food101_merged += 1
            else:
                # Yeni sınıf → direkt kopyala
                dst = os.path.join(OUTPUT_DIR, split, class_name)
                copied = copy_images(src, dst)
                class_stats[class_name][split] += copied
                combined_classes.add(class_name)
                if split == "train":
                    food101_new += 1

    print(f"   ✅ {food101_new} yeni sınıf eklendi")
    print(f"   🔗 {food101_merged} sınıf örtüşen Turkish Food sınıfına birleştirildi")

    # Sonuçları göster
    total_train = sum(s["train"] for s in class_stats.values())
    total_val = sum(s["val"] for s in class_stats.values())

    print(f"\n{'=' * 60}")
    print(f"  📊 Birleşik Dataset Sonuçları")
    print(f"{'=' * 60}")
    print(f"   Toplam Sınıf  : {len(combined_classes)}")
    print(f"   Train Görüntü : {total_train:,}")
    print(f"   Val Görüntü   : {total_val:,}")
    print(f"   Çıktı Dizini  : {OUTPUT_DIR}")

    # classes.txt oluştur
    classes_file = os.path.join(OUTPUT_DIR, "classes.txt")
    sorted_classes = sorted(combined_classes)
    with open(classes_file, "w", encoding="utf-8") as f:
        for i, cls in enumerate(sorted_classes):
            f.write(f"{i}: {cls}\n")
    print(f"   Sınıflar      : {classes_file}")

    # En az/en çok görüntülü sınıflar
    print(f"\n📈 Sınıf Dağılımı (ilk 10):")
    by_count = sorted(class_stats.items(), key=lambda x: x[1]["train"], reverse=True)
    for name, stats in by_count[:10]:
        print(f"   {name:30s} train={stats['train']:5d}  val={stats['val']:5d}")

    print(f"\n📉 En az görüntülü sınıflar:")
    for name, stats in by_count[-5:]:
        print(f"   {name:30s} train={stats['train']:5d}  val={stats['val']:5d}")

    print(f"\n{'=' * 60}")
    print(f"  ✅ Birleşik dataset hazır!")
    print(f"  Eğitim için: python scripts/train_yolo.py --data datasets/combined_food")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
