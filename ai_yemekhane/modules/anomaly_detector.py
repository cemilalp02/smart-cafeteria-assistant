"""
Anomali Tespit Modülü — Öneri 4B (Akademik Katkı)
═══════════════════════════════════════════════════════════════════
Beklenmedik israf/tüketim sapmalarını otomatik tespit eder.

İki yöntem:
  1) Z-Score (univariate): Her yemek için son N gün israf değerlerinin
     z-skorunu hesaplar, |z| > eşik ise anomali işaretler.
  2) Isolation Forest (multivariate): (israf, porsiyon, puan, gün_tipi)
     vektörü üzerinde unsupervised anomali tespiti.

Sonuç: AnomaliKaydi tablosuna işlenir, alert_system'e entegre edilir.
XAI ile entegrasyon: anomali için SHAP açıklaması üretilebilir.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from models import SessionLocal, UretimLog, MenuPuanlama, AnomaliKaydi, Alert

# Isolation Forest opsiyonel (sklearn zaten yüklü)
try:
    from sklearn.ensemble import IsolationForest
    _HAS_IFOREST = True
except ImportError:
    _HAS_IFOREST = False


# ── Eşikler & Konfigürasyon ──────────────────────────────────────
ZSCORE_THRESHOLD = 2.0       # |z| > 2.0 → anomali (yaklaşık %95 güven)
MIN_HISTORY_DAYS = 14        # En az 14 günlük geçmiş gerekli
ISO_FOREST_CONTAMINATION = 0.05  # Beklenen anomali oranı (%5)
ISO_FOREST_MIN_SAMPLES = 30  # En az 30 örnek olmalı

# Şiddet eşikleri (z-score absolute value)
SIDDET_ESIKLERI = [
    (4.0, "KRITIK"),
    (3.0, "YUKSEK"),
    (2.5, "ORTA"),
    (2.0, "DUSUK"),
]


def _get_siddet(z_abs: float) -> str:
    """Z-score mutlak değerine göre şiddet seviyesi döndürür."""
    for esik, seviye in SIDDET_ESIKLERI:
        if z_abs >= esik:
            return seviye
    return "DUSUK"


def _normalize_score(z_abs: float) -> float:
    """Z-skoru 0-1 aralığına normalize eder (sigmoid benzeri)."""
    # |z|=2 → 0.5, |z|=4 → 0.88, |z|=6 → 0.99
    return float(min(1.0, z_abs / 6.0))


def detect_zscore_anomalies(
    target_date: date,
    db: Session,
    threshold: float = ZSCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Z-score yöntemiyle anomali tespit eder.

    Her yemek için son 30 günlük israf_orani değerlerinin
    ortalama ve standart sapmasını hesaplar, hedef tarihteki
    değerin z-skoru |threshold|'u aşıyorsa anomali olarak işaretler.
    """
    anomaliler: list[dict[str, Any]] = []

    # Hedef tarihteki üretim logları
    bugun_loglar = (
        db.query(UretimLog)
        .filter(
            UretimLog.tarih == target_date,
            UretimLog.israf_orani.isnot(None),
            UretimLog.uretilen_porsiyon > 0,
        )
        .all()
    )

    if not bugun_loglar:
        return anomaliler

    # Geçmiş periyot
    gecmis_basla = target_date - timedelta(days=30)

    for log in bugun_loglar:
        # Bu yemek için son 30 günün geçmişi (hedef tarih hariç)
        gecmis = (
            db.query(UretimLog.israf_orani)
            .filter(
                UretimLog.yemek_adi == log.yemek_adi,
                UretimLog.tarih >= gecmis_basla,
                UretimLog.tarih < target_date,
                UretimLog.israf_orani.isnot(None),
            )
            .all()
        )
        gecmis_vals = [float(g.israf_orani) for g in gecmis if g.israf_orani is not None]

        if len(gecmis_vals) < 5:
            # Yeterli geçmiş yoksa kategori bazında karşılaştır
            kategori_gecmis = (
                db.query(UretimLog.israf_orani)
                .filter(
                    UretimLog.kategori == log.kategori,
                    UretimLog.tarih >= gecmis_basla,
                    UretimLog.tarih < target_date,
                    UretimLog.israf_orani.isnot(None),
                )
                .all()
            )
            gecmis_vals = [float(g.israf_orani) for g in kategori_gecmis if g.israf_orani is not None]
            yontem_detay = "zscore (kategori)"
        else:
            yontem_detay = "zscore"

        if len(gecmis_vals) < 5:
            continue

        ortalama = float(np.mean(gecmis_vals))
        std = float(np.std(gecmis_vals))

        if std < 0.001:  # Varyans çok düşükse anlamsız
            continue

        gerceklesen = float(log.israf_orani)
        z = (gerceklesen - ortalama) / std

        if abs(z) < threshold:
            continue

        # Anomali tipi belirle
        if z > 0:
            tip = "ISRAF_ARTIS"
            yon = "yüksek"
        else:
            tip = "ISRAF_DUSUS"
            yon = "düşük"

        sapma_yuzde = ((gerceklesen - ortalama) / max(ortalama, 0.01)) * 100

        aciklama = (
            f"'{log.yemek_adi}' israf oranı normalin {yon}: "
            f"%{gerceklesen:.1f} (beklenen: %{ortalama:.1f}, z={z:+.2f}). "
            f"Son {len(gecmis_vals)} gün ortalamasından %{abs(sapma_yuzde):.0f} sapma."
        )

        anomaliler.append({
            "tarih": target_date,
            "yemek_adi": log.yemek_adi,
            "kategori": log.kategori,
            "anomali_tipi": tip,
            "yontem": yontem_detay,
            "skor": _normalize_score(abs(z)),
            "siddet": _get_siddet(abs(z)),
            "beklenen_deger": ortalama,
            "gerceklesen_deger": gerceklesen,
            "sapma_yuzdesi": sapma_yuzde,
            "aciklama": aciklama,
            "z_score": z,
        })

    return anomaliler


