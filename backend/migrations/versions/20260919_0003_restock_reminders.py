"""Add durable seller restock reminder queue."""
from alembic import op
import sqlalchemy as sa

revision = "20260919_0003"
down_revision = "20260919_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restock_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_restock_reminders_merchant_id", "restock_reminders", ["merchant_id"])
    op.create_index("ix_restock_reminders_status", "restock_reminders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_restock_reminders_status", table_name="restock_reminders")
    op.drop_index("ix_restock_reminders_merchant_id", table_name="restock_reminders")
    op.drop_table("restock_reminders")
