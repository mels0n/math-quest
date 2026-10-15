"""placement runs and placed mastery

placement_runs records each placement round (its probes in ``state``, its outcome in
``result``). skill_mastery gains ``placed``: mastery confirmed by a review after
placement marked the skill, before the rating rule agrees. The new skill state
"provisional" needs no schema change (state is free text).

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "placement_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grade_hint", sa.Text(), nullable=True),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_placement_runs_player_id", "placement_runs", ["player_id"])
    op.add_column(
        "skill_mastery",
        sa.Column("placed", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    # Provisional marks have no meaning without placement: drop them, keep real progress.
    op.execute("DELETE FROM skill_mastery WHERE state = 'provisional' AND attempts = 0")
    op.execute(
        "UPDATE skill_mastery SET state = 'learning', review_interval_days = NULL,"
        " review_due_at = NULL WHERE state = 'provisional'"
    )
    op.drop_column("skill_mastery", "placed")
    op.drop_index("ix_placement_runs_player_id", table_name="placement_runs")
    op.drop_table("placement_runs")
