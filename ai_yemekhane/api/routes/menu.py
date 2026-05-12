"""
Menü CRUD, tahmin, A/B test, optimizasyon ağırlıkları,
besin değeri ve AI menü takibi endpoint'leri.
"""

from datetime import date, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from api.dependencies import (
    get_db, get_menu_model,
    MenuPredictRequest,
    Yemek, Menu, MenuPuanlama, UretimLog,
)
from modules.menu_optimizer import (
    generate_weekly_menu,
    calculate_menu_score,
    save_menu_suggestion,
    compare_ai_vs_actual,
    save_optimization_weights,
    _load_optimization_weights,
    OPTIMIZATION_WEIGHTS,
)

router = APIRouter(prefix="/api/v1", tags=["menu"])


# ──────────────────────────────────────────────────────────────────
# POST /api/predict-menu — Haftalık menü önerisi
# ──────────────────────────────────────────────────────────────────
@router.post("/predict-menu")
async def predict_menu(
    request_body: MenuPredictRequest,
    db: Session = Depends(get_db),
):
    """
    ML tabanlı haftalık menü önerisi oluşturur.
    Eğitilmiş model varsa popülerlik skorlarını kullanır,
    yoksa baz popülerlik değerlerine göre çalışır.
    """
    try:
        # Tüm yemekleri DB'den çek
        yemekler = db.query(Yemek).all()
        yemek_listesi = [y.to_dict() for y in yemekler]

        if not yemek_listesi:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "Veritabanında yemek bulunamadı. Önce scripts/data/seed_data.py veya scripts/data/load_menu_data.py çalıştırın.",
                },
            )

        # Başlangıç tarihi
        baslangic = None
        if request_body.baslangic_tarihi:
            baslangic = date.fromisoformat(request_body.baslangic_tarihi)

        # ML modelini yükle (lazy)
        ml_model, ml_encoders, ml_cols = get_menu_model()

        # Haftalık menü oluştur
        haftalik_menu = generate_weekly_menu(
            yemek_listesi=yemek_listesi,
            baslangic_tarihi=baslangic,
            model=ml_model,
            encoders=ml_encoders,
            feature_cols=ml_cols,
        )

        # Menü skoru hesapla
        skor = calculate_menu_score(haftalik_menu)
        model_durumu = "ML model aktif" if ml_model else "Baz popülerlik (model eğitilmemiş)"

        # ── A/B Test: AI önerisini otomatik kaydet ──
        ab_kayit = None
        if baslangic and haftalik_menu:
            try:
                ab_kayit = save_menu_suggestion(haftalik_menu, baslangic, db=db)
            except Exception:
                pass

        return {
            "success": True,
            "message": f"Haftalık menü önerisi oluşturuldu. [{model_durumu}]",
            "data": haftalik_menu,
            "skor_ozet": skor,
            "ab_test_kayit": ab_kayit,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────
# A/B TEST & OPTİMİZASYON AYARLARI
# ──────────────────────────────────────────────────────────────────
@router.get("/menu/ab-test")
async def menu_ab_test(
    hafta_baslangic: str,
    db: Session = Depends(get_db),
):
    """AI menü önerisi vs gerçek menü karşılaştırma raporu."""
    try:
        tarih = date.fromisoformat(hafta_baslangic)
    except ValueError:
        raise HTTPException(status_code=400, detail="Gecersiz tarih formati. YYYY-MM-DD kullanin.")
    return compare_ai_vs_actual(tarih, db=db)


@router.get("/menu/optimization-weights")
async def get_optimization_weights():
    """Mevcut multi-objective optimizasyon ağırlıklarını döndürür."""
    return {
        "success": True,
        "weights": _load_optimization_weights(),
        "defaults": dict(OPTIMIZATION_WEIGHTS),
    }


@router.post("/menu/optimization-weights")
async def set_optimization_weights_endpoint(weights: dict):
    """
    Multi-objective optimizasyon ağırlıklarını günceller.
    Body: {"populerlik": 0.35, "israf": 0.30, "beslenme": 0.20, "maliyet": 0.15}
    """
    ok = save_optimization_weights(weights)
    if ok:
        return {"success": True, "message": "Agirliklar kaydedildi.", "weights": _load_optimization_weights()}
    raise HTTPException(status_code=400, detail="Gecersiz agirliklar. populerlik, israf, beslenme, maliyet anahtarlari gerekli.")


# ──────────────────────────────────────────────────────────────────
# GET /api/nutrition/{yemek_adi} — Besin değeri getir
# ──────────────────────────────────────────────────────────────────
@router.get("/nutrition/{yemek_adi}")
async def get_nutrition(
    yemek_adi: str,
    db: Session = Depends(get_db),
):
    """Yemek adına göre besin değeri bilgisini döndürür."""
    yemek = (
        db.query(Yemek)
        .filter(Yemek.ad.ilike(f"%{yemek_adi}%"))
        .first()
    )

    if not yemek:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"'{yemek_adi}' adlı yemek bulunamadı.",
            },
        )

    return {
        "success": True,
        "data": yemek.to_dict(),
    }


