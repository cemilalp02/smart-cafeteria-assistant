"""add israf_self_report column to menu_puanlama

Revision ID: 3b8f1a2c9d5e
Revises: 222a7fe9f174
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b8f1a2c9d5e'
down_revision: Union[str, Sequence[str], None] = '222a7fe9f174'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "menu_puanlama",
        sa.Column(
            "israf_self_report",
            sa.Integer,
            nullable=True,
            comment="Öğrenci israf self-report: 0=hiç, 1=az(<%25), 2=orta(%25-50), 3=çok(>%50)",
        ),
    )


def downgrade() -> None:
    op.drop_column("menu_puanlama", "israf_self_report")
