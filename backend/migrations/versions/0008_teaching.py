"""hints, explanations, stuck events and warm-ups

problem_instances gains hints_used (hint levels viewed) and warmup_for (the skill a
warm-up problem was inserted for). explanation_views records each "explain it another
way" shown; stuck_events records problems scored wrong after every explanation was shown.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problem_instances",
        sa.Column("hints_used", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("problem_instances", sa.Column("warmup_for", sa.Text(), nullable=True))
    op.create_table(
        "explanation_views",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("approach", sa.Integer(), nullable=False),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["play_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["problem_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_explanation_views_player_id", "explanation_views", ["player_id"])
    op.create_index("ix_explanation_views_session_id", "explanation_views", ["session_id"])
    op.create_table(
        "stuck_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("problem_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("generator", sa.Text(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("wrong_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["problem_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("problem_id"),
    )
    op.create_index("ix_stuck_events_player_id", "stuck_events", ["player_id"])
    op.create_index("ix_stuck_events_created_at", "stuck_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_stuck_events_created_at", table_name="stuck_events")
    op.drop_index("ix_stuck_events_player_id", table_name="stuck_events")
    op.drop_table("stuck_events")
    op.drop_index("ix_explanation_views_session_id", table_name="explanation_views")
    op.drop_index("ix_explanation_views_player_id", table_name="explanation_views")
    op.drop_table("explanation_views")
    op.drop_column("problem_instances", "warmup_for")
    op.drop_column("problem_instances", "hints_used")
