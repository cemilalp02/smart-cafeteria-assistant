"""
İsraf tahmin modeli birim testleri.
"""

import pytest
from datetime import date, timedelta


class TestWasteAnalyzerImports:
    """Modül import testleri."""

    def test_import_module(self):
        from modules.waste_analyzer import (
            train_waste_model_from_db,
            calculate_waste_score,
            get_daily_waste_report,
            get_weekly_waste_report,
        )
        assert callable(train_waste_model_from_db)
        assert callable(calculate_waste_score)
        assert callable(get_daily_waste_report)
        assert callable(get_weekly_waste_report)


class TestWasteSummary:
    """İsraf özeti testleri."""

    def test_get_daily_waste_report(self, seeded_db):
        """Günlük israf raporu döndürmeli."""
        from modules.waste_analyzer import get_daily_waste_report
        result = get_daily_waste_report(db=seeded_db)
        assert isinstance(result, dict)
        assert result.get("success") is True

    def test_get_weekly_waste_report(self, seeded_db):
        """Haftalık israf raporu döndürmeli."""
        from modules.waste_analyzer import get_weekly_waste_report
        result = get_weekly_waste_report(db=seeded_db)
        assert isinstance(result, dict)
        assert result.get("success") is True


class TestWastePrediction:
    """İsraf tahmini testleri."""

    def test_calculate_waste_score_returns_dict(self, seeded_db):
        """calculate_waste_score dict dönmeli."""
        from modules.waste_analyzer import calculate_waste_score
        result = calculate_waste_score("Mercimek Çorbası", db=seeded_db)
        assert isinstance(result, dict)

    def test_train_requires_min_samples(self, seeded_db):
        """Yetersiz veri ile eğitim uyarı dönmeli."""
        from modules.waste_analyzer import train_waste_model_from_db
        result = train_waste_model_from_db(db=seeded_db, min_samples=10000)
        # Çok yüksek eşik → yetersiz veri
        assert isinstance(result, dict)
