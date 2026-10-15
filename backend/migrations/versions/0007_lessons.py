"""lessons_seen and lesson_tries: lessons a player has seen and their practice problems

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lessons_seen",
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "skill_id"),
    )
    op.create_table(
        "lesson_tries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("misses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lesson_tries_player_id", "lesson_tries", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_lesson_tries_player_id", table_name="lesson_tries")
    op.drop_table("lesson_tries")
    op.drop_table("lessons_seen")
