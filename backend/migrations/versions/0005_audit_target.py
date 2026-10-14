"""admin_audit.target_nickname and detail keep a deleted or renamed player attributable

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_audit", sa.Column("target_nickname", sa.Text(), nullable=True))
    op.add_column("admin_audit", sa.Column("detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_audit", "detail")
    op.drop_column("admin_audit", "target_nickname")
