"""mark whether a skill was played outside practice

skill_mastery gains ``played_in_adventure``. A learner who tries a skill only in practice
has a row for it, but readiness treats the skill as never played, so trying one that sits
under what they know does not make it offered in the adventure. Every existing row counts
as played (the column defaults to true), so existing learners keep what they have.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill_mastery",
        sa.Column("played_in_adventure", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("skill_mastery", "played_in_adventure")
