"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - FastAPI Backend
═══════════════════════════════════════════════════════════════
Ana uygulama dosyası. Tüm API endpoint'lerini ve template
route'larını içerir.
"""

import os
import io
import shutil
import re
from datetime import date, datetime, timedelta

import hashlib
import hmac

from fastapi import FastAPI, File, UploadFile, Request, Depends, HTTPException, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import active_config
from models import (
    init_db,
    get_db,
    Yemek,
    Menu,
    MenuPuanlama,
    Alert,
    UretimLog,
)
from modules.menu_optimizer import generate_weekly_menu, load_trained_model, calculate_menu_score
from modules.food_recognizer import (
    load_model, load_ensemble_models,
    analyze_food_photo, analyze_tray_photo,
    recognize_food_ensemble, get_nutrition_info,
)
from modules.chatbot import init_chatbot, get_response
from modules.waste_analyzer import (
    get_daily_waste_report,
    get_weekly_waste_report,
    get_dish_waste_history,
    train_waste_model_from_db,
    get_waste_model_status,
)
from modules.trend_analyzer import (
    get_monthly_trends,
    get_seasonal_analysis,
    get_dish_trend,
)
from modules.alert_system import (
    get_active_alerts,
    get_alert_history,
)
from modules.pdf_report import generate_weekly_pdf, generate_monthly_pdf
from modules.predictive_analyzer import (
    predict_next_week_waste,
    predict_dish_risk,
    generate_predictive_alerts,
)
from modules.consumption_tracker import (
    save_production_log,
    save_bulk_production_log,
    get_daily_consumption,
    get_weekly_consumption,
    get_dish_consumption_history,
)
from modules.production_planner import (
    get_dish_recommendation,
    generate_production_plan,
)
from modules.feedback_analyzer import analyze_feedback

# ─── Uygulama Başlatma ────────────────────────────────────────────
app = FastAPI(
    title="AI Akıllı Yemekhane Asistan Sistemi",
    description="Menü optimizasyonu, yemek tanıma ve chatbot asistan",
    version="1.0.0",
)

# Statik dosyalar ve template'ler
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Veritabanını başlat
init_db()

# Modülleri başlat (lazy loading)
food_model = None
food_models_ensemble = None  # Ensemble: [turkish_food_model, food101_model]
chatbot_model = None
menu_ml_model = None
menu_encoders = None
menu_feature_cols = None


def get_food_model():
    """Tek model yükler (geriye uyumluluk)."""
    global food_model
    if food_model is None:
        model_path = getattr(active_config, 'YOLO_MODEL_PATH', None)
        food_model = load_model(model_path)
    return food_model


def get_food_models_ensemble():
    """Her iki modeli de yükler (Turkish Food + Food101)."""
    global food_models_ensemble
    if food_models_ensemble is None:
        food_models_ensemble = load_ensemble_models()
    return food_models_ensemble


def get_chatbot_model():
    global chatbot_model
    if chatbot_model is None:
        chatbot_model = init_chatbot()
    return chatbot_model


def get_menu_model():
    global menu_ml_model, menu_encoders, menu_feature_cols
    if menu_ml_model is None:
        menu_ml_model, menu_encoders, menu_feature_cols = load_trained_model()
    return menu_ml_model, menu_encoders, menu_feature_cols


# ─── Pydantic Şemaları ────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


class MenuPredictRequest(BaseModel):
    baslangic_tarihi: str | None = None


class RateMealRequest(BaseModel):
    tarih: str
    yemek_adi: str
    kategori: str
    puan: int = Field(..., ge=1, le=5)
    yorum: str | None = None


class WasteModelTrainRequest(BaseModel):
    min_samples: int = Field(default=8, ge=4, le=10000)


def _canonicalize_meal_name(name: str) -> str:
    """Yemek adını standart forma çevirir: trim + tek boşluk + title-case."""
    normalized = re.sub(r"\s+", " ", (name or "").strip())
    if not normalized:
        return ""
    return normalized.title()


def _meal_group_key(name: str) -> str:
    """Case-insensitive ve boşluk normalize edilmiş grup anahtarı üretir."""
    normalized = re.sub(r"\s+", " ", (name or "").strip())
    return normalized.casefold()


def _merge_meal_rating_aggregates(rows):
    """
    SQL'den gelen satırları (yemek_adi, kategori, ortalama, toplam_oy)
    yemek adı normalizasyonu ile birleştirir.
    """
    merged = {}

    for row in rows:
        canonical_name = _canonicalize_meal_name(row.yemek_adi)
        key = _meal_group_key(canonical_name)

        if key not in merged:
            merged[key] = {
                "yemek_adi": canonical_name,
                "toplam_oy": 0,
                "puan_toplami": 0.0,
                "kategori_oylari": {},
            }

        oy_sayisi = int(row.toplam_oy or 0)
        merged[key]["toplam_oy"] += oy_sayisi
        merged[key]["puan_toplami"] += float(row.ortalama or 0) * oy_sayisi
        merged[key]["kategori_oylari"][row.kategori] = (
            merged[key]["kategori_oylari"].get(row.kategori, 0) + oy_sayisi
        )

    result = []
    for item in merged.values():
        toplam_oy = item["toplam_oy"]
        ortalama = (item["puan_toplami"] / toplam_oy) if toplam_oy else 0.0

        kategori = "diger"
        if item["kategori_oylari"]:
            kategori_adaylari = set(item["kategori_oylari"].keys())
            if "icecek" in kategori_adaylari and kategori_adaylari.issubset({"salata", "icecek"}):
                kategori = "icecek"
            else:
                kategori = sorted(
                    item["kategori_oylari"].items(),
                    key=lambda x: (x[1], x[0] == "icecek"),
                    reverse=True,
                )[0][0]

        result.append(
            {
                "yemek_adi": item["yemek_adi"],
                "kategori": kategori,
                "ortalama": ortalama,
                "toplam_oy": toplam_oy,
            }
        )

    return result


# ═══════════════════════════════════════════════════════════════════
# ADMIN AUTH YARDIMCILARI
# ═══════════════════════════════════════════════════════════════════

def _make_admin_token() -> str:
    """Admin oturumu için imzalı token oluşturur."""
    secret = active_config.SECRET_KEY
    return hmac.new(secret.encode(), b"admin_session", hashlib.sha256).hexdigest()


def _is_admin(request: Request) -> bool:
    """İstekte geçerli admin cookie'si var mı kontrol eder."""
    token = request.cookies.get("admin_token")
    return token == _make_admin_token()


