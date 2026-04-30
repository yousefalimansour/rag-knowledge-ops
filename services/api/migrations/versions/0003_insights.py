"""insights — insights, insight_runs, notifications

Revision ID: 0003_insights
Revises: 0002_ingestion
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_insights"
down_revision = "0002_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_default = sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'")
    json_arr_default = sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'")
    json_type = postgresql.JSONB if is_postgres else sa.JSON

    op.create_table(
        "insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("severity", sa.String(8), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("evidence", json_type, nullable=False, server_default=json_arr_default),
        sa.Column("dedup_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "severity in ('low','medium','high')", name="ck_insight_severity"
        ),
        sa.CheckConstraint(
            "state in ('active','dismissed','read')", name="ck_insight_state"
        ),
    )
    op.create_index("ix_insights_dedup_hash", "insights", ["dedup_hash"], unique=True)
    op.create_index(
        "ix_insights_ws_state_created", "insights", ["workspace_id", "state", "created_at"]
    )

    op.create_table(
        "insight_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("source_doc_ids", json_type, nullable=False, server_default=json_arr_default),
        sa.Column("insights_generated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("insights_skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("watermark_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "trigger in ('post_ingest','coordinator','nightly','manual')",
            name="ck_run_trigger",
        ),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','failed')", name="ck_run_status"
        ),
    )
    op.create_index("ix_runs_ws_started", "insight_runs", ["workspace_id", "started_at"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("severity", sa.String(8), nullable=True),
        sa.Column("link_kind", sa.String(32), nullable=True),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "severity is null or severity in ('low','medium','high','info')",
            name="ck_notif_severity",
        ),
    )
    op.create_index(
        "ix_notif_user_unread_created", "notifications", ["user_id", "read_at", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_notif_user_unread_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_runs_ws_started", table_name="insight_runs")
    op.drop_table("insight_runs")
    op.drop_index("ix_insights_ws_state_created", table_name="insights")
    op.drop_index("ix_insights_dedup_hash", table_name="insights")
    op.drop_table("insights")
