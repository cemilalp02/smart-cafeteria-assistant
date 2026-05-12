"""
Auto Trainer testleri — model sağlığı, eşik kontrolü, retrain flow.
Gerçek model eğitimi yapmaz (mock fonksiyonlarla flow doğrulanır).
"""

import os
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from models import UretimLog, MenuPuanlama
from modules import auto_trainer
from modules.auto_trainer import (
    _count_new_records,
    _total_records,
    _model_exists,
    _load_state,
    _save_state,
    check_and_retrain,
    get_model_health,
    RETRAIN_THRESHOLDS,
)


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """auto_trainer state dosyasını test boyunca tmp_path'e yönlendirir."""
    fake_state = tmp_path / "auto_trainer_state.json"
    monkeypatch.setattr(auto_trainer, "TRAINER_STATE_FILE", str(fake_state))
    yield fake_state


class TestCountRecords:
    """Yeni kayıt sayma mantığı."""

    def test_count_waste_empty_db(self, test_db):
        assert _count_new_records(test_db, "waste", None) == 0

    def test_count_waste_with_data(self, seeded_db):
        sayi = _count_new_records(seeded_db, "waste", None)
        assert sayi > 0

    def test_count_sentiment_only_with_yorum(self, test_db):
        """yorum=None veya boş olanlar sentiment için sayılmaz."""
        test_db.add(MenuPuanlama(
            tarih=date.today(),
            yemek_adi="X", kategori="corba",
            puan=4, yorum=None,
        ))
        test_db.add(MenuPuanlama(
            tarih=date.today(),
            yemek_adi="Y", kategori="corba",
            puan=4, yorum="",
        ))
        test_db.add(MenuPuanlama(
            tarih=date.today(),
            yemek_adi="Z", kategori="corba",
            puan=5, yorum="Çok güzeldi",
        ))
        test_db.commit()
        assert _count_new_records(test_db, "sentiment", None) == 1

    def test_unknown_model_returns_zero(self, test_db):
        assert _count_new_records(test_db, "unknown_xyz", None) == 0

    def test_total_records(self, seeded_db):
        assert _total_records(seeded_db, "waste") > 0


class TestGetModelHealth:
    """Model sağlık durumu raporu."""

    def test_empty_db_returns_all_models(self, test_db, isolated_state):
        sonuc = get_model_health(test_db)
        assert sonuc["success"] is True
        assert "waste" in sonuc["models"]
        assert "sentiment" in sonuc["models"]

    def test_model_status_keys(self, test_db, isolated_state):
        sonuc = get_model_health(test_db)
        for mname, info in sonuc["models"].items():
            assert "status" in info
            assert info["status"] in ("missing", "stale", "retrain_needed", "healthy")
            assert "needs_retrain" in info
            assert "exists" in info
            assert "new_records_since" in info


class TestCheckAndRetrain:
    """Retrain karar mantığı (gerçek eğitim mock'lanır)."""

    def test_unknown_model_skipped(self, test_db, isolated_state):
        sonuc = check_and_retrain(test_db, model_name="bogus_model")
        assert sonuc["success"] is True
        assert sonuc["models"]["bogus_model"]["action"] == "skipped"

    def test_insufficient_data_skips(self, test_db, isolated_state):
        """Eşik altı yeni veride retrain atlanır."""
        # Tek bir kayıt → waste eşiği 20, atlanmalı
        test_db.add(UretimLog(
            tarih=date.today(),
            yemek_adi="X", kategori="corba",
            uretilen_porsiyon=100, kalan_porsiyon=10,
            tuketim_orani=90, israf_orani=10,
        ))
        test_db.commit()

        sonuc = check_and_retrain(test_db, model_name="waste")
        assert sonuc["models"]["waste"]["action"] == "skipped"
        assert "yetersiz" in sonuc["models"]["waste"]["reason"].lower()

    def test_force_triggers_training(self, test_db, isolated_state):
        """force=True ile eşik atlanır ve eğitim çağrılır (mock)."""
        with patch.dict(
            auto_trainer._TRAIN_FN,
            {"waste": lambda db: {"success": True, "samples": 10, "rmse": 5.0}},
        ), patch("modules.auto_trainer._backup_model", return_value=None), \
           patch("modules.auto_trainer._rollback_model"):
            sonuc = check_and_retrain(test_db, model_name="waste", force=True)

        assert sonuc["models"]["waste"]["action"] == "retrained"
        assert sonuc["models"]["waste"]["train_result"]["success"] is True

    def test_failed_training_rollback(self, test_db, isolated_state):
        """Eğitim başarısız olursa rollback action'ı dönmeli."""
        with patch.dict(
            auto_trainer._TRAIN_FN,
            {"waste": lambda db: {"success": False, "error": "test"}},
        ), patch("modules.auto_trainer._backup_model", return_value="/fake/path"), \
           patch("modules.auto_trainer._rollback_model") as mock_rb:
            sonuc = check_and_retrain(test_db, model_name="waste", force=True)

        assert sonuc["models"]["waste"]["action"] == "failed_rollback"
        mock_rb.assert_called_once()

    def test_exception_in_training_caught(self, test_db, isolated_state):
        """Eğitim exception fırlatırsa error_rollback action'ı dönmeli."""
        def raise_fn(db):
            raise RuntimeError("boom")

        with patch.dict(
            auto_trainer._TRAIN_FN,
            {"waste": raise_fn},
        ), patch("modules.auto_trainer._backup_model", return_value="/fake/path"), \
           patch("modules.auto_trainer._rollback_model"):
            sonuc = check_and_retrain(test_db, model_name="waste", force=True)

        assert sonuc["models"]["waste"]["action"] == "error_rollback"
        assert "boom" in sonuc["models"]["waste"]["error"]


class TestStateManagement:
    """State dosyası okuma/yazma."""

    def test_load_state_missing_file(self, isolated_state):
        """Dosya yoksa boş dict döner."""
        state = _load_state()
        assert isinstance(state, dict)

    def test_save_and_load_roundtrip(self, isolated_state):
        """Yazılan state geri okunabilir."""
        sample = {"waste": {"last_trained_at": "2025-01-01T00:00:00", "records": 100}}
        _save_state(sample)
        loaded = _load_state()
        assert loaded["waste"]["records"] == 100
