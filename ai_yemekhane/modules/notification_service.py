"""
Push Notification Servisi — Expo Push Notifications
════════════════════════════════════════════════════
Mobil uygulama kullanıcılarına günlük menü bildirimi gönderir.

Özellikler:
  - Expo Push Token kayıt/silme
  - Günlük menü bildirimi gönderme
  - Token doğrulama
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

import httpx

from models import SessionLocal, Menu, PushToken

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# TOKEN YÖNETİMİ (DB-Backed — restart'ta kaybolmaz)
# ═══════════════════════════════════════════════════════════════════

def register_token(token: str, platform: Optional[str] = None) -> dict[str, Any]:
    """Expo push token'ı DB'ye kaydeder (idempotent)."""
    if not token or not token.startswith("ExponentPushToken["):
        return {
            "success": False,
            "message": "Geçersiz Expo push token formatı.",
        }

    db = SessionLocal()
    try:
        mevcut = db.query(PushToken).filter(PushToken.token == token).first()
        if mevcut:
            # Zaten kayıtlı → aktif hale getir ve last_seen'i güncelle
            mevcut.aktif = True
            mevcut.last_seen_at = datetime.utcnow()
            if platform and not mevcut.platform:
                mevcut.platform = platform
            db.commit()
            toplam = db.query(PushToken).filter(PushToken.aktif.is_(True)).count()
            return {
                "success": True,
                "message": "Push token güncellendi.",
                "total_tokens": toplam,
            }

        # Yeni kayıt
        yeni = PushToken(token=token, platform=platform, aktif=True)
        db.add(yeni)
        db.commit()
        toplam = db.query(PushToken).filter(PushToken.aktif.is_(True)).count()
        return {
            "success": True,
            "message": "Push token başarıyla kaydedildi.",
            "total_tokens": toplam,
        }
    except Exception as e:
        db.rollback()
        logger.error("[Notification] Token kayıt hatası: %s", e)
        return {"success": False, "message": str(e)}
    finally:
        db.close()


def unregister_token(token: str) -> dict[str, Any]:
    """Expo push token'ı pasifleştirir (soft delete)."""
    db = SessionLocal()
    try:
        mevcut = db.query(PushToken).filter(PushToken.token == token).first()
        if mevcut:
            mevcut.aktif = False
            db.commit()
        return {
            "success": True,
            "message": "Push token silindi.",
        }
    except Exception as e:
        db.rollback()
        logger.error("[Notification] Token silme hatası: %s", e)
        return {"success": False, "message": str(e)}
    finally:
        db.close()


