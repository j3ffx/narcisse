"""create the initial schema

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event")),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_event_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_event_scan_id"), ["scan_id"], unique=False)

    op.create_table(
        "profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile")),
    )
    op.create_table(
        "entity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("normalized", sa.String(length=1000), nullable=False),
        sa.Column("display", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk", sa.Float(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_entity_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entity")),
        sa.UniqueConstraint("profile_id", "kind", "normalized", name=op.f("uq_entity_profile_id")),
    )
    with op.batch_alter_table("entity", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_entity_profile_id"), ["profile_id"], unique=False)

    op.create_table(
        "scan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_scan_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scan")),
    )
    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_scan_profile_id"), ["profile_id"], unique=False)

    op.create_table(
        "seed",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("normalized", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_seed_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seed")),
        sa.UniqueConstraint("profile_id", "kind", "normalized", name=op.f("uq_seed_profile_id")),
    )
    with op.batch_alter_table("seed", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_seed_profile_id"), ["profile_id"], unique=False)

    op.create_table(
        "edge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.String(length=50), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("fk_edge_profile_id_profile"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["entity.id"],
            name=op.f("fk_edge_source_id_entity"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["entity.id"],
            name=op.f("fk_edge_target_id_entity"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edge")),
        sa.UniqueConstraint(
            "source_id",
            "target_id",
            "relation",
            "module",
            name=op.f("uq_edge_source_id"),
        ),
    )
    with op.batch_alter_table("edge", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_edge_profile_id"), ["profile_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_edge_source_id"), ["source_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_edge_target_id"), ["target_id"], unique=False)

    op.create_table(
        "module_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("input_entity_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress_done", sa.Integer(), nullable=True),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_params", sa.JSON(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("checkpoint", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["input_entity_id"],
            ["entity.id"],
            name=op.f("fk_module_run_input_entity_id_entity"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scan.id"],
            name=op.f("fk_module_run_scan_id_scan"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module_run")),
    )
    with op.batch_alter_table("module_run", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_module_run_scan_id"), ["scan_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_module_run_status"), ["status"], unique=False)

    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("edge_id", sa.Integer(), nullable=True),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["edge_id"],
            ["edge.id"],
            name=op.f("fk_evidence_edge_id_edge"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entity.id"],
            name=op.f("fk_evidence_entity_id_entity"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["module_run.id"],
            name=op.f("fk_evidence_run_id_module_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scan.id"],
            name=op.f("fk_evidence_scan_id_scan"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_evidence_entity_id"), ["entity_id"], unique=False)
        batch_op.create_index("ix_evidence_scan_id_id", ["scan_id", "id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.drop_index("ix_evidence_scan_id_id")
        batch_op.drop_index(batch_op.f("ix_evidence_entity_id"))

    op.drop_table("evidence")
    with op.batch_alter_table("module_run", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_module_run_status"))
        batch_op.drop_index(batch_op.f("ix_module_run_scan_id"))

    op.drop_table("module_run")
    with op.batch_alter_table("edge", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_edge_target_id"))
        batch_op.drop_index(batch_op.f("ix_edge_source_id"))
        batch_op.drop_index(batch_op.f("ix_edge_profile_id"))

    op.drop_table("edge")
    with op.batch_alter_table("seed", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_seed_profile_id"))

    op.drop_table("seed")
    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scan_profile_id"))

    op.drop_table("scan")
    with op.batch_alter_table("entity", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_entity_profile_id"))

    op.drop_table("entity")
    op.drop_table("profile")
    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_event_scan_id"))
        batch_op.drop_index(batch_op.f("ix_event_created_at"))

    op.drop_table("event")
