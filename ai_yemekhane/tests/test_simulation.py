"""
Simulation route testleri — /api/v1/simulation/* endpoint'leri.
"""

import pytest


class TestYemekListesi:
    """GET /api/v1/simulation/yemek-listesi"""

    def test_returns_categories(self, client):
        r = client.get("/api/v1/simulation/yemek-listesi")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "kategoriler" in data
        assert isinstance(data["kategoriler"], dict)

    def test_sorted_by_popularity(self, client):
        """Her kategori popülerliğe göre azalan sırada olmalı."""
        r = client.get("/api/v1/simulation/yemek-listesi")
        data = r.json()
        for kat, yemekler in data["kategoriler"].items():
            if len(yemekler) >= 2:
                prev = yemekler[0]["populerlik"]
                for y in yemekler[1:]:
                    assert y["populerlik"] <= prev
                    prev = y["populerlik"]

    def test_yemek_fields(self, client):
        r = client.get("/api/v1/simulation/yemek-listesi")
        data = r.json()
        for yemekler in data["kategoriler"].values():
            if yemekler:
                y = yemekler[0]
                assert "ad" in y
                assert "populerlik" in y
                assert "birim_maliyet" in y
                break


class TestMenuBugun:
    """GET /api/v1/simulation/menu-bugun"""

    def test_returns_menu_or_message(self, client):
        r = client.get("/api/v1/simulation/menu-bugun")
        assert r.status_code == 200
        data = r.json()
        # Ya success+menu, ya success=False+message
        if data["success"]:
            assert "menu" in data
            assert "tarih" in data
            assert "gun" in data
        else:
            assert "message" in data


class TestWhatIfSimulation:
    """POST /api/v1/simulation/what-if"""

    def test_empty_changes(self, client):
        r = client.post(
            "/api/v1/simulation/what-if",
            json={"degisiklikler": [], "uretilen_porsiyon": 100},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["ozet"]["degisiklik_sayisi"] == 0

    def test_single_change(self, client):
        r = client.post(
            "/api/v1/simulation/what-if",
            json={
                "degisiklikler": [
                    {
                        "slot": "corba",
                        "mevcut_yemek": "Mercimek Çorbası",
                        "yeni_yemek": "Domates Çorbası",
                    },
                ],
                "uretilen_porsiyon": 100,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert len(data["sonuclar"]) == 1

        sonuc = data["sonuclar"][0]
        assert sonuc["slot"] == "corba"
        assert "mevcut" in sonuc
        assert "yeni" in sonuc
        assert "fark" in sonuc
        assert sonuc["oneri"] in ("degistir", "dusun", "degistirme")

    def test_invalid_production_rejected(self, client):
        # ge=1 ihlali → 422
        r = client.post(
            "/api/v1/simulation/what-if",
            json={
                "degisiklikler": [],
                "uretilen_porsiyon": 0,
            },
        )
        assert r.status_code == 422

    def test_summary_totals(self, client):
        """Özet doğru hesaplanır."""
        r = client.post(
            "/api/v1/simulation/what-if",
            json={
                "degisiklikler": [
                    {"slot": "corba", "mevcut_yemek": "Mercimek Çorbası", "yeni_yemek": "Domates Çorbası"},
                    {"slot": "ana_yemek", "mevcut_yemek": "Tavuk Sote", "yeni_yemek": "Köfte"},
                ],
                "uretilen_porsiyon": 200,
            },
        )
        data = r.json()
        assert data["ozet"]["degisiklik_sayisi"] == 2

        toplam_yeni = sum(s["yeni"]["maliyet_kayip_tl"] for s in data["sonuclar"])
        assert abs(data["ozet"]["toplam_yeni_kayip_tl"] - round(toplam_yeni, 2)) < 0.05
