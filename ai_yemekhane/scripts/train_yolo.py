"""
YOLOv8 Yemek Tanıma Model Eğitimi
══════════════════════════════════
102 sınıf Türk Yemekleri + Food101 birleşik dataseti üzerinde
YOLOv8 classification modelini fine-tune eder.

Kullanılan teknikler:
  - Transfer learning: yolov8s-cls.pt (small, pre-trained)
  - Early stopping: patience=30
  - Optimizer: AdamW, lr=0.001
  - Dropout: 0.3 (overfitting önleyici)
  - Freeze: ilk 10 katman (transfer learning iyileştirme)
  - Data augmentation: mosaic, mixup, hsv, flip, rotate
  - 100 epoch, 640px, batch=16

Önce dataset hazırlığını yapın:
  python scripts/prepare_turkish_food.py

Kullanım:
  python scripts/train_yolo.py
  python scripts/train_yolo.py --epochs 50 --batch 8  (özel ayarlar)
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime

# Proje kök dizinini path'e ekle
PROJE_KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJE_KOK)

# ─── Varsayılan Eğitim Parametreleri ─────────────────────────────
DEFAULT_CONFIG = {
    # Food101 eğitilmiş model üzerine fine-tune (yemek feature'larını zaten biliyor)
    "model": os.path.join(PROJE_KOK, "runs", "classify", "food101_yolov8s", "weights", "best.pt"),
    "data": os.path.join(PROJE_KOK, "datasets", "combined_food"),
    "epochs": 100,
    "imgsz": 640,
    "batch": 16,
    "patience": 30,                  # Early stopping (artırıldı)
    "optimizer": "AdamW",
    "lr0": 0.001,                    # Initial learning rate
    "lrf": 0.01,                     # Final learning rate factor
    "weight_decay": 0.001,           # Artırıldı: overfitting azaltır
    "warmup_epochs": 5,
    "warmup_momentum": 0.8,
    "warmup_bias_lr": 0.1,
    "dropout": 0.3,                  # YENI: Overfitting önleyici
    "freeze": 7,                     # YENI: İlk 7 katmanı dondur (son 3 katman + head eğitilir)
    # Data augmentation (güçlendirildi)
    "hsv_h": 0.015,                  # HSV-Hue augmentation
    "hsv_s": 0.7,                    # HSV-Saturation augmentation
    "hsv_v": 0.4,                    # HSV-Value augmentation
    "degrees": 25.0,                 # Rotation artırıldı (±25 derece)
    "translate": 0.15,               # Translation artırıldı
    "scale": 0.5,                    # Scale
    "shear": 2.0,                    # Shear
    "perspective": 0.0001,           # Hafif perspektif bozma
    "flipud": 0.1,                   # Vertical flip eklendi
    "fliplr": 0.5,                   # Horizontal flip
    "mosaic": 1.0,                   # Mosaic augmentation
    "mixup": 0.3,                    # MixUp artırıldı (0.2 → 0.3)
    "erasing": 0.5,                  # Random erasing artırıldı (0.4 → 0.5)
    "crop_fraction": 0.9,            # Crop fraction düşürüldü
    # Diğer
    "project": os.path.join(PROJE_KOK, "runs", "classify"),
    "name": "combined_food_yolov8s",
    "exist_ok": True,
    "pretrained": True,
    "verbose": True,
    "seed": 42,
    "workers": 4,
    "cos_lr": True,                  # Cosine learning rate scheduler
    "label_smoothing": 0.1,         # Label smoothing
}


def parse_args():
    """Komut satırı argümanlarını okur."""
    parser = argparse.ArgumentParser(
        description="YOLOv8 Yemek Tanıma Model Eğitimi",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--model", type=str, default=DEFAULT_CONFIG["model"],
                        help="Pre-trained model (yolov8n-cls.pt, yolov8s-cls.pt, yolov8m-cls.pt)")
    parser.add_argument("--data", type=str, default=DEFAULT_CONFIG["data"],
                        help="Dataset dizini (YOLO classification format)")
    parser.add_argument("--epochs", type=int, default=DEFAULT_CONFIG["epochs"],
                        help="Eğitim epoch sayısı")
    parser.add_argument("--imgsz", type=int, default=DEFAULT_CONFIG["imgsz"],
                        help="Girdi görüntü boyutu")
    parser.add_argument("--batch", type=int, default=DEFAULT_CONFIG["batch"],
                        help="Batch size")
    parser.add_argument("--patience", type=int, default=DEFAULT_CONFIG["patience"],
                        help="Early stopping patience")
    parser.add_argument("--optimizer", type=str, default=DEFAULT_CONFIG["optimizer"],
                        help="Optimizer (SGD, Adam, AdamW)")
    parser.add_argument("--lr", type=float, default=DEFAULT_CONFIG["lr0"],
                        help="Learning rate")
    parser.add_argument("--workers", type=int, default=DEFAULT_CONFIG["workers"],
                        help="DataLoader worker sayısı")
    parser.add_argument("--resume", action="store_true",
                        help="Son checkpoint'tan devam et")
    return parser.parse_args()


def check_dataset(data_dir: str) -> bool:
    """Dataset dizinini kontrol eder."""
    train_dir = os.path.join(data_dir, "train")
    val_dir = os.path.join(data_dir, "val")

    if not os.path.exists(data_dir):
        print(f"❌ Dataset dizini bulunamadı: {data_dir}")
        print("   Önce prepare_turkish_food.py scriptini çalıştırın:")
        print("   python scripts/prepare_turkish_food.py")
        return False

    if not os.path.exists(train_dir):
        print(f"❌ Train dizini bulunamadı: {train_dir}")
        return False

    if not os.path.exists(val_dir):
        print(f"❌ Val dizini bulunamadı: {val_dir}")
        return False

    # Sınıf sayısını kontrol et
    train_classes = [d for d in os.listdir(train_dir)
                     if os.path.isdir(os.path.join(train_dir, d))]
    val_classes = [d for d in os.listdir(val_dir)
                   if os.path.isdir(os.path.join(val_dir, d))]

    # Toplam görüntü sayısı
    train_count = sum(
        len([f for f in os.listdir(os.path.join(train_dir, c)) if f.endswith(".jpg")])
        for c in train_classes
    )
    val_count = sum(
        len([f for f in os.listdir(os.path.join(val_dir, c)) if f.endswith(".jpg")])
        for c in val_classes
    )

    print(f"📊 Dataset Bilgileri:")
    print(f"   Train: {train_count:,} görüntü, {len(train_classes)} sınıf")
    print(f"   Val  : {val_count:,} görüntü, {len(val_classes)} sınıf")

    return True


def train(args):
    """YOLOv8 classification modelini eğitir."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ ultralytics kütüphanesi yüklü değil!")
        print("   pip install ultralytics")
        sys.exit(1)

    print("\n" + "═" * 60)
    print("  🏋️  YOLOv8 Eğitim Başlıyor")
    print("═" * 60)

    # Eğitim parametrelerini göster
    print(f"\n  📋 Eğitim Parametreleri:")
    print(f"     Model      : {args.model}")
    print(f"     Dataset    : {args.data}")
    print(f"     Epochs     : {args.epochs}")
    print(f"     Image Size : {args.imgsz}")
    print(f"     Batch Size : {args.batch}")
    print(f"     Patience   : {args.patience}")
    print(f"     Optimizer  : {args.optimizer}")
    print(f"     LR         : {args.lr}")
    print(f"     Workers    : {args.workers}")

    # Model yükle
    if args.resume:
        # Son checkpoint'tan devam
        last_path = os.path.join(
            DEFAULT_CONFIG["project"],
            DEFAULT_CONFIG["name"],
            "weights",
            "last.pt",
        )
        if os.path.exists(last_path):
            print(f"\n🔄 Son checkpoint'tan devam ediliyor: {last_path}")
            model = YOLO(last_path)
        else:
            print(f"⚠️ Checkpoint bulunamadı: {last_path}")
            print("   Sıfırdan başlanıyor...")
            model = YOLO(args.model)
    else:
        print(f"\n📥 Pre-trained model yükleniyor: {args.model}")
        model = YOLO(args.model)

    # Eğitimi başlat
    print(f"\n🚀 Eğitim başlıyor... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("─" * 60)

    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        optimizer=args.optimizer,
        lr0=args.lr,
        lrf=DEFAULT_CONFIG["lrf"],
        weight_decay=DEFAULT_CONFIG["weight_decay"],
        warmup_epochs=DEFAULT_CONFIG["warmup_epochs"],
        warmup_momentum=DEFAULT_CONFIG["warmup_momentum"],
        warmup_bias_lr=DEFAULT_CONFIG["warmup_bias_lr"],
        dropout=DEFAULT_CONFIG["dropout"],
        freeze=DEFAULT_CONFIG["freeze"],
        # Augmentation
        hsv_h=DEFAULT_CONFIG["hsv_h"],
        hsv_s=DEFAULT_CONFIG["hsv_s"],
        hsv_v=DEFAULT_CONFIG["hsv_v"],
        degrees=DEFAULT_CONFIG["degrees"],
        translate=DEFAULT_CONFIG["translate"],
        scale=DEFAULT_CONFIG["scale"],
        shear=DEFAULT_CONFIG["shear"],
        perspective=DEFAULT_CONFIG["perspective"],
        flipud=DEFAULT_CONFIG["flipud"],
        fliplr=DEFAULT_CONFIG["fliplr"],
        mosaic=DEFAULT_CONFIG["mosaic"],
        mixup=DEFAULT_CONFIG["mixup"],
        erasing=DEFAULT_CONFIG["erasing"],
        crop_fraction=DEFAULT_CONFIG["crop_fraction"],
        # Diğer
        project=DEFAULT_CONFIG["project"],
        name=DEFAULT_CONFIG["name"],
        exist_ok=DEFAULT_CONFIG["exist_ok"],
        pretrained=DEFAULT_CONFIG["pretrained"],
        verbose=DEFAULT_CONFIG["verbose"],
        seed=DEFAULT_CONFIG["seed"],
        workers=args.workers,
        cos_lr=DEFAULT_CONFIG["cos_lr"],
        label_smoothing=DEFAULT_CONFIG["label_smoothing"],
    )

    print("\n" + "─" * 60)
    print(f"✅ Eğitim tamamlandı! ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

    # Sonuçlar
    run_dir = os.path.join(DEFAULT_CONFIG["project"], DEFAULT_CONFIG["name"])
    best_model = os.path.join(run_dir, "weights", "best.pt")
    last_model = os.path.join(run_dir, "weights", "last.pt")

    print(f"\n📁 Eğitim çıktıları: {run_dir}")
    print(f"   🏆 En iyi model  : {best_model}")
    print(f"   📸 Son model     : {last_model}")

    # En iyi modeli models_data/ dizinine kopyala
    models_dir = os.path.join(PROJE_KOK, "models_data")
    os.makedirs(models_dir, exist_ok=True)
    target_model = os.path.join(models_dir, "combined_food_yolov8s_best.pt")

    if os.path.exists(best_model):
        shutil.copy2(best_model, target_model)
        print(f"\n   ✅ En iyi model kopyalandı: {target_model}")
    elif os.path.exists(last_model):
        shutil.copy2(last_model, target_model)
        print(f"\n   ✅ Son model kopyalandı: {target_model}")

    # Validation çalıştır
    print("\n" + "═" * 60)
    print("  📊 Validation Sonuçları")
    print("═" * 60)

    val_results = model.val()
    print(f"\n  Top-1 Accuracy: {val_results.top1:.4f}")
    print(f"  Top-5 Accuracy: {val_results.top5:.4f}")

    # Eğitim metriklerini listele
    metrics_files = [
        "confusion_matrix.png",
        "confusion_matrix_normalized.png",
        "results.png",
        "results.csv",
    ]

    print(f"\n📊 Oluşturulan Grafikler:")
    for mf in metrics_files:
        path = os.path.join(run_dir, mf)
        if os.path.exists(path):
            print(f"   ✅ {mf}")
        else:
            print(f"   ⚠️ {mf} (bulunamadı)")

    return results


def main():
    args = parse_args()

    print("=" * 60)
    print("  🍽️  YOLOv8 Türk Yemekleri - Model Eğitimi (102 sınıf)")
    print("=" * 60)

    # Dataset kontrolü
    if not check_dataset(args.data):
        sys.exit(1)

    # Eğitimi başlat
    train(args)

    print("\n" + "=" * 60)
    print("  🎉 Tüm işlemler tamamlandı!")
    print("=" * 60)
    print(f"\n  Modeli test etmek için:")
    print(f"  python scripts/test_food_recognition.py --image <foto.jpg>")


if __name__ == "__main__":
    main()
