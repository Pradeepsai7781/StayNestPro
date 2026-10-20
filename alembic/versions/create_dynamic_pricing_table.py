
"""Create dynamic pricing table."""

from alembic import op
import sqlalchemy as sa


# Replace these values with the correct migration revision IDs.
revision = "d42a91bc730e"
down_revision = "c82f1a6d904e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dynamic_pricing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "rule_type",
            sa.Enum(
                "SEASONAL",
                "WEEKEND",
                "HOLIDAY",
                "PROMOTIONAL",
                name="pricing_rule_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "adjustment_type",
            sa.Enum(
                "FIXED_PRICE",
                "PERCENTAGE",
                name="pricing_adjustment_type",
            ),
            nullable=False,
        ),
        sa.Column("adjustment_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "end_date >= start_date",
            name="ck_dynamic_pricing_valid_dates",
        ),
        sa.CheckConstraint(
            "adjustment_value >= 0",
            name="ck_dynamic_pricing_nonnegative_adjustment",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_dynamic_pricing_id",
        "dynamic_pricing",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_dynamic_pricing_room_id",
        "dynamic_pricing",
        ["room_id"],
        unique=False,
    )
    op.create_index(
        "ix_dynamic_pricing_rule_type",
        "dynamic_pricing",
        ["rule_type"],
        unique=False,
    )
    op.create_index(
        "ix_dynamic_pricing_start_date",
        "dynamic_pricing",
        ["start_date"],
        unique=False,
    )
    op.create_index(
        "ix_dynamic_pricing_end_date",
        "dynamic_pricing",
        ["end_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dynamic_pricing_end_date",
        table_name="dynamic_pricing",
    )
    op.drop_index(
        "ix_dynamic_pricing_start_date",
        table_name="dynamic_pricing",
    )
    op.drop_index(
        "ix_dynamic_pricing_rule_type",
        table_name="dynamic_pricing",
    )
    op.drop_index(
        "ix_dynamic_pricing_room_id",
        table_name="dynamic_pricing",
    )
    op.drop_index(
        "ix_dynamic_pricing_id",
        table_name="dynamic_pricing",
    )
    op.drop_table("dynamic_pricing")
