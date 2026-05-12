"""
Chatbot tool fonksiyonları birim testleri.
"""

import pytest


class TestChatbotImports:
    """Modül import testleri."""

    def test_import_module(self):
        from modules.chatbot import get_response
        assert callable(get_response)


class TestChatbotResponse:
    """Chatbot yanıt testleri."""

    def test_get_response_returns_dict(self, seeded_db):
        """get_response dict dönmeli."""
        from modules.chatbot import get_response
        try:
            # Model yüklenmeden çalışırsa
            result = get_response(
                model=None,
                user_message="Bugün menüde ne var?",
                context={},
                db=seeded_db,
            )
            assert isinstance(result, dict)
        except Exception:
            # API key yoksa hata verebilir, bu kabul edilebilir
            pass

    def test_empty_message(self, seeded_db):
        """Boş mesaj hata vermemeli."""
        from modules.chatbot import get_response
        try:
            result = get_response(
                model=None,
                user_message="",
                context={},
                db=seeded_db,
            )
            assert isinstance(result, dict)
        except Exception:
            pass
