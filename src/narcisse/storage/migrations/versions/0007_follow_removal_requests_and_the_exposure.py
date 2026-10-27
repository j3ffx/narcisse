"""follow removal requests and the exposure

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exposure_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=True),
        sa.Column("taken_at", sa.DateTime(), nullable=False),
        sa.Column("levels", sa.JSON(), nullable=False),
        sa.Column("exposure", sa.Double(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_exposure_snapshot_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scan.id"],
            name=op.f("fk_exposure_snapshot_scan_id_scan"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exposure_snapshot")),
    )
    with op.batch_alter_table("exposure_snapshot", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_exposure_snapshot_profile_id"), ["profile_id"], unique=False
        )

    op.create_table(
        "removal_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("service", sa.String(length=200), nullable=False),
        sa.Column("letter", sa.String(length=30), nullable=True),
        sa.Column("recipient", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("reminded_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("check", sa.String(length=20), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("check_scan_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["check_scan_id"],
            ["scan.id"],
            name=op.f("fk_removal_request_check_scan_id_scan"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entity.id"],
            name=op.f("fk_removal_request_entity_id_entity"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_removal_request_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_removal_request")),
        sa.UniqueConstraint(
            "entity_id", "action", "service", name=op.f("uq_removal_request_entity_id")
        ),
    )
    with op.batch_alter_table("removal_request", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_removal_request_entity_id"), ["entity_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_removal_request_profile_id"), ["profile_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_removal_request_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("removal_request", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_removal_request_status"))
        batch_op.drop_index(batch_op.f("ix_removal_request_profile_id"))
        batch_op.drop_index(batch_op.f("ix_removal_request_entity_id"))

    op.drop_table("removal_request")
    with op.batch_alter_table("exposure_snapshot", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_exposure_snapshot_profile_id"))

    op.drop_table("exposure_snapshot")
