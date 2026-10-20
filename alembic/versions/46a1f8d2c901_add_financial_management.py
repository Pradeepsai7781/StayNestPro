"""Add financial records, settlements, and payment reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "46a1f8d2c901"
down_revision = "e81c7b2a940d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotels.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("gross_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("hotel_earnings", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("payment_id", name="uq_financial_records_payment_id"),
    )
    op.create_index("ix_financial_records_id", "financial_records", ["id"])
    op.create_index("ix_financial_records_payment_id", "financial_records", ["payment_id"])
    op.create_index("ix_financial_records_hotel_id", "financial_records", ["hotel_id"])

    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotels.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PROCESSING", "PAID", "FAILED", name="payout_status"), nullable=False),
        sa.Column("provider_payout_reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_payout_reference", name="uq_settlements_provider_payout_reference"),
    )
    op.create_index("ix_settlements_id", "settlements", ["id"])
    op.create_index("ix_settlements_hotel_id", "settlements", ["hotel_id"])
    op.create_index("ix_settlements_status", "settlements", ["status"])

    op.create_table(
        "payment_reconciliations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_transaction_id", sa.String(length=255), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("provider_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("local_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("provider_status", sa.String(length=50), nullable=False),
        sa.Column("local_status", sa.String(length=50), nullable=True),
        sa.Column("status", sa.Enum("MATCHED", "MISMATCHED", "NOT_FOUND", name="reconciliation_status"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_transaction_id", name="uq_reconciliation_provider_transaction"),
    )
    op.create_index("ix_payment_reconciliations_id", "payment_reconciliations", ["id"])
    op.create_index("ix_payment_reconciliations_payment_id", "payment_reconciliations", ["payment_id"])
    op.create_index("ix_payment_reconciliations_status", "payment_reconciliations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_reconciliations_status", table_name="payment_reconciliations")
    op.drop_index("ix_payment_reconciliations_payment_id", table_name="payment_reconciliations")
    op.drop_index("ix_payment_reconciliations_id", table_name="payment_reconciliations")
    op.drop_table("payment_reconciliations")
    op.drop_index("ix_settlements_status", table_name="settlements")
    op.drop_index("ix_settlements_hotel_id", table_name="settlements")
    op.drop_index("ix_settlements_id", table_name="settlements")
    op.drop_table("settlements")
    op.drop_index("ix_financial_records_hotel_id", table_name="financial_records")
    op.drop_index("ix_financial_records_payment_id", table_name="financial_records")
    op.drop_index("ix_financial_records_id", table_name="financial_records")
    op.drop_table("financial_records")