def detect_isolation_forest_anomalies(
    target_date: date,
    db: Session,
    contamination: float = ISO_FOREST_CONTAMINATION,
) -> list[dict[str, Any]]:
    """
    Isolation Forest ile multivariate anomali tespiti.
    Feature'lar: israf_orani, uretilen_porsiyon, gun_hafta, kategori_kodu

    Geçmiş 60 günü eğitir, hedef tarihi tahmin eder.
    """
    if not _HAS_IFOREST:
        return []

    anomaliler: list[dict[str, Any]] = []

    # Eğitim periyodu: son 60 gün
    egitim_basla = target_date - timedelta(days=60)

    egitim_query = (
        db.query(UretimLog)
        .filter(
            UretimLog.tarih >= egitim_basla,
            UretimLog.tarih < target_date,
            UretimLog.israf_orani.isnot(None),
            UretimLog.uretilen_porsiyon > 0,
        )
        .all()
    )

    if len(egitim_query) < ISO_FOREST_MIN_SAMPLES:
        return []

    # Hedef tarih kayıtları
    hedef_query = (
        db.query(UretimLog)
        .filter(
            UretimLog.tarih == target_date,
            UretimLog.israf_orani.isnot(None),
            UretimLog.uretilen_porsiyon > 0,
        )
        .all()
    )

    if not hedef_query:
        return anomaliler

    # Kategori kodlama
    kategori_map = {"corba": 0, "ana_yemek": 1, "yan_yemek": 2, "tatli": 3, "salata": 4}

    def to_features(log: UretimLog) -> list[float]:
        return [
            float(log.israf_orani or 0),
            float(log.uretilen_porsiyon or 0),
            float(log.tarih.weekday() if log.tarih else 0),
            float(kategori_map.get(log.kategori, 5)),
        ]

    X_train = np.array([to_features(l) for l in egitim_query])
    X_target = np.array([to_features(l) for l in hedef_query])

    # Model eğit
    iso = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
    )
    iso.fit(X_train)

    # Tahmin: -1 = anomali, +1 = normal
    predictions = iso.predict(X_target)
    # Decision score: negatif = anomali (daha negatif = daha şiddetli)
    scores = iso.decision_function(X_target)

    for log, pred, score in zip(hedef_query, predictions, scores):
        if pred == -1:  # Anomali
            # Score'u 0-1 aralığına çevir
            # decision_function genelde [-0.5, 0.5] aralığında
            normalized_score = float(min(1.0, max(0.0, (-score + 0.1) * 2)))

            # Beklenen değeri eğitim setinden hesapla
            similar_train = [
                l for l in egitim_query
                if l.kategori == log.kategori
                and abs((l.tarih.weekday() if l.tarih else 0) - (log.tarih.weekday() if log.tarih else 0)) <= 1
            ]
            beklenen = (
                float(np.mean([l.israf_orani for l in similar_train if l.israf_orani is not None]))
                if similar_train else None
            )
            gerceklesen = float(log.israf_orani)
            sapma = (
                ((gerceklesen - beklenen) / max(beklenen, 0.01)) * 100
                if beklenen else None
            )

            # Şiddet
            if normalized_score >= 0.85:
                siddet = "KRITIK"
            elif normalized_score >= 0.70:
                siddet = "YUKSEK"
            elif normalized_score >= 0.55:
                siddet = "ORTA"
            else:
                siddet = "DUSUK"

            aciklama = (
                f"Isolation Forest: '{log.yemek_adi}' çok değişkenli profili "
                f"normalden farklı (skor={normalized_score:.2f}). "
                f"İsraf: %{gerceklesen:.1f}, Üretim: {log.uretilen_porsiyon:.0f} porsiyon."
            )

            anomaliler.append({
                "tarih": target_date,
                "yemek_adi": log.yemek_adi,
                "kategori": log.kategori,
                "anomali_tipi": "ISRAF_ARTIS" if (gerceklesen > (beklenen or 0)) else "ISRAF_DUSUS",
                "yontem": "isolation_forest",
                "skor": normalized_score,
                "siddet": siddet,
                "beklenen_deger": beklenen,
                "gerceklesen_deger": gerceklesen,
                "sapma_yuzdesi": sapma,
                "aciklama": aciklama,
            })

    return anomaliler


