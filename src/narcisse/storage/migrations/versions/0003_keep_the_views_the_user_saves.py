"""keep the views the user saves

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_view",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_saved_view_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_view")),
        sa.UniqueConstraint("profile_id", "name", name=op.f("uq_saved_view_profile_id")),
    )
    with op.batch_alter_table("saved_view", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_saved_view_profile_id"), ["profile_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("saved_view", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_saved_view_profile_id"))

    op.drop_table("saved_view")
