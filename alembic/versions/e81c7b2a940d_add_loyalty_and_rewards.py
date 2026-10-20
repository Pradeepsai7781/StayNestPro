
"""Add loyalty accounts and rewards ledger."""

from alembic import op
import sqlalchemy as sa


revision = "e81c7b2a940d"
down_revision = "d42a91bc730e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loyalty_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "points_balance",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "membership_tier",
            sa.String(length=20),
            nullable=False,
            server_default="BRONZE",
        ),
        sa.Column("referral_code", sa.String(length=20), nullable=False),
        sa.Column(
            "referred_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
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
            "points_balance >= 0",
            name="ck_loyalty_points_balance_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["referred_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("referral_code"),
    )

    op.create_index(
        "ix_loyalty_accounts_id",
        "loyalty_accounts",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_loyalty_accounts_user_id",
        "loyalty_accounts",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_loyalty_accounts_referral_code",
        "loyalty_accounts",
        ["referral_code"],
        unique=True,
    )

    op.create_table(
        "loyalty_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column(
            "entry_type",
            sa.Enum(
                "BOOKING_REWARD",
                "REDEMPTION",
                "REFERRAL_REWARD",
                "REFERRAL_BONUS",
                name="loyalty_entry_type",
            ),
            nullable=False,
        ),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("monetary_value", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "idempotency_key",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "points != 0",
            name="ck_loyalty_ledger_points_nonzero",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["reservations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_loyalty_ledger_idempotency_key",
        ),
    )

    op.create_index(
        "ix_loyalty_ledger_id",
        "loyalty_ledger",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_loyalty_ledger_user_id",
        "loyalty_ledger",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_loyalty_ledger_reservation_id",
        "loyalty_ledger",
        ["reservation_id"],
        unique=False,
    )
    op.create_index(
        "ix_loyalty_ledger_payment_id",
        "loyalty_ledger",
        ["payment_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_loyalty_ledger_payment_id",
        table_name="loyalty_ledger",
    )
    op.drop_index(
        "ix_loyalty_ledger_reservation_id",
        table_name="loyalty_ledger",
    )
    op.drop_index(
        "ix_loyalty_ledger_user_id",
        table_name="loyalty_ledger",
    )
    op.drop_index(
        "ix_loyalty_ledger_id",
        table_name="loyalty_ledger",
    )
    op.drop_table("loyalty_ledger")

    op.drop_index(
        "ix_loyalty_accounts_referral_code",
        table_name="loyalty_accounts",
    )
    op.drop_index(
        "ix_loyalty_accounts_user_id",
        table_name="loyalty_accounts",
    )
    op.drop_index(
        "ix_loyalty_accounts_id",
        table_name="loyalty_accounts",
    )
    op.drop_table("loyalty_accounts")
