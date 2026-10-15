"""practice sessions, session summaries and revisits

play_sessions gains ``focus`` (a practice session's skills) and ``mastered_at_start``
(those of them mastered when it started). problem_instances gains
``newly_mastered`` (scoring it made its skill mastered, for the session summary).
revisit_events records a mastered skill practised again, once per session and skill.
The session mode "practice" needs no schema change (mode is free text).

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "play_sessions",
        sa.Column("focus", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "play_sessions",
        sa.Column("mastered_at_start", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "problem_instances",
        sa.Column("newly_mastered", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_table(
        "revisit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["play_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "skill_id"),
    )
    op.create_index("ix_revisit_events_player_id", "revisit_events", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_revisit_events_player_id", table_name="revisit_events")
    op.drop_table("revisit_events")
    op.drop_column("problem_instances", "newly_mastered")
    op.drop_column("play_sessions", "mastered_at_start")
    op.drop_column("play_sessions", "focus")
