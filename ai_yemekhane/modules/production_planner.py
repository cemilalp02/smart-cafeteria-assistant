"""
Üretim Planlama Modülü — ML-Destekli Hibrit Porsiyon Önerisi
═══════════════════════════════════════════════════════════════
Geçmiş tüketim verileri ve eğitilmiş ML israf modeli birlikte
kullanılarak her yemek için optimum üretim miktarı önerilir.

Mimari:
    1) ML modeli israf oranını tahmin eder (waste_analyzer)
    2) Geçmiş tüketim → beklenen talep (D)
    3) Talep belirsizliği → güvenlik payı (z·σ)
    4) Hibrit porsiyon formülü:
       P = max(D + z*sigma, P_geçmiş * (1 - max(0, w_pred - hedef_israf)))
    5) Sanity bounds + multi-fallback ile robust sonuç

Kullanılan veriler:
  - UretimLog: üretilen/kalan porsiyon geçmişi (talep tahmini)
  - MenuPuanlama: ortalama puan + self-report
  - waste_predictor.joblib: ML israf tahmin modeli
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import UretimLog, MenuPuanlama
from modules.waste_analyzer import estimate_waste_ratio

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Sabitler — Servis Seviyesi & Güvenlik Payı
# ══════════════════════════════════════════════════════════════════

# Servis seviyesi (z-skoru): %90 → 1.28, %95 → 1.65, %99 → 2.33
# Yetersizlik olasılığını düşürmek için talep belirsizliğine eklenecek pay.
SERVICE_LEVEL_Z = 1.28  # %90 servis seviyesi (yemekhane için makul)

# ML modelinin önerdiği israf hedefi: bunun üzerindeki israfı azaltmaya çalış.
# Yemekhanede %10 doğal/teknik israf kabul edilebilir bir alt sınır.
HEDEF_ISRAF_ORANI = 0.10  # %10

# ML model güvenilir değilse minimum güvenlik payı (kural tabanlı fallback)
FALLBACK_GUVENLIK_PAYI = 0.10  # %10

# Önerinin ortalama üretimden ne kadar sapabileceği (sanity bound)
ALT_SINIR_CARPAN = 0.60  # ortalama × 0.60'tan az olamaz
UST_SINIR_CARPAN = 1.50  # ortalama × 1.50'den fazla olamaz


# ──────────────────────────────────────────────────────────────────
# 1) Yemek Bazlı Üretim Önerisi
# ──────────────────────────────────────────────────────────────────

def get_dish_recommendation(
    yemek_adi: str,
    db: Session,
    target_date: date | None = None,
) -> dict[str, Any]:
    """
    Belirli bir yemek için ML-destekli hibrit üretim önerisi.

    Algoritma:
    ──────────
    1) Geçmiş 60 günün tüketim (üretilen - kalan) ortalaması ve std sapması
    2) ML modeli bu yemeğin israf oranını tahmin eder (waste_analyzer)
    3) İki sinyali birleştir:
       a) TALEP TABANI = D + z·σ (yetersizlik olmasın)
          - D: beklenen talep (geçmiş ortalama tüketim)
          - z·σ: güvenlik payı (servis seviyesi × talep std sapması)
       b) ML TASARRUF SİNYALİ:
          fark = max(0, w_pred - hedef_israf)
          ml_oneri = ortalama_üretim × (1 - fark)
          # ML yüksek israf bekliyorsa → üretimi düşür
          # ML düşük israf bekliyorsa → mevcut seviyeyi koru
       c) FİNAL = max(talep_tabanı, ml_oneri)
          # Talebi mutlaka karşıla, ama mümkün olan en düşük seviyede
    4) Multi-fallback: ML yoksa → gerçek geçmiş israf → kural tabanlı puan → %10 sabit
    5) Sanity bounds: ortalama × [0.60, 1.50] arasına sıkıştır

    Args:
        yemek_adi: Yemek adı (ilike ile aranır)
        db: SQLAlchemy session
        target_date: Hedef tarih (varsayılan: bugün)
    """
    bugun = target_date or date.today()
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

    # ──────────────────────────────────────────────────────────────
    # 1) Talep & İstatistik Hesabı
    # ──────────────────────────────────────────────────────────────
    tuketimler = [k.uretilen_porsiyon - k.kalan_porsiyon for k in kayitlar]
    uretilenler = [k.uretilen_porsiyon for k in kayitlar]
    israflar = [k.kalan_porsiyon for k in kayitlar]
    kategori = kayitlar[-1].kategori or "diger"

    n = len(tuketimler)
    ort_tuketim = sum(tuketimler) / n
    ort_uretilen = sum(uretilenler) / n
    ort_israf = sum(israflar) / n
    ort_israf_orani = (ort_israf / ort_uretilen * 100) if ort_uretilen > 0 else 0

    # Talep belirsizliği için std sapması (Bessel düzeltmeli)
    if n >= 2:
        varyans = sum((x - ort_tuketim) ** 2 for x in tuketimler) / (n - 1)
        tuketim_std = math.sqrt(varyans)
    else:
        tuketim_std = ort_tuketim * 0.10  # n=1 durumu: ort'un %10'unu varsay

    # Trend: son 3 kayıt vs önceki kayıtlar
    if n >= 4:
        son3_ort = sum(tuketimler[-3:]) / 3
        onceki_ort = sum(tuketimler[:-3]) / len(tuketimler[:-3])
        trend_degisim = ((son3_ort - onceki_ort) / onceki_ort * 100) if onceki_ort > 0 else 0
    else:
        son3_ort = ort_tuketim
        trend_degisim = 0

    if trend_degisim > 10:
        trend_yon = "Artıyor ↑"
    elif trend_degisim < -10:
        trend_yon = "Azalıyor ↓"
    else:
        trend_yon = "Stabil →"

    # ──────────────────────────────────────────────────────────────
    # 2) Puan & Self-Report Verisi
    # ──────────────────────────────────────────────────────────────
    puan_row = db.query(
        func.avg(MenuPuanlama.puan).label("ort"),
        func.count(MenuPuanlama.id).label("oy"),
    ).filter(MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%")).first()

    puan_ort = float(puan_row.ort) if puan_row and puan_row.ort else None
    toplam_oy = int(puan_row.oy) if puan_row and puan_row.oy else 0

    if puan_ort is not None:
        if puan_ort < 2.5:
            puan_durumu = "Düşük puan — talep azalabilir"
        elif puan_ort < 3.5:
            puan_durumu = "Orta puan"
        else:
            puan_durumu = "İyi puan"
    else:
        puan_durumu = "Puan verisi yok"

    # ──────────────────────────────────────────────────────────────
    # 3) ML Modelinin İsraf Tahmini
    # ──────────────────────────────────────────────────────────────
    # Geçmiş ortalama gerçek israf oranı (ML fallback için)
    gercek_ort_israf_orani = ort_israf_orani  # 0-100 ölçeğinde

    israf_tahmini_pct, kaynak = estimate_waste_ratio(
        yemek_adi=yemek_adi,
        kategori=kategori,
        tarih=bugun,
        ortalama_puan=puan_ort,
        toplam_oy=toplam_oy,
        uretilen_porsiyon=ort_uretilen,
        uretim_israf_orani=gercek_ort_israf_orani,
    )

    # ──────────────────────────────────────────────────────────────
    # 4) Hibrit Porsiyon Hesabı: TALEP TABANI ⊔ ML TASARRUF SİNYALİ
    # ──────────────────────────────────────────────────────────────
    if israf_tahmini_pct is not None:
        w_pred = max(0.0, min(1.0, israf_tahmini_pct / 100.0))
        kaynak_aciklama = {
            "ml_model": "ML modeli tahmini",
            "uretim_gercek": "Geçmiş üretim ortalaması",
            "kural_puan": "Puan-bazlı kural",
        }.get(kaynak, "Belirlenemedi")
    else:
        # Hiçbir tahmin yoksa: geçmiş gerçek israfı kullan
        w_pred = max(0.0, min(1.0, gercek_ort_israf_orani / 100.0))
        kaynak = "fallback_sabit"
        kaynak_aciklama = "Veri yetersiz — geçmiş ortalama"

    # ─── A) TALEP TABANI: P_talep = D + z·σ + trend ───
    guvenlik_payi = SERVICE_LEVEL_Z * tuketim_std
    talep_tabani = ort_tuketim + guvenlik_payi

    # Trend etkisi: son dönemde artış/azalış varsa talebi düzelt
    if trend_degisim > 10:
        talep_tabani *= 1.05  # %5 daha fazla
    elif trend_degisim < -10:
        talep_tabani *= 0.95  # %5 daha az

    # ─── B) ML TASARRUF SİNYALİ: P_ml = mevcut × (1 - fark) ───
    # ML yüksek israf öngörüyorsa → üretimi orantılı azalt.
    # Hedef israfın altında israf bekleniyorsa → mevcut seviyeyi koru.
    israf_fark = max(0.0, w_pred - HEDEF_ISRAF_ORANI)
    ml_oneri = ort_uretilen * (1.0 - israf_fark)

    # ─── C) FİNAL: max(talep_tabanı, ML_oneri) — talebi karşıla ama tasarrufa zorla
    ham_oneri = max(talep_tabani, ml_oneri)

    # ──────────────────────────────────────────────────────────────
    # 5) Sanity Bounds: makul aralığa sıkıştır
    # ──────────────────────────────────────────────────────────────
    alt_sinir = ort_uretilen * ALT_SINIR_CARPAN
    ust_sinir = ort_uretilen * UST_SINIR_CARPAN
    onerilen_porsiyon = max(alt_sinir, min(ust_sinir, ham_oneri))
    onerilen_porsiyon = int(round(onerilen_porsiyon))

    # Sınırlara dokunduysa not düş
    if ham_oneri < alt_sinir:
        sinir_uyarisi = "Alt sınıra sabitlendi (aşırı düşük tahmin)"
    elif ham_oneri > ust_sinir:
        sinir_uyarisi = "Üst sınıra sabitlendi (aşırı yüksek tahmin)"
    else:
        sinir_uyarisi = None

    # Tasarruf hesabı
    tasarruf_porsiyon = round(ort_uretilen - onerilen_porsiyon)
    tasarruf_yuzde = round((tasarruf_porsiyon / ort_uretilen) * 100, 1) if ort_uretilen > 0 else 0

    # Güven seviyesi: kayıt sayısı + tahmin kaynağı
    if n >= 10 and kaynak == "ml_model":
        guven = "Yüksek"
    elif n >= 5:
        guven = "Orta"
    else:
        guven = "Düşük"

    return {
        "success": True,
        "yemek_adi": yemek_adi,
        "kategori": kategori,
        "veri_var": True,
        "kayit_sayisi": n,
        "istatistik": {
            "ort_uretilen": round(ort_uretilen, 1),
            "ort_tuketilen": round(ort_tuketim, 1),
            "tuketim_std": round(tuketim_std, 1),
            "ort_israf": round(ort_israf, 1),
            "ort_israf_orani": round(ort_israf_orani, 1),
        },
        "trend": {
            "yon": trend_yon,
            "degisim_yuzde": round(trend_degisim, 1),
            "son_donem_tuketim": round(son3_ort, 1),
        },
        "puan": {
            "ortalama": round(puan_ort, 1) if puan_ort is not None else None,
            "durum": puan_durumu,
            "oy_sayisi": toplam_oy,
        },
        "ml_tahmin": {
            "israf_orani_pct": round(israf_tahmini_pct, 1) if israf_tahmini_pct is not None else None,
            "kaynak": kaynak,
            "kaynak_aciklama": kaynak_aciklama,
        },
        "hesaplama": {
            "beklenen_talep": round(ort_tuketim, 1),
            "guvenlik_payi": round(guvenlik_payi, 1),
            "talep_tabani": round(talep_tabani, 1),
            "tahmini_israf_orani": round(w_pred * 100, 1),
            "israf_fark": round(israf_fark * 100, 1),
            "ml_oneri": round(ml_oneri, 1),
            "ham_oneri": round(ham_oneri, 1),
            "sinir_uyarisi": sinir_uyarisi,
            "formul": "P = max(D + z·σ,  P_geçmiş × (1 − max(0, w_pred − %10)))",
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
