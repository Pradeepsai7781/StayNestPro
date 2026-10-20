
"""add room booking fields"""

from alembic import op
import sqlalchemy as sa


revision = "3ba62d6c8d14"
down_revision = "d70f72383e51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Add room_type_id as nullable to preserve existing rooms.
    op.add_column(
        "rooms",
        sa.Column("room_type_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_rooms_room_type_id_room_types",
        "rooms",
        "room_types",
        ["room_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 2. Assign a compatible room type from the same hotel.
    connection.execute(
        sa.text("""
            UPDATE rooms AS r
            SET room_type_id = (
                SELECT rt.id
                FROM room_types AS rt
                WHERE rt.hotel_id = r.hotel_id
                  AND rt.capacity >= r.capacity
                ORDER BY rt.id
                LIMIT 1
            )
            WHERE r.room_type_id IS NULL
        """)
    )

    missing = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM rooms WHERE room_type_id IS NULL"
        )
    ).scalar_one()

    if missing:
        raise RuntimeError(
            "Some rooms have no compatible room type in their hotel. "
            "Create compatible room types and rerun the migration."
        )

    op.alter_column(
        "rooms",
        "room_type_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 3. Add reservation booking fields.
    op.add_column(
        "reservations",
        sa.Column(
            "guest_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    op.add_column(
        "reservations",
        sa.Column(
            "booking_reference",
            sa.String(length=20),
            nullable=True,
        ),
    )

    op.add_column(
        "reservations",
        sa.Column(
            "total_price",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
    )

    # 4. Backfill unique references for existing reservations.
    reservation_ids = connection.execute(
        sa.text("SELECT id FROM reservations ORDER BY id")
    ).scalars().all()

    for reservation_id in reservation_ids:
        connection.execute(
            sa.text("""
                UPDATE reservations
                SET booking_reference = :reference
                WHERE id = :reservation_id
            """),
            {
                "reference": f"SN-LEGACY-{reservation_id:08d}",
                "reservation_id": reservation_id,
            },
        )

    op.alter_column(
        "reservations",
        "booking_reference",
        existing_type=sa.String(length=20),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_reservations_booking_reference",
        "reservations",
        ["booking_reference"],
    )

    op.create_index(
        "ix_reservations_booking_reference",
        "reservations",
        ["booking_reference"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_reservation_guest_count_positive",
        "reservations",
        "guest_count >= 1",
    )

    op.create_check_constraint(
        "ck_reservation_total_price_nonnegative",
        "reservations",
        "total_price >= 0",
    )

    # 5. Remove temporary defaults after existing rows are populated.
    op.alter_column(
        "reservations",
        "guest_count",
        existing_type=sa.Integer(),
        server_default=None,
    )

    op.alter_column(
        "reservations",
        "total_price",
        existing_type=sa.Numeric(10, 2),
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_reservation_total_price_nonnegative",
        "reservations",
        type_="check",
    )

    op.drop_constraint(
        "ck_reservation_guest_count_positive",
        "reservations",
        type_="check",
    )

    op.drop_index(
        "ix_reservations_booking_reference",
        table_name="reservations",
    )

    op.drop_constraint(
        "uq_reservations_booking_reference",
        "reservations",
        type_="unique",
    )

    op.drop_column("reservations", "total_price")
    op.drop_column("reservations", "booking_reference")
    op.drop_column("reservations", "guest_count")

    op.drop_constraint(
        "fk_rooms_room_type_id_room_types",
        "rooms",
        type_="foreignkey",
    )

    op.drop_column("rooms", "room_type_id")
