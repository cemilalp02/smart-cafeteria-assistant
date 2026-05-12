"""
Experiment Engine testleri — A/B test, t-test, haftalık özet.
"""

from datetime import date, timedelta

import pytest

from models import Menu, MenuOneriLog, UretimLog, MenuPuanlama
from modules.experiment_engine import (
    _ttest,
    run_ab_experiment,
    get_experiment_summary,
)


class TestTTest:
    """İki grup arasında t-test."""

    def test_insufficient_data(self):
        """Az örnekle insufficient_data döner."""
        sonuc = _ttest([1.0], [2.0])
        assert sonuc["test"] == "insufficient_data"
        assert sonuc["significant"] is False

    def test_similar_groups_not_significant(self):
        """Benzer iki grup anlamlı fark vermemeli."""
        a = [10.0, 11.0, 9.5, 10.5, 10.2]
        b = [10.1, 10.8, 9.8, 10.3, 10.0]
        sonuc = _ttest(a, b)
        assert sonuc["significant"] is False

    def test_different_groups_significant(self):
        """Açıkça farklı iki grup anlamlı fark vermeli."""
        a = [80.0, 82.0, 79.0, 81.0, 83.0]
        b = [10.0, 12.0, 9.0, 11.0, 13.0]
        sonuc = _ttest(a, b)
        # scipy varsa significant true olmalı
        if sonuc["test"] == "welch_t_test":
            assert sonuc["significant"] is True
        assert abs(sonuc["diff"]) > 60


class TestRunABExperiment:
    """A/B deneyi ana flow."""

    def test_no_data_returns_failure(self, test_db):
        """Hiç menü yoksa success=False."""
        sonuc = run_ab_experiment(test_db)
        assert sonuc["success"] is False

    def test_only_real_menu_no_ai(self, test_db):
        """Sadece gerçek menü varsa, AI tarafı boş ama success=True."""
        bugun = date.today()
        menu_tarih = bugun - timedelta(days=5)
        test_db.add(Menu(
            tarih=menu_tarih,
            gun="Pazartesi",
            corba="X Çorba", ana_yemek="Y Kebap",
            yan_yemek="Z Pilav", tatli="W Tatlı", salata="V Salata",
        ))
        test_db.commit()

        # Pencereyi tarih etrafına ayarla
        sonuc = run_ab_experiment(
            test_db,
            hafta_baslangic=menu_tarih - timedelta(days=2),
            hafta_sayisi=2,
        )
        assert sonuc["success"] is True
        assert sonuc["grup_a_gercek_menu"]["yemek_sayisi"] >= 1
        assert sonuc["grup_b_ai_oneri"]["yemek_sayisi"] == 0

    def test_both_groups_with_metrics(self, test_db):
        """Her iki grup veri ile A/B sonuç döndürür."""
        bugun = date.today()
        menu_tarih = bugun - timedelta(days=5)

        # Gerçek menü
        test_db.add(Menu(
            tarih=menu_tarih,
            gun="Pazartesi",
            corba="Ezogelin", ana_yemek="Köfte",
            yan_yemek="Pilav", tatli="Baklava", salata="Mevsim",
        ))
        # AI önerisi
        test_db.add(MenuOneriLog(
            hafta_baslangic=bugun - timedelta(days=7),
            tarih=menu_tarih,
            gun="Pazartesi",
            corba="Mercimek", ana_yemek="Tavuk",
            yan_yemek="Bulgur", tatli="Sütlaç", salata="Mevsim",
        ))
        # Israf/puan metrikleri
        for y, kat in [
            ("Ezogelin", "corba"), ("Köfte", "ana_yemek"),
            ("Mercimek", "corba"), ("Tavuk", "ana_yemek"),
        ]:
            test_db.add(UretimLog(
                tarih=menu_tarih,
                yemek_adi=y, kategori=kat,
                uretilen_porsiyon=100, kalan_porsiyon=15,
                tuketim_orani=85.0, israf_orani=15.0,
            ))
            test_db.add(MenuPuanlama(
                tarih=menu_tarih,
                yemek_adi=y, kategori=kat, puan=4,
            ))
        test_db.commit()

        sonuc = run_ab_experiment(
            test_db,
            hafta_baslangic=menu_tarih - timedelta(days=2),
            hafta_sayisi=2,
        )
        assert sonuc["success"] is True
        assert sonuc["grup_a_gercek_menu"]["yemek_sayisi"] >= 1
        assert sonuc["grup_b_ai_oneri"]["yemek_sayisi"] >= 1
        assert "israf_testi" in sonuc
        assert "puan_testi" in sonuc
        assert sonuc["israf_testi"]["kazanan"] in ("ai", "gercek", "esit")


class TestGetExperimentSummary:
    """Haftalık özet."""

    def test_empty_db_returns_empty_list(self, test_db):
        sonuc = get_experiment_summary(test_db, son_hafta=4)
        assert sonuc["success"] is True
        assert sonuc["son_hafta"] == 4
        assert isinstance(sonuc["haftalik_sonuclar"], list)
