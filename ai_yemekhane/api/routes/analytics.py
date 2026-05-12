"""
Gelişmiş analitik endpoint'leri — israf trend, kategori dağılım,
top israf, haftalık karşılaştırma, maliyet analizi, sentiment,
trend analizi, uyarılar ve geri bildirim.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from api.dependencies import get_db, UretimLog, MenuPuanlama
from modules.trend_analyzer import (
    get_monthly_trends,
    get_seasonal_analysis,
    get_dish_trend,
)
from modules.alert_system import (
    get_active_alerts,
    get_alert_history,
)
from modules.feedback_analyzer import analyze_feedback

router = APIRouter(prefix="/api/v1", tags=["analytics"])


# ═══════════════════════════════════════════════════════════════════
# İSRAF TREND & CHART VERİLERİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/analytics/israf-trend")
async def analytics_israf_trend(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Son N günün günlük israf trend çizgi grafiği verisi."""
    try:
        baslangic = date.today() - timedelta(days=gun)
        rows = (
            db.query(
                UretimLog.tarih,
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                sqla_func.sum(UretimLog.uretilen_porsiyon).label("toplam_uretilen"),
                sqla_func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
                sqla_func.count(UretimLog.id).label("yemek_sayisi"),
            )
            .filter(UretimLog.tarih >= baslangic, UretimLog.israf_orani.isnot(None))
            .group_by(UretimLog.tarih)
            .order_by(UretimLog.tarih)
            .all()
        )
        trend = [
            {
                "tarih": str(r.tarih),
                "ort_israf": round(float(r.ort_israf or 0), 1),
                "toplam_uretilen": int(r.toplam_uretilen or 0),
                "toplam_kalan": int(r.toplam_kalan or 0),
                "yemek_sayisi": int(r.yemek_sayisi or 0),
            }
            for r in rows
        ]
        # Genel ortalama
        genel_ort = round(sum(t["ort_israf"] for t in trend) / len(trend), 1) if trend else 0
        return {"success": True, "trend": trend, "genel_ortalama": genel_ort}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/kategori-dagilim")
