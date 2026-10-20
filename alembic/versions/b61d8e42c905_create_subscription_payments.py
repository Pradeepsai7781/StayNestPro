
from alembic import op
import sqlalchemy as sa


revision = "b61d8e42c905"
down_revision = "a74c2e91b630"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hotel_subscriptions",
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "hotel_subscriptions",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )

    op.create_unique_constraint(
        "uq_hotel_subscriptions_stripe_customer_id",
        "hotel_subscriptions",
        ["stripe_customer_id"],
    )
    op.create_unique_constraint(
        "uq_hotel_subscriptions_stripe_subscription_id",
        "hotel_subscriptions",
        ["stripe_subscription_id"],
    )

    op.create_index(
        "ix_hotel_subscriptions_stripe_subscription_id",
        "hotel_subscriptions",
        ["stripe_subscription_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hotel_subscriptions_stripe_subscription_id",
        table_name="hotel_subscriptions",
    )
    op.drop_constraint(
        "uq_hotel_subscriptions_stripe_subscription_id",
        "hotel_subscriptions",
        type_="unique",
    )
    op.drop_constraint(
        "uq_hotel_subscriptions_stripe_customer_id",
        "hotel_subscriptions",
        type_="unique",
    )
    op.drop_column("hotel_subscriptions", "stripe_subscription_id")
    op.drop_column("hotel_subscriptions", "stripe_customer_id")
