"""
Anomaly Detector testleri — z-score, kategori sapması, detect_and_save,
siddet hesaplama, list_anomalies.
"""

from datetime import date, timedelta

import pytest

from models import UretimLog, AnomaliKaydi
from modules.anomaly_detector import (
    _get_siddet,
    _normalize_score,
    detect_zscore_anomalies,
    detect_kategori_sapmasi,
    detect_and_save,
    list_anomalies,
    resolve_anomaly,
    ZSCORE_THRESHOLD,
)


class TestSiddetVeNormalize:
    """Şiddet seviyesi ve skor normalizasyonu."""

    def test_siddet_kritik(self):
        assert _get_siddet(5.0) == "KRITIK"
        assert _get_siddet(4.0) == "KRITIK"

    def test_siddet_yuksek(self):
        assert _get_siddet(3.5) == "YUKSEK"
        assert _get_siddet(3.0) == "YUKSEK"

    def test_siddet_orta(self):
        assert _get_siddet(2.7) == "ORTA"
        assert _get_siddet(2.5) == "ORTA"

    def test_siddet_dusuk(self):
        assert _get_siddet(2.1) == "DUSUK"
        assert _get_siddet(1.5) == "DUSUK"  # Eşik altı da DUSUK

    def test_normalize_range(self):
        """Skor 0-1 aralığında olmalı."""
        assert 0 <= _normalize_score(0) <= 1
        assert 0 <= _normalize_score(2) <= 1
        assert _normalize_score(6) == 1.0
        assert _normalize_score(100) == 1.0  # Max clamp

    def test_normalize_monotonic(self):
        """z arttıkça skor artmalı."""
        assert _normalize_score(2) < _normalize_score(3) < _normalize_score(5)


class TestZScoreAnomali:
    """Z-score anomali tespiti."""

    def test_empty_db_no_anomaly(self, test_db):
        """Boş DB'de anomali çıkmamalı."""
        sonuc = detect_zscore_anomalies(date.today(), test_db)
        assert sonuc == []

    def test_no_history_no_anomaly(self, test_db):
        """Bugün kayıt var ama geçmiş yok → anomali çıkmamalı."""
        bugun = date.today()
        test_db.add(UretimLog(
            tarih=bugun,
            yemek_adi="Test Yemek",
            kategori="corba",
            uretilen_porsiyon=100,
            kalan_porsiyon=10,
            tuketim_orani=90.0,
            israf_orani=10.0,
        ))
        test_db.commit()

        sonuc = detect_zscore_anomalies(bugun, test_db)
        # Geçmiş yok → anomali listesi boş
        assert sonuc == []

    def test_high_spike_detected(self, test_db):
        """Son 30 günde stabil israf, bugün ani yüksek → anomali tespit edilmeli."""
        bugun = date.today()
        yemek = "Stabil Çorba"

        # Son 30 gün: israf_orani 8-12% arası (küçük varyans, std≈1.4)
        for i in range(1, 31):
            val = 8.0 + (i % 5)  # 8,9,10,11,12 döngü
            test_db.add(UretimLog(
                tarih=bugun - timedelta(days=i),
                yemek_adi=yemek,
                kategori="corba",
                uretilen_porsiyon=100,
                kalan_porsiyon=int(val),
                tuketim_orani=100.0 - val,
                israf_orani=val,
            ))

        # Bugün: %70 israf (aşırı sapma)
        test_db.add(UretimLog(
            tarih=bugun,
            yemek_adi=yemek,
            kategori="corba",
            uretilen_porsiyon=100,
            kalan_porsiyon=70,
            tuketim_orani=30.0,
            israf_orani=70.0,
        ))
        test_db.commit()

        sonuc = detect_zscore_anomalies(bugun, test_db, threshold=2.0)
        assert len(sonuc) >= 1
        a = sonuc[0]
        assert a["yemek_adi"] == yemek
        assert a["anomali_tipi"] == "ISRAF_ARTIS"
        assert a["siddet"] in ("KRITIK", "YUKSEK", "ORTA", "DUSUK")
        assert a["z_score"] > 2.0


class TestKategoriSapmasi:
    """Kategori ortalaması sapma tespiti."""

    def test_empty_returns_empty(self, test_db):
        sonuc = detect_kategori_sapmasi(date.today(), test_db)
        assert sonuc == []


