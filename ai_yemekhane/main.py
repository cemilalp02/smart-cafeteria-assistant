"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - FastAPI Backend
═══════════════════════════════════════════════════════════════
Ana uygulama dosyası. Tüm API endpoint'lerini ve template
route'larını içerir.
"""

import os
import shutil
from datetime import date, datetime

from fastapi import FastAPI, File, UploadFile, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import active_config
from models import (
    init_db,
    get_db,
    Yemek,
    Menu,
    Kullanici,
    KullaniciYemekLog,
)
from modules.menu_optimizer import generate_weekly_menu
from modules.food_recognizer import load_model, analyze_food_photo
from modules.chatbot import init_chatbot, get_response, get_meal_recommendation

# ─── Uygulama Başlatma ────────────────────────────────────────────
app = FastAPI(
    title="AI Akıllı Yemekhane Asistan Sistemi",
    description="Menü optimizasyonu, yemek tanıma ve chatbot asistan",
    version="1.0.0",
)

# Statik dosyalar ve template'ler
os.makedirs("static/css", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Veritabanını başlat
init_db()

# Modülleri başlat (lazy loading)
food_model = None
chatbot_model = None


def get_food_model():
    global food_model
    if food_model is None:
        food_model = load_model()
    return food_model


def get_chatbot_model():
    global chatbot_model
    if chatbot_model is None:
        chatbot_model = init_chatbot()
    return chatbot_model


# ─── Pydantic Şemaları ────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    kullanici_id: int | None = None


class MenuPredictRequest(BaseModel):
    baslangic_tarihi: str | None = None


# ═══════════════════════════════════════════════════════════════════
# SAYFA ROUTE'LARI
# ═══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def anasayfa(request: Request):
    """Ana sayfa — Projenin landing page'i."""
    return templates.TemplateResponse("index.html", {"request": request})


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
    Yemek popülerlik skorlarını ve besin dengesini dikkate alır.
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
                    "message": "Veritabanında yemek bulunamadı. Önce seed_data.py çalıştırın.",
                },
            )

        # Menü oluştur
        baslangic = None
        if request_body.baslangic_tarihi:
            baslangic = date.fromisoformat(request_body.baslangic_tarihi)

        haftalik_menu = generate_weekly_menu(yemek_listesi, baslangic)

        return {
            "success": True,
            "message": "Haftalık menü önerisi oluşturuldu.",
            "data": haftalik_menu,
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

        # Yemek tanıma
        model = get_food_model()
        sonuc = analyze_food_photo(model, dosya_yolu, db)

        return {
            "success": True,
            "message": "Yemek tanıma tamamlandı.",
            "dosya": dosya_adi,
            "data": sonuc,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
