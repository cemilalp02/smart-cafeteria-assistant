"""
Push bildirim endpoint'leri — token kayıt/silme, günlük menü,
israf uyarısı, popüler yemekler ve özel bildirim gönderme.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import (
    get_db,
    PushTokenRequest,
    CustomNotificationRequest,
)
from modules.notification_service import (
    register_token,
    unregister_token,
    get_registered_tokens,
    send_daily_menu_notification,
)

router = APIRouter(prefix="/api/v1", tags=["notifications"])


@router.post("/notifications/register")
async def api_register_push_token(req: PushTokenRequest):
    """Mobil cihazdan gelen Expo push token'ı kaydeder."""
    return register_token(req.token)


@router.post("/notifications/unregister")
async def api_unregister_push_token(req: PushTokenRequest):
    """Expo push token'ı siler."""
    return unregister_token(req.token)


@router.post("/notifications/send-daily-menu")
async def api_send_daily_menu_notification(db: Session = Depends(get_db)):
    """Bugünkü menüyü tüm kayıtlı cihazlara push notification olarak gönderir."""
    return await send_daily_menu_notification(db=db)


@router.get("/notifications/status")
async def api_notification_status():
    """Kayıtlı push token sayısını döndürür."""
    tokens = get_registered_tokens()
    return {
        "success": True,
        "registered_devices": len(tokens),
    }


@router.post("/notifications/send-waste-alert")
async def api_send_waste_alert(
    esik: float = Query(default=40.0, ge=10, le=90),
    db: Session = Depends(get_db),
):
    """İsraf oranı eşiği aşan yemekler için uyarı bildirimi gönderir."""
    from modules.notification_service import send_waste_alert_notification
    return await send_waste_alert_notification(db=db, esik=esik)


@router.post("/notifications/send-popular-meals")
async def api_send_popular_meals(db: Session = Depends(get_db)):
    """Haftanın en beğenilen yemeklerini bildirim olarak gönderir."""
    from modules.notification_service import send_popular_meal_notification
    return await send_popular_meal_notification(db=db)


@router.post("/notifications/send-custom")
async def api_send_custom_notification(req: CustomNotificationRequest):
    """Admin tarafından özel bildirim gönderir."""
    from modules.notification_service import send_custom_notification
    return await send_custom_notification(title=req.title, body=req.body)
