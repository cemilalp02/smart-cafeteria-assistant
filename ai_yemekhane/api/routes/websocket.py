"""
WebSocket endpoint'leri — Dashboard için gerçek zamanlı güncelleme.

Desteklenen event türleri:
  - new_rating     : Yeni puanlama geldiğinde
  - waste_alert    : İsraf uyarısı tetiklendiğinde
  - task_update    : Arka plan görevi durumu değiştiğinde
  - menu_update    : Menü güncellendiğinde
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["websocket"])


# ═══════════════════════════════════════════════════════════════════
# CONNECTION MANAGER
# ═══════════════════════════════════════════════════════════════════

class ConnectionManager:
    """Aktif WebSocket bağlantılarını yönetir."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket bağlantı açıldı. Aktif: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket bağlantı kapandı. Aktif: %d", len(self.active_connections))

    async def broadcast(self, event_type: str, data: dict[str, Any]):
        """Tüm bağlı istemcilere event gönderir."""
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }, ensure_ascii=False, default=str)

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


# Global singleton
manager = ConnectionManager()


# ═══════════════════════════════════════════════════════════════════
# BROADCAST HELPER — diğer modüllerden çağrılır
# ═══════════════════════════════════════════════════════════════════

async def broadcast_event(event_type: str, data: dict[str, Any]):
    """
    Herhangi bir modülden WebSocket broadcast tetiklemek için.

    Kullanım:
        from api.routes.websocket import broadcast_event
        await broadcast_event("new_rating", {"yemek": "Mercimek", "puan": 5})
    """
    if manager.client_count > 0:
        await manager.broadcast(event_type, data)


def get_ws_status() -> dict:
    """WebSocket bağlantı durumunu döndürür."""
    return {
        "active_connections": manager.client_count,
    }


# ═══════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """
    Admin dashboard WebSocket bağlantısı.

    Bağlanınca hoş geldin mesajı gönderir.
    İstemci mesaj gönderirse (ping vb.) yanıtlar.
    Sunucu tarafından broadcast edilen event'ler otomatik iletilir.
    """
    await manager.connect(websocket)
    try:
        # Hoş geldin mesajı
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {
                "message": "Dashboard WebSocket bağlantısı kuruldu.",
                "active_clients": manager.client_count,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }, ensure_ascii=False))

        # İstemciden gelen mesajları dinle (keep-alive)
        while True:
            data = await websocket.receive_text()
            # Ping-pong
            if data == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "data": {"active_clients": manager.client_count},
                    "timestamp": datetime.utcnow().isoformat(),
                }))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ═══════════════════════════════════════════════════════════════════
# REST API — WebSocket durumu
# ═══════════════════════════════════════════════════════════════════

@router.get("/ws/status")
async def ws_status():
    """Aktif WebSocket bağlantı sayısını döndürür.

    Tam yol: /api/v1/ws/status (router prefix dahil).
    Eski /api/ws/status istekleri ApiVersionRedirectMiddleware tarafından
    otomatik olarak /api/v1/ws/status'a 307 ile yönlendirilir.
    """
    return {
        "success": True,
        **get_ws_status(),
    }
