"""score traces and follow them

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("entity", schema=None) as batch_op:
        batch_op.add_column(sa.Column("module_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("score_reasons", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("pivot_dismissed", sa.Boolean(), server_default="0", nullable=False)
        )
    # Until now `confidence` held the sources' highest one: it becomes that column, and the
    # scores (with `score_reasons` still empty) are computed on the next start.
    op.execute("UPDATE entity SET module_confidence = confidence")

    with op.batch_alter_table("module_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("depth", sa.Integer(), server_default="0", nullable=False))

    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notes", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.drop_column("notes")

    with op.batch_alter_table("module_run", schema=None) as batch_op:
        batch_op.drop_column("depth")

    op.execute("UPDATE entity SET confidence = module_confidence")
    with op.batch_alter_table("entity", schema=None) as batch_op:
        batch_op.drop_column("pivot_dismissed")
        batch_op.drop_column("score_reasons")
        batch_op.drop_column("module_confidence")
