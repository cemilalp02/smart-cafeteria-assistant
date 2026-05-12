"""initial_schema — tüm tabloları oluşturur.

Revision ID: 222a7fe9f174
Revises:
Create Date: 2026-04-16 01:25:59.214942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '222a7fe9f174'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── yemekler ─────────────────────────────────────────────────
    op.create_table(
        "yemekler",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ad", sa.String(100), nullable=False, unique=True),
        sa.Column("kategori", sa.String(50), nullable=False),
        sa.Column("kalori", sa.Float, nullable=False, server_default="0"),
        sa.Column("protein", sa.Float, nullable=False, server_default="0"),
        sa.Column("karbonhidrat", sa.Float, nullable=False, server_default="0"),
        sa.Column("yag", sa.Float, nullable=False, server_default="0"),
    )

    # ── menuler ──────────────────────────────────────────────────
    op.create_table(
        "menuler",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tarih", sa.Date, nullable=False),
        sa.Column("gun", sa.String(20), nullable=False),
        sa.Column("corba", sa.String(100), nullable=True),
        sa.Column("ana_yemek", sa.String(100), nullable=True),
        sa.Column("yan_yemek", sa.String(100), nullable=True),
        sa.Column("tatli", sa.String(100), nullable=True),
        sa.Column("salata", sa.String(100), nullable=True),
    )

    # ── kullanicilar ─────────────────────────────────────────────
    op.create_table(
        "kullanicilar",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ad", sa.String(100), nullable=False),
        sa.Column("email", sa.String(150), nullable=False, unique=True),
        sa.Column("gunluk_kalori_hedefi", sa.Float, nullable=False, server_default="2000"),
    )

    # ── kullanici_yemek_log ──────────────────────────────────────
    op.create_table(
        "kullanici_yemek_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kullanici_id", sa.Integer, sa.ForeignKey("kullanicilar.id"), nullable=False),
        sa.Column("yemek_id", sa.Integer, sa.ForeignKey("yemekler.id"), nullable=False),
        sa.Column("tarih", sa.DateTime, nullable=False),
        sa.Column("miktar", sa.Float, nullable=False, server_default="1"),
        sa.Column("kaynak_tipi", sa.String(20), nullable=False, server_default="'manuel'"),
    )

    # ── menu_puanlama ────────────────────────────────────────────
    op.create_table(
        "menu_puanlama",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tarih", sa.Date, nullable=False),
        sa.Column("yemek_adi", sa.String(100), nullable=False),
        sa.Column("kategori", sa.String(50), nullable=False),
        sa.Column("puan", sa.Integer, nullable=False),
        sa.Column("yorum", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # ── alerts ───────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tarih", sa.Date, nullable=False),
        sa.Column("seviye", sa.String(20), nullable=False),
        sa.Column("yemek_adi", sa.String(100), nullable=True),
        sa.Column("kategori", sa.String(50), nullable=True),
        sa.Column("mesaj", sa.String(500), nullable=False),
        sa.Column("aktif", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # ── uretim_log ───────────────────────────────────────────────
    op.create_table(
        "uretim_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tarih", sa.Date, nullable=False),
        sa.Column("yemek_adi", sa.String(100), nullable=False),
        sa.Column("kategori", sa.String(50), nullable=False),
        sa.Column("uretilen_porsiyon", sa.Float, nullable=False),
        sa.Column("kalan_porsiyon", sa.Float, nullable=False),
        sa.Column("tuketim_orani", sa.Float, nullable=True),
        sa.Column("israf_orani", sa.Float, nullable=True),
        sa.Column("notlar", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # ── menu_oneri_log ───────────────────────────────────────────
    op.create_table(
        "menu_oneri_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("hafta_baslangic", sa.Date, nullable=False),
        sa.Column("gun", sa.String(20), nullable=False),
        sa.Column("tarih", sa.Date, nullable=False),
        sa.Column("corba", sa.String(100), nullable=True),
        sa.Column("ana_yemek", sa.String(100), nullable=True),
        sa.Column("yan_yemek", sa.String(100), nullable=True),
        sa.Column("tatli", sa.String(100), nullable=True),
        sa.Column("salata", sa.String(100), nullable=True),
        sa.Column("toplam_skor", sa.Float, nullable=True),
        sa.Column("beslenme_skoru", sa.Float, nullable=True),
        sa.Column("israf_skoru", sa.Float, nullable=True),
        sa.Column("maliyet_skoru", sa.Float, nullable=True),
        sa.Column("populerlik_skoru", sa.Float, nullable=True),
        sa.Column("toplam_kalori", sa.Float, nullable=True),
        sa.Column("toplam_protein", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("menu_oneri_log")
    op.drop_table("uretim_log")
    op.drop_table("alerts")
    op.drop_table("menu_puanlama")
    op.drop_table("kullanici_yemek_log")
    op.drop_table("kullanicilar")
    op.drop_table("menuler")
    op.drop_table("yemekler")
