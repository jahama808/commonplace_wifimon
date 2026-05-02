"""add mdu_olt_map

Revision ID: 1772705ecfe3
Revises: 40f9492a92b5
Create Date: 2026-05-02 16:01:42.621090

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1772705ecfe3'
down_revision: Union[str, None] = '40f9492a92b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mdu_olt_map",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mdu_name", sa.String(length=255), nullable=False),
        sa.Column("fdh_name", sa.String(length=64), nullable=True),
        sa.Column("equip_name", sa.String(length=64), nullable=True),
        sa.Column("serving_olt", sa.String(length=64), nullable=True),
        sa.Column("equip_name_1", sa.String(length=64), nullable=True),
        sa.Column("equip_model", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "mdu_name", "equip_name", "equip_name_1", name="uq_mdu_olt_map_natural"
        ),
    )
    op.create_index("ix_mdu_olt_map_mdu_name", "mdu_olt_map", ["mdu_name"])


def downgrade() -> None:
    op.drop_index("ix_mdu_olt_map_mdu_name", table_name="mdu_olt_map")
    op.drop_table("mdu_olt_map")
