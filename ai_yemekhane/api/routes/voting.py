"""
Menü Oylama Sistemi (3C) — API endpoint'leri.

AI 3 farklı haftalık menü alternatifi üretir; öğrenciler anonim oy verir.
En çok oy alan menü gelecek haftanın menüsü olur.
"""

import json
from datetime import date, timedelta, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from api.dependencies import get_db, _is_admin, Yemek
from models import MenuAlternatif, MenuOylama

router = APIRouter(prefix="/api/v1/voting", tags=["voting"])


# ─── Yardımcılar ─────────────────────────────────────────────────

def _current_vote_week() -> str:
    """Oylamanın hedeflediği haftayı döndürür (gelecek haftanın ISO haftası)."""
    bugun = date.today()
    # Gelecek Pazartesi
    gun_fark = (7 - bugun.weekday()) % 7
    if gun_fark == 0:
        gun_fark = 7
    gelecek_pzt = bugun + timedelta(days=gun_fark)
    iso = gelecek_pzt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_start_date(hafta_str: str) -> date:
    """ISO hafta stringinden Pazartesi tarihini döndürür."""
    return datetime.strptime(hafta_str + "-1", "%G-W%V-%u").date()


# ─── Şemalar ─────────────────────────────────────────────────────

class OyVerRequest(BaseModel):
    hafta: str = Field(..., description="ISO hafta: 2026-W19")
    alternatif: str = Field(..., description="A / B / C")
    anonim_id: str | None = Field(default=None, description="Tarayıcı parmak izi")


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT: Alternatif Üret (Admin)
# ═══════════════════════════════════════════════════════════════════

