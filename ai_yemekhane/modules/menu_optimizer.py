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

import os
import random
import hashlib
import re
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder

from models import SessionLocal, MenuPuanlama, Alert, UretimLog

# ─── Sabitler ──────────────────────────────────────────────────────
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
GUN_MAP = {"Pazartesi": 0, "Salı": 1, "Çarşamba": 2, "Perşembe": 3, "Cuma": 4}

MEVSIM_MAP = {1: "kış", 2: "kış", 3: "ilkbahar", 4: "ilkbahar", 5: "ilkbahar",
              6: "yaz", 7: "yaz", 8: "yaz", 9: "sonbahar", 10: "sonbahar",
              11: "sonbahar", 12: "kış"}
MEVSIM_NUM = {"kış": 0, "ilkbahar": 1, "yaz": 2, "sonbahar": 3}

KATEGORI_KOLONLARI = ["corba", "ana_yemek", "pilav_makarna", "tatli", "salata"]

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models_data")
MODEL_PATH = os.path.join(MODEL_DIR, "menu_popularity_model.joblib")
ENCODERS_PATH = os.path.join(MODEL_DIR, "label_encoders.joblib")
FEATURES_PATH = os.path.join(MODEL_DIR, "feature_columns.joblib")

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
                # CSV'deki "pilav_makarna" kolonu, uygulamadaki "pilav"
                # kategorisine karşılık gelir; eğitim ve runtime tutarlı olmalı.
                kategori = "pilav" if kat == "pilav_makarna" else kat
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
# 9) HAFTALIK MENÜ OPTİMİZASYONU
# ═══════════════════════════════════════════════════════════════════
def generate_weekly_menu(
    yemek_listesi: list[dict],
    baslangic_tarihi: date | None = None,
    model=None,
    encoders: dict | None = None,
    feature_cols: list | None = None,
) -> list[dict]:
    """
    Kısıt tabanlı haftalık menü optimizasyonu.

    Kısıtlar:
      - Aynı yemek haftada en fazla 2 kez
      - Her gün farklı çorba
      - Popülerlik skoru en yüksek kombinasyon tercih edilir

    Args:
        yemek_listesi: DB'den gelen yemek dict listesi soru
        baslangic_tarihi: Menünün başlangıç tarihi
        model/encoders/feature_cols: Eğitilmiş ML model (opsiyonel)

    Returns:
        list[dict]: 5 günlük optimize edilmiş menü
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

    # Yemekleri kategoriye göre grupla
    havuz: dict[str, list[dict]] = {
        "corba": [], "ana_yemek": [], "pilav": [], "tatli": [], "salata": [],
    }
    for y in yemek_listesi:
        kat = y.get("kategori", "")
        if kat in havuz:
            havuz[kat].append(y)

    # Haftalık seçim takibi (kısıt: haftada en fazla 2 kez)
    haftalik_kullanim: dict[str, int] = {}
    secilen_corba: set[str] = set()  # Her gün farklı çorba

    haftalik_menu = []

    for i, gun in enumerate(GUNLER):
        tarih = baslangic_tarihi + timedelta(days=i)
        gun_menusu = {"tarih": str(tarih), "gun": gun}

        for kat_key in ["corba", "ana_yemek", "pilav", "tatli", "salata"]:
            adaylar = havuz.get(kat_key, [])
            if not adaylar:
                gun_menusu[kat_key] = "Belirtilmedi"
                continue

            # Adayları skorla
            skorlu = []

            # KRİTİK uyarılı yemekleri filtrele
            try:
                kritik_yemekler = set()
                db_temp = SessionLocal()
                kritik_alerts = db_temp.query(Alert.yemek_adi).filter(
                    Alert.seviye == "KRITIK",
                    Alert.aktif == True,
                    Alert.yemek_adi.isnot(None),
                ).all()
                kritik_yemekler = {a.yemek_adi for a in kritik_alerts}
                db_temp.close()
            except Exception:
                kritik_yemekler = set()

            for aday in adaylar:
                ad = aday["ad"]

                # KRİTİK uyarılı yemek → atla
                if ad in kritik_yemekler:
                    continue

                # Kısıt kontrolü
                if haftalik_kullanim.get(ad, 0) >= 2:
                    continue  # Haftada 2'den fazla → geç
                if kat_key == "corba" and ad in secilen_corba:
                    continue  # Aynı çorba tekrar → geç

                # Skor hesapla
                if model is not None and encoders is not None:
                    tekrar = haftalik_kullanim.get(ad, 0)
                    skor = predict_popularity(
                        model, encoders, feature_cols,
                        yemek_adi=ad,
                        kategori=kat_key,
                        tarih=tarih,
                        gun=gun,
                        tekrar_7gun=tekrar,
                    )
                else:
                    # Model yoksa baz popülerlik + random
                    skor = YEMEK_BAZI_POPULERLIK.get(ad, 0.5) + random.uniform(-0.05, 0.05)

                skorlu.append((aday, skor))

            # Gerçek puan bazlı bonus/penaltı
            try:
                puan_info = get_meal_average_rating(ad)
                if puan_info["ortalama"] is not None:
                    ort = puan_info["ortalama"]
                    if ort < 2.5:
                        skor -= 0.15  # Düşük puanlı yemeklere penaltı
                    elif ort > 4.0:
                        skor += 0.10  # Yüksek puanlı yemeklere bonus
            except Exception:
                pass

            # İsraf skoru penaltısı
            try:
                from modules.waste_analyzer import calculate_waste_score
                israf = calculate_waste_score(ad)
                if israf["israf_skoru"] is not None and israf["israf_skoru"] > 50:
                    skor -= 0.12  # Yüksek israf skoru → daha az öner
                elif israf["israf_skoru"] is not None and israf["israf_skoru"] > 35:
                    skor -= 0.06  # Orta israf → hafif penaltı
            except Exception:
                pass

            # En yüksek skora göre sırala ve ilkini seç
            if skorlu:
                skorlu.sort(key=lambda x: x[1], reverse=True)
                secilen, skor = skorlu[0]
                ad_secilen = secilen["ad"]
                gun_menusu[kat_key] = ad_secilen
                gun_menusu[f"{kat_key}_skor"] = round(skor, 3)

                # Kısıt güncelle
                haftalik_kullanim[ad_secilen] = haftalik_kullanim.get(ad_secilen, 0) + 1
                if kat_key == "corba":
                    secilen_corba.add(ad_secilen)
            else:
                # Tüm adaylar kısıtla elendiyse rastgele seç
                secilen = random.choice(adaylar)
                gun_menusu[kat_key] = secilen["ad"]
                gun_menusu[f"{kat_key}_skor"] = 0.5

        haftalik_menu.append(gun_menusu)

    return haftalik_menu


# ═══════════════════════════════════════════════════════════════════
# 10) MENÜ SKORU HESAPLA
# ═══════════════════════════════════════════════════════════════════
def calculate_menu_score(haftalik_menu: list[dict]) -> dict:
    """Haftalık menünün toplam ve ortalama popülerlik skorunu hesaplar."""
    tum_skorlar = []
    for gun_menu in haftalik_menu:
        for kat in ["corba", "ana_yemek", "pilav", "tatli", "salata"]:
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