def detect_kategori_sapmasi(
    target_date: date,
    db: Session,
) -> list[dict[str, Any]]:
    """
    Kategori bazında sistemik sapma tespiti.
    'Bugün tüm çorbalarda %40+ israf' gibi durumları yakalar.
    """
    anomaliler: list[dict[str, Any]] = []
    gecmis_basla = target_date - timedelta(days=30)
    kategoriler = ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]
    kat_labels = {
        "corba": "Çorba", "ana_yemek": "Ana Yemek", "yan_yemek": "Yan Yemek",
        "tatli": "Tatlı", "salata": "Salata",
    }

    for kat in kategoriler:
        # Bugün ortalama
        bugun_avg = db.query(sqla_func.avg(UretimLog.israf_orani)).filter(
            UretimLog.tarih == target_date,
            UretimLog.kategori == kat,
            UretimLog.israf_orani.isnot(None),
        ).scalar()

        # Geçmiş ortalama
        gecmis = db.query(UretimLog.israf_orani).filter(
            UretimLog.tarih >= gecmis_basla,
            UretimLog.tarih < target_date,
            UretimLog.kategori == kat,
            UretimLog.israf_orani.isnot(None),
        ).all()
        gecmis_vals = [float(g.israf_orani) for g in gecmis if g.israf_orani is not None]

        if bugun_avg is None or len(gecmis_vals) < 7:
            continue

        bugun = float(bugun_avg)
        gecmis_ort = float(np.mean(gecmis_vals))
        gecmis_std = float(np.std(gecmis_vals))

        if gecmis_std < 0.001:
            continue

        z = (bugun - gecmis_ort) / gecmis_std

        if abs(z) < 1.8:  # Kategori için biraz daha düşük eşik
            continue

        sapma = ((bugun - gecmis_ort) / max(gecmis_ort, 0.01)) * 100
        yon = "artış" if z > 0 else "düşüş"

        aciklama = (
            f"{kat_labels.get(kat, kat)} kategorisinde sistemik {yon}: "
            f"bugün %{bugun:.1f}, geçmiş ortalama %{gecmis_ort:.1f} "
            f"(z={z:+.2f}, sapma %{abs(sapma):.0f})."
        )

        anomaliler.append({
            "tarih": target_date,
            "yemek_adi": None,
            "kategori": kat,
            "anomali_tipi": "KATEGORI_SAPMA",
            "yontem": "zscore (kategori)",
            "skor": _normalize_score(abs(z)),
            "siddet": _get_siddet(abs(z)),
            "beklenen_deger": gecmis_ort,
            "gerceklesen_deger": bugun,
            "sapma_yuzdesi": sapma,
            "aciklama": aciklama,
        })

    return anomaliler


