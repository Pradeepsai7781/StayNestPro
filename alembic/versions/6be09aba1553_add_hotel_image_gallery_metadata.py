
"""add hotel image gallery metadata

Revision ID: 6be09aba1553
Revises: ac0580d305ac
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6be09aba1553"
down_revision: Union[str, Sequence[str], None] = "ac0580d305ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hotel_images",
        sa.Column(
            "category",
            sa.Enum(
                "EXTERIOR",
                "ROOM",
                "BATHROOM",
                "DINING",
                "AMENITIES",
                "OTHER",
                name="hotel_image_category",
            ),
            nullable=False,
            server_default="OTHER",
        ),
    )

    op.add_column(
        "hotel_images",
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "hotel_images",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_check_constraint(
        "ck_hotel_image_display_order_nonnegative",
        "hotel_images",
        "display_order >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_hotel_image_display_order_nonnegative",
        "hotel_images",
        type_="check",
    )

    op.drop_column("hotel_images", "is_primary")
    op.drop_column("hotel_images", "display_order")
    op.drop_column("hotel_images", "category")
