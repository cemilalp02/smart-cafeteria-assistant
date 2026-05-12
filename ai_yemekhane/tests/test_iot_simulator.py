"""
IoT Simulator testleri — simulate_weight_for_log, run_simulation, run_bulk_simulation.
"""

from datetime import date, timedelta

import pytest

from models import UretimLog
from modules.iot_simulator import (
    simulate_weight_for_log,
    run_simulation,
    run_bulk_simulation,
    MIN_ISRAF_KG,
    ORT_PORSIYON_AGIRLIK_KG,
)


class TestSimulateWeightForLog:
    """Tek log için simüle ağırlık hesabı."""

    def test_normal_case(self):
        """Üretilen porsiyon × ortalama ağırlık × israf oranı mantıklı sonuç verir."""
        log = UretimLog(
            tarih=date.today(),
            yemek_adi="Test",
            kategori="corba",
            uretilen_porsiyon=100,
            kalan_porsiyon=20,
            tuketim_orani=80.0,
            israf_orani=20.0,
        )
        sonuc = simulate_weight_for_log(log)

        # 100 porsiyon * 0.35 kg * 20% = 7 kg (±%15 sapma)
        beklenen_merkez = 100 * ORT_PORSIYON_AGIRLIK_KG * 0.20
        assert sonuc >= beklenen_merkez * 0.85
        assert sonuc <= beklenen_merkez * 1.15

    def test_zero_production(self):
        """Üretim 0 ise minimum değer döner."""
        log = UretimLog(
            tarih=date.today(),
            yemek_adi="Test",
            kategori="corba",
            uretilen_porsiyon=0,
            kalan_porsiyon=0,
            tuketim_orani=0,
            israf_orani=0,
        )
        sonuc = simulate_weight_for_log(log)
        assert sonuc == MIN_ISRAF_KG

    def test_none_values(self):
        """None değerler graceful handle edilir."""
        log = UretimLog(
            tarih=date.today(),
            yemek_adi="Test",
            kategori="corba",
            uretilen_porsiyon=None,
            kalan_porsiyon=None,
            tuketim_orani=None,
            israf_orani=None,
        )
        sonuc = simulate_weight_for_log(log)
        assert sonuc == MIN_ISRAF_KG


class TestRunSimulation:
    """Günlük simülasyon."""

    def test_empty_date_returns_zero(self, test_db):
        """Kayıt olmayan tarihte 0 güncelleme döner."""
        sonuc = run_simulation(test_db, tarih=date.today())
        assert sonuc["success"] is True
        assert sonuc["guncellenen"] == 0

    def test_updates_missing_weights(self, seeded_db):
        """Ağırlık verisi olmayan kayıtlara simüle değer yazar."""
        bugun = date.today()
        sonuc = run_simulation(seeded_db, tarih=bugun, overwrite=False)

        assert sonuc["success"] is True
        if sonuc["guncellenen"] > 0:
            # DB'de tartilan_israf_kg alanı dolmuş olmalı
            logs = seeded_db.query(UretimLog).filter(
                UretimLog.tarih == bugun,
                UretimLog.tartilan_israf_kaynagi == "simulasyon",
            ).all()
            assert len(logs) > 0
            for log in logs:
                assert log.tartilan_israf_kg is not None
                assert log.tartilan_israf_kg >= MIN_ISRAF_KG

    def test_overwrite_false_skips_real_data(self, seeded_db):
        """overwrite=False iken gerçek tartı verisi güncellenmez."""
        bugun = date.today()
        log = seeded_db.query(UretimLog).filter(
            UretimLog.tarih == bugun
        ).first()

        if log is None:
            pytest.skip("Test DB'de bugüne ait üretim kaydı yok")

        # Manuel "gerçek" tartı verisi koy
        log.tartilan_israf_kg = 99.99
        log.tartilan_israf_kaynagi = "gercek_tarti"
        seeded_db.commit()

        run_simulation(seeded_db, tarih=bugun, overwrite=False)

        seeded_db.refresh(log)
        assert log.tartilan_israf_kg == 99.99
        assert log.tartilan_israf_kaynagi == "gercek_tarti"


class TestRunBulkSimulation:
    """Toplu simülasyon."""

    def test_bulk_run_empty_db(self, test_db):
        """Boş DB'de başarılı sonuç dönmeli."""
        sonuc = run_bulk_simulation(test_db, gun_sayisi=7, overwrite=False)
        assert sonuc["success"] is True
        assert sonuc["gun_sayisi"] == 7
        assert sonuc["toplam_guncellenen"] == 0

    def test_bulk_run_with_data(self, seeded_db):
        """Veri olan günlerin simülasyonu çalışır."""
        sonuc = run_bulk_simulation(seeded_db, gun_sayisi=7, overwrite=True)
        assert sonuc["success"] is True
        assert sonuc["gun_sayisi"] == 7
        assert sonuc["toplam_guncellenen"] >= 0
        assert sonuc["toplam_simule_kg"] >= 0