# ═══════════════════════════════════════════════════════════════════
# SAYFA ROUTE'LARI — ÖĞRENCİ (HERKESE AÇIK)
# ═══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def anasayfa(request: Request):
    """Ana sayfa — Projenin landing page'i."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/recognize", response_class=HTMLResponse)
async def recognize_page(request: Request):
    """Yemek tanıma sayfası."""
    return templates.TemplateResponse("recognize.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chatbot sayfası."""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/rate", response_class=HTMLResponse)
async def rate_page(request: Request):
    """Anonim yemek puanlama sayfası."""
    return templates.TemplateResponse("rate.html", {"request": request})


@app.get("/today-menu", response_class=HTMLResponse)
async def today_menu_page(request: Request):
    """Öğrenci günün menüsü sayfası (herkese açık)."""
    return templates.TemplateResponse("today_menu.html", {"request": request})


# ═══════════════════════════════════════════════════════════════════
# SAYFA ROUTE'LARI — ADMİN (ŞİFRE KORUMALI)
# ═══════════════════════════════════════════════════════════════════

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin giriş sayfası."""
    # Zaten giriş yapmışsa dashboard'a yönlendir
    if _is_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})


@app.post("/admin/login")
async def admin_login_submit(request: Request, password: str = Form(...)):
    """Admin şifre kontrolü."""
    if password == active_config.ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=302)
        response.set_cookie(
            key="admin_token",
            value=_make_admin_token(),
            httponly=True,
            max_age=8 * 3600,  # 8 saat
            samesite="lax",
        )
        return response
    else:
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "Yanlış şifre! Lütfen tekrar deneyin."},
            status_code=401,
        )


@app.get("/admin/logout")
async def admin_logout():
    """Admin oturumunu sonlandırır."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("admin_token")
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Yönetici dashboard sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/menu", response_class=HTMLResponse)
async def menu_page(request: Request):
    """Menü yönetimi sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse("menu.html", {"request": request})


@app.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    """Raporlar sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse("report.html", {"request": request})


