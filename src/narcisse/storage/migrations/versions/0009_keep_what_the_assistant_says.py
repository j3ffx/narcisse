"""keep what the assistant says

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_annotation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("task", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("edited", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_params", sa.JSON(), nullable=True),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entity.id"],
            name=op.f("fk_llm_annotation_entity_id_entity"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_llm_annotation_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_annotation")),
    )
    with op.batch_alter_table("llm_annotation", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_llm_annotation_entity_id"), ["entity_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_llm_annotation_profile_id"), ["profile_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_llm_annotation_state"), ["state"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("llm_annotation", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_llm_annotation_state"))
        batch_op.drop_index(batch_op.f("ix_llm_annotation_profile_id"))
        batch_op.drop_index(batch_op.f("ix_llm_annotation_entity_id"))
    op.drop_table("llm_annotation")
