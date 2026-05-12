"""
What-If Simülasyon API Endpoint'leri
─────────────────────────────────────
- GET  /api/v1/simulation/yemek-listesi  → Kategorilere göre yemek listesi
- POST /api/v1/simulation/what-if        → Mevcut vs değişiklik karşılaştırması
- GET  /api/v1/simulation/menu-bugun     → Bugünkü menüyü getir

Silme: Bu dosyayı silip main.py'den import'u kaldırmak yeterlidir.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from api.dependencies import get_db, Yemek, UretimLog, Menu, MenuPuanlama

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


# ── Varsayılan maliyet ────────────────────────────────────────────
_VARSAYILAN_MALIYET = {
    "corba": 15.0, "ana_yemek": 35.0, "yan_yemek": 10.0,
    "tatli": 20.0, "salata": 12.0, "icecek": 8.0,
}

# ── Request Modelleri ─────────────────────────────────────────────

class WhatIfItem(BaseModel):
    slot: str = Field(..., description="corba | ana_yemek | yan_yemek | tatli | salata")
    mevcut_yemek: str
    yeni_yemek: str


class WhatIfRequest(BaseModel):
    tarih: str | None = None
    degisiklikler: list[WhatIfItem]
    uretilen_porsiyon: float = Field(default=200, ge=1)


# ═══════════════════════════════════════════════════════════════════
# YEMEK LİSTESİ (Kategorilere Göre)
# ═══════════════════════════════════════════════════════════════════

@router.get("/yemek-listesi")
async def yemek_listesi(db: Session = Depends(get_db)):
    """Simülasyonda kullanılabilecek tüm yemeklerin kategoriye göre listesi."""
    try:
        from modules.menu_optimizer import YEMEK_BAZI_POPULERLIK
    except ImportError:
        YEMEK_BAZI_POPULERLIK = {}

    # DB'deki yemekler
    db_yemekler = db.query(Yemek).order_by(Yemek.kategori, Yemek.ad).all()
    db_set = {y.ad.lower() for y in db_yemekler}

    kategoriler = {}

    # DB yemekleri
    for y in db_yemekler:
        kat = y.kategori or "diger"
        if kat not in kategoriler:
            kategoriler[kat] = []
        kategoriler[kat].append({
            "ad": y.ad,
            "populerlik": YEMEK_BAZI_POPULERLIK.get(y.ad, 0.5),
            "birim_maliyet": y.birim_maliyet or _VARSAYILAN_MALIYET.get(kat, 20.0),
        })

    # Popülerlik sözlüğündekilerden DB'de olmayanlar
    for ad, pop in YEMEK_BAZI_POPULERLIK.items():
        if ad.lower() not in db_set:
            kat = _guess_kategori(ad)
            if kat not in kategoriler:
                kategoriler[kat] = []
            kategoriler[kat].append({
                "ad": ad,
                "populerlik": pop,
                "birim_maliyet": _VARSAYILAN_MALIYET.get(kat, 20.0),
            })

    # Popülerliğe göre sırala
    for kat in kategoriler:
        kategoriler[kat].sort(key=lambda x: x["populerlik"], reverse=True)

    return {"success": True, "kategoriler": kategoriler}


def _guess_kategori(ad: str) -> str:
    """Yemek adından kategori tahmin et."""
    ad_lower = ad.lower()
    if "çorba" in ad_lower or "corba" in ad_lower:
        return "corba"
    if "pilav" in ad_lower or "makarna" in ad_lower or "bulgur" in ad_lower or "spagetti" in ad_lower:
        return "yan_yemek"
    if "salata" in ad_lower or "cacık" in ad_lower or "cacik" in ad_lower:
        return "salata"
    if any(t in ad_lower for t in ["puding", "sütlaç", "baklava", "revani", "kadayıf", "helva",
                                     "kemal paşa", "komposto", "aşure", "brownie", "kek",
                                     "muhallebi", "trileçe", "trilece", "tatlı", "tatli"]):
        return "tatli"
    return "ana_yemek"


# ═══════════════════════════════════════════════════════════════════
# BUGÜNKÜ MENÜ
# ═══════════════════════════════════════════════════════════════════

@router.get("/menu-bugun")
async def menu_bugun(db: Session = Depends(get_db)):
    """Bugünkü veya en son menüyü getir."""
    bugun = date.today()

    menu = db.query(Menu).filter(Menu.tarih == bugun).first()
    if not menu:
        menu = db.query(Menu).order_by(Menu.tarih.desc()).first()

    if not menu:
        return {"success": False, "message": "Menü bulunamadı."}

    slots = {}
    for slot, attr in [("corba", "corba"), ("ana_yemek", "ana_yemek"),
                        ("yan_yemek", "yan_yemek"), ("tatli", "tatli"), ("salata", "salata")]:
        val = getattr(menu, attr, None)
        if val:
            slots[slot] = val

    return {
        "success": True,
        "tarih": str(menu.tarih),
        "gun": menu.gun,
        "menu": slots,
    }


# ═══════════════════════════════════════════════════════════════════
# WHAT-IF SİMÜLASYON
# ═══════════════════════════════════════════════════════════════════

@router.post("/what-if")
async def what_if_simulation(
    body: WhatIfRequest,
    db: Session = Depends(get_db),
):
    """Mevcut menü vs değişiklik yapılmış menü karşılaştırması."""
    from modules.waste_analyzer import estimate_waste_ratio
    try:
        from modules.menu_optimizer import YEMEK_BAZI_POPULERLIK
    except ImportError:
        YEMEK_BAZI_POPULERLIK = {}

    hedef_tarih = date.fromisoformat(body.tarih) if body.tarih else date.today()
    uretilen = body.uretilen_porsiyon

    # Maliyet haritası
    yemekler_db = db.query(Yemek).all()
    maliyet_map = {}
    for y in yemekler_db:
        if y.birim_maliyet is not None:
            maliyet_map[y.ad.lower()] = y.birim_maliyet

    sonuclar = []

    for deg in body.degisiklikler:
        mevcut = _simulate_yemek(
            db, deg.mevcut_yemek, deg.slot, hedef_tarih, uretilen,
            maliyet_map, YEMEK_BAZI_POPULERLIK, estimate_waste_ratio,
        )
        yeni = _simulate_yemek(
            db, deg.yeni_yemek, deg.slot, hedef_tarih, uretilen,
            maliyet_map, YEMEK_BAZI_POPULERLIK, estimate_waste_ratio,
        )

        fark = {
            "israf_orani": round(yeni["israf_orani"] - mevcut["israf_orani"], 1),
            "israf_porsiyon": round(yeni["israf_porsiyon"] - mevcut["israf_porsiyon"], 0),
            "maliyet_kayip_tl": round(yeni["maliyet_kayip_tl"] - mevcut["maliyet_kayip_tl"], 2),
            "populerlik": round(yeni["populerlik"] - mevcut["populerlik"], 2),
        }

        sonuclar.append({
            "slot": deg.slot,
            "mevcut": mevcut,
            "yeni": yeni,
            "fark": fark,
            "oneri": "degistir" if fark["israf_orani"] < -2 else (
                "dusun" if fark["israf_orani"] < 0 else "degistirme"
            ),
        })

    # Genel toplam
    toplam_mevcut_kayip = sum(s["mevcut"]["maliyet_kayip_tl"] for s in sonuclar)
    toplam_yeni_kayip = sum(s["yeni"]["maliyet_kayip_tl"] for s in sonuclar)
    toplam_tasarruf = round(toplam_mevcut_kayip - toplam_yeni_kayip, 2)

    return {
        "success": True,
        "tarih": str(hedef_tarih),
        "sonuclar": sonuclar,
        "ozet": {
            "toplam_mevcut_kayip_tl": round(toplam_mevcut_kayip, 2),
            "toplam_yeni_kayip_tl": round(toplam_yeni_kayip, 2),
            "toplam_tasarruf_tl": toplam_tasarruf,
            "degisiklik_sayisi": len(sonuclar),
        },
    }


def _simulate_yemek(db, yemek_adi, kategori, tarih, uretilen,
                     maliyet_map, populerlik_map, estimate_fn):
    """Tek bir yemek için israf/maliyet/popülerlik simülasyonu."""

    # Popülerlik
    pop = populerlik_map.get(yemek_adi, 0.5)

    # Ortalama puan
    puan_row = db.query(
        sqla_func.avg(MenuPuanlama.puan).label("ort"),
        sqla_func.count(MenuPuanlama.id).label("sayi"),
    ).filter(
        MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%")
    ).first()

    ort_puan = float(puan_row.ort) if puan_row and puan_row.ort else 3.0
    toplam_oy = int(puan_row.sayi) if puan_row and puan_row.sayi else 0

    # Geçmiş israf ortalaması
    gecmis_israf = db.query(
        sqla_func.avg(UretimLog.israf_orani)
    ).filter(
        UretimLog.yemek_adi.ilike(f"%{yemek_adi}%"),
        UretimLog.israf_orani.isnot(None),
    ).scalar()

    # ML tahmini
    tahmin, kaynak = estimate_fn(
        yemek_adi=yemek_adi,
        kategori=kategori,
        tarih=tarih,
        ortalama_puan=ort_puan,
        toplam_oy=toplam_oy,
        uretilen_porsiyon=uretilen,
        uretim_israf_orani=float(gecmis_israf) if gecmis_israf else None,
        populerlik_skoru=pop,
    )

    israf_orani = float(tahmin) if tahmin is not None else (
        float(gecmis_israf) if gecmis_israf else _fallback_israf(ort_puan)
    )

    israf_porsiyon = round(uretilen * israf_orani / 100, 0)

    # Maliyet
    birim = maliyet_map.get(yemek_adi.lower(), _VARSAYILAN_MALIYET.get(kategori, 20.0))
    maliyet_kayip = israf_porsiyon * birim

    return {
        "yemek_adi": yemek_adi,
        "kategori": kategori,
        "populerlik": round(pop, 2),
        "ort_puan": round(ort_puan, 1),
        "israf_orani": round(israf_orani, 1),
        "israf_porsiyon": israf_porsiyon,
        "birim_maliyet_tl": birim,
        "maliyet_kayip_tl": round(maliyet_kayip, 2),
        "tahmin_kaynagi": kaynak if tahmin is not None else "fallback",
    }


def _fallback_israf(puan: float) -> float:
    """Puan bazlı basit israf tahmini (fallback)."""
    if puan >= 4.5:
        return 8.0
    elif puan >= 4.0:
        return 14.0
    elif puan >= 3.5:
        return 22.0
    elif puan >= 3.0:
        return 30.0
    elif puan >= 2.5:
        return 38.0
    else:
        return 45.0
