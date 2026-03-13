"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - FastAPI Backend
═══════════════════════════════════════════════════════════════
Ana uygulama dosyası. Tüm API endpoint'lerini ve template
route'larını içerir.
"""

import os
import io
import shutil
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
    Kullanici,
    KullaniciYemekLog,
    MenuPuanlama,
    Alert,
)
from modules.menu_optimizer import generate_weekly_menu, load_trained_model, calculate_menu_score
from modules.food_recognizer import (
    load_model, load_ensemble_models,
    analyze_food_photo, analyze_tray_photo,
    recognize_food_ensemble, get_nutrition_info,
)
from modules.chatbot import init_chatbot, get_response, get_meal_recommendation
from modules.waste_analyzer import (
    get_daily_waste_report,
    get_weekly_waste_report,
    get_dish_waste_history,
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
    kullanici_id: int | None = None


class MenuPredictRequest(BaseModel):
    baslangic_tarihi: str | None = None


class LogFoodRequest(BaseModel):
    yemek_adi: str
    kullanici_id: int = 1
    miktar: float = 1.0
    kaynak_tipi: str = "manuel"


class RateMealRequest(BaseModel):
    tarih: str
    yemek_adi: str
    kategori: str
    puan: int = Field(..., ge=1, le=5)
    yorum: str | None = None


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
        {"message": "Bugün öğlen pilav ve tavuk yedim", "kullanici_id": 1}

    Response:
        {
            "success": true,
            "data": {
                "response": "...",
                "suggestions": [...],
                "gunluk_toplam": 430.0
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

        # Kullanıcı ID
        kullanici_id = request_body.kullanici_id or 0

        # Chatbot yanıtı al
        yanit = get_response(
            model=model,
            user_message=request_body.message,
            kullanici_id=kullanici_id,
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


# ──────────────────────────────────────────────────────────────────
# 5) GET /api/report/{kullanici_id} — Günlük/haftalık rapor
# ──────────────────────────────────────────────────────────────────
@app.get("/api/report/{kullanici_id}")
async def get_report(
    kullanici_id: int,
    db: Session = Depends(get_db),
):
    """
    Kullanıcının günlük/haftalık besin değeri raporunu döndürür.
    """
    # Kullanıcı kontrolü
    kullanici = db.query(Kullanici).filter(Kullanici.id == kullanici_id).first()
    if not kullanici:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"ID={kullanici_id} kullanıcı bulunamadı.",
            },
        )

    # Bugünkü loglar
    bugun = date.today()
    loglar = (
        db.query(KullaniciYemekLog)
        .filter(
            KullaniciYemekLog.kullanici_id == kullanici_id,
            KullaniciYemekLog.tarih >= datetime(bugun.year, bugun.month, bugun.day),
        )
        .all()
    )

    # Toplam besin değeri
    toplam_kalori = 0.0
    toplam_protein = 0.0
    toplam_karbonhidrat = 0.0
    toplam_yag = 0.0
    yenen_yemekler = []

    for log in loglar:
        yemek = db.query(Yemek).filter(Yemek.id == log.yemek_id).first()
        if yemek:
            miktar = log.miktar
            toplam_kalori += yemek.kalori * miktar
            toplam_protein += yemek.protein * miktar
            toplam_karbonhidrat += yemek.karbonhidrat * miktar
            toplam_yag += yemek.yag * miktar
            yenen_yemekler.append({
                "yemek": yemek.ad,
                "miktar": miktar,
                "kaynak": log.kaynak_tipi,
                "kalori": yemek.kalori * miktar,
            })

    hedef = kullanici.gunluk_kalori_hedefi
    kalan = hedef - toplam_kalori

    return {
        "success": True,
        "data": {
            "kullanici": kullanici.to_dict(),
            "tarih": str(bugun),
            "gunluk_ozet": {
                "toplam_kalori": round(toplam_kalori, 1),
                "toplam_protein": round(toplam_protein, 1),
                "toplam_karbonhidrat": round(toplam_karbonhidrat, 1),
                "toplam_yag": round(toplam_yag, 1),
                "kalori_hedefi": hedef,
                "kalan_kalori": round(kalan, 1),
                "hedef_yuzdesi": round((toplam_kalori / hedef) * 100, 1) if hedef > 0 else 0,
            },
            "yenen_yemekler": yenen_yemekler,
        },
    }


# ──────────────────────────────────────────────────────────────────
# 6) GET /api/menu/today — Bugünün menüsü
# ──────────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────
# 7) POST /api/log-food — Yemek kaydı ekle
# ──────────────────────────────────────────────────────────────────
@app.post("/api/log-food")
async def log_food(
    request_body: LogFoodRequest,
    db: Session = Depends(get_db),
):
    """
    Kullanıcının yemek loguna yeni bir kayıt ekler.
    Yemek adına göre DB'den eşleşen yemeği bulur.
    """
    yemek = (
        db.query(Yemek)
        .filter(Yemek.ad.ilike(f"%{request_body.yemek_adi}%"))
        .first()
    )

    if not yemek:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"'{request_body.yemek_adi}' adlı yemek veritabanında bulunamadı.",
            },
        )

    yeni_log = KullaniciYemekLog(
        kullanici_id=request_body.kullanici_id,
        yemek_id=yemek.id,
        miktar=request_body.miktar,
        kaynak_tipi=request_body.kaynak_tipi,
    )
    db.add(yeni_log)
    db.commit()
    db.refresh(yeni_log)

    return {
        "success": True,
        "message": f"'{yemek.ad}' yemek logunuza eklendi.",
        "data": yeni_log.to_dict(),
    }


# ──────────────────────────────────────────────────────────────────
# 8) POST /api/rate-meal — Anonim yemek puanlama
# ──────────────────────────────────────────────────────────────────
@app.post("/api/rate-meal")
async def rate_meal(
    request_body: RateMealRequest,
    db: Session = Depends(get_db),
):
    """
    Anonim olarak yemek puanı kaydeder.
    Giriş veya kullanıcı ID gerektirmez.
    """
    gecerli_kategoriler = ["corba", "ana_yemek", "pilav", "tatli", "salata"]
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

    yeni_puan = MenuPuanlama(
        tarih=tarih,
        yemek_adi=request_body.yemek_adi,
        kategori=request_body.kategori,
        puan=request_body.puan,
        yorum=request_body.yorum,
    )
    db.add(yeni_puan)
    db.commit()
    db.refresh(yeni_puan)

    return {
        "success": True,
        "message": f"'{request_body.yemek_adi}' için {request_body.puan}⭐ puanınız kaydedildi. Teşekkürler!",
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

    data = {}
    for row in sonuclar:
        data[row.yemek_adi] = {
            "kategori": row.kategori,
            "ortalama": round(float(row.ortalama), 1),
            "toplam_oy": row.toplam_oy,
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

    tum_yemekler = [
        {
            "yemek_adi": row.yemek_adi,
            "kategori": row.kategori,
            "ortalama": round(float(row.ortalama), 2),
            "toplam_oy": row.toplam_oy,
        }
        for row in yemek_ort
    ]

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
