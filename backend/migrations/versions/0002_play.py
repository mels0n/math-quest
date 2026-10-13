"""play tables

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _player_fk() -> sa.ForeignKey:
    return sa.ForeignKey("players.id", ondelete="CASCADE")


def upgrade() -> None:
    op.create_table(
        "skill_mastery",
        sa.Column("player_id", postgresql.UUID(as_uuid=True), _player_fk(), primary_key=True),
        sa.Column("skill_id", sa.Text(), primary_key=True),
        sa.Column("rating", sa.Float(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recent", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("state", sa.Text(), nullable=False, server_default="learning"),
        sa.Column("review_interval_days", sa.Integer(), nullable=True),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "play_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), _player_fk(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("problem_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "problem_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("play_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), _player_fk(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
    )
    op.create_table(
        "attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problem_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), _player_fk(), nullable=False),
        sa.Column("latex", sa.Text(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("misconception", sa.Text(), nullable=True),
        sa.Column("seconds", sa.Float(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("attempts")
    op.drop_table("problem_instances")
    op.drop_table("play_sessions")
    op.drop_table("skill_mastery")
