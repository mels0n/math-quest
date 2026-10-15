"""problem_instances.variant and template_id: how an issued problem was presented

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problem_instances",
        sa.Column("variant", sa.Text(), nullable=False, server_default="bare"),
    )
    op.add_column("problem_instances", sa.Column("template_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("problem_instances", "template_id")
    op.drop_column("problem_instances", "variant")
