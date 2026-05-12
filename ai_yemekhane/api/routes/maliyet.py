"""
İsraf Maliyet Hesaplayıcı API Endpoint'leri
─────────────────────────────────────────────
- GET  /api/v1/maliyet/yemekler         → Tüm yemeklerin maliyet listesi
- PUT  /api/v1/maliyet/guncelle         → Yemek birim maliyeti güncelle
- PUT  /api/v1/maliyet/toplu-guncelle   → Toplu maliyet güncelleme
- GET  /api/v1/maliyet/analiz           → Günlük/haftalık/aylık israf maliyeti
- GET  /api/v1/maliyet/trend            → Maliyet trend verisi (son N gün)
- GET  /api/v1/maliyet/detay            → Yemek bazlı maliyet detayı

Silme: Bu dosyayı silip main.py'den import'u kaldırmak yeterlidir.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from api.dependencies import get_db, Yemek, UretimLog

router = APIRouter(prefix="/api/v1/maliyet", tags=["maliyet"])


# ── Varsayılan Kategorilere Göre Maliyet ──────────────────────────
VARSAYILAN_MALIYET = {
    "corba": 15.0,
    "ana_yemek": 35.0,
    "yan_yemek": 10.0,
    "tatli": 20.0,
    "salata": 12.0,
    "icecek": 8.0,
}


# ── Request Modelleri ─────────────────────────────────────────────

class MaliyetGuncelleRequest(BaseModel):
    yemek_id: int
    birim_maliyet: float = Field(..., ge=0, le=1000)


class TopluMaliyetRequest(BaseModel):
    maliyetler: list[MaliyetGuncelleRequest]


# ═══════════════════════════════════════════════════════════════════
# YEMEK MALİYET LİSTESİ
# ═══════════════════════════════════════════════════════════════════

@router.get("/yemekler")
async def maliyet_yemek_listesi(db: Session = Depends(get_db)):
    """Tüm yemeklerin maliyet bilgisiyle listesi."""
    yemekler = db.query(Yemek).order_by(Yemek.kategori, Yemek.ad).all()

    return {
        "success": True,
        "yemekler": [
            {
                "id": y.id,
                "ad": y.ad,
                "kategori": y.kategori,
                "birim_maliyet": y.birim_maliyet,
                "birim_maliyet_gosterim": y.birim_maliyet if y.birim_maliyet is not None
                    else VARSAYILAN_MALIYET.get(y.kategori, 20.0),
                "kaynak": "girilmis" if y.birim_maliyet is not None else "varsayilan",
            }
            for y in yemekler
        ],
        "varsayilan_maliyetler": VARSAYILAN_MALIYET,
    }


# ═══════════════════════════════════════════════════════════════════
# MALİYET GÜNCELLE (TEKLİ)
# ═══════════════════════════════════════════════════════════════════

@router.put("/guncelle")
async def maliyet_guncelle(
    body: MaliyetGuncelleRequest,
    db: Session = Depends(get_db),
):
    """Tek bir yemeğin birim maliyetini günceller."""
    yemek = db.query(Yemek).filter(Yemek.id == body.yemek_id).first()
    if not yemek:
        return {"success": False, "message": "Yemek bulunamadı."}

    yemek.birim_maliyet = body.birim_maliyet
    db.commit()

    return {
        "success": True,
        "message": f"'{yemek.ad}' birim maliyeti {body.birim_maliyet} TL olarak güncellendi.",
        "yemek": yemek.to_dict(),
    }


# ═══════════════════════════════════════════════════════════════════
# TOPLU MALİYET GÜNCELLE
# ═══════════════════════════════════════════════════════════════════

@router.put("/toplu-guncelle")
async def maliyet_toplu_guncelle(
    body: TopluMaliyetRequest,
    db: Session = Depends(get_db),
):
    """Birden fazla yemeğin maliyetini tek seferde günceller."""
    guncellenen = 0
    hatalar = []

    for item in body.maliyetler:
        yemek = db.query(Yemek).filter(Yemek.id == item.yemek_id).first()
        if yemek:
            yemek.birim_maliyet = item.birim_maliyet
            guncellenen += 1
        else:
            hatalar.append(f"ID {item.yemek_id} bulunamadı")

    db.commit()

    return {
        "success": True,
        "guncellenen": guncellenen,
        "hatalar": hatalar,
        "message": f"{guncellenen} yemek maliyeti güncellendi.",
    }


# ═══════════════════════════════════════════════════════════════════
# MALİYET ANALİZ (Günlük / Haftalık / Aylık)
# ═══════════════════════════════════════════════════════════════════

def _get_birim_maliyet(db: Session, yemek_adi: str, kategori: str) -> float:
    """Yemek adına göre birim maliyeti döndürür; bulunamazsa varsayılan kullanır."""
    yemek = db.query(Yemek).filter(Yemek.ad.ilike(f"%{yemek_adi}%")).first()
    if yemek and yemek.birim_maliyet is not None:
        return yemek.birim_maliyet
    return VARSAYILAN_MALIYET.get(kategori, 20.0)


@router.get("/analiz")
async def maliyet_analiz(db: Session = Depends(get_db)):
    """Günlük, haftalık ve aylık israf maliyet özeti."""
    bugun = date.today()
    hafta_bas = bugun - timedelta(days=bugun.weekday())
    ay_bas = bugun.replace(day=1)
    gecen_ay_bas = (ay_bas - timedelta(days=1)).replace(day=1)
    gecen_ay_son = ay_bas - timedelta(days=1)

    def donem_maliyet(baslangic, bitis):
        logs = (
            db.query(UretimLog)
            .filter(
                UretimLog.tarih >= baslangic,
                UretimLog.tarih <= bitis,
                UretimLog.kalan_porsiyon.isnot(None),
            )
            .all()
        )
        toplam = 0.0
        detay = []
        for log in logs:
            birim = _get_birim_maliyet(db, log.yemek_adi, log.kategori)
            kayip = (log.kalan_porsiyon or 0) * birim
            toplam += kayip
            detay.append({
                "tarih": str(log.tarih),
                "yemek_adi": log.yemek_adi,
                "kalan_porsiyon": log.kalan_porsiyon,
                "birim_maliyet": birim,
                "kayip_tl": round(kayip, 2),
            })
        return round(toplam, 2), detay

    gunluk_toplam, gunluk_detay = donem_maliyet(bugun, bugun)
    haftalik_toplam, _ = donem_maliyet(hafta_bas, bugun)
    aylik_toplam, _ = donem_maliyet(ay_bas, bugun)
    gecen_ay_toplam, _ = donem_maliyet(gecen_ay_bas, gecen_ay_son)

    # Değişim oranı
    degisim_pct = 0.0
    if gecen_ay_toplam > 0:
        degisim_pct = round(((aylik_toplam - gecen_ay_toplam) / gecen_ay_toplam) * 100, 1)

    return {
        "success": True,
        "gunluk": {
            "toplam_tl": gunluk_toplam,
            "tarih": str(bugun),
            "detay": gunluk_detay,
        },
        "haftalik": {
            "toplam_tl": haftalik_toplam,
            "baslangic": str(hafta_bas),
            "bitis": str(bugun),
        },
        "aylik": {
            "toplam_tl": aylik_toplam,
            "ay": bugun.strftime("%Y-%m"),
        },
        "gecen_ay": {
            "toplam_tl": gecen_ay_toplam,
            "ay": gecen_ay_bas.strftime("%Y-%m"),
        },
        "degisim_pct": degisim_pct,
        "degisim_yonu": "azalma" if degisim_pct < 0 else ("artis" if degisim_pct > 0 else "ayni"),
    }


# ═══════════════════════════════════════════════════════════════════
# MALİYET TREND (Son N gün)
# ═══════════════════════════════════════════════════════════════════

@router.get("/trend")
async def maliyet_trend(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Son N günün günlük israf maliyet trendi."""
    baslangic = date.today() - timedelta(days=gun)

    # Tüm yemeklerin maliyet haritası
    yemekler = db.query(Yemek).all()
    maliyet_map = {}
    for y in yemekler:
        if y.birim_maliyet is not None:
            maliyet_map[y.ad.lower()] = y.birim_maliyet

    # Günlük grupla
    rows = (
        db.query(
            UretimLog.tarih,
            UretimLog.yemek_adi,
            UretimLog.kategori,
            UretimLog.kalan_porsiyon,
        )
        .filter(
            UretimLog.tarih >= baslangic,
            UretimLog.kalan_porsiyon.isnot(None),
        )
        .order_by(UretimLog.tarih)
        .all()
    )

    gunluk = {}
    for r in rows:
        tarih_str = str(r.tarih)
        birim = maliyet_map.get(r.yemek_adi.lower(), VARSAYILAN_MALIYET.get(r.kategori, 20.0))
        kayip = (r.kalan_porsiyon or 0) * birim

        if tarih_str not in gunluk:
            gunluk[tarih_str] = 0.0
        gunluk[tarih_str] += kayip

    trend = [
        {"tarih": t, "maliyet_tl": round(v, 2)}
        for t, v in sorted(gunluk.items())
    ]

    return {
        "success": True,
        "gun": gun,
        "trend": trend,
    }


