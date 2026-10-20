"""add customer travel preferences and profile picture

Revision ID: 8af74769522d
Revises: f9e6ff52f830
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8af74769522d"
down_revision: Union[str, Sequence[str], None] = "f9e6ff52f830"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("travel_preferences", sa.JSON(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("profile_picture", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "profile_picture")
    op.drop_column("users", "travel_preferences")
