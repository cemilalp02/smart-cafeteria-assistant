"""add birim_maliyet column to yemekler

Revision ID: 5d9f3e2a7b1c
Revises: 4c7e2d1f8a3b
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d9f3e2a7b1c'
down_revision: Union[str, Sequence[str], None] = '4c7e2d1f8a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "yemekler",
        sa.Column(
            "birim_maliyet",
            sa.Float,
            nullable=True,
            comment="Porsiyon başı maliyet (TL)",
        ),
    )


def downgrade() -> None:
    op.drop_column("yemekler", "birim_maliyet")
