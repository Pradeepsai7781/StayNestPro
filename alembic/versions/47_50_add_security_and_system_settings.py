"""Add security alerts and system configuration for modules 47-50."""
from alembic import op
import sqlalchemy as sa

revision = "b7c9e21a4f60"
down_revision = ("3ba62d6c8d14", "46a1f8d2c901")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.Enum("OPEN", "REVIEWED", "RESOLVED", name="security_alert_status"), nullable=False, server_default="OPEN"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_alerts_id", "security_alerts", ["id"])
    op.create_index("ix_security_alerts_alert_type", "security_alerts", ["alert_type"])
    op.create_index("ix_security_alerts_status", "security_alerts", ["status"])
    op.create_index("ix_security_alerts_user_id", "security_alerts", ["user_id"])
    op.create_index("ix_security_alerts_ip_address", "security_alerts", ["ip_address"])

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", name="uq_system_settings_key"),
    )
    op.create_index("ix_system_settings_id", "system_settings", ["id"])
    op.create_index("ix_system_settings_key", "system_settings", ["key"])


def downgrade() -> None:
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_index("ix_system_settings_id", table_name="system_settings")
    op.drop_table("system_settings")
    op.drop_index("ix_security_alerts_ip_address", table_name="security_alerts")
    op.drop_index("ix_security_alerts_user_id", table_name="security_alerts")
    op.drop_index("ix_security_alerts_status", table_name="security_alerts")
    op.drop_index("ix_security_alerts_alert_type", table_name="security_alerts")
    op.drop_index("ix_security_alerts_id", table_name="security_alerts")
    op.drop_table("security_alerts")
