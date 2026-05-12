"""add IoT weight columns to uretim_log

Revision ID: 4c7e2d1f8a3b
Revises: 3b8f1a2c9d5e
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c7e2d1f8a3b'
down_revision: Union[str, Sequence[str], None] = '3b8f1a2c9d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "uretim_log",
        sa.Column(
            "tartilan_israf_kg",
            sa.Float,
            nullable=True,
            comment="IoT tartıdan gelen gerçek israf ağırlığı (kg)",
        ),
    )
    op.add_column(
        "uretim_log",
        sa.Column(
            "tartilan_israf_kaynagi",
            sa.String(30),
            nullable=True,
            comment="Veri kaynağı: iot_tarti | simulasyon | manuel",
        ),
    )


def downgrade() -> None:
    op.drop_column("uretim_log", "tartilan_israf_kaynagi")
    op.drop_column("uretim_log", "tartilan_israf_kg")
