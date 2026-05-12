"""
Test fixture'ları ve DB setup.
In-memory SQLite veritabanı ile izole test ortamı sağlar.
"""

import sys
import os
import pytest
from datetime import date, datetime, timedelta

# Proje kök dizinini sys.path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Yemek, Menu, MenuPuanlama, UretimLog, Alert, MenuOneriLog
from config import active_config


# ═══════════════════════════════════════════════════════════════════
# IN-MEMORY TEST VERİTABANI
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def test_db():
    """Her test için temiz in-memory SQLite DB oluşturur."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture(scope="function")
def seeded_db(test_db):
    """Örnek verilerle doldurulmuş test DB."""
    db = test_db

    # Yemekler
    yemekler = [
        Yemek(ad="Mercimek Çorbası", kategori="corba", kalori=150, protein=8, karbonhidrat=22, yag=3),
        Yemek(ad="Tavuk Sote", kategori="ana_yemek", kalori=280, protein=25, karbonhidrat=10, yag=15),
        Yemek(ad="Pirinç Pilavı", kategori="yan_yemek", kalori=200, protein=4, karbonhidrat=40, yag=3),
        Yemek(ad="Sütlaç", kategori="tatli", kalori=220, protein=5, karbonhidrat=38, yag=6),
        Yemek(ad="Mevsim Salata", kategori="salata", kalori=50, protein=2, karbonhidrat=8, yag=1),
    ]
    db.add_all(yemekler)
    db.flush()

    # Menüler (son 7 gün)
    bugun = date.today()
    gun_adlari = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma"]
    for i in range(5):
        tarih = bugun - timedelta(days=4 - i)
        db.add(Menu(
            tarih=tarih,
            gun=gun_adlari[i],
            corba="Mercimek Çorbası",
            ana_yemek="Tavuk Sote",
            yan_yemek="Pirinç Pilavı",
            tatli="Sütlaç",
            salata="Mevsim Salata",
        ))

    # Puanlamalar
    for i in range(20):
        tarih = bugun - timedelta(days=i % 5)
        db.add(MenuPuanlama(
            tarih=tarih,
            yemek_adi="Mercimek Çorbası" if i % 3 == 0 else "Tavuk Sote",
            kategori="corba" if i % 3 == 0 else "ana_yemek",
            puan=(i % 5) + 1,
            yorum="Güzel" if i % 2 == 0 else "İdare eder",
        ))

    # Üretim logları
    for i in range(10):
        tarih = bugun - timedelta(days=i % 5)
        uretilen = 100
        kalan = 10 + (i * 3)
        db.add(UretimLog(
            tarih=tarih,
            yemek_adi="Mercimek Çorbası" if i % 2 == 0 else "Tavuk Sote",
            kategori="corba" if i % 2 == 0 else "ana_yemek",
            uretilen_porsiyon=uretilen,
            kalan_porsiyon=kalan,
            tuketim_orani=round((uretilen - kalan) / uretilen * 100, 1),
            israf_orani=round(kalan / uretilen * 100, 1),
        ))

    db.commit()
    yield db


# ═══════════════════════════════════════════════════════════════════
# FASTAPI TEST CLIENT
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient — gerçek uygulamayı test eder."""
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        yield c
