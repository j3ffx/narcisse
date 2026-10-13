"""let the user add a trace by hand

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.alter_column("scan_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("run_id", existing_type=sa.INTEGER(), nullable=True)


def downgrade() -> None:
    # Proofs of traces added by hand have no scan to belong to.
    op.execute("DELETE FROM evidence WHERE scan_id IS NULL OR run_id IS NULL")
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.alter_column("run_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("scan_id", existing_type=sa.INTEGER(), nullable=False)
