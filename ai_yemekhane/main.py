"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - FastAPI Backend
═══════════════════════════════════════════════════════════════
Ana uygulama dosyası. Modüler router'ları yükler ve uygulamayı başlatır.
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from config import active_config
from models import init_db

# ─── Router import'ları ──────────────────────────────────────────
from api.routes.pages import router as pages_router
from api.routes.menu import router as menu_router
from api.routes.ratings import router as ratings_router
from api.routes.waste import router as waste_router
from api.routes.analytics import router as analytics_router
from api.routes.reports import router as reports_router
from api.routes.production import router as production_router
from api.routes.chatbot import router as chatbot_router
from api.routes.notifications import router as notifications_router
from api.routes.tasks import router as tasks_router
from api.routes.websocket import router as ws_router
from api.routes.experiments import router as experiments_router
from api.routes.auto_trainer import router as auto_trainer_router
from api.routes.model_tracker import router as model_tracker_router
from api.routes.iot import router as iot_router
from api.routes.maliyet import router as maliyet_router
from api.routes.simulation import router as simulation_router
from api.routes.voting import router as voting_router
from api.routes.xai import router as xai_router
from api.routes.anomaly import router as anomaly_router

# ─── Uygulama Başlatma ──────────────────────────────────────────
app = FastAPI(
    title="AI Akıllı Yemekhane Asistan Sistemi",
    description="Menü optimizasyonu, yemek tanıma ve chatbot asistan",
    version="1.0.0",
)

# ─── Geriye Uyumluluk Middleware ─────────────────────────────────
# Eski /api/* isteklerini otomatik olarak /api/v1/* 'e yönlendirir.
# Böylece mobil uygulama ve admin paneli güncellenmeden çalışmaya devam eder.
class ApiVersionRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # /api/ ile başlayıp /api/v1/ ile başlamayan istekleri yönlendir
        # Sayfalar (/), statik dosyalar (/static) ve WebSocket'leri hariç tut
        if (
            path.startswith("/api/")
            and not path.startswith("/api/v1/")
            and not path.startswith("/api/version")
        ):
            new_path = "/api/v1/" + path[len("/api/"):]
            query = str(request.url.query)
            redirect_url = new_path + ("?" + query if query else "")
            return RedirectResponse(url=redirect_url, status_code=307)
        return await call_next(request)

app.add_middleware(ApiVersionRedirectMiddleware)

# ─── CORS Middleware (mobil app ve farklı originlerden erişim) ────
# Güvenlik notu: allow_origins=["*"] ile allow_credentials=True kombinasyonu
# cookie-based auth ile güvensizdir. Origin whitelist .env'den okunur.
_cors_origins_raw = os.getenv("CORS_ORIGINS", "").strip()
if _cors_origins_raw:
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    _cors_credentials = True
elif active_config.DEBUG:
    # Dev modda tüm origin'lere izin ver ama credential'sız
    _cors_origins = ["*"]
    _cors_credentials = False
else:
    # Production'da env yoksa sadece localhost
    _cors_origins = ["http://localhost:3000", "http://localhost:8001"]
    _cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyalar
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Veritabanını başlat
init_db()

# ─── Router'ları Kaydet ──────────────────────────────────────────
app.include_router(pages_router)
app.include_router(menu_router)
app.include_router(ratings_router)
app.include_router(waste_router)
app.include_router(analytics_router)
app.include_router(reports_router)
app.include_router(production_router)
app.include_router(chatbot_router)
app.include_router(notifications_router)
app.include_router(tasks_router)
app.include_router(ws_router)
app.include_router(experiments_router)
app.include_router(auto_trainer_router)
app.include_router(model_tracker_router)
app.include_router(iot_router)
app.include_router(maliyet_router)
app.include_router(simulation_router)
app.include_router(voting_router)
app.include_router(xai_router)
app.include_router(anomaly_router)

# ─── API Versiyonlama ────────────────────────────────────────────
# Mevcut /api/* endpoint'leri = v1.  Gelecekte breaking change olursa
# /api/v2/ prefix'li yeni router'lar eklenir; eski istemciler
# /api/* (v1) kullanmaya devam eder.
@app.get("/api/version", tags=["version"])
async def api_version():
    """Aktif API versiyonunu döndürür."""
    return {
        "success": True,
        "version": "v1",
        "api_prefix": "/api/v1",
        "docs_url": "/docs",
        "backward_compat": "Eski /api/* istekleri otomatik olarak /api/v1/* 'e yönlendirilir.",
        "note": "Gelecekte /api/v2/* ile yeni versiyon sunulabilir.",
    }


# ─── Sunucuyu Başlat ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("[START] AI Akilli Yemekhane Asistan Sistemi baslatiliyor...")
    print(f"   URL: http://localhost:{active_config.PORT}")
    print(f"   Docs: http://localhost:{active_config.PORT}/docs")
    print(f"   Debug: {active_config.DEBUG}")

    uvicorn.run(
        "main:app",
        host=active_config.HOST,
        port=active_config.PORT,
        reload=active_config.DEBUG,
    )