# ──────────────────────────────────────────────────────────────────
# GET /api/menu/today — Bugünün menüsü
# ──────────────────────────────────────────────────────────────────
@router.get("/menu/today")
async def get_today_menu(db: Session = Depends(get_db)):
    """Bugünün menüsünü döndürür."""
    bugun = date.today()
    menu = db.query(Menu).filter(Menu.tarih == bugun).first()

    if not menu:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"Bugün ({bugun}) için menü bulunamadı.",
                "ipucu": "scripts/data/seed_data.py dosyasını çalıştırarak örnek veri yükleyin.",
            },
        )

    return {
        "success": True,
        "data": menu.to_dict(),
    }


# ──────────────────────────────────────────────────────────────────
# GET /api/ai/menu-tracking — AI menü takibi
# ──────────────────────────────────────────────────────────────────
@router.get("/ai/menu-tracking")
async def ai_menu_tracking(db: Session = Depends(get_db)):
    """
    AI menu onerisi sonuc takibi:
    Gercek menulerin israf oranlarini hesaplar,
    AI onerisindeki yemeklerin israf oranlarini karsilastirir.
    """
    try:
        # Son 4 haftanin menuleri
        baslangic = date.today() - timedelta(days=28)
        menuler = (
            db.query(Menu)
            .filter(Menu.tarih >= baslangic, Menu.tarih <= date.today())
            .order_by(Menu.tarih)
            .all()
        )

        if not menuler:
            return {"success": False, "message": "Menu verisi bulunamadi."}

        # Tum yemeklerin ortalama israf oranlari
        israf_map = {}
        israf_rows = (
            db.query(
                UretimLog.yemek_adi,
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            )
            .group_by(UretimLog.yemek_adi)
            .all()
        )
        for row in israf_rows:
            israf_map[row.yemek_adi] = round(float(row.ort_israf or 0), 1)

        # Tum yemeklerin ortalama puanlari
        puan_rows = (
            db.query(
                MenuPuanlama.yemek_adi,
                sqla_func.avg(MenuPuanlama.puan).label("ort_puan"),
            )
            .group_by(MenuPuanlama.yemek_adi)
            .all()
        )
        puan_map = {}
        for row in puan_rows:
            puan_map[row.yemek_adi] = round(float(row.ort_puan or 0), 2)

        # En populer yemekler (en yuksek puanli) — AI bunlari onerirdi
        en_populer = {}
        for kategori in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
            kat_yemekler = (
                db.query(
                    MenuPuanlama.yemek_adi,
                    sqla_func.avg(MenuPuanlama.puan).label("ort"),
                )
                .filter(MenuPuanlama.kategori == kategori)
                .group_by(MenuPuanlama.yemek_adi)
                .order_by(sqla_func.avg(MenuPuanlama.puan).desc())
                .first()
            )
            if kat_yemekler:
                en_populer[kategori] = kat_yemekler.yemek_adi

        # Haftalik karsilastirma
        hafta_verileri = defaultdict(lambda: {"gercek_israf": [], "ai_israf": [], "gunler": 0})

        for menu in menuler:
            hafta_no = menu.tarih.isocalendar()[1]
            hafta_key = f"Hafta {hafta_no}"
            hafta_verileri[hafta_key]["gunler"] += 1

            # Gercek menunun israf ortalamasini hesapla
            gercek_yemekler = [menu.corba, menu.ana_yemek, menu.yan_yemek, menu.tatli, menu.salata]
            for y in gercek_yemekler:
                if y and y in israf_map:
                    hafta_verileri[hafta_key]["gercek_israf"].append(israf_map[y])

            # AI onerisindeki yemeklerin israf ortalamasini hesapla
            for kat in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
                ai_yemek = en_populer.get(kat)
                if ai_yemek and ai_yemek in israf_map:
                    hafta_verileri[hafta_key]["ai_israf"].append(israf_map[ai_yemek])

        # Ozet hesapla
        haftalik_sonuc = []
        toplam_gercek = 0
        toplam_ai = 0
        sayac = 0

        for hafta, veri in sorted(hafta_verileri.items()):
            g_ort = round(sum(veri["gercek_israf"]) / len(veri["gercek_israf"]), 1) if veri["gercek_israf"] else 0
            a_ort = round(sum(veri["ai_israf"]) / len(veri["ai_israf"]), 1) if veri["ai_israf"] else 0
            fark = round(g_ort - a_ort, 1)

            haftalik_sonuc.append({
                "hafta": hafta,
                "gercek_israf": g_ort,
                "ai_israf": a_ort,
                "fark": fark,
                "iyilestirme": f"%{abs(fark)}" if fark > 0 else "—",
            })
            toplam_gercek += g_ort
            toplam_ai += a_ort
            sayac += 1

        genel_gercek = round(toplam_gercek / sayac, 1) if sayac else 0
        genel_ai = round(toplam_ai / sayac, 1) if sayac else 0
        genel_fark = round(genel_gercek - genel_ai, 1)

        return {
            "success": True,
            "haftalik_karsilastirma": haftalik_sonuc,
            "genel_ozet": {
                "gercek_ort_israf": genel_gercek,
                "ai_ort_israf": genel_ai,
                "potansiyel_iyilestirme": genel_fark,
                "yuzde_iyilestirme": round((genel_fark / genel_gercek) * 100, 1) if genel_gercek > 0 else 0,
            },
            "ai_oneri_menusu": en_populer,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
