
from alembic import op
import sqlalchemy as sa


revision = "a74c2e91b630"
down_revision = "9c2f1a7b6d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hotel_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column(
            "plan",
            sa.Enum(
                "FREE", "BASIC", "PREMIUM", "ENTERPRISE",
                name="subscription_plan",
            ),
            nullable=False,
            server_default="FREE",
        ),
        sa.Column(
            "billing_period",
            sa.Enum("MONTHLY", "YEARLY", name="subscription_billing_period"),
            nullable=False,
            server_default="MONTHLY",
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "EXPIRED", "CANCELLED", name="subscription_status"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotels.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hotel_id",
            name="uq_hotel_subscriptions_hotel_id",
        ),
    )

    op.create_index(
        "ix_hotel_subscriptions_id",
        "hotel_subscriptions",
        ["id"],
    )
    op.create_index(
        "ix_hotel_subscriptions_hotel_id",
        "hotel_subscriptions",
        ["hotel_id"],
    )
    op.create_index(
        "ix_hotel_subscriptions_status",
        "hotel_subscriptions",
        ["status"],
    )
    op.create_index(
        "ix_hotel_subscriptions_expires_at",
        "hotel_subscriptions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hotel_subscriptions_expires_at",
        table_name="hotel_subscriptions",
    )
    op.drop_index(
        "ix_hotel_subscriptions_status",
        table_name="hotel_subscriptions",
    )
    op.drop_index(
        "ix_hotel_subscriptions_hotel_id",
        table_name="hotel_subscriptions",
    )
    op.drop_index(
        "ix_hotel_subscriptions_id",
        table_name="hotel_subscriptions",
    )
    op.drop_table("hotel_subscriptions")