def get_registered_tokens() -> list[str]:
    """Aktif kayıtlı tüm token'ları döndürür."""
    db = SessionLocal()
    try:
        rows = db.query(PushToken.token).filter(PushToken.aktif.is_(True)).all()
        return [r.token for r in rows]
    except Exception as e:
        logger.error("[Notification] Token listesi alma hatası: %s", e)
        return []
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# BİLDİRİM GÖNDERME
# ═══════════════════════════════════════════════════════════════════

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push_notification(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Expo Push Notification API üzerinden bildirim gönderir.

    Args:
        tokens: Expo push token listesi
        title: Bildirim başlığı
        body: Bildirim metni
        data: Opsiyonel ek veri

    Returns:
        dict: Gönderim sonucu
    """
    if not tokens:
        return {"success": False, "message": "Gönderilecek token yok."}

    messages = []
    for token in tokens:
        message = {
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "channelId": "menu-notifications",
        }
        if data:
            message["data"] = data
        messages.append(message)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )

        result = response.json()
        return {
            "success": True,
            "sent_count": len(messages),
            "response": result,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Bildirim gönderme hatası: {str(e)}",
        }


async def send_daily_menu_notification(db=None) -> dict[str, Any]:
    """
    Bugünkü menüyü tüm kayıtlı cihazlara push notification olarak gönderir.

    Returns:
        dict: Gönderim sonucu
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        menu = db.query(Menu).filter(Menu.tarih == bugun).first()

        if not menu:
            return {
                "success": False,
                "message": f"Bugün ({bugun}) için menü bulunamadı.",
            }

        # Bildirim içeriği oluştur
        gun_adi = menu.gun or bugun.strftime("%A")
        body_parts = []
        if menu.corba:
            body_parts.append(f"🍲 {menu.corba}")
        if menu.ana_yemek:
            body_parts.append(f"🥩 {menu.ana_yemek}")
        if menu.yan_yemek:
            body_parts.append(f"🍚 {menu.yan_yemek}")
        if menu.tatli:
            body_parts.append(f"🍮 {menu.tatli}")

        body = " • ".join(body_parts) if body_parts else "Menü bilgisi mevcut."

        tokens = get_registered_tokens()

        if not tokens:
            return {
                "success": True,
                "message": "Menü hazır ancak kayıtlı cihaz yok.",
                "menu": {
                    "gun": gun_adi,
                    "corba": menu.corba,
                    "ana_yemek": menu.ana_yemek,
                    "yan_yemek": menu.yan_yemek,
                    "tatli": menu.tatli,
                    "salata": menu.salata,
                },
            }

        result = await send_push_notification(
            tokens=tokens,
            title=f"🍽️ {gun_adi} Menüsü",
            body=body,
            data={
                "type": "daily_menu",
                "tarih": str(bugun),
                "gun": gun_adi,
            },
        )

        result["menu"] = {
            "gun": gun_adi,
            "corba": menu.corba,
            "ana_yemek": menu.ana_yemek,
            "yan_yemek": menu.yan_yemek,
            "tatli": menu.tatli,
            "salata": menu.salata,
        }

        return result

    finally:
        if close_db:
            db.close()


async def send_waste_alert_notification(db=None, esik: float = 40.0) -> dict[str, Any]:
    """
    İsraf oranı eşiği aşan yemekler için uyarı bildirimi gönderir.

    Args:
        db: SQLAlchemy session
        esik: İsraf oranı eşiği (%). Varsayılan %40.
    """
    from sqlalchemy import func as sqla_func
    from models import UretimLog

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()

        # Son 7 günde eşiği aşan yemekler
        yuksek_israf = (
            db.query(
                UretimLog.yemek_adi,
                sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
            )
            .filter(
                UretimLog.tarih >= bugun - __import__("datetime").timedelta(days=7),
            )
            .group_by(UretimLog.yemek_adi)
            .having(sqla_func.avg(UretimLog.israf_orani) >= esik)
            .order_by(sqla_func.avg(UretimLog.israf_orani).desc())
            .limit(5)
            .all()
        )

        if not yuksek_israf:
            return {
                "success": True,
                "message": f"Son 7 günde %{esik} üzerinde israf oranı olan yemek yok.",
                "uyari_sayisi": 0,
            }

        # Bildirim metni oluştur
        yemek_listesi = ", ".join(
            f"{y.yemek_adi} (%{y.ort_israf:.0f})" for y in yuksek_israf
        )
        body = f"⚠️ Yüksek israf: {yemek_listesi}"

        tokens = get_registered_tokens()
        if not tokens:
            return {
                "success": True,
                "message": "Uyarı hazır ancak kayıtlı cihaz yok.",
                "uyari_yemekler": [
                    {"yemek": y.yemek_adi, "israf_orani": round(float(y.ort_israf), 1)}
                    for y in yuksek_israf
                ],
            }

        result = await send_push_notification(
            tokens=tokens,
            title="🚨 İsraf Uyarısı",
            body=body,
            data={"type": "waste_alert"},
        )
        result["uyari_yemekler"] = [
            {"yemek": y.yemek_adi, "israf_orani": round(float(y.ort_israf), 1)}
            for y in yuksek_israf
        ]
        return result

    finally:
        if close_db:
            db.close()


async def send_popular_meal_notification(db=None) -> dict[str, Any]:
    """
    Bu haftanın en beğenilen yemeklerini bildirim olarak gönderir.
    """
    from sqlalchemy import func as sqla_func

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        hafta_basi = bugun - __import__("datetime").timedelta(days=7)

        # En beğenilen 3 yemek
        from models import MenuPuanlama
        en_iyi = (
            db.query(
                MenuPuanlama.yemek_adi,
                sqla_func.avg(MenuPuanlama.puan).label("ort_puan"),
                sqla_func.count(MenuPuanlama.id).label("oy"),
            )
            .filter(MenuPuanlama.tarih >= hafta_basi)
            .group_by(MenuPuanlama.yemek_adi)
            .having(sqla_func.count(MenuPuanlama.id) >= 2)
            .order_by(sqla_func.avg(MenuPuanlama.puan).desc())
            .limit(3)
            .all()
        )

        if not en_iyi:
            return {"success": True, "message": "Yeterli puanlama verisi yok."}

        body_parts = [f"⭐ {y.yemek_adi} ({y.ort_puan:.1f}/5)" for y in en_iyi]
        body = " | ".join(body_parts)

        tokens = get_registered_tokens()
        if not tokens:
            return {
                "success": True,
                "message": "Sonuçlar hazır ancak kayıtlı cihaz yok.",
                "en_iyi_yemekler": [
                    {"yemek": y.yemek_adi, "puan": round(float(y.ort_puan), 1)}
                    for y in en_iyi
                ],
            }

        result = await send_push_notification(
            tokens=tokens,
            title="🏆 Haftanın En Beğenilen Yemekleri",
            body=body,
            data={"type": "popular_meals"},
        )
        result["en_iyi_yemekler"] = [
            {"yemek": y.yemek_adi, "puan": round(float(y.ort_puan), 1)}
            for y in en_iyi
        ]
        return result

    finally:
        if close_db:
            db.close()


async def send_custom_notification(
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Admin tarafından özel bildirim gönderir.

    Args:
        title: Bildirim başlığı
        body: Bildirim metni
        data: Opsiyonel ek veri
    """
    tokens = get_registered_tokens()
    if not tokens:
        return {"success": False, "message": "Kayıtlı cihaz yok."}

    extra = data or {}
    extra["type"] = "custom_admin"

    return await send_push_notification(
        tokens=tokens,
        title=title,
        body=body,
        data=extra,
    )

