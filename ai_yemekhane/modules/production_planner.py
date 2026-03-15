"""
Üretim Planlama Modülü — Data-Driven Üretim Önerisi
═══════════════════════════════════════════════════════
Geçmiş tüketim verileri (UretimLog) ve puanlama verilerinden
her yemek için optimum üretim miktarı önerisi üretir.

Kullanılan veriler:
  - UretimLog: üretilen/kalan porsiyon geçmişi
  - MenuPuanlama: yemek puan ortalamaları
  - Menu: hangi günde ne yemek çıktığı
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import UretimLog, MenuPuanlama, Menu


# ──────────────────────────────────────────────────────────────────
# 1) Yemek Bazlı Üretim Önerisi
# ──────────────────────────────────────────────────────────────────

def get_dish_recommendation(yemek_adi: str, db: Session) -> dict[str, Any]:
    """
    Belirli bir yemek için geçmiş verilere dayalı üretim önerisi.
    
    Mantık:
    1) Geçmiş ortalama tüketimi (üretilen - kalan) hesapla
    2) Puan ortalamasını al — düşük puanlı yemek → üretimi azalt
    3) Güvenlik payı (%10) ekle ve önerilen porsiyon hesapla
    """
    bugun = date.today()
    baslangic = bugun - timedelta(days=60)

    # ── Geçmiş üretim verileri ──
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
            "mesaj": f"'{yemek_adi}' için yeterli üretim verisi bulunamadı.",
            "oneri": None,
        }

    # İstatistikler
    tuketimler = [k.uretilen_porsiyon - k.kalan_porsiyon for k in kayitlar]
    uretilenler = [k.uretilen_porsiyon for k in kayitlar]
    israflar = [k.kalan_porsiyon for k in kayitlar]

    ort_tuketim = sum(tuketimler) / len(tuketimler)
    ort_uretilen = sum(uretilenler) / len(uretilenler)
    ort_israf = sum(israflar) / len(israflar)
    ort_israf_orani = (ort_israf / ort_uretilen * 100) if ort_uretilen > 0 else 0

    # Trend: son 3 kayıt vs önceki kayıtlar
    if len(tuketimler) >= 4:
        son3_ort = sum(tuketimler[-3:]) / 3
        onceki_ort = sum(tuketimler[:-3]) / len(tuketimler[:-3])
        trend_degisim = ((son3_ort - onceki_ort) / onceki_ort * 100) if onceki_ort > 0 else 0
    else:
        son3_ort = ort_tuketim
        trend_degisim = 0

    # ── Puan ortalamasını al ──
    puan_ort = (
        db.query(func.avg(MenuPuanlama.puan))
        .filter(MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"))
        .scalar()
    )
    puan_ort = round(float(puan_ort), 1) if puan_ort else None

    # ── Üretim önerisi hesapla ──
    # Temel: ortalama tüketim + %10 güvenlik payı
    temel_oneri = ort_tuketim * 1.10

    # Trend ayarlaması: artan trend → biraz artır
    if trend_degisim > 10:
        trend_carpan = 1.05
        trend_yon = "Artıyor ↑"
    elif trend_degisim < -10:
        trend_carpan = 0.95
        trend_yon = "Azalıyor ↓"
    else:
        trend_carpan = 1.0
        trend_yon = "Stabil →"

    temel_oneri *= trend_carpan

    # Puan ayarlaması: düşük puan → üretimi azalt
    if puan_ort is not None:
        if puan_ort < 2.5:
            puan_carpan = 0.85
            puan_durumu = "Düşük puan — üretim azaltılmalı"
        elif puan_ort < 3.5:
            puan_carpan = 0.95
            puan_durumu = "Orta puan"
        else:
            puan_carpan = 1.0
            puan_durumu = "İyi puan"
    else:
        puan_carpan = 1.0
        puan_durumu = "Puan verisi yok"

    onerilen_porsiyon = round(temel_oneri * puan_carpan)

    # Tasarruf hesabı
    tasarruf_porsiyon = round(ort_uretilen - onerilen_porsiyon)
    tasarruf_yuzde = round((tasarruf_porsiyon / ort_uretilen) * 100, 1) if ort_uretilen > 0 else 0

    # Güven seviyesi
    if len(kayitlar) >= 10:
        guven = "Yüksek"
    elif len(kayitlar) >= 5:
        guven = "Orta"
    else:
        guven = "Düşük"

    return {
        "success": True,
        "yemek_adi": yemek_adi,
        "veri_var": True,
        "kayit_sayisi": len(kayitlar),
        "istatistik": {
            "ort_uretilen": round(ort_uretilen, 1),
            "ort_tuketilen": round(ort_tuketim, 1),
            "ort_israf": round(ort_israf, 1),
            "ort_israf_orani": round(ort_israf_orani, 1),
        },
        "trend": {
            "yon": trend_yon,
            "degisim_yuzde": round(trend_degisim, 1),
            "son_donem_tuketim": round(son3_ort, 1),
        },
        "puan": {
            "ortalama": puan_ort,
            "durum": puan_durumu,
        },
        "oneri": {
            "onerilen_porsiyon": onerilen_porsiyon,
            "mevcut_ortalama": round(ort_uretilen),
            "tasarruf_porsiyon": tasarruf_porsiyon,
            "tasarruf_yuzde": tasarruf_yuzde,
            "guven_seviyesi": guven,
        },
    }


# ──────────────────────────────────────────────────────────────────
# 2) Haftalık Üretim Planı
# ──────────────────────────────────────────────────────────────────

def generate_production_plan(db: Session) -> dict[str, Any]:
    """
    Geçmiş verilere dayanarak tüm yemekler için üretim planı oluşturur.

    Her yemek için:
    - Ortalama tüketim
    - Trend yönü
    - Puan ortalaması
    - Önerilen üretim miktarı
    - Aksiyon (Azalt / Koru / Artır / Çıkar)
    """
    bugun = date.today()
    baslangic = bugun - timedelta(days=60)

    # Tüm yemekleri topla (üretim loglarından)
    yemek_listesi = (
        db.query(UretimLog.yemek_adi, UretimLog.kategori)
        .filter(UretimLog.tarih >= baslangic)
        .group_by(UretimLog.yemek_adi, UretimLog.kategori)
        .all()
    )

    if not yemek_listesi:
        return {
            "success": True,
            "veri_var": False,
            "mesaj": "Üretim planı oluşturmak için yeterli üretim verisi yok. "
                     "Önce 'Veri Girişi' sayfasından birkaç gün veri girin.",
            "plan": [],
        }

    plan = []
    toplam_mevcut = 0
    toplam_onerilen = 0

    for yemek_adi, kategori in yemek_listesi:
        result = get_dish_recommendation(yemek_adi, db)

        if not result["veri_var"]:
            continue

        oneri = result["oneri"]
        istatistik = result["istatistik"]
        trend = result["trend"]
        puan = result["puan"]

        # Aksiyon belirleme
        tasarruf_yuzde = oneri["tasarruf_yuzde"]
        if tasarruf_yuzde > 25:
            aksiyon = "🔴 Ciddi Azalt"
            aksiyon_kodu = "ciddi_azalt"
        elif tasarruf_yuzde > 10:
            aksiyon = "🟠 Azalt"
            aksiyon_kodu = "azalt"
        elif tasarruf_yuzde > -5:
            aksiyon = "🟢 Koru"
            aksiyon_kodu = "koru"
        else:
            aksiyon = "🔵 Artır"
            aksiyon_kodu = "artir"

        # Çok düşük puanlı yemekleri menüden çıkarmayı öner
        if puan["ortalama"] is not None and puan["ortalama"] < 2.0 and istatistik["ort_israf_orani"] > 30:
            aksiyon = "⛔ Menüden Çıkar"
            aksiyon_kodu = "cikar"

        toplam_mevcut += oneri["mevcut_ortalama"]
        toplam_onerilen += oneri["onerilen_porsiyon"]

        plan.append({
            "yemek_adi": yemek_adi,
            "kategori": kategori,
            "kayit_sayisi": result["kayit_sayisi"],
            "ort_uretilen": istatistik["ort_uretilen"],
            "ort_tuketilen": istatistik["ort_tuketilen"],
            "ort_israf_orani": istatistik["ort_israf_orani"],
            "trend_yon": trend["yon"],
            "trend_degisim": trend["degisim_yuzde"],
            "puan_ort": puan["ortalama"],
            "onerilen_porsiyon": oneri["onerilen_porsiyon"],
            "mevcut_ortalama": oneri["mevcut_ortalama"],
            "tasarruf_porsiyon": oneri["tasarruf_porsiyon"],
            "tasarruf_yuzde": oneri["tasarruf_yuzde"],
            "guven": oneri["guven_seviyesi"],
            "aksiyon": aksiyon,
            "aksiyon_kodu": aksiyon_kodu,
        })

    # İsraf oranına göre sırala (en çok israf eden üstte)
    plan.sort(key=lambda x: x["ort_israf_orani"], reverse=True)

    # Genel özet
    toplam_tasarruf = toplam_mevcut - toplam_onerilen
    tasarruf_yuzde_genel = round((toplam_tasarruf / toplam_mevcut) * 100, 1) if toplam_mevcut > 0 else 0

    # Aksiyona göre sayılar
    aksiyon_sayilari = {}
    for item in plan:
        kod = item["aksiyon_kodu"]
        aksiyon_sayilari[kod] = aksiyon_sayilari.get(kod, 0) + 1

    return {
        "success": True,
        "veri_var": True,
        "tarih": str(bugun),
        "ozet": {
            "toplam_yemek": len(plan),
            "toplam_mevcut_uretim": toplam_mevcut,
            "toplam_onerilen_uretim": toplam_onerilen,
            "toplam_tasarruf_porsiyon": toplam_tasarruf,
            "tasarruf_yuzde": tasarruf_yuzde_genel,
            "aksiyon_dagilimi": aksiyon_sayilari,
        },
        "plan": plan,
    }
