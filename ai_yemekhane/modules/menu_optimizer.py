"""
Modül 1: Menü Optimizasyonu ve Yemek Öneri Sistemi
═══════════════════════════════════════════════════
ML tabanlı yemek popülerlik tahmini ve kısıt optimizasyonlu
haftalık menü önerisi oluşturma modülü.

Pipeline:
  1. CSV verisinden feature engineering
  2. Sentetik popülerlik skoru üretimi
  3. GradientBoosting / RandomForest model eğitimi
  4. Kısıtlı haftalık menü optimizasyonu

Kullanılan teknolojiler:
  - scikit-learn (GradientBoostingRegressor)
  - pandas / numpy
  - joblib (model kayıt / yükleme)
"""

import json
import logging
import os
import random
import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder

from models import SessionLocal, MenuPuanlama, Alert, UretimLog, Menu, MenuOneriLog

logger = logging.getLogger(__name__)

# ─── Sabitler ──────────────────────────────────────────────────────
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
GUN_MAP = {"Pazartesi": 0, "Salı": 1, "Çarşamba": 2, "Perşembe": 3, "Cuma": 4}

MEVSIM_MAP = {1: "kış", 2: "kış", 3: "ilkbahar", 4: "ilkbahar", 5: "ilkbahar",
              6: "yaz", 7: "yaz", 8: "yaz", 9: "sonbahar", 10: "sonbahar",
              11: "sonbahar", 12: "kış"}
MEVSIM_NUM = {"kış": 0, "ilkbahar": 1, "yaz": 2, "sonbahar": 3}

KATEGORI_KOLONLARI = ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]

# ─── Beslenme Dengesi Hedefleri ────────────────────────────────────
# Referans: Sağlık Bakanlığı üniversite yemekhanesi öğle yemeği önerileri
BESLENME_HEDEF = {
    "kalori_min": 650,       # kcal — minimum günlük öğle yemeği
    "kalori_max": 950,       # kcal — maximum günlük öğle yemeği
    "protein_min": 25,       # gram — minimum protein
    "kalori_ideal": 800,     # kcal — ideal merkez
}

# Sebze yemeği tespiti için anahtar kelimeler
SEBZE_ANAHTAR = [
    "ıspanak", "ispanak", "brokoli", "karnabahar", "pırasa", "pirasa",
    "kabak", "patlıcan", "biber", "domates", "bamya", "bezelye",
    "fasulye", "börülce", "borulce", "enginar", "kereviz", "havuç",
    "havuc", "mantar", "turlu", "türlü", "sebze", "zeytinyağlı",
    "zeytinyagli", "salata", "sote", "kavurma", "dolma", "sarma",
]

# ─── Et Türü Anahtar Kelimeleri (Constraint: hafta max 2) ────────
ET_TURU_ANAHTAR = {
    "tavuk": [
        "tavuk", "kanat", "pane", "chicken", "but", "pirzola",
        "büryan", "fajita", "tantuni tavuk", "döner tavuk",
    ],
    "kirmizi_et": [
        "et ", "köfte", "kebab", "kebabı", "dana", "kuzu", "kavurma",
        "güveç", "rosto", "haşlama", "sote et", "tandır", "döner et",
        "iskender", "ciğer",
    ],
    "balik": [
        "balık", "hamsi", "uskumru", "levrek", "çipura", "somon",
        "sardalya", "mezgit", "palamut",
    ],
}

# ─── Allerjen Grupları (Constraint: aynı gün max 3 grup) ────────
ALLERJEN_GRUPLAR = {
    "gluten": [
        "makarna", "börek", "ekmek", "pide", "mantı", "erişte",
        "yufka", "lavaş", "bulgur", "şehriye", "kuskus",
    ],
    "sut": [
        "peynir", "süt", "yoğurt", "krema", "beşamel", "kaşar",
        "muhallebi", "keşkül", "puding", "sütlaç",
    ],
    "yumurta": [
        "yumurta", "pane", "mücver", "omlet",
    ],
}

# ─── Multi-Objective Optimizasyon Ağırlıkları ────────────────────
# Admin dashboard'dan ayarlanabilir; varsayılan değerler
OPTIMIZATION_WEIGHTS = {
    "populerlik": 0.35,     # Popülerlik maximizasyonu
    "israf": 0.30,          # İsraf minimizasyonu
    "beslenme": 0.20,       # Beslenme dengesi
    "maliyet": 0.15,        # Maliyet optimizasyonu
}

# Tahmini porsiyon maliyeti (TL) — kategori bazlı
KATEGORI_MALIYET = {
    "corba": 8.0,
    "ana_yemek": 25.0,
    "yan_yemek": 10.0,
    "tatli": 12.0,
    "salata": 7.0,
}

# Haftalık günlük ortalama bütçe hedefi (TL)
GUNLUK_BUTCE_HEDEF = 65.0

# Haftalık constraint limitleri
HAFTALIK_ET_LIMIT = 2          # Aynı et türü haftada max 2 kez
MIN_SEBZE_GUN = 1              # Haftada min 1 gün ağırlıklı sebze
MAX_AYNI_GUN_ALLERJEN = 3      # Aynı günde max 3 allerjen grubu

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models_data")
MODEL_PATH = os.path.join(MODEL_DIR, "menu_popularity_model.joblib")
ENCODERS_PATH = os.path.join(MODEL_DIR, "label_encoders.joblib")
FEATURES_PATH = os.path.join(MODEL_DIR, "feature_columns.joblib")
OPTIMIZATION_WEIGHTS_PATH = os.path.join(MODEL_DIR, "optimization_weights.json")