class TestDetectAndSave:
    """Anomalileri tespit edip DB'ye kaydeden ana orchestrator."""

    def test_empty_db_zero_saved(self, test_db):
        sonuc = detect_and_save(
            target_date=date.today(),
            db=test_db,
            use_isolation_forest=False,
        )
        assert sonuc["success"] is True
        assert sonuc["tespit_edilen"] >= 0
        assert sonuc["yeni_kaydedilen"] == 0

    def test_detects_and_persists(self, test_db):
        """Gerçek anomali DB'ye kaydediliyor."""
        bugun = date.today()
        yemek = "Aniden Sevilmeyen"

        # Stabil geçmiş (ufak varyans: 4-8%)
        for i in range(1, 31):
            val = 4.0 + (i % 5)
            test_db.add(UretimLog(
                tarih=bugun - timedelta(days=i),
                yemek_adi=yemek,
                kategori="ana_yemek",
                uretilen_porsiyon=100,
                kalan_porsiyon=int(val),
                tuketim_orani=100.0 - val,
                israf_orani=val,
            ))
        # Bugün ani spike
        test_db.add(UretimLog(
            tarih=bugun,
            yemek_adi=yemek,
            kategori="ana_yemek",
            uretilen_porsiyon=100,
            kalan_porsiyon=80,
            tuketim_orani=20.0,
            israf_orani=80.0,
        ))
        test_db.commit()

        sonuc = detect_and_save(
            target_date=bugun,
            db=test_db,
            use_isolation_forest=False,  # Hızlı test için kapalı
        )
        assert sonuc["success"] is True
        assert sonuc["yeni_kaydedilen"] >= 1

        # DB'de kayıt var mı?
        db_kayit = test_db.query(AnomaliKaydi).filter(
            AnomaliKaydi.tarih == bugun,
        ).all()
        assert len(db_kayit) >= 1


class TestListAnomalies:
    """Anomali listesi endpoint mantığı."""

    def test_empty_returns_empty_list(self, test_db):
        sonuc = list_anomalies(db=test_db)
        assert sonuc["success"] is True
        assert sonuc["toplam"] == 0
        assert sonuc["anomaliler"] == []

    def test_siddet_filter(self, test_db):
        """Şiddet filtresi uygulanır."""
        test_db.add(AnomaliKaydi(
            tarih=date.today(),
            yemek_adi="A", kategori="corba",
            anomali_tipi="ISRAF_ARTIS", yontem="zscore",
            skor=0.8, siddet="KRITIK",
            beklenen_deger=10, gerceklesen_deger=70, sapma_yuzdesi=600,
            aciklama="Test",
        ))
        test_db.add(AnomaliKaydi(
            tarih=date.today(),
            yemek_adi="B", kategori="corba",
            anomali_tipi="ISRAF_DUSUS", yontem="zscore",
            skor=0.4, siddet="DUSUK",
            beklenen_deger=30, gerceklesen_deger=5, sapma_yuzdesi=-83,
            aciklama="Test",
        ))
        test_db.commit()

        sonuc = list_anomalies(db=test_db, siddet_filtre="KRITIK")
        assert sonuc["toplam"] == 1
        assert sonuc["anomaliler"][0]["yemek_adi"] == "A"


class TestResolveAnomaly:
    """Anomaliyi çözüldü olarak işaretleme."""

    def test_resolve_marks_as_solved(self, test_db):
        kayit = AnomaliKaydi(
            tarih=date.today(),
            yemek_adi="X", kategori="corba",
            anomali_tipi="ISRAF_ARTIS", yontem="zscore",
            skor=0.7, siddet="YUKSEK",
            beklenen_deger=10, gerceklesen_deger=50, sapma_yuzdesi=400,
            aciklama="Test",
        )
        test_db.add(kayit)
        test_db.commit()
        test_db.refresh(kayit)

        sonuc = resolve_anomaly(
            anomali_id=kayit.id,
            cozum_notu="Düzeltildi",
            db=test_db,
        )
        assert sonuc["success"] is True

        test_db.refresh(kayit)
        assert kayit.cozuldu_mu is True
        assert kayit.cozum_notu == "Düzeltildi"

    def test_resolve_nonexistent_fails(self, test_db):
        sonuc = resolve_anomaly(anomali_id=99999, db=test_db)
        assert sonuc["success"] is False
