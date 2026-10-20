
"""Add hotel moderation decision and report fields.

Revision ID: f635e4f84a7b
Revises: baee8e74c986
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f635e4f84a7b"
down_revision: Union[str, Sequence[str], None] = "baee8e74c986"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hotels",
        sa.Column("decision_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "hotels",
        sa.Column("decision_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "hotels",
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "hotels",
        sa.Column(
            "is_reported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "hotels",
        sa.Column("report_reason", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_hotels_decision_by_users",
        "hotels",
        "users",
        ["decision_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_hotels_decision_by_users",
        "hotels",
        type_="foreignkey",
    )
    op.drop_column("hotels", "report_reason")
    op.drop_column("hotels", "is_reported")
    op.drop_column("hotels", "decision_at")
    op.drop_column("hotels", "decision_by")
    op.drop_column("hotels", "decision_reason")