# ─── Popülerlik puanları (gerçek menü verisi bazlı) ───────────────
# 270 yemek - gerçek üniversite menü verisi
YEMEK_BAZI_POPULERLIK = {
    # Çorbalar
    "Alaca Çorba": 0.8,
    "Arabaşı Çorba": 0.64,
    "Ayranaşı Çorba": 0.7,
    "Brokoli Çorba": 0.69,
    "Domates Çorba": 0.83,
    "Düğün Çorba": 0.81,
    "Ezogelin Çorba": 0.87,
    "Hanımağa Çorba": 0.65,
    "Kabak Çorbası": 0.74,
    "Kremalı Mantar Çorba": 0.64,
    "Kremalı Sebze Çorba": 0.69,
    "Kru. Domates Çorba": 0.77,
    "Krut. Domates Çorba": 0.64,
    "Krutonlu Domates Çorba": 0.68,
    "Köylüm Çorba": 0.81,
    "Köz Biber Çorba": 0.78,
    "Lebeniye Çorba": 0.69,
    "Mahluta Çorba": 0.79,
    "Mercimek Çorba": 0.85,
    "Minestrone Çorba": 0.63,
    "Pirinç Çorba": 0.85,
    "Saray Çorba": 0.82,
    "Sebze Çorba": 0.72,
    "Sebzeli Şehriye Çorba": 0.67,
    "Süzme Mercimek Çorba": 0.89,
    "Tandır Çorba": 0.72,
    "Tarhana Çorba": 0.66,
    "Tarhana Çorbası": 0.66,
    "Tavuk Suyu Çorba": 0.86,
    "Tavuk Çorba": 0.79,
    "Tel Şehriye Çorba": 0.85,
    "Terbiyeli Tavuk Çorba": 0.83,
    "Toyga Çorba": 0.77,
    "Yayla Çorba": 0.89,
    "Yeşil Mercimek Çorba": 0.73,
    "Yoğurt Çorba": 0.78,
    "Şehriye Çorba": 0.85,
    # Ana Yemekler
    "Adana Köfte (lavaş)": 0.83,
    "Akdeniz Usulü Ispanak": 0.89,
    "Ankara Tava": 0.82,
    "Arnavut Ciğer /May. Roka Soğan Söğüş": 0.85,
    "Babagannuş": 0.67,
    "Bahçıvan Kebabı": 0.72,
    "Barbekü Soslu Tavuk": 0.74,
    "Bezelye Yemeği": 0.68,
    "Beğendili Misket Köfte": 0.72,
    "Beşamelli Fırın Patates": 0.69,
    "Dana Navarin": 0.74,
    "Dürüm Tavuk Tantuni": 0.83,
    "Ekmek arası Balık/Soğan Söğüş": 0.76,
    "Et Döner": 0.76,
    "Et Fajita": 0.72,
    "Et Haşlama": 0.91,
    "Et Sote": 0.83,
    "Et Stroganoff": 0.82,
    "Etli Barbunya": 0.71,
    "Etli Nohut": 0.86,
    "Etli Taze Fasulye": 0.7,
    "Etli Türlü": 0.76,
    "Etli Yaz Türlüsü": 0.93,
    "Fırın Köfte": 0.83,
    "Fırın Tavuk (Brokoli, Kırmızı Biber)": 0.81,
    "Fırında Patatesli Hamsi": 0.84,
    "Fırında Tavuk Pirzola/Brokoli, Kırmızı Biber,Mısır Garnitür": 0.89,
    "Hamburger": 0.87,
    "Hamburger (Patates Kızartması)": 0.72,
    "Hamburger /Patates Kızartma": 0.67,
    "Hamburger/Patates Kızartması": 0.75,
    "Hasanpaşa Köfte (Püreli)": 0.73,
    "Hünkar Beğendi": 0.72,
    "Ispanak Kavurma": 0.91,
    "Ispanak Yemeği / Yoğurt": 0.9,
    "Izgara Kanat / Brokoli Karnabahar Haşlama": 0.74,
    "Izgara Köfte / Elma Dilim Patates": 0.84,
    "Izgara Tavuk Kanat / Elma Dilim Patates": 0.77,
    "Kabak Dolma": 0.91,
    "Kabak Mücver (domates,biber)": 0.78,
    "Kapuska": 0.73,
    "Karnabahar Pane": 0.73,
    "Karnabahar Pane (yoğurt)": 0.81,
    "Karnabahar Pane / Yoğurt": 0.73,
    "Karnıyarık": 0.82,
    "Karışık Dolma (yoğurt)": 0.9,
    "Kekikli Fırın Tavuk Pirzola": 0.77,
    "Kremalı Köri Soslu Tavuk": 0.72,
    "Kuru Fasulye": 0.93,
    "Köfteli Avcı Kebabı": 0.8,
    "Köri Soslu Tavuk": 0.68,
    "Kıymalı Bezelye": 0.67,
    "Kıymalı Biber Dolma (Yoğurt)": 0.69,
    "Kıymalı Ispanak / Yoğurt": 0.83,
    "Kıymalı Karnabahar Yemeği": 0.87,
    "Kıymalı Patates Oturtma": 0.77,
    "Kıymalı Pırasa": 0.68,
    "Lahana Kapama/ Yoğurt": 0.76,
    "Lavaşlı Et Tantuni": 0.93,
    "Lavaşlı Tavuk Tantuni": 0.8,
    "Macar Gulaş": 0.92,
    "Mantarlı Tavuk Sote": 0.89,
    "Meksika Soslu Tavuk": 0.66,
    "Mevsim Türlü": 0.85,
    "Nohut Kavurma": 0.84,
    "Nohut Yemeği": 0.8,
    "Nohutlu Pirinç Pilavı": 0.73,
    "Nohutlu, Portakallı Kereviz": 0.83,
    "Orman Kebabı": 0.69,
    "Paris Soslu Tavuk": 0.78,
    "Patates Oturtma": 0.9,
    "Patlıcan Musakka": 0.73,
    "Patlıcanlı Fırın Köfte": 0.8,
    "Pideli Köfte": 0.71,
    "Pideli Parmak Köfte": 0.91,
    "Pideli Tavuk Kebabı": 0.9,
    "Pilav Üstü Kavurma": 0.74,
    "Portakallı Noh.Kereviz": 0.83,
    "Püreli Hasan Paşa Köfte": 0.82,
    "Püreli Misket Köfte": 0.7,
    "Püreli Rosto Köfte": 0.87,
    "Sahan Köfte": 0.81,
    "Sebze Graten": 0.87,
    "Sebze Şöleni": 0.8,
    "Sebzeli Tavuk Sote": 0.66,
    "Sebzeli Çanak Köfte": 0.75,
    "Soslu Köfte(Patates Kzt)": 0.67,
    "Soslu Misket Köfte": 0.91,
    "Soslu Tavuk Kanat / Sebze Garnitür (patates, havuç, bezelye)": 0.9,
    "Soslu Tavuk Külbastı / Elma Dilim Patates": 0.88,
    "Tas Kebabı": 0.74,
    "Tavuk But/Pat. Kızartma": 0.68,
    "Tavuk Büryan": 0.9,
    "Tavuk Döner": 0.92,
    "Tavuk Döner / Elma Dilim Patates": 0.68,
    "Tavuk Fajita": 0.79,
    "Tavuk Fajıta": 0.68,
    "Tavuk Haşlama": 0.87,
    "Tavuk Külbastı": 0.87,
    "Tavuk Pane / Elma Dilim Patates": 0.69,
    "Tavuk Pane / ElmaDilim Patates": 0.79,
    "Tavuk Pirzola/ Sebze Haşlama": 0.81,
    "Tavuk Şiş ( Elma Dili Patates)": 0.73,
    "Taze Fasulye": 0.9,
    "Tepsi Köfte / Brokoli Karnabahar Havuç Haşlama": 0.77,
    "Uskumru Fileto Kızartma / Roka,Tere, Soğan Söğüş": 0.72,
    "Yufkalı Tavuk Sarma": 0.81,
    "Yumurtalı Ispanak": 0.86,
    "Zyt Barbunya": 0.71,
    "Zyt. Bamya": 0.74,
    "Zyt. Barbunya": 0.93,
    "Zyt. Taze Fasulye": 0.84,
    "Zyt.Barbunya": 0.78,
    "Zyt.Taze Fasulye": 0.8,
    "Çiftlik Kebabı": 0.69,
    "Çiftlik Kebap": 0.72,
    "Çiftlik Köfte": 0.75,
    "Çoban Kavurma": 0.82,
    "Çökertme Kebabı": 0.72,
    "Çıtır Tavuk Paget / Baharatlı Patates": 0.72,
    "İslim Köfte": 0.68,
    "İsveç Köfte / Sebze Garnitür": 0.83,
    "İzmir Köfte": 0.72,
    "İçli Köfte": 0.9,
    "Şakşuka": 0.89,
    "Şinitzel Burger": 0.68,
    "Şinitzel/ Patates Kızartma": 0.72,
    # Pilav / Makarna / Börek
    "Bolonez Soslu Makarna": 0.74,
    "Bulgur Pilavı": 0.62,
    "Cevizli Erişte": 0.81,
    "Dom. Bulgur Pilavı": 0.71,
    "Erişte": 0.69,
    "Fesleğen Soslu Makarna": 0.77,
    "Fırın Makarna": 0.78,
    "Hav. Pirinç Pilavı": 0.61,
    "Kuskus Pilavı": 0.59,
    "Mıs. Pirinç Pilavı": 0.68,
    "Mısırlı Pirinç Pilavı": 0.67,
    "Nap. Soslu Makarna": 0.69,
    "Napoliten Soslu Makarna": 0.76,
    "Patatesli Gül Böreği": 0.83,
    "Patatesli Kol Böreği": 0.59,
    "Peynirli Gül Böreği": 0.67,
    "Pilav Üstü Dana Tandır": 0.65,
    "Pirinç Pilavı": 0.79,
    "Sebzeli Makarna": 0.63,
    "Soslu Makarna": 0.61,
    "Su Böreği": 0.68,
    "Yeşil Mercimekli Bulgur Pilavı": 0.67,
    "Yoğurtlu Mantı Makarna": 0.64,
    "İç Pilav": 0.63,
    "Şeh Pirinç Pilavı": 0.81,
    "Şeh. Bulgur Pilavı": 0.68,
    "Şeh. Pirinç Pilavı": 0.79,
    "Şehriye Pilavı": 0.71,
    "Şehriyeli Bulgur Pilavı": 0.57,
    "Şehriyeli Kuskus Pilavı": 0.83,
    "Şehriyeli Pirinç Pilavı": 0.79,
    # Tatlılar
    "Baklava": 0.86,
    "Balbadem Tatlısı": 0.85,
    "Brownie": 0.83,
    "Cevizli Baklava": 0.64,
    "Cevizli Kabak Tatlısı": 0.73,
    "Cevizli Kalburabastı": 0.66,
    "Ekler": 0.71,
    "Havuç Dilim Baklava": 0.62,
    "Helva": 0.7,
    "Islak Kek": 0.87,
    "Kakaolu Puding": 0.67,
    "Kayısı / Üzüm Komposto": 0.81,
    "Keşkül": 0.72,
    "Komposto": 0.71,
    "Komposto / Meyve Suyu": 0.86,
    "Komposto /Meyve Suyu": 0.87,
    "Komposto/ Meyve Suyu": 0.75,
    "Kıbrıs Tatlısı": 0.79,
    "Muhallebili Kemalpaşa": 0.64,
    "Muzlu Keşkül": 0.68,
    "Pembe Sultan": 0.86,
    "Sarışınım Tatlısı": 0.76,
    "Sevgi Tatlısı": 0.75,
    "Soslu Brownie": 0.8,
    "Soğuk Baklava": 0.62,
    "Sütlü İrmik Tatlısı": 0.76,
    "Tiramisu": 0.74,
    "Trileçe": 0.83,
    "İncirli Keşkül": 0.64,
    "İrmik Helvası": 0.86,
    "Şekerpare": 0.62,
    # Meyveler
    "Elma": 0.71,
    "Mandalina": 0.7,
    "Meyve": 0.7,
    "Meyve ( Üzüm)": 0.56,
    "Meyve (Armut)": 0.5,
    "Meyve (Elma)": 0.69,
    "Meyve (kavun)": 0.65,
    "Meyve (üzüm)": 0.63,
    "Meyve(Portakal)": 0.73,
    "Muz": 0.64,
    "Portakal": 0.46,
    # Salatalar / Mezeler
    "Biber Borani": 0.58,
    "Cacık": 0.69,
    "Coleslow Salata": 0.71,
    "Ezme": 0.59,
    "Havuç Tarator": 0.56,
    "Haydari": 0.77,
    "Kabak Tarator": 0.6,
    "Karışık Salata": 0.69,
    "Kısır": 0.7,
    "Kış Salata": 0.64,
    "Mercimek Salata": 0.69,
    "Mevsim Salata": 0.67,
    "Mevsim salata": 0.78,
    "Mıs Börülce Salata": 0.59,
    "Mıs. Iceberg Salata": 0.72,
    "Mıs. Pancar Salata": 0.59,
    "Mısır, Havuç, Kırmızı Lahana Salata": 0.64,
    "Patates Salatası": 0.71,
    "Piyaz": 0.61,
    "Salata": 0.62,
    "Turşu": 0.73,
    "Yoğ. Semizotu Salata": 0.55,
    "Yoğurt": 0.65,
    "Yoğurtlu Semizotu Salata": 0.8,
    "Çin Salatası": 0.8,
    "Çoban Salata": 0.55,
    # İçecekler
    "Ayran": 0.54,
    "Şalgam/ Meyve Suyu": 0.55,
}


