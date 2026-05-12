"""
Puanlama endpoint'leri — yemek puanlama, bugünkü puanlar,
haftalık rapor, puan geçmişi ve tüm puanlanan yemekler.
"""

import asyncio
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.dependencies import (
    get_db,
    RateMealRequest,
    Menu,
    MenuPuanlama,
    _canonicalize_meal_name,
    _merge_meal_rating_aggregates,
)

router = APIRouter(prefix="/api/v1", tags=["ratings"])


# ──────────────────────────────────────────────────────────────────
# POST /api/rate-meal — Anonim yemek puanlama
# ──────────────────────────────────────────────────────────────────
@router.post("/rate-meal")
async def rate_meal(
    request_body: RateMealRequest,
    db: Session = Depends(get_db),
):
    """
    Anonim olarak yemek puanı kaydeder.
    Giriş veya kullanıcı ID gerektirmez.
    """
    gecerli_kategoriler = ["corba", "ana_yemek", "yan_yemek", "tatli", "salata", "icecek"]
    if request_body.kategori not in gecerli_kategoriler:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"Geçersiz kategori: '{request_body.kategori}'. "
                           f"Geçerli: {gecerli_kategoriler}",
            },
        )

    try:
        tarih = date.fromisoformat(request_body.tarih)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Geçersiz tarih formatı. YYYY-MM-DD kullanın.",
            },
        )

    canonical_meal_name = _canonicalize_meal_name(request_body.yemek_adi)
    if not canonical_meal_name:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Yemek adı boş olamaz.",
            },
        )

    yeni_puan = MenuPuanlama(
        tarih=tarih,
        yemek_adi=canonical_meal_name,
        kategori=request_body.kategori,
        puan=request_body.puan,
        yorum=request_body.yorum,
        israf_self_report=request_body.israf_self_report,
    )
    db.add(yeni_puan)
    db.commit()
    db.refresh(yeni_puan)

    # Alert cache'i temizle — yeni puanlama kuralları etkileyebilir
    try:
        from modules.alert_system import invalidate_alerts_cache
        invalidate_alerts_cache()
    except Exception:
        pass

    # WebSocket broadcast — yeni puanlama bildir
    try:
        from api.routes.websocket import broadcast_event
        asyncio.ensure_future(broadcast_event("new_rating", {
            "yemek_adi": canonical_meal_name,
            "kategori": request_body.kategori,
            "puan": request_body.puan,
            "tarih": str(tarih),
        }))
    except Exception:
        pass  # WS başarısız olursa API yanıtını etkilemesin

    return {
        "success": True,
        "message": f"'{canonical_meal_name}' için {request_body.puan}⭐ puanınız kaydedildi. Teşekkürler!",
        "data": yeni_puan.to_dict(),
    }


# ──────────────────────────────────────────────────────────────────
# GET /api/ratings/today — Bugünün ortalama puanları
# ──────────────────────────────────────────────────────────────────
@router.get("/ratings/today")
async def get_today_ratings(db: Session = Depends(get_db)):
    """Bugünün menüsündeki yemeklerin anonim ortalama puanlarını döndürür."""
    bugun = date.today()

    # Bugünkü menüdeki yemek adlarını çek
    bugunun_menusu = db.query(Menu).filter(Menu.tarih == bugun).first()
    menu_yemekleri = set()
    if bugunun_menusu:
        for alan in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
            yemek = getattr(bugunun_menusu, alan, None)
            if yemek:
                menu_yemekleri.add(yemek.strip())

    sonuclar = (
        db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.kategori,
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
            func.avg(MenuPuanlama.israf_self_report).label("ort_self_report"),
            func.count(MenuPuanlama.israf_self_report).label("self_report_sayisi"),
        )
        .filter(MenuPuanlama.tarih == bugun)
        .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
        .all()
    )

    birlesik_sonuclar = _merge_meal_rating_aggregates(sonuclar)

    # Sadece bugünkü menüdeki yemekleri filtrele
    if menu_yemekleri:
        birlesik_sonuclar = [
            r for r in birlesik_sonuclar
            if r["yemek_adi"].strip() in menu_yemekleri
        ]

    # Self-report verilerini ayrı sorgula (merge sonrası yemek adlarıyla eşleştir)
    self_report_raw = (
        db.query(
            MenuPuanlama.yemek_adi,
            func.avg(MenuPuanlama.israf_self_report).label("ort_self_report"),
            func.count(MenuPuanlama.israf_self_report).label("self_report_sayisi"),
        )
        .filter(
            MenuPuanlama.tarih == bugun,
            MenuPuanlama.israf_self_report.isnot(None),
        )
        .group_by(MenuPuanlama.yemek_adi)
        .all()
    )
    sr_map = {}
    for r in self_report_raw:
        sr_map[_canonicalize_meal_name(r.yemek_adi)] = {
            "ort_self_report": round(float(r.ort_self_report), 2) if r.ort_self_report else None,
            "self_report_sayisi": int(r.self_report_sayisi or 0),
        }

    data = {}
    for row in birlesik_sonuclar:
        sr = sr_map.get(row["yemek_adi"], {})
        data[row["yemek_adi"]] = {
            "kategori": row["kategori"],
            "ortalama": round(float(row["ortalama"]), 1),
            "toplam_oy": row["toplam_oy"],
            "ort_self_report": sr.get("ort_self_report"),
            "self_report_sayisi": sr.get("self_report_sayisi", 0),
        }

    return {
        "success": True,
        "tarih": str(bugun),
        "data": data,
    }


