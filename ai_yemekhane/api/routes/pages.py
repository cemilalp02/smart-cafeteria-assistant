"""
Sayfa route'ları — Öğrenci (herkese açık) ve Admin (şifre korumalı) HTML sayfaları.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config import active_config
from api.dependencies import templates, _make_admin_token, _is_admin

router = APIRouter(tags=["pages"])


# ═══════════════════════════════════════════════════════════════════
# WEB UYGULAMASI — YALNIZCA YÖNETİCİ ARAYÜZÜ
# ═══════════════════════════════════════════════════════════════════
# Öğrenci sayfaları (Ana Sayfa, Chatbot, Günün Menüsü, Puanlama, Oylama)
# mobil uygulamaya taşındığı için web tarafında yalnızca yetkili paneli sunulur.
# Eski öğrenci URL'lerine gelen istekler yetkili giriş sayfasına yönlendirilir.
# ═══════════════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_redirect(request: Request):
    """Web kök sayfası — yetkili giriş sayfasına yönlendirir.

    Öğrenci işlevselliği mobil uygulamada bulunduğundan, web yalnızca
    yöneticiler için tasarlanmıştır.
    """
    if _is_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    return RedirectResponse(url="/admin/login", status_code=302)


@router.get("/chat", include_in_schema=False)
@router.get("/rate", include_in_schema=False)
@router.get("/today-menu", include_in_schema=False)
@router.get("/vote", include_in_schema=False)
async def deprecated_student_pages():
    """Eski öğrenci sayfası URL'leri — mobil uygulamaya yönlendirir.

    Öğrenci sayfaları (Chatbot, Günün Menüsü, Puanlama, Oylama) mobil
    uygulamaya taşınmıştır. Eski bağlantılarla gelen ziyaretçiler kök
    sayfaya, oradan da yetkili giriş ekranına yönlendirilir.
    """
    return RedirectResponse(url="/", status_code=302)


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


@router.get("/admin/simulation", response_class=HTMLResponse)
async def simulation_page(request: Request):
    """What-If Simülasyon aracı sayfası (şifre korumalı)."""
    if not _is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "simulation.html")