def _save_anomalies(
    anomaliler: list[dict[str, Any]],
    db: Session,
) -> int:
    """Anomalileri DB'ye kaydet (mükerrer kontrolü ile)."""
    kaydedilen = 0
    for a in anomaliler:
        # Aynı tarih + yemek + tip varsa atla
        mevcut = (
            db.query(AnomaliKaydi)
            .filter(
                AnomaliKaydi.tarih == a["tarih"],
                AnomaliKaydi.anomali_tipi == a["anomali_tipi"],
            )
        )
        if a.get("yemek_adi"):
            mevcut = mevcut.filter(AnomaliKaydi.yemek_adi == a["yemek_adi"])
        else:
            mevcut = mevcut.filter(
                AnomaliKaydi.yemek_adi.is_(None),
                AnomaliKaydi.kategori == a.get("kategori"),
            )
        if mevcut.first():
            continue

        kayit = AnomaliKaydi(
            tarih=a["tarih"],
            yemek_adi=a.get("yemek_adi"),
            kategori=a.get("kategori"),
            anomali_tipi=a["anomali_tipi"],
            yontem=a["yontem"],
            skor=a["skor"],
            siddet=a["siddet"],
            beklenen_deger=a.get("beklenen_deger"),
            gerceklesen_deger=a.get("gerceklesen_deger"),
            sapma_yuzdesi=a.get("sapma_yuzdesi"),
            aciklama=a["aciklama"],
            cozuldu_mu=False,
        )
        db.add(kayit)
        kaydedilen += 1

        # alert_system'e de ekle (KRITIK ve YUKSEK için)
        if a["siddet"] in ("KRITIK", "YUKSEK"):
            alert_seviye = "KRITIK" if a["siddet"] == "KRITIK" else "UYARI"
            alert_mevcut = (
                db.query(Alert)
                .filter(
                    Alert.tarih == a["tarih"],
                    Alert.seviye == alert_seviye,
                    Alert.mesaj == a["aciklama"],
                )
                .first()
            )
            if not alert_mevcut:
                db.add(Alert(
                    tarih=a["tarih"],
                    seviye=alert_seviye,
                    yemek_adi=a.get("yemek_adi"),
                    kategori=a.get("kategori"),
                    mesaj=f"[ANOMALI] {a['aciklama']}",
                    aktif=True,
                ))

    db.commit()
    return kaydedilen


def detect_and_save(
    target_date: Optional[date] = None,
    db: Optional[Session] = None,
    use_isolation_forest: bool = True,
) -> dict[str, Any]:
    """
    Ana giriş fonksiyonu: tüm yöntemleri çalıştır, DB'ye kaydet.
    """
    if target_date is None:
        target_date = date.today()

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        all_anomalies: list[dict[str, Any]] = []

        # 1) Z-score (yemek bazında)
        zscore_anom = detect_zscore_anomalies(target_date, db)
        all_anomalies.extend(zscore_anom)

        # 2) Kategori sapması
        kategori_anom = detect_kategori_sapmasi(target_date, db)
        all_anomalies.extend(kategori_anom)

        # 3) Isolation Forest (multivariate)
        if use_isolation_forest:
            iso_anom = detect_isolation_forest_anomalies(target_date, db)
            # Aynı yemek için zaten z-score yakaladıysa Iso Forest'i atla
            zscore_yemekler = {a.get("yemek_adi") for a in zscore_anom if a.get("yemek_adi")}
            iso_filtered = [
                a for a in iso_anom
                if a.get("yemek_adi") and a["yemek_adi"] not in zscore_yemekler
            ]
            all_anomalies.extend(iso_filtered)

        kaydedilen = _save_anomalies(all_anomalies, db)

        # Şiddet özeti
        siddet_ozet = {"KRITIK": 0, "YUKSEK": 0, "ORTA": 0, "DUSUK": 0}
        for a in all_anomalies:
            siddet_ozet[a["siddet"]] = siddet_ozet.get(a["siddet"], 0) + 1

        return {
            "success": True,
            "tarih": str(target_date),
            "tespit_edilen": len(all_anomalies),
            "yeni_kaydedilen": kaydedilen,
            "siddet_ozet": siddet_ozet,
            "iso_forest_aktif": _HAS_IFOREST and use_isolation_forest,
            "anomaliler": all_anomalies[:20],  # İlk 20'sini döndür
        }

    finally:
        if close_db:
            db.close()