@app.get("/production", response_class=HTMLResponse)
async def production_entry_page(request: Request):
    """Günlük üretim & tüketim veri girişi sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse("production_entry.html", {"request": request})


@app.get("/production-plan", response_class=HTMLResponse)
async def production_plan_page(request: Request):
    """Üretim planlama sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse("production_plan.html", {"request": request})


@app.get("/feedback-analysis", response_class=HTMLResponse)
async def feedback_analysis_page(request: Request):
    """Geri bildirim analizi sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse("feedback_analysis.html", {"request": request})


# ═══════════════════════════════════════════════════════════════════
# API ENDPOINT'LERİ
# ═══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# 1) POST /api/predict-menu — Haftalık menü önerisi
# ──────────────────────────────────────────────────────────────────
@app.post("/api/predict-menu")
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
                    "message": "Veritabanında yemek bulunamadı. Önce seed_data.py veya scripts/load_menu_data.py çalıştırın.",
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

        return {
            "success": True,
            "message": f"Haftalık menü önerisi oluşturuldu. [{model_durumu}]",
            "data": haftalik_menu,
            "skor_ozet": skor,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────
# 2) POST /api/recognize-food — Fotoğraftan yemek tanıma
# ──────────────────────────────────────────────────────────────────
@app.post("/api/recognize-food")
async def recognize_food_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Yüklenen fotoğraftan yemek tanıma ve besin analizi yapar.

    Response:
        {
            "success": true,
            "dosya": "20260302_192055_pizza.jpg",
            "en_olasi_yemek": {
                "yemek": "Pizza",
                "guven": 0.92,
                "kalori": 266,
                "protein": 11,
                "karbonhidrat": 33,
                "yag": 10
            },
            "taninan_yemekler": [...]
        }
    """
    # Dosya uzantısı kontrolü
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in active_config.ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"Desteklenmeyen dosya formatı: .{ext}. "
                           f"İzin verilenler: {active_config.ALLOWED_EXTENSIONS}",
            },
        )

    try:
        # Dosyayı kaydet
        dosya_adi = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        dosya_yolu = os.path.join(active_config.UPLOAD_FOLDER, dosya_adi)

        with open(dosya_yolu, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Yemek tanıma + besin değeri analizi (tek model)
        model = get_food_model()
        sonuc = analyze_food_photo(model, dosya_yolu, db)

        return {
            "success": True,
            "message": "Yemek tanıma tamamlandı.",
            "dosya": dosya_adi,
            "en_olasi_yemek": sonuc.get("en_olasi_yemek"),
            "taninan_yemekler": sonuc.get("taninan_yemekler", []),
            "porsiyon": sonuc.get("porsiyon"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────
# 2b) POST /api/recognize-tray — Tepsi tanıma (çoklu yemek)
# ──────────────────────────────────────────────────────────────────
@app.post("/api/recognize-tray")
async def recognize_tray_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Tepsi fotoğrafından birden fazla yemeği tanır.
    Fotoğrafı grid'lere bölerek her bölgeden ayrı sınıflandırma yapar.
    """
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in active_config.ALLOWED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"success": False, "message": "Desteklenmeyen format."})

    try:
        dosya_adi = f"tray_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        dosya_yolu = os.path.join(active_config.UPLOAD_FOLDER, dosya_adi)
        with open(dosya_yolu, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        model = get_food_model()
        sonuc = analyze_tray_photo(model, dosya_yolu, db)

        return {
            "success": True,
            "message": f"{sonuc['yemek_sayisi']} yemek tespit edildi.",
            "dosya": dosya_adi,
            "yemek_sayisi": sonuc["yemek_sayisi"],
            "taninan_yemekler": sonuc["taninan_yemekler"],
            "toplam_besin": sonuc["toplam_besin"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────
# PDF RAPOR İNDİRME
# ──────────────────────────────────────────────────────────────────
from fastapi.responses import StreamingResponse

@app.get("/api/report/pdf")
async def download_pdf_report(
    period: str = Query("weekly", description="weekly veya monthly"),
    db: Session = Depends(get_db),
):
    """
    Haftalık veya aylık raporu PDF olarak indirir.
    """
    try:
        if period == "monthly":
            pdf_bytes = generate_monthly_pdf(db)
            filename = f"aylik_rapor_{date.today().strftime('%Y%m%d')}.pdf"
        else:
            pdf_bytes = generate_weekly_pdf(db)
            filename = f"haftalik_rapor_{date.today().strftime('%Y%m%d')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────
# TAHMİNSEL ANALİZ
# ──────────────────────────────────────────────────────────────────
@app.get("/api/predictions/weekly")
async def weekly_prediction(db: Session = Depends(get_db)):
    """Gelecek haftaya ait israf tahmini ve riskli yemekler."""
    try:
        result = predict_next_week_waste(db)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/predictions/dish/{yemek_adi}")
async def dish_prediction(yemek_adi: str, db: Session = Depends(get_db)):
    """Belirli bir yemeğin israf risk tahmini."""
    try:
        result = predict_dish_risk(yemek_adi, db)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/predictions/alerts")
async def predictive_alerts(db: Session = Depends(get_db)):
    """Tahmine dayalı uyarılar."""
    try:
        alerts = generate_predictive_alerts(db)
        return {"success": True, "alerts": alerts, "toplam": len(alerts)}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ──────────────────────────────────────────────────────────────────
# 3) POST /api/chat — Chatbot mesajı gönder
# ──────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat_endpoint(
    request_body: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Yemekhane chatbot'una mesaj gönderir ve yanıt alır.

    Body:
        {"message": "Bugünkü menü ne?"}

    Response:
        {
            "success": true,
            "data": {
                "response": "...",
                "suggestions": [...],
                "gunluk_toplam": 0.0
            }
        }
    """
    try:
        model = get_chatbot_model()

        # Bağlam bilgisi oluştur
        bugun = date.today()
        bugunki_menu = (
            db.query(Menu).filter(Menu.tarih == bugun).first()
        )

        context = {}
        if bugunki_menu:
            context["bugunki_menu"] = bugunki_menu.to_dict()

        # Chatbot yanıtı al
        yanit = get_response(
            model=model,
            user_message=request_body.message,
            context=context,
            db=db,
        )

        return {
            "success": True,
            "data": yanit,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────
# 4) GET /api/nutrition/{yemek_adi} — Besin değeri getir
# ──────────────────────────────────────────────────────────────────
@app.get("/api/nutrition/{yemek_adi}")
async def get_nutrition(
    yemek_adi: str,
    db: Session = Depends(get_db),
):
    """
    Yemek adına göre besin değeri bilgisini döndürür.
    """
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


# ------------------------------------------------------------------
# 5) GET /api/menu/today - Bugunun menusu
# ------------------------------------------------------------------
@app.get("/api/menu/today")
async def get_today_menu(db: Session = Depends(get_db)):
    """
    Bugünün menüsünü döndürür.
    """
    bugun = date.today()
    menu = db.query(Menu).filter(Menu.tarih == bugun).first()

    if not menu:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"Bugün ({bugun}) için menü bulunamadı.",
                "ipucu": "seed_data.py dosyasını çalıştırarak örnek veri yükleyin.",
            },
        )

    return {
        "success": True,
        "data": menu.to_dict(),
    }


# ------------------------------------------------------------------
# 6) POST /api/rate-meal - Anonim yemek puanlama
# ------------------------------------------------------------------
@app.post("/api/rate-meal")
async def rate_meal(
    request_body: RateMealRequest,
    db: Session = Depends(get_db),
):
    """
    Anonim olarak yemek puanı kaydeder.
    Giriş veya kullanıcı ID gerektirmez.
    """
    gecerli_kategoriler = ["corba", "ana_yemek", "pilav", "tatli", "salata", "icecek"]
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
    )
    db.add(yeni_puan)
    db.commit()
    db.refresh(yeni_puan)

    return {
        "success": True,
        "message": f"'{canonical_meal_name}' için {request_body.puan}⭐ puanınız kaydedildi. Teşekkürler!",
        "data": yeni_puan.to_dict(),
    }


# ──────────────────────────────────────────────────────────────────
# 9) GET /api/ratings/today — Bugünün ortalama puanları
# ──────────────────────────────────────────────────────────────────
@app.get("/api/ratings/today")
async def get_today_ratings(db: Session = Depends(get_db)):
    """
    Bugünün menüsündeki yemeklerin anonim ortalama puanlarını döndürür.
    """
    bugun = date.today()

    sonuclar = (
        db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.kategori,
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
        )
        .filter(MenuPuanlama.tarih == bugun)
        .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
        .all()
    )

    birlesik_sonuclar = _merge_meal_rating_aggregates(sonuclar)

    data = {}
    for row in birlesik_sonuclar:
        data[row["yemek_adi"]] = {
            "kategori": row["kategori"],
            "ortalama": round(float(row["ortalama"]), 1),
            "toplam_oy": row["toplam_oy"],
        }

    return {
        "success": True,
        "tarih": str(bugun),
        "data": data,
    }