# ──────────────────────────────────────────────────────────────────
# GET /api/ratings/weekly-report — Haftalık puanlama raporu
# ──────────────────────────────────────────────────────────────────
@router.get("/ratings/weekly-report")
async def get_weekly_rating_report(db: Session = Depends(get_db)):
    """
    Son 7 günün yemek puanlama raporunu döndürür.
    En beğenilen / en az beğenilen yemekler ve kategori ortalamaları.
    """
    bugun = date.today()
    hafta_basi = bugun - timedelta(days=7)

    # Yemek bazında ortalamalar
    yemek_ort = (
        db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.kategori,
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .filter(MenuPuanlama.tarih >= hafta_basi)
        .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
        .order_by(func.avg(MenuPuanlama.puan).desc())
        .all()
    )

    birlesik_yemek_ort = _merge_meal_rating_aggregates(yemek_ort)

    tum_yemekler = sorted([
        {
            "yemek_adi": row["yemek_adi"],
            "kategori": row["kategori"],
            "ortalama": round(float(row["ortalama"]), 2),
            "toplam_oy": row["toplam_oy"],
        }
        for row in birlesik_yemek_ort
    ], key=lambda item: item["ortalama"], reverse=True)

    en_begenilen = tum_yemekler[:5]
    en_az_begenilen = list(reversed(tum_yemekler[-5:])) if len(tum_yemekler) >= 5 else list(reversed(tum_yemekler))

    # Kategori bazında ortalamalar
    kategori_ort = (
        db.query(
            MenuPuanlama.kategori,
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .filter(MenuPuanlama.tarih >= hafta_basi)
        .group_by(MenuPuanlama.kategori)
        .all()
    )

    kategoriler = {
        row.kategori: {
            "ortalama": round(float(row.ortalama), 2),
            "toplam_oy": row.toplam_oy,
        }
        for row in kategori_ort
    }

    return {
        "success": True,
        "donem": {"baslangic": str(hafta_basi), "bitis": str(bugun)},
        "en_begenilen": en_begenilen,
        "en_az_begenilen": en_az_begenilen,
        "kategori_ortalama": kategoriler,
        "tum_yemekler": tum_yemekler,
    }


# ──────────────────────────────────────────────────────────────────
# GET /api/ratings/all-rated-meals — Son N gündeki tüm puanlanan yemekler
# ──────────────────────────────────────────────────────────────────
@router.get("/ratings/all-rated-meals")
async def get_all_rated_meals(
    gun: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Son N gün içinde puanlanan tüm benzersiz yemekleri döndürür.
    Puan Trendi dropdown'ı için kullanılır.
    """
    bugun = date.today()
    baslangic = bugun - timedelta(days=gun)

    sonuclar = (
        db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.kategori,
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .filter(MenuPuanlama.tarih >= baslangic)
        .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
        .order_by(func.avg(MenuPuanlama.puan).desc())
        .all()
    )

    birlesik = _merge_meal_rating_aggregates(sonuclar)

    yemekler = sorted([
        {
            "yemek_adi": row["yemek_adi"],
            "kategori": row["kategori"],
            "ortalama": round(float(row["ortalama"]), 2),
            "toplam_oy": row["toplam_oy"],
        }
        for row in birlesik
    ], key=lambda item: item["ortalama"], reverse=True)

    return {
        "success": True,
        "gun": gun,
        "donem": {"baslangic": str(baslangic), "bitis": str(bugun)},
        "yemekler": yemekler,
        "toplam": len(yemekler),
    }


# ──────────────────────────────────────────────────────────────────
# GET /api/ratings/history/{yemek_adi} — Yemek puan geçmişi
# ──────────────────────────────────────────────────────────────────
@router.get("/ratings/history/{yemek_adi}")
async def get_meal_rating_history(
    yemek_adi: str,
    gun: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Belirli bir yemeğin geçmiş puanlarını ve trendini döndürür."""
    bugun = date.today()
    baslangic = bugun - timedelta(days=gun)

    # Günlük ortalamalar
    gunluk = (
        db.query(
            MenuPuanlama.tarih,
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .filter(
            MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
            MenuPuanlama.tarih >= baslangic,
        )
        .group_by(MenuPuanlama.tarih)
        .order_by(MenuPuanlama.tarih)
        .all()
    )

    trend = [
        {
            "tarih": str(row.tarih),
            "ortalama": round(float(row.ortalama), 2),
            "toplam_oy": row.toplam_oy,
        }
        for row in gunluk
    ]

    # Genel ortalama
    genel = (
        db.query(
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .filter(
            MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
            MenuPuanlama.tarih >= baslangic,
        )
        .first()
    )

    # Son yorumlar (en yeni 5)
    son_yorumlar = (
        db.query(MenuPuanlama)
        .filter(
            MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
            MenuPuanlama.yorum.isnot(None),
            MenuPuanlama.yorum != "",
        )
        .order_by(MenuPuanlama.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "success": True,
        "yemek_adi": yemek_adi,
        "donem_gun": gun,
        "genel_ortalama": round(float(genel.ortalama), 2) if genel.ortalama else 0,
        "toplam_oy": genel.toplam_oy if genel.toplam_oy else 0,
        "trend": trend,
        "son_yorumlar": [
            {"puan": y.puan, "yorum": y.yorum, "tarih": str(y.tarih)}
            for y in son_yorumlar
        ],
    }
