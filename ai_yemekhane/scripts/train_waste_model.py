"""
Israf ML modeli egitim scripti.

Kullanim:
  python scripts/train_waste_model.py
  python scripts/train_waste_model.py --min-samples 20
"""

from __future__ import annotations

import argparse
import os
import sys

# Proje kok dizinini path'e ekle
PROJE_KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJE_KOK)

from models import SessionLocal  # noqa: E402
from modules.waste_analyzer import (  # noqa: E402
    get_waste_model_status,
    train_waste_model_from_db,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Israf ML modeli egitimi")
    parser.add_argument(
        "--min-samples",
        type=int,
        default=8,
        help="Egitim icin minimum UretimLog kaydi sayisi",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        result = train_waste_model_from_db(db=db, min_samples=args.min_samples)
        if not result.get("success"):
            print(f"Model egitilemedi: {result.get('message')}")
            print(f"Mevcut ornek: {result.get('sample_count')}")
            return 1

        print("Model egitildi.")
        print(f"Model yolu: {result.get('model_path')}")
        print(f"Ornek sayisi: {result.get('sample_count')}")
        print(f"Metrikler: {result.get('metrics')}")

        status = get_waste_model_status(db=db)
        print(f"Durum: {status}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