# ═══════════════════════════════════════════════════════════════════
# YEMEK BAZLI MALİYET DETAYI
# ═══════════════════════════════════════════════════════════════════

@router.get("/detay")
async def maliyet_detay(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Yemek bazlı toplam israf maliyet sıralaması."""
    baslangic = date.today() - timedelta(days=gun)

    yemekler = db.query(Yemek).all()
    maliyet_map = {}
    for y in yemekler:
        if y.birim_maliyet is not None:
            maliyet_map[y.ad.lower()] = y.birim_maliyet

    rows = (
        db.query(
            UretimLog.yemek_adi,
            UretimLog.kategori,
            sqla_func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
            sqla_func.count(UretimLog.id).label("kayit_sayisi"),
        )
        .filter(
            UretimLog.tarih >= baslangic,
            UretimLog.kalan_porsiyon.isnot(None),
        )
        .group_by(UretimLog.yemek_adi, UretimLog.kategori)
        .all()
    )

    detay = []
    for r in rows:
        birim = maliyet_map.get(r.yemek_adi.lower(), VARSAYILAN_MALIYET.get(r.kategori, 20.0))
        toplam_kayip = (float(r.toplam_kalan) or 0) * birim
        detay.append({
            "yemek_adi": r.yemek_adi,
            "kategori": r.kategori,
            "toplam_kalan_porsiyon": round(float(r.toplam_kalan or 0), 1),
            "birim_maliyet_tl": birim,
            "toplam_kayip_tl": round(toplam_kayip, 2),
            "kayit_sayisi": int(r.kayit_sayisi or 0),
        })

    detay.sort(key=lambda x: x["toplam_kayip_tl"], reverse=True)

    return {
        "success": True,
        "gun": gun,
        "toplam_maliyet_tl": round(sum(d["toplam_kayip_tl"] for d in detay), 2),
        "yemekler": detay,
    }
