"""
Modül: IoT Tartı Simülatörü
────────────────────────────
Gerçek IoT tartı cihazı olmadan tutarlı israf ağırlık verisi üretir.

Mantık:
  - UretimLog'daki mevcut üretim ve israf verisinden yola çıkar
  - Üretilen porsiyon × ortalama porsiyon ağırlığı = toplam üretim (kg)
  - israf_orani (%) × toplam üretim = tahmini israf (kg)
  - ± rastgele sapma ekler (gerçekçi olsun)
  - Sonucu UretimLog.tartilan_israf_kg alanına yazar
  - kaynak = "simulasyon" olarak işaretler

Silme: Bu dosyayı silmek yeterlidir, mevcut sistemi etkilemez.
"""

import random
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from models import UretimLog, SessionLocal


# ── Sabitler ──────────────────────────────────────────────────────
ORT_PORSIYON_AGIRLIK_KG = 0.35  # Ortalama bir porsiyon ~350g
SAPMA_YUZDESI = 0.15            # ±%15 rastgele sapma
MIN_ISRAF_KG = 0.1              # Minimum simülasyon değeri


def simulate_weight_for_log(log: UretimLog) -> float:
    """Tek bir UretimLog kaydı için simüle israf ağırlığı (kg) hesaplar.

    Returns:
        Simüle edilmiş israf ağırlığı (kg).
    """
    uretilen_kg = (log.uretilen_porsiyon or 0) * ORT_PORSIYON_AGIRLIK_KG
    israf_oran = (log.israf_orani or 0) / 100.0

    baz_israf_kg = uretilen_kg * israf_oran

    # Rastgele sapma: ±SAPMA_YUZDESI
    sapma = random.uniform(-SAPMA_YUZDESI, SAPMA_YUZDESI)
    simule_kg = baz_israf_kg * (1 + sapma)

    return max(MIN_ISRAF_KG, round(simule_kg, 2))


def run_simulation(
    db: Session,
    tarih: Optional[date] = None,
    overwrite: bool = False,
) -> dict:
    """Belirtilen tarih için tüm UretimLog kayıtlarına simüle tartı verisi yazar.

    Args:
        db: Veritabanı oturumu.
        tarih: Hedef tarih (varsayılan: bugün).
        overwrite: True ise mevcut tartı verilerinin üzerine yazar.

    Returns:
        İşlem sonucu dict.
    """
    if tarih is None:
        tarih = date.today()

    query = db.query(UretimLog).filter(UretimLog.tarih == tarih)

    if not overwrite:
        # Sadece tartı verisi olmayanları güncelle
        query = query.filter(
            (UretimLog.tartilan_israf_kg.is_(None))
            | (UretimLog.tartilan_israf_kaynagi == "simulasyon")
        )

    logs = query.all()

    if not logs:
        return {
            "success": True,
            "tarih": str(tarih),
            "guncellenen": 0,
            "mesaj": "Bu tarih için güncellenecek kayıt bulunamadı.",
        }

    guncellenen = 0
    detaylar = []

    for log in logs:
        if log.uretilen_porsiyon and log.uretilen_porsiyon > 0:
            simule_kg = simulate_weight_for_log(log)
            log.tartilan_israf_kg = simule_kg
            log.tartilan_israf_kaynagi = "simulasyon"
            guncellenen += 1
            detaylar.append({
                "yemek_adi": log.yemek_adi,
                "uretilen_porsiyon": log.uretilen_porsiyon,
                "israf_orani_pct": log.israf_orani,
                "simule_israf_kg": simule_kg,
            })

    db.commit()

    return {
        "success": True,
        "tarih": str(tarih),
        "guncellenen": guncellenen,
        "toplam_simule_kg": round(sum(d["simule_israf_kg"] for d in detaylar), 2),
        "detaylar": detaylar,
    }


def run_bulk_simulation(
    db: Session,
    gun_sayisi: int = 30,
    overwrite: bool = False,
) -> dict:
    """Son N gün için toplu simülasyon çalıştırır.

    Args:
        db: Veritabanı oturumu.
        gun_sayisi: Kaç günlük veri simüle edilecek.
        overwrite: Mevcut verilerin üzerine yaz.

    Returns:
        Toplam sonuç dict.
    """
    from datetime import timedelta

    bugun = date.today()
    toplam_guncellenen = 0
    toplam_kg = 0.0
    gun_detaylari = []

    for i in range(gun_sayisi):
        hedef_tarih = bugun - timedelta(days=i)
        sonuc = run_simulation(db=db, tarih=hedef_tarih, overwrite=overwrite)
        toplam_guncellenen += sonuc.get("guncellenen", 0)
        toplam_kg += sonuc.get("toplam_simule_kg", 0.0)
        if sonuc.get("guncellenen", 0) > 0:
            gun_detaylari.append({
                "tarih": str(hedef_tarih),
                "guncellenen": sonuc["guncellenen"],
                "toplam_kg": sonuc.get("toplam_simule_kg", 0),
            })

    return {
        "success": True,
        "gun_sayisi": gun_sayisi,
        "toplam_guncellenen": toplam_guncellenen,
        "toplam_simule_kg": round(toplam_kg, 2),
        "gun_detaylari": gun_detaylari,
    }