# ─── Gerçek Puanlama Verisi Yardımcıları ──────────────────────────
def get_meal_average_rating(yemek_adi: str, db=None) -> dict:
    """
    Veritabanından bir yemeğin ortalama puanını ve oy sayısını döndürür.
    """
    from sqlalchemy import func as sqla_func

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        result = (
            db.query(
                sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
            )
            .filter(MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"))
            .first()
        )

        if result and result.toplam_oy and result.toplam_oy > 0:
            return {
                "yemek_adi": yemek_adi,
                "ortalama": round(float(result.ortalama), 2),
                "toplam_oy": result.toplam_oy,
            }
        return {"yemek_adi": yemek_adi, "ortalama": None, "toplam_oy": 0}
    finally:
        if close_db:
            db.close()


def _normalize_meal_key(value: str) -> str:
    """Farkli yazimlari tek anahtarda toplamak icin yemek adini normalize eder."""
    return re.sub(r"[\W_]+", " ", str(value).casefold()).strip()


def _build_rating_signal_map(db) -> dict[str, dict]:
    """Yemek adina gore normalize edilmis gercek puan sinyallerini toplar."""
    from sqlalchemy import func as sqla_func

    rows = (
        db.query(
            MenuPuanlama.yemek_adi,
            sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
            sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .group_by(MenuPuanlama.yemek_adi)
        .all()
    )

    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        key = _normalize_meal_key(row.yemek_adi)
        toplam_oy = int(row.toplam_oy or 0)
        if not key or toplam_oy <= 0:
            continue

        item = grouped.setdefault(key, {"puan_toplam": 0.0, "toplam_oy": 0})
        item["puan_toplam"] += float(row.ortalama) * toplam_oy
        item["toplam_oy"] += toplam_oy

    result = {}
    for key, item in grouped.items():
        toplam_oy = int(item["toplam_oy"])
        result[key] = {
            "ortalama": round(item["puan_toplam"] / toplam_oy, 3),
            "toplam_oy": toplam_oy,
        }
    return result


def _build_production_signal_map(db) -> dict[str, dict]:
    """Yemek adina gore normalize edilmis tuketim/israf sinyallerini toplar."""
    from sqlalchemy import func as sqla_func

    rows = (
        db.query(
            UretimLog.yemek_adi,
            sqla_func.avg(UretimLog.tuketim_orani).label("ort_tuketim"),
            sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            sqla_func.count(UretimLog.id).label("kayit_sayisi"),
        )
        .group_by(UretimLog.yemek_adi)
        .all()
    )

    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        key = _normalize_meal_key(row.yemek_adi)
        kayit_sayisi = int(row.kayit_sayisi or 0)
        if not key or kayit_sayisi <= 0:
            continue

        item = grouped.setdefault(
            key,
            {"tuketim_toplam": 0.0, "israf_toplam": 0.0, "kayit_sayisi": 0},
        )
        item["tuketim_toplam"] += float(row.ort_tuketim or 0.0) * kayit_sayisi
        item["israf_toplam"] += float(row.ort_israf or 0.0) * kayit_sayisi
        item["kayit_sayisi"] += kayit_sayisi

    result = {}
    for key, item in grouped.items():
        kayit_sayisi = int(item["kayit_sayisi"])
        result[key] = {
            "ort_tuketim_orani": round(item["tuketim_toplam"] / kayit_sayisi, 3),
            "ort_israf_orani": round(item["israf_toplam"] / kayit_sayisi, 3),
            "kayit_sayisi": kayit_sayisi,
        }
    return result


def _blend_real_world_signals(
    synthetic_score: float,
    rating_info: dict | None = None,
    production_info: dict | None = None,
) -> float:
    """
    Sentetik skoru, gercek puan ve operasyon verisiyle agirlikli sekilde birlestirir.

    Puan sayisi ve uretim kaydi azsa sentetik hedef baskin kalir; veri arttikca
    gercek dunya sinyalleri hedef uzerinde daha etkili olur.
    """
    weighted_sum = synthetic_score * 0.55
    total_weight = 0.55

    if rating_info and rating_info.get("toplam_oy", 0) > 0:
        rating_norm = max(0.0, min(1.0, (float(rating_info["ortalama"]) - 1.0) / 4.0))
        rating_conf = min(float(rating_info["toplam_oy"]) / 12.0, 1.0)
        rating_weight = 0.25 * rating_conf
        weighted_sum += rating_norm * rating_weight
        total_weight += rating_weight

    if production_info and production_info.get("kayit_sayisi", 0) > 0:
        tuketim_norm = max(
            0.0,
            min(1.0, float(production_info.get("ort_tuketim_orani", 0.0)) / 100.0),
        )
        production_conf = min(float(production_info["kayit_sayisi"]) / 8.0, 1.0)
        production_weight = 0.35 * production_conf
        weighted_sum += tuketim_norm * production_weight
        total_weight += production_weight

    blended = weighted_sum / total_weight if total_weight else synthetic_score
    return round(max(0.10, min(1.0, blended)), 3)


# ═══════════════════════════════════════════════════════════════════
# 1) VERİ YÜKLEME
# ═══════════════════════════════════════════════════════════════════
def load_menu_csv(csv_path: str) -> pd.DataFrame:
    """menu_data.csv dosyasını yükler ve temel dönüşümleri yapar."""
    df = pd.read_csv(csv_path, encoding="utf-8")
    df["tarih"] = pd.to_datetime(df["tarih"])
    # Legacy CSV uyumu: 'pilav_makarna' kolonu artık 'yan_yemek' olarak adlandırılıyor
    if "pilav_makarna" in df.columns and "yan_yemek" not in df.columns:
        df = df.rename(columns={"pilav_makarna": "yan_yemek"})
    df = df.sort_values("tarih").reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════════
# 2) VERİYİ "UZUN FORMATA" ÇEVİR  (her satır = 1 yemek)
# ═══════════════════════════════════════════════════════════════════
def melt_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """
    Geniş formatı (her günde 5 sütun) uzun formata çevirir.
    Her satır = bir gün + bir kategori + bir yemek.
    """
    rows = []
    for _, row in df.iterrows():
        tarih = row["tarih"]
        gun = row["gun"]
        for kat in KATEGORI_KOLONLARI:
            yemek = row.get(kat, None)
            if pd.notna(yemek) and str(yemek).strip():
                kategori = kat
                rows.append({
                    "tarih": tarih,
                    "gun": gun,
                    "kategori": kategori,
                    "yemek_adi": str(yemek).strip(),
                })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════
# 3) FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════
def add_features(df_long: pd.DataFrame) -> pd.DataFrame:
    """Her yemek kaydına ML feature'ları ekler."""
    df = df_long.copy()

    # Zaman feature'ları
    df["gun_hafta"] = df["gun"].map(GUN_MAP).fillna(0).astype(int)
    df["ay"] = df["tarih"].dt.month
    df["mevsim_str"] = df["ay"].map(MEVSIM_MAP)
    df["mevsim"] = df["mevsim_str"].map(MEVSIM_NUM).fillna(0).astype(int)
    df["hafta_no"] = df["tarih"].dt.isocalendar().week.astype(int)
    df["yilin_gunu"] = df["tarih"].dt.dayofyear

    # Kategori tekrar sayısı: bu yemek son 7 günde kaç kez çıktı
    df = df.sort_values("tarih").reset_index(drop=True)
    tekrar_liste = []
    for i, row in df.iterrows():
        tarih = row["tarih"]
        yemek = row["yemek_adi"]
        pencere_bas = tarih - pd.Timedelta(days=7)
        onceki = df[(df["tarih"] >= pencere_bas) & (df["tarih"] < tarih) & (df["yemek_adi"] == yemek)]
        tekrar_liste.append(len(onceki))
    df["kategori_tekrar_7gun"] = tekrar_liste

    # Önceki gün aynı kategoride ne çıktı
    df = df.sort_values(["kategori", "tarih"]).reset_index(drop=True)
    df["onceki_yemek"] = df.groupby("kategori")["yemek_adi"].shift(1).fillna("yok")

    # Aynı yemek mi? (1/0)
    df["ayni_onceki"] = (df["yemek_adi"] == df["onceki_yemek"]).astype(int)

    # Sıralama düzelt
    df = df.sort_values("tarih").reset_index(drop=True)

    return df


# ═══════════════════════════════════════════════════════════════════
# 4) SENTETİK POPÜLERLİK SKORU
# ═══════════════════════════════════════════════════════════════════
def generate_popularity_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Kurallara dayali sentetik skoru, varsa gercek puan ve uretim verisiyle
    harmanlayarak 0-1 arasi hedef populerlik skoru uretir.
    """
    df = df.copy()
    skorlar = []

    for _, row in df.iterrows():
        yemek = row["yemek_adi"]
        mevsim = row.get("mevsim_str", "kış")
        gun_hafta = row["gun_hafta"]
        tekrar = row["kategori_tekrar_7gun"]
        ayni_onceki = row["ayni_onceki"]
        kategori = row["kategori"]

        # Baz popülerlik
        baz = YEMEK_BAZI_POPULERLIK.get(yemek, 0.60)

        # Mevsimsel düzeltme
        if mevsim == "kış" and kategori == "corba":
            baz += 0.05          # Kışın çorba daha popüler
        elif mevsim == "yaz" and kategori == "salata":
            baz += 0.06          # Yazın salata daha popüler
        elif mevsim == "yaz" and kategori == "corba":
            baz -= 0.04          # Yazın çorba biraz düşer

        # Cuma etkisi (hafta sonu öncesi motivasyon düşük)
        if gun_hafta == 4:
            baz -= 0.03

        # Pazartesi etkisi
        if gun_hafta == 0:
            baz += 0.02

        # Tekrar cezası
        baz -= tekrar * 0.06     # Son 7 günde her tekrar -0.06

        # Üst üste aynı çıkma cezası
        if ayni_onceki:
            baz -= 0.10

        # Deterministik gürültü (aynı yemek+tarih = aynı gürültü)
        seed_str = f"{yemek}_{row['tarih']}"
        seed_hash = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 10000
        rng = np.random.RandomState(seed_hash)
        gurultu = rng.normal(0, 0.04)
        baz += gurultu

        # Sınırla [0.1, 1.0]
        skor = max(0.10, min(1.0, baz))
        skorlar.append(round(skor, 3))

    df["populerlik"] = skorlar

    # ── Gerçek puanlama ve uretim verisi ile hedefi guclendir ──
    try:
        db = SessionLocal()
        rating_map = _build_rating_signal_map(db)
        production_map = _build_production_signal_map(db)
        db.close()

        if rating_map or production_map:
            def blend_real_signals(row):
                key = _normalize_meal_key(row["yemek_adi"])
                return _blend_real_world_signals(
                    synthetic_score=float(row["populerlik"]),
                    rating_info=rating_map.get(key),
                    production_info=production_map.get(key),
                )

            df["populerlik"] = df.apply(blend_real_signals, axis=1)
    except Exception:
        pass  # Gercek sinyal yoksa sentetik skorlarla devam et

    return df


# ═══════════════════════════════════════════════════════════════════
# 5) ÖZELLİK MATRİSİ OLUŞTUR
# ═══════════════════════════════════════════════════════════════════
def build_feature_matrix(df: pd.DataFrame):
    """
    DataFrame'den X (feature matrix) ve y (target) oluşturur.
    Label encoder'ları da döndürür.
    """
    df = df.copy()

    # Label encoding
    le_yemek = LabelEncoder()
    le_kategori = LabelEncoder()
    le_onceki = LabelEncoder()

    df["yemek_encoded"] = le_yemek.fit_transform(df["yemek_adi"])
    df["kategori_encoded"] = le_kategori.fit_transform(df["kategori"])
    df["onceki_encoded"] = le_onceki.fit_transform(df["onceki_yemek"])

    feature_cols = [
        "gun_hafta",
        "ay",
        "mevsim",
        "hafta_no",
        "yilin_gunu",
        "yemek_encoded",
        "kategori_encoded",
        "kategori_tekrar_7gun",
        "onceki_encoded",
        "ayni_onceki",
    ]

    X = df[feature_cols].values
    y = df["populerlik"].values

    encoders = {
        "yemek": le_yemek,
        "kategori": le_kategori,
        "onceki": le_onceki,
    }

    return X, y, encoders, feature_cols


# ═══════════════════════════════════════════════════════════════════
# 6) MODEL EĞİTİMİ
# ═══════════════════════════════════════════════════════════════════
def train_model(
    csv_path: str,
    model_type: str = "gradient_boosting",
    test_size: float = 0.20,
    cv_folds: int = 5,
    verbose: bool = True,
) -> dict:
    """
    Tam pipeline: CSV → feature eng. → sentetik skor → model eğitimi.

    Returns:
        dict: model, encoders, feature_cols, metrics
    """
    if verbose:
        print("=" * 60)
        print("  📊 Menü Popülerlik Modeli Eğitimi")
        print("=" * 60)

    # 1) Veri yükle
    df_raw = load_menu_csv(csv_path)
    if verbose:
        print(f"\n📥 CSV yüklendi: {len(df_raw)} günlük menü")

    # 2) Uzun formata çevir
    df_long = melt_to_long(df_raw)
    if verbose:
        print(f"📐 Uzun format: {len(df_long)} yemek kaydı")
        print(f"   Benzersiz yemek: {df_long['yemek_adi'].nunique()}")

    # 3) Feature engineering
    df_feat = add_features(df_long)
    if verbose:
        print(f"🔧 Feature engineering tamamlandı")

    # 4) Sentetik popülerlik skoru
    df_scored = generate_popularity_scores(df_feat)
    if verbose:
        print(f"⭐ Popülerlik skorları üretildi")
        print(f"   Min: {df_scored['populerlik'].min():.3f}  "
              f"Max: {df_scored['populerlik'].max():.3f}  "
              f"Ort: {df_scored['populerlik'].mean():.3f}")

    # 5) Feature matrix
    X, y, encoders, feature_cols = build_feature_matrix(df_scored)
    if verbose:
        print(f"📋 Feature matrix: {X.shape[0]} örnek x {X.shape[1]} feature")

    # 6) Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )
    if verbose:
        print(f"\n🔀 Train/Test split: {len(X_train)} / {len(X_test)} (%{int((1-test_size)*100)}/%{int(test_size*100)})")

    # 7) Model seçimi ve eğitimi
    if model_type == "random_forest":
        model = RandomForestRegressor(
            n_estimators=100, max_depth=8, random_state=42, n_jobs=-1
        )
        model_name = "RandomForestRegressor"
    else:
        model = GradientBoostingRegressor(
            n_estimators=150, max_depth=5, learning_rate=0.1,
            subsample=0.8, random_state=42
        )
        model_name = "GradientBoostingRegressor"

    if verbose:
        print(f"\n🤖 Model: {model_name}")
        print("   Eğitim başladı...")

    model.fit(X_train, y_train)

    # 8) Tahmin ve metrikler
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    metrics = {
        "model_type": model_name,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "train_rmse": float(np.sqrt(mean_squared_error(y_train, y_pred_train))),
        "test_rmse": float(np.sqrt(mean_squared_error(y_test, y_pred_test))),
        "train_mae": float(mean_absolute_error(y_train, y_pred_train)),
        "test_mae": float(mean_absolute_error(y_test, y_pred_test)),
        "train_r2": float(r2_score(y_train, y_pred_train)),
        "test_r2": float(r2_score(y_test, y_pred_test)),
    }

    # 9) Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=cv_folds, scoring="neg_mean_squared_error")
    cv_rmse = np.sqrt(-cv_scores)
    metrics["cv_rmse_mean"] = float(cv_rmse.mean())
    metrics["cv_rmse_std"] = float(cv_rmse.std())

    if verbose:
        print("\n" + "─" * 50)
        print("  📈 MODEL METRİKLERİ")
        print("─" * 50)
        print(f"  {'Metrik':<20} {'Train':>10} {'Test':>10}")
        print(f"  {'─'*20} {'─'*10} {'─'*10}")
        print(f"  {'RMSE':<20} {metrics['train_rmse']:>10.4f} {metrics['test_rmse']:>10.4f}")
        print(f"  {'MAE':<20} {metrics['train_mae']:>10.4f} {metrics['test_mae']:>10.4f}")
        print(f"  {'R²':<20} {metrics['train_r2']:>10.4f} {metrics['test_r2']:>10.4f}")
        print(f"\n  Cross-Validation ({cv_folds}-fold):")
        print(f"  RMSE = {metrics['cv_rmse_mean']:.4f} ± {metrics['cv_rmse_std']:.4f}")

        # Feature importance
        if hasattr(model, "feature_importances_"):
            print("\n  🏆 Feature Importance:")
            importances = list(zip(feature_cols, model.feature_importances_))
            importances.sort(key=lambda x: x[1], reverse=True)
            for feat, imp in importances:
                bar = "█" * int(imp * 50)
                print(f"  {feat:25s} {imp:.4f} {bar}")

    return {
        "model": model,
        "encoders": encoders,
        "feature_cols": feature_cols,
        "metrics": metrics,
        "df_scored": df_scored,
    }


# ═══════════════════════════════════════════════════════════════════
# 7) MODEL KAYDET / YÜKLE
# ═══════════════════════════════════════════════════════════════════
def save_model(model, encoders, feature_cols, model_dir: str | None = None):
    """Modeli ve encoder'ları diske kaydeder."""
    save_dir = model_dir or MODEL_DIR
    os.makedirs(save_dir, exist_ok=True)

    m_path = os.path.join(save_dir, "menu_popularity_model.joblib")
    e_path = os.path.join(save_dir, "label_encoders.joblib")
    f_path = os.path.join(save_dir, "feature_columns.joblib")

    joblib.dump(model, m_path)
    joblib.dump(encoders, e_path)
    joblib.dump(feature_cols, f_path)

    print(f"\n💾 Model kaydedildi: {m_path}")
    print(f"   Encoder'lar     : {e_path}")
    print(f"   Feature sütunlar: {f_path}")


def load_trained_model(model_dir: str | None = None):
    """Kaydedilmiş modeli ve encoder'ları yükler."""
    load_dir = model_dir or MODEL_DIR

    m_path = os.path.join(load_dir, "menu_popularity_model.joblib")
    e_path = os.path.join(load_dir, "label_encoders.joblib")
    f_path = os.path.join(load_dir, "feature_columns.joblib")

    if not os.path.exists(m_path):
        print(f"⚠️ Model dosyası bulunamadı: {m_path}")
        return None, None, None

    model = joblib.load(m_path)
    encoders = joblib.load(e_path)
    feature_cols = joblib.load(f_path)

    print(f"✅ Model yüklendi: {type(model).__name__}")
    return model, encoders, feature_cols


# ═══════════════════════════════════════════════════════════════════
# 8) TEK YEMEK İÇİN POPÜLERLİK TAHMİNİ
# ═══════════════════════════════════════════════════════════════════
def predict_popularity(
    model,
    encoders: dict,
    feature_cols: list,
    yemek_adi: str,
    kategori: str,
    tarih: date,
    gun: str,
    onceki_yemek: str = "yok",
    tekrar_7gun: int = 0,
) -> float:
    """Tek bir yemek için popülerlik skoru tahmini."""
    ay = tarih.month
    mevsim_str = MEVSIM_MAP.get(ay, "kış")
    mevsim = MEVSIM_NUM[mevsim_str]
    gun_hafta = GUN_MAP.get(gun, 0)
    hafta_no = tarih.isocalendar()[1]
    yilin_gunu = tarih.timetuple().tm_yday
    ayni_onceki = 1 if yemek_adi == onceki_yemek else 0

    # Encode — bilinmeyen sınıf güvenli
    def safe_encode(encoder, value):
        if value in encoder.classes_:
            return encoder.transform([value])[0]
        return len(encoder.classes_)  # bilinmeyen = son index + 1

    yemek_enc = safe_encode(encoders["yemek"], yemek_adi)
    kat_enc = safe_encode(encoders["kategori"], kategori)
    onceki_enc = safe_encode(encoders["onceki"], onceki_yemek)

    features = np.array([[
        gun_hafta, ay, mevsim, hafta_no, yilin_gunu,
        yemek_enc, kat_enc, tekrar_7gun, onceki_enc, ayni_onceki,
    ]])

    skor = float(model.predict(features)[0])
    return max(0.0, min(1.0, skor))


# ═══════════════════════════════════════════════════════════════════
# 8.5) MULTI-OBJECTIVE & CONSTRAINT YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def _load_optimization_weights() -> dict[str, float]:
    """Kaydedilmiş ağırlıkları yükler; yoksa varsayılanları döndürür."""
    try:
        if os.path.exists(OPTIMIZATION_WEIGHTS_PATH):
            with open(OPTIMIZATION_WEIGHTS_PATH, "r", encoding="utf-8") as f:
                w = json.load(f)
            # Validasyon
            if all(k in w for k in OPTIMIZATION_WEIGHTS):
                return w
    except Exception:
        pass
    return dict(OPTIMIZATION_WEIGHTS)


def save_optimization_weights(weights: dict[str, float]) -> bool:
    """Admin dashboard'dan gelen ağırlıkları kaydeder."""
    try:
        required_keys = {"populerlik", "israf", "beslenme", "maliyet"}
        if not required_keys.issubset(weights.keys()):
            return False
        total = sum(weights[k] for k in required_keys)
        if total <= 0:
            return False
        # Normalize et (toplam = 1.0)
        normalized = {k: round(weights[k] / total, 4) for k in required_keys}
        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(OPTIMIZATION_WEIGHTS_PATH, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _detect_et_turu(yemek_adi: str) -> str | None:
    """Yemek adından et türünü tespit eder. Bulamazsa None döner."""
    ad_lower = yemek_adi.lower()
    for tur, keywords in ET_TURU_ANAHTAR.items():
        for kw in keywords:
            if kw in ad_lower:
                return tur
    return None


def _detect_allerjenler(yemek_adi: str) -> set[str]:
    """Yemek adından içerdiği allerjen gruplarını tespit eder."""
    ad_lower = yemek_adi.lower()
    sonuc = set()
    for grup, keywords in ALLERJEN_GRUPLAR.items():
        for kw in keywords:
            if kw in ad_lower:
                sonuc.add(grup)
                break
    return sonuc


def _is_sebze_yemegi(yemek_adi: str) -> bool:
    """Yemek adının sebze yemeği olup olmadığını kontrol eder."""
    ad_lower = yemek_adi.lower()
    return any(sk in ad_lower for sk in SEBZE_ANAHTAR)


def _build_israf_map(db, tarih: date) -> dict[str, float]:
    """Son 30 günlük yemek bazlı ortalama israf oranlarını döndürür."""
    from sqlalchemy import func as _sqla_f
    try:
        son_30_gun = tarih - timedelta(days=30)
        rows = (
            db.query(
                UretimLog.yemek_adi,
                _sqla_f.avg(UretimLog.israf_orani).label("ort_israf"),
                _sqla_f.count(UretimLog.id).label("kayit"),
            )
            .filter(
                UretimLog.tarih >= son_30_gun,
                UretimLog.israf_orani.isnot(None),
            )
            .group_by(UretimLog.yemek_adi)
            .all()
        )
        result = {}
        for row in rows:
            if row.kayit and row.kayit >= 2:
                key = _normalize_meal_key(row.yemek_adi)
                result[key] = float(row.ort_israf or 0)
        return result
    except Exception:
        return {}


def _compute_multi_objective_score(
    *,
    populerlik_skor: float,
    israf_orani: float,
    beslenme_skoru: float,
    maliyet_skoru: float,
    weights: dict[str, float],
) -> float:
    """
    Çok amaçlı optimizasyon skor fonksiyonu.

    Her bileşen 0-1 arasında normalize edilmiş olmalıdır:
      - populerlik_skor: 0-1, yüksek = iyi
      - israf_orani: 0-1 (0-100 / 100), düşük = iyi → (1 - israf) ile çevrilir
      - beslenme_skoru: 0-1, yüksek = iyi
      - maliyet_skoru: 0-1, yüksek = uygun bütçe
    """
    israf_normalized = max(0.0, 1.0 - israf_orani)

    score = (
        weights.get("populerlik", 0.35) * populerlik_skor
        + weights.get("israf", 0.30) * israf_normalized
        + weights.get("beslenme", 0.20) * beslenme_skoru
        + weights.get("maliyet", 0.15) * maliyet_skoru
    )
    return round(max(0.0, min(1.0, score)), 4)


def _compute_beslenme_skoru(
    gun_kalori: float,
    gun_protein: float,
    aday_kalori: float,
    aday_protein: float,
) -> float:
    """
    Günlük beslenme durumuna göre 0-1 arası skor döndürür.
    İdeal kalori aralığına yakınlık + protein yeterliliği ölçer.
    """
    tahmini_kalori = gun_kalori + aday_kalori
    tahmini_protein = gun_protein + aday_protein

    # Kalori skoru: ideal merkezden (800) uzaklık
    ideal = BESLENME_HEDEF["kalori_ideal"]
    kalori_fark = abs(tahmini_kalori - ideal) / ideal
    kalori_skor = max(0.0, 1.0 - kalori_fark)

    # Kalori aşım/düşüş cezası
    if tahmini_kalori > BESLENME_HEDEF["kalori_max"]:
        asim = (tahmini_kalori - BESLENME_HEDEF["kalori_max"]) / 300
        kalori_skor -= min(asim, 0.4)
    elif tahmini_kalori < BESLENME_HEDEF["kalori_min"] * 0.7:
        kalori_skor -= 0.2

    # Protein skoru
    protein_skor = min(1.0, tahmini_protein / BESLENME_HEDEF["protein_min"])

    return round(max(0.0, kalori_skor * 0.6 + protein_skor * 0.4), 3)


def _compute_maliyet_skoru(
    gun_maliyet: float,
    aday_kategori: str,
    aday_maliyet: float | None = None,
) -> float:
    """
    Günlük maliyet durumuna göre 0-1 arası bütçe uygunluk skoru döndürür.
    Bütçe hedefini aşmamak daha yüksek skor verir.

    Args:
        gun_maliyet: O güne kadar birikmiş maliyet (TL)
        aday_kategori: Aday yemeğin kategorisi (fallback için)
        aday_maliyet: Aday yemeğin gerçek birim maliyeti. None ise KATEGORI_MALIYET kullanılır.
    """
    if aday_maliyet is None:
        aday_maliyet = KATEGORI_MALIYET.get(aday_kategori, 15.0)
    tahmini_toplam = gun_maliyet + aday_maliyet

    if tahmini_toplam <= GUNLUK_BUTCE_HEDEF:
        # Bütçe altında — tam skor
        return 1.0
    else:
        # Bütçe aşımı — orantılı penaltı
        asim_oran = (tahmini_toplam - GUNLUK_BUTCE_HEDEF) / GUNLUK_BUTCE_HEDEF
        return round(max(0.0, 1.0 - asim_oran * 2), 3)


# ═══════════════════════════════════════════════════════════════════
# 9) HAFTALIK MENÜ OPTİMİZASYONU (Multi-Objective + Constraint)
# ═══════════════════════════════════════════════════════════════════
def generate_weekly_menu(
    yemek_listesi: list[dict],
    baslangic_tarihi: date | None = None,
    model=None,
    encoders: dict | None = None,
    feature_cols: list | None = None,
    custom_weights: dict[str, float] | None = None,
) -> list[dict]:
    """
    Multi-objective + constraint-based haftalık menü optimizasyonu.

    Multi-Objective Hedefler (ağırlıklı):
      - Popülerlik maximizasyonu
      - İsraf minimizasyonu
      - Beslenme dengesi (kalori, protein hedefleri)
      - Maliyet optimizasyonu

    Hard Constraints:
      - Aynı yemek haftada en fazla 2 kez
      - Her gün farklı çorba
      - Aynı et türü (tavuk/kırmızı et/balık) haftada max 2 kez
      - Haftada min 1 gün ağırlıklı sebze menüsü
      - Aynı gün max 3 allerjen grubu
      - KRİTİK uyarılı yemekler otomatik elenir

    Args:
        yemek_listesi: DB'den gelen yemek dict listesi
        baslangic_tarihi: Menünün başlangıç tarihi
        model/encoders/feature_cols: Eğitilmiş ML model (opsiyonel)
        custom_weights: Özel optimizasyon ağırlıkları (opsiyonel)

    Returns:
        list[dict]: 5 günlük optimize edilmiş menü (beslenme + maliyet özeti dahil)
    """
    # Varsayılan başlangıç: gelecek Pazartesi
    if baslangic_tarihi is None:
        bugun = date.today()
        gun_fark = (7 - bugun.weekday()) % 7
        if gun_fark == 0:
            gun_fark = 7
        baslangic_tarihi = bugun + timedelta(days=gun_fark)

    # Model yükleme (eğer verilmemişse diskten)
    if model is None:
        model, encoders, feature_cols = load_trained_model()

    # ── Optimizasyon ağırlıklarını yükle ──
    weights = custom_weights if custom_weights else _load_optimization_weights()

    # Yemekleri kategoriye göre grupla
    havuz: dict[str, list[dict]] = {
        "corba": [], "ana_yemek": [], "yan_yemek": [], "tatli": [], "salata": [],
    }
    for y in yemek_listesi:
        kat = y.get("kategori", "")
        if kat in havuz:
            havuz[kat].append(y)

    # Besin değeri lookup: yemek adı → {kalori, protein, karbonhidrat, yag}
    besin_lookup: dict[str, dict] = {}
    for y in yemek_listesi:
        besin_lookup[y["ad"]] = {
            "kalori": float(y.get("kalori", 0) or 0),
            "protein": float(y.get("protein", 0) or 0),
            "karbonhidrat": float(y.get("karbonhidrat", 0) or 0),
            "yag": float(y.get("yag", 0) or 0),
        }

    # Maliyet lookup: yemek adı → birim_maliyet (TL)
    # Öncelik: Yemek.birim_maliyet → fallback KATEGORI_MALIYET
    maliyet_lookup: dict[str, float] = {}
    for y in yemek_listesi:
        birim = y.get("birim_maliyet")
        if birim is not None:
            try:
                maliyet_lookup[y["ad"]] = float(birim)
                continue
            except (TypeError, ValueError):
                pass
        maliyet_lookup[y["ad"]] = KATEGORI_MALIYET.get(y.get("kategori", ""), 15.0)

    def _maliyet_for(ad: str, kategori: str) -> float:
        """Yemek adı için maliyet (DB öncelikli, fallback kategori)."""
        if ad in maliyet_lookup:
            return maliyet_lookup[ad]
        return KATEGORI_MALIYET.get(kategori, 15.0)

    # ── İsraf haritasını batch olarak oluştur (her aday için ayrı DB sorgusu yerine) ──
    israf_map: dict[str, float] = {}
    try:
        db_israf = SessionLocal()
        israf_map = _build_israf_map(db_israf, baslangic_tarihi)
        db_israf.close()
    except Exception:
        pass

    # ── KRİTİK uyarılı yemekleri toplu al ──
    kritik_yemekler: set[str] = set()
    try:
        db_krt = SessionLocal()
        kritik_alerts = db_krt.query(Alert.yemek_adi).filter(
            Alert.seviye == "KRITIK",
            Alert.aktif == True,
            Alert.yemek_adi.isnot(None),
        ).all()
        kritik_yemekler = {a.yemek_adi for a in kritik_alerts}
        db_krt.close()
    except Exception:
        pass

    # ── Gerçek puan haritasını toplu al ──
    puan_map: dict[str, dict] = {}
    try:
        db_puan = SessionLocal()
        puan_map = _build_rating_signal_map(db_puan)
        db_puan.close()
    except Exception:
        pass

    # ── Haftalık constraint takibi ──
    haftalik_kullanim: dict[str, int] = {}
    haftalik_et_sayac: dict[str, int] = {
        "tavuk": 0, "kirmizi_et": 0, "balik": 0,
    }
    haftalik_sebze_gun_sayisi = 0

    haftalik_menu = []

    for i, gun in enumerate(GUNLER):
        tarih = baslangic_tarihi + timedelta(days=i)
        gun_menusu: dict[str, Any] = {"tarih": str(tarih), "gun": gun}

        # ── Günlük takip ──
        gun_kalori = 0.0
        gun_protein = 0.0
        gun_karbonhidrat = 0.0
        gun_yag = 0.0
        gun_maliyet = 0.0
        gun_sebze_var = False
        gun_allerjenler: set[str] = set()
        gun_skor_detay: dict[str, float] = {}

        # Son günlerdeyiz ve sebze günü dolmadıysa → bonus artır
        kalan_gun = len(GUNLER) - i
        sebze_acil = (
            haftalik_sebze_gun_sayisi < MIN_SEBZE_GUN
            and kalan_gun <= MIN_SEBZE_GUN
        )

        for kat_key in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
            adaylar = havuz.get(kat_key, [])
            if not adaylar:
                gun_menusu[kat_key] = "Belirtilmedi"
                continue

            skorlu: list[tuple[dict, float]] = []

            for aday in adaylar:
                ad = aday["ad"]

                # ── Hard Constraint 1: KRİTİK uyarılı yemek → atla ──
                if ad in kritik_yemekler:
                    continue

                # ── Hard Constraint 2: Her yemek haftada en fazla 1 kez ──
                if haftalik_kullanim.get(ad, 0) >= 1:
                    continue

                # ── Hard Constraint 4: Et türü haftada max 2 ──
                et_turu = _detect_et_turu(ad)
                if et_turu and haftalik_et_sayac.get(et_turu, 0) >= HAFTALIK_ET_LIMIT:
                    continue

                # ── Hard Constraint 5: Günlük allerjen çeşitliliği ──
                aday_allerjenler = _detect_allerjenler(ad)
                birlesmis_allerjen = gun_allerjenler | aday_allerjenler
                if len(birlesmis_allerjen) > MAX_AYNI_GUN_ALLERJEN:
                    continue

                # ── Popülerlik Skoru ──
                if model is not None and encoders is not None:
                    tekrar = haftalik_kullanim.get(ad, 0)
                    pop_skor = predict_popularity(
                        model, encoders, feature_cols,
                        yemek_adi=ad,
                        kategori=kat_key,
                        tarih=tarih,
                        gun=gun,
                        tekrar_7gun=tekrar,
                    )
                else:
                    pop_skor = YEMEK_BAZI_POPULERLIK.get(ad, 0.5) + random.uniform(-0.05, 0.05)

                # Gerçek puan feedback
                meal_key = _normalize_meal_key(ad)
                puan_info = puan_map.get(meal_key)
                if puan_info and puan_info.get("toplam_oy", 0) > 0:
                    ort = puan_info["ortalama"]
                    if ort < 2.0:
                        pop_skor -= 0.20
                    elif ort < 2.5:
                        pop_skor -= 0.12
                    elif ort > 4.5:
                        pop_skor += 0.15
                    elif ort > 4.0:
                        pop_skor += 0.08
                pop_skor = max(0.0, min(1.0, pop_skor))

                # ── İsraf Skoru ──
                israf_oran = israf_map.get(meal_key, 20.0)  # varsayılan %20
                israf_normalized = min(1.0, israf_oran / 100.0)

                # ── Beslenme Skoru ──
                besin = besin_lookup.get(ad, {})
                aday_kalori = besin.get("kalori", 0)
                aday_protein = besin.get("protein", 0)
                beslenme_s = _compute_beslenme_skoru(
                    gun_kalori, gun_protein, aday_kalori, aday_protein,
                )

                # Sebze bonusu: son günler + sebze günü eksikse
                if _is_sebze_yemegi(ad):
                    if kat_key in ("ana_yemek", "salata") and not gun_sebze_var:
                        beslenme_s = min(1.0, beslenme_s + 0.10)
                    if sebze_acil:
                        beslenme_s = min(1.0, beslenme_s + 0.15)

                # ── Maliyet Skoru ──
                maliyet_s = _compute_maliyet_skoru(gun_maliyet, kat_key, _maliyet_for(ad, kat_key))

                # ── Multi-Objective Birleşik Skor ──
                final_skor = _compute_multi_objective_score(
                    populerlik_skor=pop_skor,
                    israf_orani=israf_normalized,
                    beslenme_skoru=beslenme_s,
                    maliyet_skoru=maliyet_s,
                    weights=weights,
                )

                skorlu.append((aday, final_skor))

            # En yüksek skora göre sırala ve ilkini seç
            if skorlu:
                skorlu.sort(key=lambda x: x[1], reverse=True)
                secilen, skor = skorlu[0]
                ad_secilen = secilen["ad"]
                gun_menusu[kat_key] = ad_secilen
                gun_menusu[f"{kat_key}_skor"] = round(skor, 3)

                # ── Constraint state güncelle ──
                haftalik_kullanim[ad_secilen] = haftalik_kullanim.get(ad_secilen, 0) + 1

                et_t = _detect_et_turu(ad_secilen)
                if et_t:
                    haftalik_et_sayac[et_t] = haftalik_et_sayac.get(et_t, 0) + 1

                gun_allerjenler |= _detect_allerjenler(ad_secilen)

                if _is_sebze_yemegi(ad_secilen):
                    gun_sebze_var = True

                # ── Günlük beslenme + maliyet takibi güncelle ──
                besin_s = besin_lookup.get(ad_secilen, {})
                gun_kalori += besin_s.get("kalori", 0)
                gun_protein += besin_s.get("protein", 0)
                gun_karbonhidrat += besin_s.get("karbonhidrat", 0)
                gun_yag += besin_s.get("yag", 0)
                gun_maliyet += _maliyet_for(ad_secilen, kat_key)
            else:
                # Tüm adaylar kısıtla elendiyse → en az tekrar edeni seç
                adaylar_sorted = sorted(
                    adaylar,
                    key=lambda a: haftalik_kullanim.get(a["ad"], 0),
                )
                secilen = adaylar_sorted[0]
                gun_menusu[kat_key] = secilen["ad"]
                gun_menusu[f"{kat_key}_skor"] = 0.5
                haftalik_kullanim[secilen["ad"]] = haftalik_kullanim.get(secilen["ad"], 0) + 1

                besin_s = besin_lookup.get(secilen["ad"], {})
                gun_kalori += besin_s.get("kalori", 0)
                gun_protein += besin_s.get("protein", 0)
                gun_karbonhidrat += besin_s.get("karbonhidrat", 0)
                gun_yag += besin_s.get("yag", 0)
                gun_maliyet += _maliyet_for(secilen["ad"], kat_key)

        # Sebze günü sayacını güncelle
        if gun_sebze_var:
            haftalik_sebze_gun_sayisi += 1

        # ── Günlük beslenme özeti ──
        kalori_durum = "Dengeli"
        if gun_kalori < BESLENME_HEDEF["kalori_min"]:
            kalori_durum = "Dusuk kalorili"
        elif gun_kalori > BESLENME_HEDEF["kalori_max"]:
            kalori_durum = "Yuksek kalorili"

        gun_menusu["beslenme"] = {
            "toplam_kalori": round(gun_kalori, 1),
            "toplam_protein": round(gun_protein, 1),
            "toplam_karbonhidrat": round(gun_karbonhidrat, 1),
            "toplam_yag": round(gun_yag, 1),
            "kalori_durum": kalori_durum,
            "protein_yeterli": gun_protein >= BESLENME_HEDEF["protein_min"],
            "sebze_var": gun_sebze_var,
        }

        gun_menusu["maliyet"] = {
            "tahmini_gunluk_tl": round(gun_maliyet, 1),
            "butce_durum": "Uygun" if gun_maliyet <= GUNLUK_BUTCE_HEDEF else "Asim",
        }

        gun_menusu["constraint_info"] = {
            "allerjen_gruplari": sorted(gun_allerjenler),
            "et_turleri_haftalik": dict(haftalik_et_sayac),
            "sebze_gun_sayisi": haftalik_sebze_gun_sayisi,
        }

        haftalik_menu.append(gun_menusu)

    return haftalik_menu


# ═══════════════════════════════════════════════════════════════════
# 10) MENÜ SKORU HESAPLA
# ═══════════════════════════════════════════════════════════════════
def calculate_menu_score(haftalik_menu: list[dict]) -> dict:
    """Haftalık menünün toplam ve ortalama popülerlik skorunu hesaplar."""
    tum_skorlar = []
    for gun_menu in haftalik_menu:
        for kat in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
            skor_key = f"{kat}_skor"
            if skor_key in gun_menu:
                tum_skorlar.append(gun_menu[skor_key])

    if not tum_skorlar:
        return {"toplam": 0, "ortalama": 0, "min": 0, "max": 0}

    return {
        "toplam": round(sum(tum_skorlar), 3),
        "ortalama": round(np.mean(tum_skorlar), 3),
        "min": round(min(tum_skorlar), 3),
        "max": round(max(tum_skorlar), 3),
        "yemek_sayisi": len(tum_skorlar),
    }


# ═══════════════════════════════════════════════════════════════════
# 11) PUANLAMA VERİSİYLE YENİDEN EĞİTİM
# ═══════════════════════════════════════════════════════════════════
def retrain_with_ratings(
    csv_path: str = None,
    model_type: str = "gradient_boosting",
    verbose: bool = True,
) -> dict:
    """
    Gerçek puanlama verisini de dahil ederek modeli yeniden eğitir.
    Puanlama veritabanı tablosundaki ortalama puanları feature olarak ekler.
    """
    if csv_path is None:
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "menu_data.csv"
        )

    if verbose:
        print("\n🔄 Puanlama verisi dahil edilerek model yeniden eğitiliyor...")

    # Normal eğitim pipeline'ını çağır
    # (generate_popularity_scores artık DB'den gerçek puanları da çekiyor)
    result = train_model(
        csv_path=csv_path,
        model_type=model_type,
        verbose=verbose,
    )

    # Modeli kaydet
    if result and result.get("model"):
        save_model(
            result["model"],
            result["encoders"],
            result["feature_cols"],
        )
        if verbose:
            print("✅ Model gerçek puanlama verisi ile yeniden eğitildi ve kaydedildi.")

    return result


# ═══════════════════════════════════════════════════════════════════
# 12) A/B TEST: AI ÖNERİSİ KAYDET
# ═══════════════════════════════════════════════════════════════════
def save_menu_suggestion(
    haftalik_menu: list[dict],
    baslangic_tarihi: date,
    db=None,
) -> dict[str, Any]:
    """
    AI tarafından oluşturulan haftalık menü önerisini MenuOneriLog tablosuna kaydeder.
    A/B test karşılaştırması için kullanılır.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        kayit_sayisi = 0
        for gun_menu in haftalik_menu:
            tarih_str = gun_menu.get("tarih")
            tarih = date.fromisoformat(tarih_str) if tarih_str else baslangic_tarihi

            beslenme = gun_menu.get("beslenme", {})

            # Skor bileşenlerini topla
            skorlar = []
            for kat in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
                sk = gun_menu.get(f"{kat}_skor")
                if sk is not None:
                    skorlar.append(sk)
            ort_skor = sum(skorlar) / len(skorlar) if skorlar else 0.0

            log = MenuOneriLog(
                hafta_baslangic=baslangic_tarihi,
                gun=gun_menu.get("gun", ""),
                tarih=tarih,
                corba=gun_menu.get("corba"),
                ana_yemek=gun_menu.get("ana_yemek"),
                yan_yemek=gun_menu.get("yan_yemek"),
                tatli=gun_menu.get("tatli"),
                salata=gun_menu.get("salata"),
                toplam_skor=round(ort_skor, 3),
                beslenme_skoru=None,
                israf_skoru=None,
                maliyet_skoru=None,
                populerlik_skoru=round(ort_skor, 3),
                toplam_kalori=beslenme.get("toplam_kalori"),
                toplam_protein=beslenme.get("toplam_protein"),
            )
            db.add(log)
            kayit_sayisi += 1

        db.commit()
        logger.info("A/B test: %d gunluk AI menu onerisi kaydedildi.", kayit_sayisi)
        return {
            "success": True,
            "message": f"{kayit_sayisi} gunluk AI menu onerisi kaydedildi.",
            "hafta_baslangic": str(baslangic_tarihi),
            "kayit_sayisi": kayit_sayisi,
        }
    except Exception as e:
        db.rollback()
        logger.warning("A/B test kaydi basarisiz: %s", e)
        return {"success": False, "message": str(e)}
    finally:
        if close_db:
            db.close()


# ═══════════════════════════════════════════════════════════════════
# 13) A/B TEST: AI ÖNERİSİ vs GERÇEK MENÜ KARŞILAŞTIRMASI
# ═══════════════════════════════════════════════════════════════════
def compare_ai_vs_actual(
    hafta_baslangic: date,
    db=None,
) -> dict[str, Any]:
    """
    Belirli bir hafta için AI menü önerisi ile gerçek uygulanan menüyü karşılaştırır.

    Karşılaştırma metrikleri:
      - Örtüşme oranı (aynı yemek seçilme yüzdesi)
      - AI önerisinin tahmini israfı vs gerçek israf
      - Beslenme dengesi farkı
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        from sqlalchemy import func as _sqla_f

        hafta_bitis = hafta_baslangic + timedelta(days=5)

        # ── AI önerilerini al ──
        ai_oneriler = (
            db.query(MenuOneriLog)
            .filter(MenuOneriLog.hafta_baslangic == hafta_baslangic)
            .order_by(MenuOneriLog.tarih)
            .all()
        )
        if not ai_oneriler:
            return {
                "success": False,
                "message": f"{hafta_baslangic} haftasi icin AI onerisi bulunamadi.",
            }

        # ── Gerçek menüyü al (Menu tablosundan) ──
        gercek_menuler = (
            db.query(Menu)
            .filter(Menu.tarih >= hafta_baslangic, Menu.tarih < hafta_bitis)
            .order_by(Menu.tarih)
            .all()
        )

        # ── Gerçek israf verilerini al ──
        israf_rows = (
            db.query(
                UretimLog.yemek_adi,
                _sqla_f.avg(UretimLog.israf_orani).label("ort_israf"),
            )
            .filter(
                UretimLog.tarih >= hafta_baslangic,
                UretimLog.tarih < hafta_bitis,
                UretimLog.israf_orani.isnot(None),
            )
            .group_by(UretimLog.yemek_adi)
            .all()
        )
        gercek_israf_map = {
            _normalize_meal_key(r.yemek_adi): float(r.ort_israf)
            for r in israf_rows if r.ort_israf is not None
        }

        # ── Karşılaştırma hesapla ──
        kategoriler = ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]
        toplam_eslesme = 0
        toplam_slot = 0
        ai_israf_toplam = 0.0
        gercek_israf_toplam = 0.0
        israf_karsilastirma_sayisi = 0
        ai_kalori_toplam = 0.0

        gunluk_detay = []

        for ai_oneri in ai_oneriler:
            gun_detay = {
                "tarih": str(ai_oneri.tarih),
                "gun": ai_oneri.gun,
                "eslesme": {},
            }

            # Aynı tarihteki gerçek menüyü bul
            gercek = None
            for gm in gercek_menuler:
                if gm.tarih == ai_oneri.tarih:
                    gercek = gm
                    break

            for kat in kategoriler:
                ai_yemek = getattr(ai_oneri, kat, None)
                gercek_yemek = getattr(gercek, kat, None) if gercek else None
                toplam_slot += 1

                eslesti = False
                if ai_yemek and gercek_yemek:
                    ai_key = _normalize_meal_key(ai_yemek)
                    gercek_key = _normalize_meal_key(gercek_yemek)
                    eslesti = ai_key == gercek_key
                    if eslesti:
                        toplam_eslesme += 1

                gun_detay["eslesme"][kat] = {
                    "ai_oneri": ai_yemek,
                    "gercek": gercek_yemek,
                    "eslesti": eslesti,
                }

                # İsraf karşılaştırması
                if ai_yemek:
                    ai_key_israf = _normalize_meal_key(ai_yemek)
                    ai_israf = gercek_israf_map.get(ai_key_israf)
                    if ai_israf is not None:
                        ai_israf_toplam += ai_israf
                        israf_karsilastirma_sayisi += 1
                if gercek_yemek:
                    gercek_key_israf = _normalize_meal_key(gercek_yemek)
                    g_israf = gercek_israf_map.get(gercek_key_israf)
                    if g_israf is not None:
                        gercek_israf_toplam += g_israf

            # Kalori karşılaştırması
            if ai_oneri.toplam_kalori:
                ai_kalori_toplam += ai_oneri.toplam_kalori

            gunluk_detay.append(gun_detay)

        # ── Özet hesapla ──
        eslesme_orani = (toplam_eslesme / toplam_slot * 100) if toplam_slot > 0 else 0
        ai_ort_israf = (ai_israf_toplam / israf_karsilastirma_sayisi) if israf_karsilastirma_sayisi > 0 else None
        gercek_ort_israf = (gercek_israf_toplam / israf_karsilastirma_sayisi) if israf_karsilastirma_sayisi > 0 else None

        israf_farki = None
        if ai_ort_israf is not None and gercek_ort_israf is not None:
            israf_farki = round(gercek_ort_israf - ai_ort_israf, 2)

        return {
            "success": True,
            "hafta_baslangic": str(hafta_baslangic),
            "ai_oneri_gun_sayisi": len(ai_oneriler),
            "gercek_menu_gun_sayisi": len(gercek_menuler),
            "ozet": {
                "eslesme_orani": round(eslesme_orani, 1),
                "toplam_eslesme": toplam_eslesme,
                "toplam_slot": toplam_slot,
                "ai_ort_israf": round(ai_ort_israf, 2) if ai_ort_israf is not None else None,
                "gercek_ort_israf": round(gercek_ort_israf, 2) if gercek_ort_israf is not None else None,
                "israf_farki_puan": israf_farki,
                "israf_yorum": (
                    f"AI onerisi %{abs(israf_farki):.1f} daha az israf uretecekti"
                    if israf_farki and israf_farki > 0
                    else (
                        f"Gercek menu %{abs(israf_farki):.1f} daha az israf uretti"
                        if israf_farki and israf_farki < 0
                        else "Israf verisi yetersiz veya esit"
                    )
                ),
            },
            "gunluk_detay": gunluk_detay,
        }
    except Exception as e:
        logger.warning("A/B test karsilastirmasi basarisiz: %s", e)
        return {"success": False, "message": str(e)}
    finally:
        if close_db:
            db.close()
