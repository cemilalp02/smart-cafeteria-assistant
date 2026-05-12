"""
Veritabanı yedekleme scripti.

SQLite için dosya kopyası, PostgreSQL için pg_dump kullanır.
Yedekler backups/ dizinine tarih damgalı olarak kaydedilir.

Kullanım:
    python scripts/data/backup_db.py
    python scripts/data/backup_db.py --max-backups 10
"""

import os
import sys
import shutil
import subprocess
import argparse
from datetime import datetime

# Proje kök dizinini sys.path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import active_config


BACKUP_DIR = os.path.join(active_config.BASE_DIR, "backups")


def ensure_backup_dir():
    """Yedek dizinini oluşturur."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def backup_sqlite():
    """SQLite veritabanını dosya kopyası olarak yedekler."""
    db_url = active_config.DATABASE_URL
    # sqlite:///path/to/db.db → path/to/db.db
    db_path = db_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        print(f"[HATA] Veritabanı dosyası bulunamadı: {db_path}")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"yemekhane_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    shutil.copy2(db_path, backup_path)
    size_kb = os.path.getsize(backup_path) / 1024
    print(f"[OK] SQLite yedeklendi: {backup_path} ({size_kb:.1f} KB)")
    return backup_path


def backup_postgresql():
    """PostgreSQL veritabanını pg_dump ile yedekler."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"yemekhane_{timestamp}.sql"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    db_url = active_config.DATABASE_URL
    try:
        result = subprocess.run(
            ["pg_dump", db_url, "-f", backup_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            size_kb = os.path.getsize(backup_path) / 1024
            print(f"[OK] PostgreSQL yedeklendi: {backup_path} ({size_kb:.1f} KB)")
            return backup_path
        else:
            print(f"[HATA] pg_dump hatası: {result.stderr}")
            return None
    except FileNotFoundError:
        print("[HATA] pg_dump bulunamadı. PostgreSQL client araçlarını yükleyin.")
        return None


def cleanup_old_backups(max_backups: int = 7):
    """Eski yedekleri siler, en fazla max_backups adet tutar."""
    if not os.path.exists(BACKUP_DIR):
        return

    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("yemekhane_")],
        reverse=True,
    )
    removed = 0
    for old_backup in backups[max_backups:]:
        os.remove(os.path.join(BACKUP_DIR, old_backup))
        removed += 1

    if removed:
        print(f"[OK] {removed} eski yedek silindi (limit: {max_backups})")


def main():
    parser = argparse.ArgumentParser(description="Veritabanı yedekleme")
    parser.add_argument(
        "--max-backups", type=int, default=7,
        help="Tutulacak maksimum yedek sayısı (varsayılan: 7)",
    )
    args = parser.parse_args()

    ensure_backup_dir()

    db_url = active_config.DATABASE_URL
    if db_url.startswith("sqlite"):
        backup_sqlite()
    elif db_url.startswith("postgresql"):
        backup_postgresql()
    else:
        print(f"[HATA] Desteklenmeyen veritabanı: {db_url}")
        return

    cleanup_old_backups(args.max_backups)


if __name__ == "__main__":
    main()
