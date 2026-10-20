
"""add review stay and moderation fields

Revision ID: 32ac888b4d4a
Revises: 1209b9daec77
Create Date: 2026-10-15 19:13:00.277193
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision: str = "32ac888b4d4a"
down_revision: Union[str, Sequence[str], None] = "1209b9daec77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add stay linkage and review moderation fields."""

    op.add_column(
        "hotel_reviews",
        sa.Column(
            "reservation_id",
            sa.Integer(),
            nullable=False,
        ),
    )

    op.add_column(
        "hotel_reviews",
        sa.Column(
            "is_reported",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.add_column(
        "hotel_reviews",
        sa.Column(
            "is_hidden",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.create_index(
        op.f("ix_hotel_reviews_reservation_id"),
        "hotel_reviews",
        ["reservation_id"],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_hotel_review_reservation",
        "hotel_reviews",
        ["reservation_id"],
    )

    op.create_foreign_key(
        "fk_hotel_reviews_reservation_id_reservations",
        "hotel_reviews",
        "reservations",
        ["reservation_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Remove stay linkage and review moderation fields."""

    op.drop_constraint(
        "fk_hotel_reviews_reservation_id_reservations",
        "hotel_reviews",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_hotel_review_reservation",
        "hotel_reviews",
        type_="unique",
    )

    op.drop_index(
        op.f("ix_hotel_reviews_reservation_id"),
        table_name="hotel_reviews",
    )

    op.drop_column("hotel_reviews", "is_hidden")
    op.drop_column("hotel_reviews", "is_reported")
    op.drop_column("hotel_reviews", "reservation_id")
