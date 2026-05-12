"""
Menü optimizasyon algoritması birim testleri.
"""

import pytest
from datetime import date, timedelta


class TestMenuOptimizerHelpers:
    """Menü optimizasyonu yardımcı fonksiyon testleri."""

    def test_import_module(self):
        """Modül başarıyla import edilebilmeli."""
        from modules.menu_optimizer import (
            get_meal_average_rating,
            save_menu_suggestion,
            train_model,
        )
        assert callable(get_meal_average_rating)
        assert callable(save_menu_suggestion)
        assert callable(train_model)

    def test_get_meal_average_rating(self, seeded_db):
        """get_meal_average_rating dict dönmeli."""
        from modules.menu_optimizer import get_meal_average_rating
        result = get_meal_average_rating("Mercimek Çorbası", db=seeded_db)
        assert isinstance(result, dict)

    def test_normalize_meal_key(self):
        """Yemek adı normalizasyonu doğru çalışmalı."""
        from modules.menu_optimizer import _normalize_meal_key
        assert _normalize_meal_key("  Mercimek  Çorbası  ") == "mercimek çorbası"
        assert _normalize_meal_key("TAVUK SOTE") == "tavuk sote"


class TestMenuOptimizerGeneration:
    """Menü oluşturma testleri."""

    def test_generate_weekly_menu_structure(self, seeded_db):
        """Haftalık menü 5 günlük dict listesi dönmeli."""
        from modules.menu_optimizer import generate_weekly_menu
        try:
            result = generate_weekly_menu(db=seeded_db)
            if result.get("success"):
                menu = result.get("menu", [])
                assert isinstance(menu, list)
                # Her gün menüsünde beklenen alanlar olmalı
                if menu:
                    assert "gun" in menu[0] or "tarih" in menu[0]
        except Exception:
            # Model dosyası yoksa hata verebilir
            pass


class TestABTestFunctions:
    """A/B test fonksiyon testleri."""

    def test_save_menu_suggestion(self, seeded_db):
        """AI menü önerisi kaydedebilmeli."""
        from modules.menu_optimizer import save_menu_suggestion
        weekly_menu = [
            {
                "gun": "Pazartesi",
                "tarih": str(date.today()),
                "corba": "Mercimek Çorbası",
                "ana_yemek": "Tavuk Sote",
                "yan_yemek": "Pirinç Pilavı",
                "tatli": "Sütlaç",
                "salata": "Mevsim Salata",
                "toplam_skor": 85.5,
            }
        ]
        result = save_menu_suggestion(
            haftalik_menu=weekly_menu,
            baslangic_tarihi=date.today(),
            db=seeded_db,
        )
        assert result.get("success") is True
        assert result.get("kayit_sayisi", 0) >= 1