async def analytics_kategori_dagilim(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Kategori bazlı israf dağılımı (doughnut chart verisi)."""
    try:
        baslangic = date.today() - timedelta(days=gun)
        rows = (
            db.query(
                UretimLog.kategori,
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                sqla_func.sum(UretimLog.uretilen_porsiyon).label("toplam_uretilen"),
                sqla_func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
                sqla_func.count(UretimLog.id).label("kayit_sayisi"),
            )
            .filter(UretimLog.tarih >= baslangic, UretimLog.israf_orani.isnot(None))
            .group_by(UretimLog.kategori)
            .all()
        )
        KAT_LABELS = {
            "corba": "Çorbalar", "ana_yemek": "Ana Yemekler", "yan_yemek": "Yan Yemekler",
            "tatli": "Tatlılar", "salata": "Salatalar", "diger": "Diğer"
        }
        dagilim = [
            {
                "kategori": r.kategori or "diger",
                "kategori_label": KAT_LABELS.get(r.kategori, r.kategori or "Diğer"),
                "ort_israf": round(float(r.ort_israf or 0), 1),
                "toplam_uretilen": int(r.toplam_uretilen or 0),
                "toplam_kalan": int(r.toplam_kalan or 0),
                "kayit_sayisi": int(r.kayit_sayisi or 0),
            }
            for r in rows
        ]
        return {"success": True, "dagilim": dagilim}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/top-israf")
async def analytics_top_israf(
    limit: int = Query(default=10, ge=1, le=50),
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """En çok ve en az israf edilen yemekler (bar chart verisi)."""
    try:
        baslangic = date.today() - timedelta(days=gun)
        rows = (
            db.query(
                UretimLog.yemek_adi,
                UretimLog.kategori,
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                sqla_func.count(UretimLog.id).label("kayit_sayisi"),
                sqla_func.avg(UretimLog.uretilen_porsiyon).label("ort_uretilen"),
            )
            .filter(UretimLog.tarih >= baslangic, UretimLog.israf_orani.isnot(None))
            .group_by(UretimLog.yemek_adi, UretimLog.kategori)
            .having(sqla_func.count(UretimLog.id) >= 2)
            .all()
        )
        yemekler = [
            {
                "yemek_adi": r.yemek_adi,
                "kategori": r.kategori,
                "ort_israf": round(float(r.ort_israf or 0), 1),
                "kayit_sayisi": int(r.kayit_sayisi or 0),
                "ort_uretilen": round(float(r.ort_uretilen or 0), 0),
            }
            for r in rows
        ]
        en_cok = sorted(yemekler, key=lambda x: x["ort_israf"], reverse=True)[:limit]
        en_az = sorted(yemekler, key=lambda x: x["ort_israf"])[:limit]
        return {"success": True, "en_cok_israf": en_cok, "en_az_israf": en_az}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/haftalik-israf")
@router.get("/analytics/haftalik-karsilastirma")
async def analytics_haftalik_karsilastirma(db: Session = Depends(get_db)):
    """Bu hafta vs geçen hafta israf karşılaştırması."""
    try:
        bugun = date.today()
        bu_hafta_bas = bugun - timedelta(days=bugun.weekday())
        gecen_hafta_bas = bu_hafta_bas - timedelta(days=7)
        gecen_hafta_son = bu_hafta_bas - timedelta(days=1)

        def hafta_ozet(bas, son):
            rows = (
                db.query(
                    sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                    sqla_func.sum(UretimLog.uretilen_porsiyon).label("toplam_uretilen"),
                    sqla_func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
                    sqla_func.count(UretimLog.id).label("kayit"),
                )
                .filter(UretimLog.tarih >= bas, UretimLog.tarih <= son, UretimLog.israf_orani.isnot(None))
                .first()
            )
            return {
                "ort_israf": round(float(rows.ort_israf or 0), 1) if rows.ort_israf else 0,
                "toplam_uretilen": int(rows.toplam_uretilen or 0),
                "toplam_kalan": int(rows.toplam_kalan or 0),
                "kayit_sayisi": int(rows.kayit or 0),
            }

        bu_hafta = hafta_ozet(bu_hafta_bas, bugun)
        gecen_hafta = hafta_ozet(gecen_hafta_bas, gecen_hafta_son)

        # Değişim hesapla
        degisim = 0
        if gecen_hafta["ort_israf"] > 0:
            degisim = round(bu_hafta["ort_israf"] - gecen_hafta["ort_israf"], 1)

        return {
            "success": True,
            "bu_hafta": bu_hafta,
            "gecen_hafta": gecen_hafta,
            "degisim": degisim,
            "iyilesti_mi": degisim < 0,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# MALİYET ANALİZİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/analytics/maliyet")
async def analytics_maliyet(
    gun: int = Query(default=30, ge=7, le=365),
    porsiyon_maliyet_tl: float = Query(default=35.0, ge=1.0),
    db: Session = Depends(get_db),
):
    """İsrafın tahmini maliyet karşılığı (TL)."""
    try:
        baslangic = date.today() - timedelta(days=gun)
        rows = (
            db.query(
                sqla_func.sum(UretimLog.uretilen_porsiyon).label("toplam_uretilen"),
                sqla_func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
            )
            .filter(UretimLog.tarih >= baslangic)
            .first()
        )
        toplam_uretilen = int(rows.toplam_uretilen or 0)
        toplam_kalan = int(rows.toplam_kalan or 0)
        israf_maliyeti = round(toplam_kalan * porsiyon_maliyet_tl, 2)
        toplam_maliyet = round(toplam_uretilen * porsiyon_maliyet_tl, 2)
        israf_orani = round((toplam_kalan / toplam_uretilen * 100), 1) if toplam_uretilen > 0 else 0

        # AI tahmini tasarruf: israfı %30 azaltırsa
        tasarruf_30 = round(israf_maliyeti * 0.30, 2)

        return {
            "success": True,
            "toplam_uretilen_porsiyon": toplam_uretilen,
            "toplam_israf_porsiyon": toplam_kalan,
            "israf_orani_yuzde": israf_orani,
            "toplam_uretim_maliyeti_tl": toplam_maliyet,
            "israf_maliyeti_tl": israf_maliyeti,
            "ai_tasarruf_potansiyeli_tl": tasarruf_30,
            "porsiyon_birim_maliyet_tl": porsiyon_maliyet_tl,
            "donem_gun": gun,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/analytics/maliyet-detay")
async def analytics_maliyet_detay(
    gun: int = Query(default=30, ge=7, le=365),
    porsiyon_maliyet_tl: float = Query(default=35.0, ge=1.0),
    db: Session = Depends(get_db),
):
    """Yemek bazlı detaylı maliyet analizi — en pahalı israf yemekleri."""
    try:
        baslangic = date.today() - timedelta(days=gun)

        # Yemek bazlı israf detayları
        rows = (
            db.query(
                UretimLog.yemek_adi,
                sqla_func.sum(UretimLog.uretilen_porsiyon).label("uretilen"),
                sqla_func.sum(UretimLog.kalan_porsiyon).label("kalan"),
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                sqla_func.count(UretimLog.id).label("kayit"),
            )
            .filter(UretimLog.tarih >= baslangic)
            .group_by(UretimLog.yemek_adi)
            .order_by(sqla_func.sum(UretimLog.kalan_porsiyon).desc())
            .all()
        )

        yemekler = []
        toplam_israf_maliyet = 0
        for r in rows:
            uret = int(r.uretilen or 0)
            kal = int(r.kalan or 0)
            maliyet = round(kal * porsiyon_maliyet_tl, 2)
            toplam_israf_maliyet += maliyet
            yemekler.append({
                "yemek_adi": r.yemek_adi,
                "uretilen_porsiyon": uret,
                "israf_porsiyon": kal,
                "israf_orani": round(float(r.ort_israf or 0), 1),
                "israf_maliyeti_tl": maliyet,
                "kayit_sayisi": r.kayit,
            })

        # Haftalık trend (son 4 hafta)
        haftalik_trend = []
        for i in range(4):
            hafta_bitis = date.today() - timedelta(days=i * 7)
            hafta_baslangic = hafta_bitis - timedelta(days=6)
            hafta = db.query(
                sqla_func.sum(UretimLog.kalan_porsiyon).label("kalan"),
                sqla_func.sum(UretimLog.uretilen_porsiyon).label("uretilen"),
            ).filter(
                UretimLog.tarih >= hafta_baslangic,
                UretimLog.tarih <= hafta_bitis,
            ).first()
            h_kalan = int(hafta.kalan or 0)
            h_uretilen = int(hafta.uretilen or 0)
            haftalik_trend.append({
                "hafta": f"{hafta_baslangic.strftime('%d.%m')} - {hafta_bitis.strftime('%d.%m')}",
                "israf_porsiyon": h_kalan,
                "israf_maliyeti_tl": round(h_kalan * porsiyon_maliyet_tl, 2),
                "israf_orani": round(h_kalan / h_uretilen * 100, 1) if h_uretilen > 0 else 0,
            })

        return {
            "success": True,
            "donem_gun": gun,
            "toplam_israf_maliyeti_tl": round(toplam_israf_maliyet, 2),
            "ai_tasarruf_potansiyeli_tl": round(toplam_israf_maliyet * 0.30, 2),
            "yemek_detaylari": yemekler[:20],
            "haftalik_trend": list(reversed(haftalik_trend)),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# SENTIMENT ANALİZİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/analytics/sentiment")
async def analytics_sentiment(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Türkçe kelime tabanlı duygu analizi — pozitif/negatif/nötr dağılımı."""
    from modules.sentiment_analyzer import analyze_sentiment
    try:
        return analyze_sentiment(db=db, gun=gun)
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/analytics/sentiment/train")
async def train_sentiment_endpoint(
    db: Session = Depends(get_db),
):
    """TF-IDF + LogisticRegression sentiment modelini eğitir."""
    from modules.sentiment_analyzer import train_sentiment_model
    try:
        return train_sentiment_model(db=db)
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# TREND ANALİZİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/trends/monthly")
async def trends_monthly(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Aylık trend raporunu döndürür."""
    return get_monthly_trends(gun=gun, db=db)


@router.get("/trends/seasonal")
async def trends_seasonal(db: Session = Depends(get_db)):
    """Mevsimsel analizi döndürür."""
    return get_seasonal_analysis(db=db)


@router.get("/trends/dish/{yemek_adi}")
async def trends_dish(
    yemek_adi: str,
    gun: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Belirli bir yemeğin uzun vadeli trendini döndürür."""
    return get_dish_trend(yemek_adi, gun=gun, db=db)


# ═══════════════════════════════════════════════════════════════════
# UYARI SİSTEMİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/alerts/active")
async def alerts_active(db: Session = Depends(get_db)):
    """Aktif uyarıları döndürür."""
    return get_active_alerts(db=db)


@router.get("/alerts/history")
async def alerts_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Geçmiş uyarıları döndürür."""
    return get_alert_history(limit=limit, db=db)


# ═══════════════════════════════════════════════════════════════════
# GERİ BİLDİRİM ANALİZİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/feedback/analysis")
async def feedback_analysis(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Öğrenci geri bildirimlerinin AI destekli analizi ve menü önerileri."""
    try:
        result = analyze_feedback(db=db, gun=gun)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# SELF-REPORT İSTATİSTİKLERİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/analytics/self-report")
async def analytics_self_report(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Öğrenci israf self-report istatistikleri — yemek bazlı ve günlük trend."""
    try:
        baslangic = date.today() - timedelta(days=gun)

        # Yemek bazlı self-report ortalamaları
        yemek_bazli = (
            db.query(
                MenuPuanlama.yemek_adi,
                MenuPuanlama.kategori,
                sqla_func.avg(MenuPuanlama.israf_self_report).label("ort_sr"),
                sqla_func.count(MenuPuanlama.israf_self_report).label("sr_sayisi"),
                sqla_func.avg(MenuPuanlama.puan).label("ort_puan"),
            )
            .filter(
                MenuPuanlama.tarih >= baslangic,
                MenuPuanlama.israf_self_report.isnot(None),
            )
            .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
            .order_by(sqla_func.avg(MenuPuanlama.israf_self_report).desc())
            .all()
        )

        SR_LABELS = ["Hiç", "Az (<%25)", "Orta (%25-50)", "Çok (>%50)"]
        yemekler = [
            {
                "yemek_adi": r.yemek_adi,
                "kategori": r.kategori,
                "ort_self_report": round(float(r.ort_sr), 2),
                "self_report_label": SR_LABELS[min(3, round(float(r.ort_sr)))],
                "bildirim_sayisi": int(r.sr_sayisi),
                "ort_puan": round(float(r.ort_puan), 1) if r.ort_puan else None,
            }
            for r in yemek_bazli
        ]

        # Günlük trend
        gunluk_trend = (
            db.query(
                MenuPuanlama.tarih,
                sqla_func.avg(MenuPuanlama.israf_self_report).label("ort_sr"),
                sqla_func.count(MenuPuanlama.israf_self_report).label("sr_sayisi"),
            )
            .filter(
                MenuPuanlama.tarih >= baslangic,
                MenuPuanlama.israf_self_report.isnot(None),
            )
            .group_by(MenuPuanlama.tarih)
            .order_by(MenuPuanlama.tarih)
            .all()
        )

        trend = [
            {
                "tarih": str(r.tarih),
                "ort_self_report": round(float(r.ort_sr), 2),
                "bildirim_sayisi": int(r.sr_sayisi),
            }
            for r in gunluk_trend
        ]

        # Dağılım: kaç kişi hangi seçeneği seçti
        dagilim_raw = (
            db.query(
                MenuPuanlama.israf_self_report,
                sqla_func.count(MenuPuanlama.id).label("sayi"),
            )
            .filter(
                MenuPuanlama.tarih >= baslangic,
                MenuPuanlama.israf_self_report.isnot(None),
            )
            .group_by(MenuPuanlama.israf_self_report)
            .all()
        )
        dagilim = {SR_LABELS[int(r.israf_self_report)]: int(r.sayi) for r in dagilim_raw if r.israf_self_report is not None}

        toplam = sum(dagilim.values())

        return {
            "success": True,
            "donem_gun": gun,
            "toplam_bildirim": toplam,
            "dagilim": dagilim,
            "en_cok_israfa_maruz": yemekler[:5],
            "en_az_israfa_maruz": list(reversed(yemekler[-5:])) if len(yemekler) >= 5 else list(reversed(yemekler)),
            "tum_yemekler": yemekler,
            "gunluk_trend": trend,
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# KARŞILAŞTIRMALI DÖNEM RAPORU (2C)
# ═══════════════════════════════════════════════════════════════════

@router.get("/analytics/donem-karsilastirma")
async def analytics_donem_karsilastirma(
    donem: str = Query(default="ay", description="hafta | ay | ozel"),
    gun: int = Query(default=30, ge=7, le=365, description="'ozel' modu için gün sayısı"),
    db: Session = Depends(get_db),
):
    """
    İki ardışık dönemi karşılaştırır (bu dönem vs geçen dönem).
    Dönem seçenekleri: hafta (7 gün), ay (30 gün), ozel (custom gün).
    """
    try:
        from api.dependencies import Yemek
        bugun = date.today()

        if donem == "hafta":
            gun_sayisi = 7
        elif donem == "ay":
            gun_sayisi = 30
        else:
            gun_sayisi = gun

        bu_donem_bas = bugun - timedelta(days=gun_sayisi - 1)
        gecen_donem_son = bu_donem_bas - timedelta(days=1)
        gecen_donem_bas = gecen_donem_son - timedelta(days=gun_sayisi - 1)

        # ── Yardımcı: Dönem istatistikleri ────────────────────
        def donem_ozet(bas, son):
            israf = db.query(
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
                sqla_func.sum(UretimLog.uretilen_porsiyon).label("uretilen"),
                sqla_func.sum(UretimLog.kalan_porsiyon).label("kalan"),
                sqla_func.count(UretimLog.id).label("kayit"),
            ).filter(
                UretimLog.tarih >= bas, UretimLog.tarih <= son,
                UretimLog.israf_orani.isnot(None),
            ).first()

            puan = db.query(
                sqla_func.avg(MenuPuanlama.puan).label("ort_puan"),
                sqla_func.count(MenuPuanlama.id).label("oy_sayisi"),
            ).filter(
                MenuPuanlama.tarih >= bas, MenuPuanlama.tarih <= son,
            ).first()

            ort_israf = round(float(israf.ort_israf or 0), 1)
            uretilen = int(israf.uretilen or 0)
            kalan = int(israf.kalan or 0)

            # Maliyet hesabı — birim maliyet veritabanından
            maliyet_map = {}
            try:
                yemekler_db = db.query(Yemek).all()
                for y in yemekler_db:
                    if y.birim_maliyet is not None:
                        maliyet_map[y.ad.lower()] = y.birim_maliyet
            except Exception:
                pass

            varsayilan_mal = {
                "corba": 15.0, "ana_yemek": 35.0, "yan_yemek": 10.0,
                "tatli": 20.0, "salata": 12.0, "icecek": 8.0,
            }

            maliyet_kayip = 0.0
            logs = db.query(UretimLog).filter(
                UretimLog.tarih >= bas, UretimLog.tarih <= son,
            ).all()
            for log in logs:
                birim = maliyet_map.get(
                    log.yemek_adi.lower(),
                    varsayilan_mal.get(log.kategori, 20.0),
                )
                maliyet_kayip += (log.kalan_porsiyon or 0) * birim

            return {
                "ort_israf": ort_israf,
                "toplam_uretilen": uretilen,
                "toplam_kalan": kalan,
                "kayit_sayisi": int(israf.kayit or 0),
                "ort_puan": round(float(puan.ort_puan or 0), 1) if puan.ort_puan else 0,
                "toplam_oy": int(puan.oy_sayisi or 0),
                "maliyet_kayip_tl": round(maliyet_kayip, 0),
                "baslangic": str(bas),
                "bitis": str(son),
            }

        bu = donem_ozet(bu_donem_bas, bugun)
        gecen = donem_ozet(gecen_donem_bas, gecen_donem_son)

        # ── İyileşme oranları ─────────────────────────────────
        def iyilesme(eski, yeni):
            if eski == 0:
                return 0
            return round((eski - yeni) / eski * 100, 1)

        degisim = {
            "israf_puan": round(bu["ort_israf"] - gecen["ort_israf"], 1),
            "israf_iyilesme_pct": iyilesme(gecen["ort_israf"], bu["ort_israf"]),
            "maliyet_fark_tl": round(gecen["maliyet_kayip_tl"] - bu["maliyet_kayip_tl"], 0),
            "maliyet_iyilesme_pct": iyilesme(gecen["maliyet_kayip_tl"], bu["maliyet_kayip_tl"]),
            "puan_fark": round(bu["ort_puan"] - gecen["ort_puan"], 2),
            "oy_fark": bu["toplam_oy"] - gecen["toplam_oy"],
        }

        # ── Günlük trend verileri (her iki dönem) ────────────
        def gunluk_trend(bas, son):
            rows = db.query(
                UretimLog.tarih,
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            ).filter(
                UretimLog.tarih >= bas, UretimLog.tarih <= son,
                UretimLog.israf_orani.isnot(None),
            ).group_by(UretimLog.tarih).order_by(UretimLog.tarih).all()
            return [{"tarih": str(r.tarih), "ort_israf": round(float(r.ort_israf), 1)} for r in rows]

        bu_trend = gunluk_trend(bu_donem_bas, bugun)
        gecen_trend = gunluk_trend(gecen_donem_bas, gecen_donem_son)

        # ── En çok değişen yemekler ──────────────────────────
        def yemek_israf_map(bas, son):
            rows = db.query(
                UretimLog.yemek_adi,
                sqla_func.avg(UretimLog.israf_orani).label("ort"),
            ).filter(
                UretimLog.tarih >= bas, UretimLog.tarih <= son,
                UretimLog.israf_orani.isnot(None),
            ).group_by(UretimLog.yemek_adi).all()
            return {r.yemek_adi: round(float(r.ort), 1) for r in rows}

        bu_map = yemek_israf_map(bu_donem_bas, bugun)
        gecen_map = yemek_israf_map(gecen_donem_bas, gecen_donem_son)

        tum_yemekler_set = set(bu_map.keys()) | set(gecen_map.keys())
        yemek_degisim = []
        for y in tum_yemekler_set:
            eski = gecen_map.get(y, None)
            yeni = bu_map.get(y, None)
            if eski is not None and yeni is not None:
                fark = round(yeni - eski, 1)
                yemek_degisim.append({"yemek": y, "gecen": eski, "bu": yeni, "fark": fark})

        yemek_degisim.sort(key=lambda x: x["fark"])
        en_iyilesen = yemek_degisim[:5] if yemek_degisim else []
        en_kotulesen = list(reversed(yemek_degisim[-5:])) if len(yemek_degisim) >= 5 else list(reversed(yemek_degisim))

        return {
            "success": True,
            "donem": donem,
            "gun_sayisi": gun_sayisi,
            "bu_donem": bu,
            "gecen_donem": gecen,
            "degisim": degisim,
            "genel_durum": "iyilesti" if degisim["israf_puan"] < -1 else (
                "kotulesti" if degisim["israf_puan"] > 1 else "stabil"
            ),
            "bu_donem_trend": bu_trend,
            "gecen_donem_trend": gecen_trend,
            "en_iyilesen_yemekler": en_iyilesen,
            "en_kotulesen_yemekler": en_kotulesen,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
