
"""add additional services management

Revision ID: bce3cc84d643
Revises: 795b4a74a03d
Create Date: 2026-10-16 11:54:18.438485
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic.
revision: str = "bce3cc84d643"
down_revision: Union[str, Sequence[str], None] = "795b4a74a03d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create additional services, service requests, and service history."""

    op.create_table(
        "additional_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "LAUNDRY",
                "SPA",
                "RESTAURANT",
                "AIRPORT_PICKUP",
                "EXTRA_BED",
                name="additional_service_category",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "price >= 0",
            name="ck_additional_service_price_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_additional_services_category"),
        "additional_services",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_additional_services_id"),
        "additional_services",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_additional_services_name"),
        "additional_services",
        ["name"],
        unique=False,
    )

    op.create_table(
        "service_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("total_charge", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "REQUESTED",
                "CONFIRMED",
                "IN_PROGRESS",
                "COMPLETED",
                "CANCELLED",
                name="service_request_status",
            ),
            nullable=False,
        ),
        sa.Column("special_instructions", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "quantity >= 1",
            name="ck_service_request_quantity_positive",
        ),
        sa.CheckConstraint(
            "total_charge >= 0",
            name="ck_service_request_total_charge_nonnegative",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_service_request_unit_price_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["reservations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["additional_services.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_service_requests_id"),
        "service_requests",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_requests_requested_by"),
        "service_requests",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_requests_reservation_id"),
        "service_requests",
        ["reservation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_requests_service_id"),
        "service_requests",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_requests_status"),
        "service_requests",
        ["status"],
        unique=False,
    )

    op.create_table(
        "service_request_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_request_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "REQUESTED",
                "CONFIRMED",
                "IN_PROGRESS",
                "COMPLETED",
                "CANCELLED",
                name="service_request_history_status",
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_request_id"],
            ["service_requests.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_service_request_history_id"),
        "service_request_history",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_request_history_service_request_id"),
        "service_request_history",
        ["service_request_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove additional services, service requests, and service history."""

    op.drop_index(
        op.f("ix_service_request_history_service_request_id"),
        table_name="service_request_history",
    )
    op.drop_index(
        op.f("ix_service_request_history_id"),
        table_name="service_request_history",
    )
    op.drop_table("service_request_history")

    op.drop_index(
        op.f("ix_service_requests_status"),
        table_name="service_requests",
    )
    op.drop_index(
        op.f("ix_service_requests_service_id"),
        table_name="service_requests",
    )
    op.drop_index(
        op.f("ix_service_requests_reservation_id"),
        table_name="service_requests",
    )
    op.drop_index(
        op.f("ix_service_requests_requested_by"),
        table_name="service_requests",
    )
    op.drop_index(
        op.f("ix_service_requests_id"),
        table_name="service_requests",
    )
    op.drop_table("service_requests")

    op.drop_index(
        op.f("ix_additional_services_name"),
        table_name="additional_services",
    )
    op.drop_index(
        op.f("ix_additional_services_id"),
        table_name="additional_services",
    )
    op.drop_index(
        op.f("ix_additional_services_category"),
        table_name="additional_services",
    )
    op.drop_table("additional_services")