def list_anomalies(
    limit: int = 50,
    cozulmus_dahil: bool = False,
    siddet_filtre: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """Kayıtlı anomalileri listele."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        q = db.query(AnomaliKaydi)
        if not cozulmus_dahil:
            q = q.filter(AnomaliKaydi.cozuldu_mu.is_(False))
        if siddet_filtre:
            q = q.filter(AnomaliKaydi.siddet == siddet_filtre.upper())

        anomaliler = (
            q.order_by(AnomaliKaydi.tarih.desc(), AnomaliKaydi.skor.desc())
            .limit(limit)
            .all()
        )

        return {
            "success": True,
            "toplam": len(anomaliler),
            "anomaliler": [a.to_dict() for a in anomaliler],
        }
    finally:
        if close_db:
            db.close()


def get_pattern_stats(
    gun_sayisi: int = 30,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """
    Pattern analizi: hangi yemeklerde ne sıklıkla anomali var,
    hangi günlerde, hangi şiddette.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        baslangic = date.today() - timedelta(days=gun_sayisi)

        # En sık anomali yaşayan yemekler
        en_sik_yemek = (
            db.query(
                AnomaliKaydi.yemek_adi,
                sqla_func.count(AnomaliKaydi.id).label("sayi"),
                sqla_func.avg(AnomaliKaydi.skor).label("ort_skor"),
            )
            .filter(
                AnomaliKaydi.tarih >= baslangic,
                AnomaliKaydi.yemek_adi.isnot(None),
            )
            .group_by(AnomaliKaydi.yemek_adi)
            .order_by(sqla_func.count(AnomaliKaydi.id).desc())
            .limit(10)
            .all()
        )

        # Şiddet dağılımı
        siddet_dagilim = (
            db.query(
                AnomaliKaydi.siddet,
                sqla_func.count(AnomaliKaydi.id).label("sayi"),
            )
            .filter(AnomaliKaydi.tarih >= baslangic)
            .group_by(AnomaliKaydi.siddet)
            .all()
        )

        # Tip dağılımı
        tip_dagilim = (
            db.query(
                AnomaliKaydi.anomali_tipi,
                sqla_func.count(AnomaliKaydi.id).label("sayi"),
            )
            .filter(AnomaliKaydi.tarih >= baslangic)
            .group_by(AnomaliKaydi.anomali_tipi)
            .all()
        )

        # Günlük trend
        gunluk_trend = (
            db.query(
                AnomaliKaydi.tarih,
                sqla_func.count(AnomaliKaydi.id).label("sayi"),
            )
            .filter(AnomaliKaydi.tarih >= baslangic)
            .group_by(AnomaliKaydi.tarih)
            .order_by(AnomaliKaydi.tarih.asc())
            .all()
        )

        # Çözüm istatistikleri
        toplam = db.query(sqla_func.count(AnomaliKaydi.id)).filter(
            AnomaliKaydi.tarih >= baslangic,
        ).scalar() or 0
        cozulmus = db.query(sqla_func.count(AnomaliKaydi.id)).filter(
            AnomaliKaydi.tarih >= baslangic,
            AnomaliKaydi.cozuldu_mu.is_(True),
        ).scalar() or 0

        return {
            "success": True,
            "periyot_gun": gun_sayisi,
            "toplam_anomali": toplam,
            "cozulmus": cozulmus,
            "cozulme_orani": round((cozulmus / toplam * 100) if toplam > 0 else 0, 1),
            "en_sik_yemekler": [
                {"yemek_adi": y, "sayi": int(s), "ort_skor": round(float(o or 0), 3)}
                for y, s, o in en_sik_yemek
            ],
            "siddet_dagilim": {s: int(c) for s, c in siddet_dagilim},
            "tip_dagilim": {t: int(c) for t, c in tip_dagilim},
            "gunluk_trend": [
                {"tarih": str(t), "sayi": int(c)}
                for t, c in gunluk_trend
            ],
        }
    finally:
        if close_db:
            db.close()


def resolve_anomaly(
    anomali_id: int,
    cozum_notu: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """Anomaliyi çözüldü olarak işaretle."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        kayit = db.query(AnomaliKaydi).filter(AnomaliKaydi.id == anomali_id).first()
        if not kayit:
            return {"success": False, "error": "Anomali kaydı bulunamadı."}

        kayit.cozuldu_mu = True
        kayit.cozum_notu = cozum_notu
        kayit.cozum_tarihi = datetime.utcnow()
        db.commit()

        return {"success": True, "anomali": kayit.to_dict()}
    finally:
        if close_db:
            db.close()
