
"""Add hotel verification documents and suspended status."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "221a8c4f9147"
down_revision: Union[str, Sequence[str], None] = "8af74769522d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "mysql":
        op.execute(
            """
            ALTER TABLE hotels
            MODIFY COLUMN status
            ENUM('PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED')
            NOT NULL DEFAULT 'PENDING'
            """
        )

    op.create_table(
        "hotel_verification_documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotels.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_hotel_verification_documents_id",
        "hotel_verification_documents",
        ["id"],
    )
    op.create_index(
        "ix_hotel_verification_documents_hotel_id",
        "hotel_verification_documents",
        ["hotel_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "mysql":
        suspended_count = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM hotels WHERE status = 'SUSPENDED'"
            )
        ).scalar_one()

        if suspended_count:
            raise RuntimeError(
                "Reactivate suspended hotels before downgrading."
            )

    op.drop_index(
        "ix_hotel_verification_documents_hotel_id",
        table_name="hotel_verification_documents",
    )
    op.drop_index(
        "ix_hotel_verification_documents_id",
        table_name="hotel_verification_documents",
    )
    op.drop_table("hotel_verification_documents")

    if bind.dialect.name == "mysql":
        op.execute(
            """
            ALTER TABLE hotels
            MODIFY COLUMN status
            ENUM('PENDING', 'APPROVED', 'REJECTED')
            NOT NULL DEFAULT 'PENDING'
            """
        )
