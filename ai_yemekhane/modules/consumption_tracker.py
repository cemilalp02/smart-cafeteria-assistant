"""
Tüketim Takip Modülü — Manuel Üretim/İsraf Veri Girişi
═══════════════════════════════════════════════════════
Yemekhane yöneticisinin girdiği üretim ve kalan porsiyon
verilerinden tüketim oranı, israf oranı ve özet raporlar üretir.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import UretimLog, Menu


# ──────────────────────────────────────────────────────────────────
# 1) Üretim Verisi Kaydetme
# ──────────────────────────────────────────────────────────────────

def save_production_log(
    tarih: date,
    yemek_adi: str,
    kategori: str,
    uretilen: float,
    kalan: float,
    notlar: Optional[str],
    db: Session,
) -> dict[str, Any]:
    """
    Tek bir yemek için üretim verisini kaydeder.
    Tüketim ve israf oranlarını otomatik hesaplar.
    """
    if uretilen <= 0:
        return {"success": False, "message": "Üretilen porsiyon 0'dan büyük olmalı."}
    if kalan < 0:
        return {"success": False, "message": "Kalan porsiyon negatif olamaz."}
    if kalan > uretilen:
        return {"success": False, "message": "Kalan porsiyon üretilenden büyük olamaz."}

    tuketim_orani = round(((uretilen - kalan) / uretilen) * 100, 1)
    israf_orani = round((kalan / uretilen) * 100, 1)

    # Aynı tarih + yemek varsa güncelle
    mevcut = (
        db.query(UretimLog)
        .filter(UretimLog.tarih == tarih, UretimLog.yemek_adi == yemek_adi)
        .first()
    )

    if mevcut:
        mevcut.uretilen_porsiyon = uretilen
        mevcut.kalan_porsiyon = kalan
        mevcut.tuketim_orani = tuketim_orani
        mevcut.israf_orani = israf_orani
        mevcut.notlar = notlar
        db.commit()
        db.refresh(mevcut)
        return {
            "success": True,
            "message": f"'{yemek_adi}' güncellendi. Tüketim: %{tuketim_orani}",
            "data": mevcut.to_dict(),
            "guncellendi": True,
        }

    yeni = UretimLog(
        tarih=tarih,
        yemek_adi=yemek_adi,
        kategori=kategori,
        uretilen_porsiyon=uretilen,
        kalan_porsiyon=kalan,
        tuketim_orani=tuketim_orani,
        israf_orani=israf_orani,
        notlar=notlar,
    )
    db.add(yeni)
    db.commit()
    db.refresh(yeni)
    return {
        "success": True,
        "message": f"'{yemek_adi}' kaydedildi. Tüketim: %{tuketim_orani}, İsraf: %{israf_orani}",
        "data": yeni.to_dict(),
        "guncellendi": False,
    }


def save_bulk_production_log(
    tarih: date,
    girisler: list[dict[str, Any]],
    db: Session,
) -> dict[str, Any]:
    """
    Birden fazla yemek için toplu üretim verisi kaydeder.

    girisler formatı:
    [
        {"yemek_adi": "Mercimek Çorbası", "kategori": "corba",
         "uretilen": 200, "kalan": 30, "notlar": ""},
        ...
    ]
    """
    sonuclar = []
    hatalar = []

    for giris in girisler:
        # Boş girişleri atla (üretilen 0 veya None olanlar)
        uretilen = giris.get("uretilen", 0) or 0
        kalan = giris.get("kalan", 0) or 0
        if uretilen == 0:
            continue

        result = save_production_log(
            tarih=tarih,
            yemek_adi=giris["yemek_adi"],
            kategori=giris.get("kategori", "ana_yemek"),
            uretilen=float(uretilen),
            kalan=float(kalan),
            notlar=giris.get("notlar"),
            db=db,
        )
        if result["success"]:
            sonuclar.append(result["data"])
        else:
            hatalar.append({"yemek": giris["yemek_adi"], "hata": result["message"]})

    return {
        "success": True,
        "kaydedilen": len(sonuclar),
        "hatalar": hatalar,
        "veriler": sonuclar,
    }


# ──────────────────────────────────────────────────────────────────
# 2) Günlük Tüketim Raporu
# ──────────────────────────────────────────────────────────────────

def get_daily_consumption(tarih: Optional[date] = None, db: Optional[Session] = None) -> dict[str, Any]:
    """Belirli bir günün tüketim/israf raporunu döndürür."""
    if tarih is None:
        tarih = date.today()

    kayitlar = (
        db.query(UretimLog)
        .filter(UretimLog.tarih == tarih)
        .order_by(UretimLog.kategori)
        .all()
    )

    if not kayitlar:
        return {
            "success": True,
            "tarih": str(tarih),
            "veri_var": False,
            "mesaj": f"{tarih} için üretim verisi bulunamadı.",
            "yemekler": [],
            "ozet": None,
        }

    toplam_uretilen = sum(k.uretilen_porsiyon for k in kayitlar)
    toplam_kalan = sum(k.kalan_porsiyon for k in kayitlar)
    toplam_tuketilen = toplam_uretilen - toplam_kalan

    genel_tuketim = round((toplam_tuketilen / toplam_uretilen) * 100, 1) if toplam_uretilen > 0 else 0
    genel_israf = round((toplam_kalan / toplam_uretilen) * 100, 1) if toplam_uretilen > 0 else 0

    # İsraf seviyesi
    if genel_israf >= 40:
        seviye = "KRİTİK"
    elif genel_israf >= 25:
        seviye = "YÜKSEK"
    elif genel_israf >= 15:
        seviye = "ORTA"
    else:
        seviye = "DÜŞÜK"

    return {
        "success": True,
        "tarih": str(tarih),
        "veri_var": True,
        "yemekler": [k.to_dict() for k in kayitlar],
        "ozet": {
            "toplam_uretilen": toplam_uretilen,
            "toplam_tuketilen": toplam_tuketilen,
            "toplam_kalan": toplam_kalan,
            "tuketim_orani": genel_tuketim,
            "israf_orani": genel_israf,
            "israf_seviye": seviye,
            "yemek_sayisi": len(kayitlar),
        },
    }


# ──────────────────────────────────────────────────────────────────
# 3) Haftalık Tüketim Özeti
# ──────────────────────────────────────────────────────────────────

def get_weekly_consumption(db: Session) -> dict[str, Any]:
    """Son 7 günün tüketim/israf özetini döndürür."""
    bugun = date.today()
    hafta_basi = bugun - timedelta(days=7)

    kayitlar = (
        db.query(UretimLog)
        .filter(UretimLog.tarih >= hafta_basi, UretimLog.tarih <= bugun)
        .all()
    )

    if not kayitlar:
        return {
            "success": True,
            "donem": {"baslangic": str(hafta_basi), "bitis": str(bugun)},
            "veri_var": False,
            "mesaj": "Son 7 gün için üretim verisi bulunamadı.",
        }

    # Günlük trend
    gunluk = {}
    for k in kayitlar:
        gun_str = str(k.tarih)
        if gun_str not in gunluk:
            gunluk[gun_str] = {"uretilen": 0, "kalan": 0}
        gunluk[gun_str]["uretilen"] += k.uretilen_porsiyon
        gunluk[gun_str]["kalan"] += k.kalan_porsiyon

    gunluk_trend = []
    for gun, veri in sorted(gunluk.items()):
        tuketilen = veri["uretilen"] - veri["kalan"]
        israf_oran = round((veri["kalan"] / veri["uretilen"]) * 100, 1) if veri["uretilen"] > 0 else 0
        gunluk_trend.append({
            "tarih": gun,
            "uretilen": veri["uretilen"],
            "tuketilen": tuketilen,
            "kalan": veri["kalan"],
            "israf_orani": israf_oran,
        })

    # Yemek bazlı en çok israf
    yemek_israf = {}
    for k in kayitlar:
        if k.yemek_adi not in yemek_israf:
            yemek_israf[k.yemek_adi] = {"uretilen": 0, "kalan": 0, "kategori": k.kategori}
        yemek_israf[k.yemek_adi]["uretilen"] += k.uretilen_porsiyon
        yemek_israf[k.yemek_adi]["kalan"] += k.kalan_porsiyon

    en_cok_israf = []
    for yemek, veri in yemek_israf.items():
        israf_oran = round((veri["kalan"] / veri["uretilen"]) * 100, 1) if veri["uretilen"] > 0 else 0
        en_cok_israf.append({
            "yemek_adi": yemek,
            "kategori": veri["kategori"],
            "toplam_uretilen": veri["uretilen"],
            "toplam_kalan": veri["kalan"],
            "israf_orani": israf_oran,
        })
    en_cok_israf.sort(key=lambda x: x["israf_orani"], reverse=True)

    # Genel özet
    toplam_uretilen = sum(k.uretilen_porsiyon for k in kayitlar)
    toplam_kalan = sum(k.kalan_porsiyon for k in kayitlar)
    genel_israf = round((toplam_kalan / toplam_uretilen) * 100, 1) if toplam_uretilen > 0 else 0

    return {
        "success": True,
        "donem": {"baslangic": str(hafta_basi), "bitis": str(bugun)},
        "veri_var": True,
        "ozet": {
            "toplam_uretilen": toplam_uretilen,
            "toplam_kalan": toplam_kalan,
            "toplam_tuketilen": toplam_uretilen - toplam_kalan,
            "genel_israf_orani": genel_israf,
            "kayit_gun_sayisi": len(gunluk),
        },
        "gunluk_trend": gunluk_trend,
        "en_cok_israf": en_cok_israf[:10],
    }


# ──────────────────────────────────────────────────────────────────
# 4) Yemek Bazlı Tüketim Geçmişi
# ──────────────────────────────────────────────────────────────────

def get_dish_consumption_history(
    yemek_adi: str,
    gun: int = 30,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """Belirli bir yemeğin geçmiş tüketim/israf verilerini döndürür."""
    bugun = date.today()
    baslangic = bugun - timedelta(days=gun)

    kayitlar = (
        db.query(UretimLog)
        .filter(
            UretimLog.yemek_adi.ilike(f"%{yemek_adi}%"),
            UretimLog.tarih >= baslangic,
        )
        .order_by(UretimLog.tarih)
        .all()
    )

    if not kayitlar:
        return {
            "success": True,
            "yemek_adi": yemek_adi,
            "veri_var": False,
            "mesaj": f"'{yemek_adi}' için üretim verisi bulunamadı.",
        }

    toplam_uretilen = sum(k.uretilen_porsiyon for k in kayitlar)
    toplam_kalan = sum(k.kalan_porsiyon for k in kayitlar)
    ort_israf = round((toplam_kalan / toplam_uretilen) * 100, 1) if toplam_uretilen > 0 else 0

    trend = [
        {
            "tarih": str(k.tarih),
            "uretilen": k.uretilen_porsiyon,
            "kalan": k.kalan_porsiyon,
            "tuketim_orani": k.tuketim_orani,
            "israf_orani": k.israf_orani,
        }
        for k in kayitlar
    ]

    return {
        "success": True,
        "yemek_adi": yemek_adi,
        "veri_var": True,
        "donem_gun": gun,
        "kayit_sayisi": len(kayitlar),
        "ortalama_israf": ort_israf,
        "toplam_uretilen": toplam_uretilen,
        "toplam_kalan": toplam_kalan,
        "trend": trend,
    }
