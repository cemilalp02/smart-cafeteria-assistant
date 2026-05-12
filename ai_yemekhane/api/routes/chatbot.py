"""
Chatbot endpoint'i — yemekhane asistan chatbot mesajlaşma.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db, get_chatbot_model, ChatRequest, Menu
from modules.chatbot import get_response

router = APIRouter(prefix="/api/v1", tags=["chatbot"])


@router.post("/chat")
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