@router.post("/generate")
async def voting_generate(
    hafta: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Gelecek hafta için 3 menü alternatifi üretir.
    3 farklı ağırlık seti: Dengeli / Popüler / Ekonomik.
    """
    try:
        from modules.menu_optimizer import generate_weekly_menu, calculate_menu_score
        from api.dependencies import get_menu_model

        hedef_hafta = hafta or _current_vote_week()
        baslangic = _week_start_date(hedef_hafta)

        # Mevcut alternatifler varsa sil
        db.query(MenuAlternatif).filter(MenuAlternatif.hafta == hedef_hafta).delete()
        db.query(MenuOylama).filter(MenuOylama.hafta == hedef_hafta).delete()
        db.commit()

        # Yemek listesi
        yemekler = db.query(Yemek).all()
        yemek_list = [
            {
                "ad": y.ad, "kategori": y.kategori,
                "kalori": y.kalori, "protein": y.protein,
                "karbonhidrat": y.karbonhidrat, "yag": y.yag,
            }
            for y in yemekler
        ]

        if not yemek_list:
            return {"success": False, "error": "Veritabanında yemek bulunamadı."}

        model, encoders, feature_cols = get_menu_model()

        # 3 farklı ağırlık seti
        agirliklar = [
            {
                "key": "A", "etiket": "Dengeli",
                "weights": {"populerlik": 0.30, "israf": 0.30, "beslenme": 0.25, "maliyet": 0.15},
            },
            {
                "key": "B", "etiket": "Popüler",
                "weights": {"populerlik": 0.50, "israf": 0.20, "beslenme": 0.15, "maliyet": 0.15},
            },
            {
                "key": "C", "etiket": "Ekonomik",
                "weights": {"populerlik": 0.15, "israf": 0.35, "beslenme": 0.15, "maliyet": 0.35},
            },
        ]

        sonuclar = []
        for ag in agirliklar:
            menu = generate_weekly_menu(
                yemek_listesi=yemek_list,
                baslangic_tarihi=baslangic,
                model=model, encoders=encoders, feature_cols=feature_cols,
                custom_weights=ag["weights"],
            )

            skor = calculate_menu_score(menu)

            # Ortalama beslenme ve maliyet skorları
            ort_kalori = 0
            ort_maliyet = 0
            for gun in menu:
                ort_kalori += gun.get("beslenme", {}).get("toplam_kalori", 0)
                ort_maliyet += gun.get("maliyet", {}).get("tahmini_gunluk_tl", 0)
            gun_sayisi = max(len(menu), 1)

            alt = MenuAlternatif(
                hafta=hedef_hafta,
                alternatif=ag["key"],
                etiket=ag["etiket"],
                menu_json=json.dumps(menu, ensure_ascii=False, default=str),
                skor_israf=round(1 - skor.get("ortalama", 0.5), 3),
                skor_maliyet=round(ort_maliyet / gun_sayisi, 1),
                skor_populerlik=round(skor.get("ortalama", 0), 3),
                skor_beslenme=round(ort_kalori / gun_sayisi, 0),
                oy_sayisi=0,
                aktif=True,
            )
            db.add(alt)
            sonuclar.append(ag["key"])

        db.commit()

        return {
            "success": True,
            "hafta": hedef_hafta,
            "baslangic_tarihi": str(baslangic),
            "alternatifler": sonuclar,
            "mesaj": f"{len(sonuclar)} alternatif menü oluşturuldu.",
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT: Alternatifleri Getir
# ═══════════════════════════════════════════════════════════════════

@router.get("/alternatifler")
async def voting_alternatifler(
    hafta: str | None = None,
    db: Session = Depends(get_db),
):
    """Belirtilen haftanın 3 menü alternatifini döndürür."""
    try:
        hedef_hafta = hafta or _current_vote_week()
        alts = (
            db.query(MenuAlternatif)
            .filter(MenuAlternatif.hafta == hedef_hafta, MenuAlternatif.aktif == True)
            .order_by(MenuAlternatif.alternatif)
            .all()
        )
        toplam_oy = sum(a.oy_sayisi for a in alts)

        return {
            "success": True,
            "hafta": hedef_hafta,
            "baslangic_tarihi": str(_week_start_date(hedef_hafta)),
            "alternatifler": [a.to_dict() for a in alts],
            "toplam_oy": toplam_oy,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT: Oy Ver (Anonim)
# ═══════════════════════════════════════════════════════════════════

@router.post("/oy-ver")
async def voting_oy_ver(
    payload: OyVerRequest,
    db: Session = Depends(get_db),
):
    """Öğrenci oy kullanır. Aynı anonim_id ile aynı hafta tekrar oy verilemez."""
    try:
        hafta = payload.hafta
        alt = payload.alternatif.upper()
        anonim = payload.anonim_id

        if alt not in ("A", "B", "C"):
            return {"success": False, "error": "Geçersiz alternatif. A, B veya C olmalı."}

        # Alternatif var mı?
        menu_alt = db.query(MenuAlternatif).filter(
            MenuAlternatif.hafta == hafta,
            MenuAlternatif.alternatif == alt,
            MenuAlternatif.aktif == True,
        ).first()
        if not menu_alt:
            return {"success": False, "error": "Bu hafta için alternatif bulunamadı."}

        # Mükerrer oy kontrolü
        if anonim:
            mevcut = db.query(MenuOylama).filter(
                MenuOylama.hafta == hafta,
                MenuOylama.anonim_id == anonim,
            ).first()
            if mevcut:
                return {"success": False, "error": "Bu hafta zaten oy kullandınız.", "zaten_oylandi": True}

        # Oy kaydet
        oy = MenuOylama(
            hafta=hafta,
            secilen_alternatif=alt,
            anonim_id=anonim,
        )
        db.add(oy)

        # Oy sayısını güncelle
        menu_alt.oy_sayisi = (menu_alt.oy_sayisi or 0) + 1
        db.commit()

        toplam = sum(
            a.oy_sayisi for a in
            db.query(MenuAlternatif).filter(MenuAlternatif.hafta == hafta).all()
        )

        return {
            "success": True,
            "mesaj": f"Menü {alt} ({menu_alt.etiket}) için oyunuz kaydedildi!",
            "secilen": alt,
            "toplam_oy": toplam,
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT: Sonuçlar
# ═══════════════════════════════════════════════════════════════════

@router.get("/sonuclar")
async def voting_sonuclar(
    hafta: str | None = None,
    db: Session = Depends(get_db),
):
    """Oylama sonuçlarını döndürür: oy dağılımı + kazanan."""
    try:
        hedef_hafta = hafta or _current_vote_week()
        alts = (
            db.query(MenuAlternatif)
            .filter(MenuAlternatif.hafta == hedef_hafta)
            .order_by(MenuAlternatif.alternatif)
            .all()
        )
        if not alts:
            return {"success": False, "error": "Bu hafta için alternatif yok."}

        toplam = sum(a.oy_sayisi for a in alts)
        sonuclar = []
        for a in alts:
            pct = round(a.oy_sayisi / toplam * 100, 1) if toplam > 0 else 0
            sonuclar.append({
                "alternatif": a.alternatif,
                "etiket": a.etiket,
                "oy_sayisi": a.oy_sayisi,
                "oy_yuzdesi": pct,
            })

        # Kazanan
        kazanan = max(alts, key=lambda a: a.oy_sayisi)

        return {
            "success": True,
            "hafta": hedef_hafta,
            "toplam_oy": toplam,
            "sonuclar": sonuclar,
            "kazanan": {
                "alternatif": kazanan.alternatif,
                "etiket": kazanan.etiket,
                "oy_sayisi": kazanan.oy_sayisi,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT: Geçmiş Hafta Sonuçları
# ═══════════════════════════════════════════════════════════════════

@router.get("/gecmis")
async def voting_gecmis(
    limit: int = Query(default=8, ge=1, le=52),
    db: Session = Depends(get_db),
):
    """Geçmiş hafta oylama sonuçlarını döndürür."""
    try:
        haftalar = (
            db.query(MenuAlternatif.hafta)
            .group_by(MenuAlternatif.hafta)
            .order_by(MenuAlternatif.hafta.desc())
            .limit(limit)
            .all()
        )

        gecmis = []
        for (h,) in haftalar:
            alts = db.query(MenuAlternatif).filter(MenuAlternatif.hafta == h).all()
            toplam = sum(a.oy_sayisi for a in alts)
            kazanan = max(alts, key=lambda a: a.oy_sayisi) if alts else None

            gecmis.append({
                "hafta": h,
                "toplam_oy": toplam,
                "kazanan_alternatif": kazanan.alternatif if kazanan else None,
                "kazanan_etiket": kazanan.etiket if kazanan else None,
                "kazanan_oy": kazanan.oy_sayisi if kazanan else 0,
                "detay": [
                    {"alt": a.alternatif, "etiket": a.etiket, "oy": a.oy_sayisi}
                    for a in sorted(alts, key=lambda x: x.alternatif)
                ],
            })

        return {"success": True, "gecmis": gecmis}
    except Exception as e:
        return {"success": False, "error": str(e)}
