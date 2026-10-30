"""write proofs and the assistant's answers in any language

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.add_column(sa.Column("note", sa.JSON(), nullable=True))
    with op.batch_alter_table("llm_annotation", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("lang", sa.String(length=2), server_default="fr", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("llm_annotation", schema=None) as batch_op:
        batch_op.drop_column("lang")
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.drop_column("note")
