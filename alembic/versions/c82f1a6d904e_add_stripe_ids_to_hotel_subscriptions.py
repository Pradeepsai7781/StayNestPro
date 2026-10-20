
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "c82f1a6d904e"
down_revision = "b61d8e42c905"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)

    columns = {
        column["name"]
        for column in inspector.get_columns("hotel_subscriptions")
    }

    if "stripe_customer_id" not in columns:
        op.add_column(
            "hotel_subscriptions",
            sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        )

    if "stripe_subscription_id" not in columns:
        op.add_column(
            "hotel_subscriptions",
            sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        )

    inspector = inspect(connection)
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "hotel_subscriptions"
        )
    }

    if "uq_hotel_subscriptions_stripe_customer_id" not in constraints:
        op.create_unique_constraint(
            "uq_hotel_subscriptions_stripe_customer_id",
            "hotel_subscriptions",
            ["stripe_customer_id"],
        )

    if "uq_hotel_subscriptions_stripe_subscription_id" not in constraints:
        op.create_unique_constraint(
            "uq_hotel_subscriptions_stripe_subscription_id",
            "hotel_subscriptions",
            ["stripe_subscription_id"],
        )

    inspector = inspect(connection)
    indexes = {
        index["name"]
        for index in inspector.get_indexes("hotel_subscriptions")
    }

    if "ix_hotel_subscriptions_stripe_subscription_id" not in indexes:
        op.create_index(
            "ix_hotel_subscriptions_stripe_subscription_id",
            "hotel_subscriptions",
            ["stripe_subscription_id"],
        )


def downgrade() -> None:
    # Intentionally leave existing Stripe columns and constraints in place.
    # They may have existed before this migration was applied.
    pass
