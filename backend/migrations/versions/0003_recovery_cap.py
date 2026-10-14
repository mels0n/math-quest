"""per-player recovery failure cap

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players", sa.Column("recovery_locked_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "recovery_failures",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recovery_failures_player_at", "recovery_failures", ["player_id", "at"])


def downgrade() -> None:
    op.drop_index("ix_recovery_failures_player_at", table_name="recovery_failures")
    op.drop_table("recovery_failures")
    op.drop_column("players", "recovery_locked_until")
