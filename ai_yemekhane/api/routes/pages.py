"""
Sayfa route'ları — Öğrenci (herkese açık) ve Admin (şifre korumalı) HTML sayfaları.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config import active_config
from api.dependencies import templates, _make_admin_token, _is_admin

router = APIRouter(tags=["pages"])


# ═══════════════════════════════════════════════════════════════════
# SAYFA ROUTE'LARI — ÖĞRENCİ (HERKESE AÇIK)
# ═══════════════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse)
async def anasayfa(request: Request):
    """Ana sayfa — Projenin landing page'i."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chatbot sayfası."""
    return templates.TemplateResponse(request, "chat.html")


@router.get("/rate", response_class=HTMLResponse)
async def rate_page(request: Request):
    """Anonim yemek puanlama sayfası."""
    return templates.TemplateResponse(request, "rate.html")


@router.get("/today-menu", response_class=HTMLResponse)
async def today_menu_page(request: Request):
    """Öğrenci günün menüsü sayfası (herkese açık)."""
    return templates.TemplateResponse(request, "today_menu.html")


# ═══════════════════════════════════════════════════════════════════
# SAYFA ROUTE'LARI — ADMİN (ŞİFRE KORUMALI)
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin giriş sayfası."""
    # Zaten giriş yapmışsa dashboard'a yönlendir
    if _is_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@router.post("/admin/login")
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
            request,
            "admin_login.html",
            {"error": "Yanlış şifre! Lütfen tekrar deneyin."},
            status_code=401,
        )


@router.get("/admin/logout")
async def admin_logout():
    """Admin oturumunu sonlandırır."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("admin_token")
    return response


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Yönetici dashboard sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "admin.html")


@router.get("/menu", response_class=HTMLResponse)
async def menu_page(request: Request):
    """Menü yönetimi sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "menu.html")


@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    """Raporlar sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "report.html")


@router.get("/production", response_class=HTMLResponse)
async def production_entry_page(request: Request):
    """Günlük üretim & tüketim veri girişi sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "production_entry.html")


@router.get("/production-plan", response_class=HTMLResponse)
async def production_plan_page(request: Request):
    """Üretim planlama sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "production_plan.html")


@router.get("/feedback-analysis", response_class=HTMLResponse)
async def feedback_analysis_page(request: Request):
    """Geri bildirim analizi sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "feedback_analysis.html")


@router.get("/vote", response_class=HTMLResponse)
async def vote_page(request: Request):
    """Menü oylama sayfası (herkese açık, anonim)."""
    return templates.TemplateResponse(request, "vote.html")


@router.get("/admin/simulation", response_class=HTMLResponse)
async def simulation_page(request: Request):
    """What-If Simülasyon aracı sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "simulation.html")
