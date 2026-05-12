"""
Maliyet route testleri — /api/v1/maliyet/* endpoint'leri.
"""

import pytest


class TestMaliyetYemekListesi:
    """GET /api/v1/maliyet/yemekler"""

    def test_returns_list(self, client):
        r = client.get("/api/v1/maliyet/yemekler")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "yemekler" in data
        assert "varsayilan_maliyetler" in data
        assert isinstance(data["yemekler"], list)

    def test_yemek_fields(self, client):
        r = client.get("/api/v1/maliyet/yemekler")
        data = r.json()
        if data["yemekler"]:
            y = data["yemekler"][0]
            assert "id" in y
            assert "ad" in y
            assert "kategori" in y
            assert "birim_maliyet_gosterim" in y
            assert y["kaynak"] in ("girilmis", "varsayilan")


class TestMaliyetGuncelle:
    """PUT /api/v1/maliyet/guncelle"""

    def test_nonexistent_id_returns_error(self, client):
        r = client.put(
            "/api/v1/maliyet/guncelle",
            json={"yemek_id": 999999, "birim_maliyet": 25.0},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is False

    def test_negative_cost_rejected(self, client):
        r = client.put(
            "/api/v1/maliyet/guncelle",
            json={"yemek_id": 1, "birim_maliyet": -5.0},
        )
        # Pydantic validation: ge=0 → 422 dönmeli
        assert r.status_code == 422

    def test_excessive_cost_rejected(self, client):
        r = client.put(
            "/api/v1/maliyet/guncelle",
            json={"yemek_id": 1, "birim_maliyet": 5000.0},
        )
        # le=1000 → 422
        assert r.status_code == 422

    def test_valid_update(self, client):
        """Var olan ID güncellenebilir."""
        # Önce listeyi al ki gerçek bir ID kullanalım
        lst = client.get("/api/v1/maliyet/yemekler").json()
        if not lst["yemekler"]:
            pytest.skip("Yemek listesi boş")
        yid = lst["yemekler"][0]["id"]

        r = client.put(
            "/api/v1/maliyet/guncelle",
            json={"yemek_id": yid, "birim_maliyet": 42.5},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["yemek"]["birim_maliyet"] == 42.5


class TestMaliyetTopluGuncelle:
    """PUT /api/v1/maliyet/toplu-guncelle"""

    def test_empty_list(self, client):
        r = client.put(
            "/api/v1/maliyet/toplu-guncelle",
            json={"maliyetler": []},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["guncellenen"] == 0

    def test_nonexistent_ids_collected_in_hatalar(self, client):
        r = client.put(
            "/api/v1/maliyet/toplu-guncelle",
            json={"maliyetler": [
                {"yemek_id": 999999, "birim_maliyet": 10.0},
                {"yemek_id": 999998, "birim_maliyet": 15.0},
            ]},
        )
        data = r.json()
        assert data["success"] is True
        assert data["guncellenen"] == 0
        assert len(data["hatalar"]) == 2


class TestMaliyetAnaliz:
    """GET /api/v1/maliyet/analiz"""

    def test_returns_periodic_summary(self, client):
        r = client.get("/api/v1/maliyet/analiz")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "gunluk" in data
        assert "haftalik" in data
        assert "aylik" in data
        assert "gecen_ay" in data
        assert "degisim_pct" in data
        assert data["degisim_yonu"] in ("azalma", "artis", "ayni")


class TestMaliyetTrend:
    """GET /api/v1/maliyet/trend"""

    def test_default_30_days(self, client):
        r = client.get("/api/v1/maliyet/trend")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["gun"] == 30
        assert isinstance(data["trend"], list)

    def test_custom_period(self, client):
        r = client.get("/api/v1/maliyet/trend?gun=14")
        data = r.json()
        assert data["gun"] == 14

    def test_invalid_period_rejected(self, client):
        # ge=7 le=365 sınırları
        r = client.get("/api/v1/maliyet/trend?gun=3")
        assert r.status_code == 422

        r = client.get("/api/v1/maliyet/trend?gun=400")
        assert r.status_code == 422


class TestMaliyetDetay:
    """GET /api/v1/maliyet/detay"""

    def test_returns_sorted_yemekler(self, client):
        r = client.get("/api/v1/maliyet/detay")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "yemekler" in data
        assert "toplam_maliyet_tl" in data

        # Sıralama doğru mu? (desc by toplam_kayip_tl)
        if len(data["yemekler"]) >= 2:
            prev = data["yemekler"][0]["toplam_kayip_tl"]
            for y in data["yemekler"][1:]:
                assert y["toplam_kayip_tl"] <= prev
                prev = y["toplam_kayip_tl"]
