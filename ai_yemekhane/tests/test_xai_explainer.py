"""
XAI Explainer testleri — get_xai_status, get_global_explanation,
get_single_explanation. Çoğunlukla yapısal testler (model olmayabilir).
"""

from datetime import date

import pytest

from modules.xai_explainer import (
    get_xai_status,
    get_global_explanation,
    get_single_explanation,
    FEATURE_LABELS,
    _consolidate_shap_values,
)


class TestGetXaiStatus:
    """XAI status raporu."""

    def test_returns_required_keys(self):
        sonuc = get_xai_status()
        assert "shap_installed" in sonuc
        assert "model_loaded" in sonuc
        assert "feature_count" in sonuc
        assert "has_importance" in sonuc

    def test_feature_count_positive(self):
        sonuc = get_xai_status()
        assert sonuc["feature_count"] > 0


class TestFeatureLabels:
    """Türkçe etiket sözlüğü."""

    def test_labels_not_empty(self):
        assert len(FEATURE_LABELS) > 0

    def test_all_labels_are_strings(self):
        for k, v in FEATURE_LABELS.items():
            assert isinstance(k, str)
            assert isinstance(v, str)


class TestConsolidateShapValues:
    """Pipeline transform sonrası feature isimlerini orijinale toplar."""

    def test_simple_consolidation(self):
        import numpy as np
        shap_vals = np.array([0.1, 0.2, 0.3])
        feature_names = ["feat_a", "feat_b", "feat_c"]
        sonuc = _consolidate_shap_values(shap_vals, feature_names)
        assert isinstance(sonuc, dict)

    def test_one_hot_consolidation(self):
        """One-hot encoded sütunlar orijinal feature'a toplanmalı."""
        import numpy as np
        shap_vals = np.array([0.1, 0.2, 0.3, 0.05])
        feature_names = ["gun_Pazartesi", "gun_Sali", "gun_Carsamba", "kalori"]
        sonuc = _consolidate_shap_values(shap_vals, feature_names)
        # gun_* hepsi birleşmeli (eğer feature WASTE_FEATURE_COLUMNS'ta varsa)
        # En azından bir hata vermeden çalışmalı
        assert isinstance(sonuc, dict)


class TestGetGlobalExplanation:
    """Global SHAP açıklama."""

    def test_returns_dict(self):
        """Model yoksa bile bir dict döner (success False olabilir)."""
        sonuc = get_global_explanation()
        assert isinstance(sonuc, dict)
        assert "success" in sonuc

    def test_model_missing_returns_error(self, monkeypatch):
        """Model bundle yoksa açıkça error."""
        monkeypatch.setattr(
            "modules.xai_explainer.load_waste_model",
            lambda: None,
        )
        sonuc = get_global_explanation()
        assert sonuc["success"] is False
        assert "error" in sonuc

    def test_with_fake_model(self, monkeypatch):
        """Sahte model bundle ile happy path."""
        fake_bundle = {
            "pipeline": None,
            "model_type": "FakeModel",
            "sample_count": 100,
            "trained_at": "2025-01-01T00:00:00",
            "feature_importance": [
                {"feature": "kalori", "importance": 0.5},
                {"feature": "protein", "importance": 0.3},
            ],
        }
        monkeypatch.setattr(
            "modules.xai_explainer.load_waste_model",
            lambda: fake_bundle,
        )
        # SHAP'ı kapat ki gerçek SHAP çalışmasın
        monkeypatch.setattr("modules.xai_explainer._HAS_SHAP", False)

        sonuc = get_global_explanation(max_features=5)
        assert sonuc["success"] is True
        assert sonuc["model_type"] == "FakeModel"
        assert sonuc["sample_count"] == 100
        assert len(sonuc["feature_importance"]) <= 5
        # Etiket eklenmiş olmalı
        assert "label" in sonuc["feature_importance"][0]


class TestGetSingleExplanation:
    """Yemek bazlı tahmin açıklaması."""

    def test_no_model_returns_error(self, monkeypatch):
        monkeypatch.setattr(
            "modules.xai_explainer.load_waste_model",
            lambda: None,
        )
        sonuc = get_single_explanation(
            yemek_adi="Test Yemek",
            kategori="corba",
        )
        assert sonuc["success"] is False

    def test_returns_dict_structure(self):
        """Model olmasa bile başarısız ama dict yapısında dönmeli."""
        sonuc = get_single_explanation(
            yemek_adi="Mercimek Çorbası",
            kategori="corba",
            tarih=date.today(),
        )
        assert isinstance(sonuc, dict)
        assert "success" in sonuc
