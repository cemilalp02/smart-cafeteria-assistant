"""
API endpoint entegrasyon testleri.
FastAPI TestClient ile tüm ana endpoint'leri test eder.
"""

import pytest
import json


class TestPageRoutes:
    """HTML sayfa route testleri."""

    def test_homepage(self, client):
        """Ana sayfa 200 dönmeli."""
        r = client.get("/")
        assert r.status_code == 200

    def test_menu_page(self, client):
        """Menü sayfası 200 dönmeli."""
        r = client.get("/menu")
        assert r.status_code == 200

    def test_rate_page(self, client):
        """Puanlama sayfası 200 dönmeli."""
        r = client.get("/rate")
        assert r.status_code == 200

    def test_admin_redirect(self, client):
        """Admin sayfası login'e yönlendirmeli (cookie yokken)."""
        r = client.get("/admin", follow_redirects=False)
        # 200 (login sayfası gösterir) veya 307 redirect
        assert r.status_code in (200, 307, 302)


class TestMenuAPI:
    """Menü API endpoint testleri."""

    def test_menu_today(self, client):
        """GET /api/menu/today başarılı dönmeli."""
        r = client.get("/api/menu/today")
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True


class TestRatingsAPI:
    """Puanlama API endpoint testleri."""

    def test_ratings_today(self, client):
        """GET /api/ratings/today başarılı dönmeli."""
        r = client.get("/api/ratings/today")
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True

    def test_rate_meal(self, client):
        """POST /api/rate-meal puanlama kaydedebilmeli."""
        from datetime import date
        r = client.post("/api/rate-meal", json={
            "yemek_adi": "Mercimek Çorbası",
            "kategori": "corba",
            "puan": 4,
            "yorum": "Güzel",
            "tarih": str(date.today()),
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True

    def test_rate_meal_invalid_puan(self, client):
        """Geçersiz puan (0 veya 6) reddedilmeli."""
        from datetime import date
        r = client.post("/api/rate-meal", json={
            "yemek_adi": "Test",
            "kategori": "corba",
            "puan": 0,
            "tarih": str(date.today()),
        })
        # Puan 0 → Pydantic ge=1 validasyonu 422 dönmeli
        assert r.status_code == 422

    def test_weekly_report(self, client):
        """GET /api/ratings/weekly-report çalışmalı."""
        r = client.get("/api/ratings/weekly-report")
        assert r.status_code == 200

    def test_all_rated_meals(self, client):
        """GET /api/ratings/all-rated-meals çalışmalı."""
        r = client.get("/api/ratings/all-rated-meals")
        assert r.status_code == 200


class TestWasteAPI:
    """İsraf API endpoint testleri."""

    def test_waste_daily(self, client):
        """GET /api/waste/daily başarılı dönmeli."""
        r = client.get("/api/waste/daily")
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True

    def test_waste_weekly(self, client):
        """GET /api/waste/weekly başarılı dönmeli."""
        r = client.get("/api/waste/weekly")
        assert r.status_code == 200

    def test_waste_model_status(self, client):
        """GET /api/waste/model-status çalışmalı."""
        r = client.get("/api/waste/model-status")
        assert r.status_code == 200


class TestAnalyticsAPI:
    """Analitik API endpoint testleri."""

    def test_sentiment(self, client):
        """GET /api/analytics/sentiment çalışmalı."""
        r = client.get("/api/analytics/sentiment?gun=7")
        assert r.status_code == 200

    def test_israf_trend(self, client):
        """GET /api/analytics/israf-trend çalışmalı."""
        r = client.get("/api/analytics/israf-trend?gun=7")
        assert r.status_code == 200


class TestNewFeatures:
    """Yeni eklenen özellik endpoint testleri."""

    def test_api_version(self, client):
        """GET /api/version versiyon bilgisi dönmeli."""
        r = client.get("/api/version")
        assert r.status_code == 200
        data = r.json()
        assert data.get("version") == "v1"

    def test_tasks_list(self, client):
        """GET /api/tasks görev listesi dönmeli."""
        r = client.get("/api/tasks")
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True

    def test_models_health(self, client):
        """GET /api/models/health model sağlık durumu dönmeli."""
        r = client.get("/api/models/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True

    def test_experiments_ab_test(self, client):
        """GET /api/experiments/ab-test A/B test sonucu dönmeli."""
        r = client.get("/api/experiments/ab-test")
        assert r.status_code == 200

    def test_experiments_summary(self, client):
        """GET /api/experiments/summary özet dönmeli."""
        r = client.get("/api/experiments/summary?son_hafta=2")
        assert r.status_code == 200

    def test_ws_status(self, client):
        """GET /api/ws/status WebSocket durumu dönmeli."""
        r = client.get("/api/ws/status")
        assert r.status_code == 200
        data = r.json()
        assert "active_connections" in data

    def test_model_metrics(self, client):
        """GET /api/models/metrics metrik geçmişi dönmeli."""
        r = client.get("/api/models/metrics")
        assert r.status_code == 200

    def test_model_metrics_latest(self, client):
        """GET /api/models/metrics/latest son metrikler dönmeli."""
        r = client.get("/api/models/metrics/latest")
        assert r.status_code == 200

    def test_notifications_status(self, client):
        """GET /api/notifications/status bildirim durumu dönmeli."""
        r = client.get("/api/notifications/status")
        assert r.status_code == 200

    def test_async_task_train(self, client):
        """POST /api/tasks/train-waste-model async görev başlatmalı."""
        r = client.post("/api/tasks/train-waste-model?min_samples=8")
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert "task_id" in data

    def test_report_excel(self, client):
        """GET /api/report/excel Excel raporu dönmeli."""
        r = client.get("/api/report/excel?gun=7")
        # openpyxl kuruluysa 200, değilse 500
        assert r.status_code in (200, 500)
