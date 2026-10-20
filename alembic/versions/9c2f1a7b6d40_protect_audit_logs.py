
"""Protect audit logs from updates and deletions."""

from alembic import op

revision = "9c2f1a7b6d40"
down_revision = "53b95083604e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prevent existing audit records from being updated.
    op.execute("""
        CREATE TRIGGER prevent_audit_log_update
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Audit logs cannot be modified'
    """)

    # Prevent existing audit records from being deleted.
    op.execute("""
        CREATE TRIGGER prevent_audit_log_delete
        BEFORE DELETE ON audit_logs
        FOR EACH ROW
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Audit logs cannot be deleted'
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_audit_log_delete"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_audit_log_update"
    )
