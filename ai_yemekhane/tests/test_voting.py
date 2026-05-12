"""
Voting route testleri — /api/v1/voting/* endpoint'leri.

Hafta üretimini gerçekten çağırmak yerine doğrudan MenuAlternatif kayıtları
ekleyip oy verme + sonuç + geçmiş flow'unu test ediyoruz.
"""

import json
import pytest

from models import MenuAlternatif, MenuOylama, SessionLocal


@pytest.fixture
def voting_week_data(client):
    """Test için doğrudan MenuAlternatif kayıtları oluştur."""
    db = SessionLocal()
    test_hafta = "2099-W01"  # Çakışmayı önlemek için uzak hafta

    try:
        # Temizle
        db.query(MenuOylama).filter(MenuOylama.hafta == test_hafta).delete()
        db.query(MenuAlternatif).filter(MenuAlternatif.hafta == test_hafta).delete()

        # 3 alternatif ekle
        for key, etiket in [("A", "Dengeli"), ("B", "Popüler"), ("C", "Ekonomik")]:
            db.add(MenuAlternatif(
                hafta=test_hafta,
                alternatif=key,
                etiket=etiket,
                menu_json=json.dumps([], ensure_ascii=False),
                skor_israf=0.3,
                skor_maliyet=60.0,
                skor_populerlik=0.7,
                skor_beslenme=2000,
                oy_sayisi=0,
                aktif=True,
            ))
        db.commit()
        yield test_hafta
    finally:
        # Cleanup
        db.query(MenuOylama).filter(MenuOylama.hafta == test_hafta).delete()
        db.query(MenuAlternatif).filter(MenuAlternatif.hafta == test_hafta).delete()
        db.commit()
        db.close()


class TestVotingAlternatifler:
    """GET /api/v1/voting/alternatifler"""

    def test_existing_week_returns_alternatives(self, client, voting_week_data):
        r = client.get(f"/api/v1/voting/alternatifler?hafta={voting_week_data}")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["hafta"] == voting_week_data
        assert len(data["alternatifler"]) == 3
        assert data["toplam_oy"] == 0

    def test_nonexistent_week_returns_empty(self, client):
        r = client.get("/api/v1/voting/alternatifler?hafta=1900-W01")
        data = r.json()
        # success=True ama alternatifler boş
        assert data["success"] is True
        assert data["alternatifler"] == []


class TestVotingOyVer:
    """POST /api/v1/voting/oy-ver"""

    def test_invalid_alternative_rejected(self, client, voting_week_data):
        r = client.post(
            "/api/v1/voting/oy-ver",
            json={"hafta": voting_week_data, "alternatif": "D"},
        )
        data = r.json()
        assert data["success"] is False
        assert "Geçersiz" in data["error"] or "alternatif" in data["error"].lower()

    def test_nonexistent_week_rejected(self, client):
        r = client.post(
            "/api/v1/voting/oy-ver",
            json={"hafta": "1900-W01", "alternatif": "A"},
        )
        data = r.json()
        assert data["success"] is False

    def test_valid_vote_recorded(self, client, voting_week_data):
        r = client.post(
            "/api/v1/voting/oy-ver",
            json={
                "hafta": voting_week_data,
                "alternatif": "A",
                "anonim_id": "test_user_001",
            },
        )
        data = r.json()
        assert data["success"] is True
        assert data["secilen"] == "A"
        assert data["toplam_oy"] == 1

    def test_duplicate_vote_rejected(self, client, voting_week_data):
        # İlk oy
        client.post(
            "/api/v1/voting/oy-ver",
            json={
                "hafta": voting_week_data,
                "alternatif": "A",
                "anonim_id": "test_dup_user",
            },
        )
        # Aynı kullanıcı tekrar
        r = client.post(
            "/api/v1/voting/oy-ver",
            json={
                "hafta": voting_week_data,
                "alternatif": "B",
                "anonim_id": "test_dup_user",
            },
        )
        data = r.json()
        assert data["success"] is False
        assert data.get("zaten_oylandi") is True

    def test_case_insensitive_alternative(self, client, voting_week_data):
        """Küçük harfli alternatif de kabul edilmeli (upper case'e çevrilir)."""
        r = client.post(
            "/api/v1/voting/oy-ver",
            json={
                "hafta": voting_week_data,
                "alternatif": "b",
                "anonim_id": "test_case_user",
            },
        )
        data = r.json()
        assert data["success"] is True
        assert data["secilen"] == "B"


class TestVotingSonuclar:
    """GET /api/v1/voting/sonuclar"""

    def test_no_data_returns_error(self, client):
        r = client.get("/api/v1/voting/sonuclar?hafta=1900-W01")
        data = r.json()
        assert data["success"] is False

    def test_results_with_votes(self, client, voting_week_data):
        # Önce oy ver
        for i, alt in enumerate(["A", "A", "B", "C"]):
            client.post(
                "/api/v1/voting/oy-ver",
                json={
                    "hafta": voting_week_data,
                    "alternatif": alt,
                    "anonim_id": f"user_{i}",
                },
            )

        r = client.get(f"/api/v1/voting/sonuclar?hafta={voting_week_data}")
        data = r.json()
        assert data["success"] is True
        assert data["toplam_oy"] == 4
        assert data["kazanan"]["alternatif"] == "A"
        assert data["kazanan"]["oy_sayisi"] == 2

        # Yüzdeler toplamı ≈ 100
        toplam_pct = sum(s["oy_yuzdesi"] for s in data["sonuclar"])
        assert 99.0 <= toplam_pct <= 101.0


class TestVotingGecmis:
    """GET /api/v1/voting/gecmis"""

    def test_returns_list(self, client):
        r = client.get("/api/v1/voting/gecmis")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert isinstance(data["gecmis"], list)

    def test_invalid_limit_rejected(self, client):
        r = client.get("/api/v1/voting/gecmis?limit=0")
        assert r.status_code == 422

        r = client.get("/api/v1/voting/gecmis?limit=100")
        assert r.status_code == 422
