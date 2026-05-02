"""add property.island column

Revision ID: f39766dafd86
Revises: 1772705ecfe3
Create Date: 2026-05-02 18:22:41.502859

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f39766dafd86'
down_revision: Union[str, None] = '1772705ecfe3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reuse the existing `island` enum that the common_areas column already
    # has — no new type to create.
    op.add_column(
        "properties",
        sa.Column(
            "island",
            sa.Enum(
                "KAUAI",
                "OAHU",
                "MOLOKAI",
                "LANAI",
                "MAUI",
                "HAWAII",
                name="island",
                create_type=False,
            ),
            nullable=True,
        ),
    )

    # Backfill from common_areas.island — pick the most-common island per
    # property, breaking ties by the lowest common_area id (deterministic).
    op.execute(
        """
        UPDATE properties p
        SET island = sub.island
        FROM (
            SELECT DISTINCT ON (property_id)
                property_id,
                island
            FROM (
                SELECT
                    property_id,
                    island,
                    COUNT(*) AS n,
                    MIN(id) AS first_id
                FROM common_areas
                WHERE island IS NOT NULL
                GROUP BY property_id, island
            ) counts
            ORDER BY property_id, n DESC, first_id ASC
        ) sub
        WHERE p.id = sub.property_id;
        """
    )


def downgrade() -> None:
    op.drop_column("properties", "island")