# ──────────────────────────────────────────────────────────────────
# 10) GET /api/ratings/weekly-report — Haftalık puanlama raporu
# ──────────────────────────────────────────────────────────────────
@app.get("/api/ratings/weekly-report")
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
# 11) GET /api/ratings/history/{yemek_adi} — Yemek puan geçmişi
# ──────────────────────────────────────────────────────────────────
@app.get("/api/ratings/history/{yemek_adi}")
async def get_meal_rating_history(
    yemek_adi: str,
    gun: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Belirli bir yemeğin geçmiş puanlarını ve trendini döndürür.
    """
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


# ═══════════════════════════════════════════════════════════════════
# İSRAF ANALİZİ ENDPOINT'LERİ
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/waste/daily")
async def waste_daily(db: Session = Depends(get_db)):
    """Bugünün tahmini israf raporunu döndürür."""
    return get_daily_waste_report(db=db)


@app.get("/api/waste/weekly")
async def waste_weekly(db: Session = Depends(get_db)):
    """Haftalık israf özetini döndürür."""
    return get_weekly_waste_report(db=db)


@app.get("/api/waste/by-dish/{yemek_adi}")
async def waste_by_dish(
    yemek_adi: str,
    gun: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Belirli bir yemeğin israf geçmişini döndürür."""
    return get_dish_waste_history(yemek_adi, gun=gun, db=db)


@app.get("/api/waste/model-status")
async def waste_model_status(db: Session = Depends(get_db)):
    """Israf ML modelinin dosya/veri durumunu dondurur."""
    return get_waste_model_status(db=db)


@app.post("/api/waste/train-model")
async def waste_train_model(
    request_body: WasteModelTrainRequest,
    db: Session = Depends(get_db),
):
    """
    Gercek uretim + puan sinyali ile israf modelini yeniden egitir.
    Veri yetersizse fallback devam eder.
    """
    return train_waste_model_from_db(db=db, min_samples=request_body.min_samples)


# ═══════════════════════════════════════════════════════════════════
# TREND ANALİZİ ENDPOINT'LERİ
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/trends/monthly")
async def trends_monthly(
    gun: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Aylık trend raporunu döndürür."""
    return get_monthly_trends(gun=gun, db=db)


@app.get("/api/trends/seasonal")
async def trends_seasonal(db: Session = Depends(get_db)):
    """Mevsimsel analizi döndürür."""
    return get_seasonal_analysis(db=db)


@app.get("/api/trends/dish/{yemek_adi}")
async def trends_dish(
    yemek_adi: str,
    gun: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Belirli bir yemeğin uzun vadeli trendini döndürür."""
    return get_dish_trend(yemek_adi, gun=gun, db=db)


# ═══════════════════════════════════════════════════════════════════
# UYARI SİSTEMİ ENDPOINT'LERİ
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/alerts/active")
async def alerts_active(db: Session = Depends(get_db)):
    """Aktif uyarıları döndürür."""
    return get_active_alerts(db=db)


@app.get("/api/alerts/history")
async def alerts_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Geçmiş uyarıları döndürür."""
    return get_alert_history(limit=limit, db=db)


# ═══════════════════════════════════════════════════════════════════
# TÜKETİM TAKİP — MANUEL ÜRETİM VERİ GİRİŞİ
# ═══════════════════════════════════════════════════════════════════

class ProductionLogRequest(BaseModel):
    tarih: str
    yemek_adi: str
    kategori: str
    uretilen: float = Field(..., gt=0)
    kalan: float = Field(..., ge=0)
    notlar: str | None = None


class BulkProductionLogRequest(BaseModel):
    tarih: str
    girisler: list[dict]


@app.post("/api/production-log")
async def add_production_log(
    request_body: ProductionLogRequest,
    db: Session = Depends(get_db),
):
    """Tek bir yemek için üretim/kalan verisi kaydeder."""
    try:
        tarih = date.fromisoformat(request_body.tarih)
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "message": "Geçersiz tarih."})

    result = save_production_log(
        tarih=tarih,
        yemek_adi=request_body.yemek_adi,
        kategori=request_body.kategori,
        uretilen=request_body.uretilen,
        kalan=request_body.kalan,
        notlar=request_body.notlar,
        db=db,
    )
    return result


@app.post("/api/production-log/bulk")
async def add_bulk_production_log(
    request_body: BulkProductionLogRequest,
    db: Session = Depends(get_db),
):
    """Birden fazla yemek için toplu üretim verisi kaydeder."""
    try:
        tarih = date.fromisoformat(request_body.tarih)
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "message": "Geçersiz tarih."})

    result = save_bulk_production_log(tarih=tarih, girisler=request_body.girisler, db=db)
    return result


@app.get("/api/production-log/today")
async def get_today_production(db: Session = Depends(get_db)):
    """Bugün için girilmiş üretim verilerini döndürür."""
    bugun = date.today()
    kayitlar = (
        db.query(UretimLog)
        .filter(UretimLog.tarih == bugun)
        .order_by(UretimLog.kategori)
        .all()
    )
    return {
        "success": True,
        "tarih": str(bugun),
        "kayitlar": [k.to_dict() for k in kayitlar],
    }


@app.get("/api/consumption/daily")
async def consumption_daily(
    tarih: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Günlük tüketim/israf raporu."""
    t = date.fromisoformat(tarih) if tarih else None
    return get_daily_consumption(tarih=t, db=db)


@app.get("/api/consumption/weekly")
async def consumption_weekly(db: Session = Depends(get_db)):
    """Haftalık tüketim özeti."""
    return get_weekly_consumption(db=db)


@app.get("/api/consumption/by-dish/{yemek_adi}")
async def consumption_by_dish(
    yemek_adi: str,
    gun: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Belirli bir yemeğin tüketim geçmişi."""
    return get_dish_consumption_history(yemek_adi, gun=gun, db=db)


# ═══════════════════════════════════════════════════════════════════
# ÜRETİM PLANLAMA
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/production/plan")
async def production_plan(db: Session = Depends(get_db)):
    """Geçmiş verilere dayalı üretim planı önerisi."""
    return generate_production_plan(db=db)


@app.get("/api/production/dish-recommendation/{yemek_adi}")
async def dish_recommendation(
    yemek_adi: str,
    db: Session = Depends(get_db),
):
    """Belirli bir yemek için üretim önerisi."""
    return get_dish_recommendation(yemek_adi, db=db)


# ═══════════════════════════════════════════════════════════════════
# GERİ BİLDİRİM ANALİZİ
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/feedback/analysis")
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


# ─── Sunucuyu Başlat ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("🚀 AI Akıllı Yemekhane Asistan Sistemi başlatılıyor...")
    print(f"   URL: http://localhost:{active_config.PORT}")
    print(f"   Docs: http://localhost:{active_config.PORT}/docs")
    print(f"   Debug: {active_config.DEBUG}")

    uvicorn.run(
        "main:app",
        host=active_config.HOST,
        port=active_config.PORT,
        reload=active_config.DEBUG,
    )
