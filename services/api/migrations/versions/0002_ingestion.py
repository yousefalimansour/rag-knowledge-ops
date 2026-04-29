"""ingestion — documents, chunks (+ tsvector), ingest_jobs, embedding_cache

Revision ID: 0002_ingestion
Revises: 0001_initial
Create Date: 2026-04-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_ingestion"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("source_metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")) if is_postgres
        else sa.Column("source_metadata", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("storage_path", sa.String(1024), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "content_hash", name="uq_doc_workspace_content"),
        sa.CheckConstraint(
            "source_type in ('pdf','txt','md','slack','notion')", name="ck_doc_source_type"
        ),
        sa.CheckConstraint(
            "status in ('pending','processing','ready','failed')", name="ck_doc_status"
        ),
    )
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_index("ix_documents_workspace_status", "documents", ["workspace_id", "status"])
    op.create_index("ix_documents_workspace_title", "documents", ["workspace_id", "title"])

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_document", "chunks", ["document_id"])
    op.create_index("ix_chunks_text_hash", "chunks", ["text_hash"])

    if is_postgres:
        # tsvector column + GIN index — Postgres only; SQLite test path uses LIKE in repo.
        op.execute(
            "ALTER TABLE chunks ADD COLUMN content_tsv tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
        )
        op.execute("CREATE INDEX ix_chunks_content_tsv ON chunks USING GIN (content_tsv)")

    op.create_table(
        "ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(32), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','failed')", name="ck_job_status"
        ),
    )
    op.create_index("ix_jobs_document", "ingest_jobs", ["document_id"])
    op.create_index("ix_jobs_workspace_created", "ingest_jobs", ["workspace_id", "created_at"])

    op.create_table(
        "embedding_cache",
        sa.Column("text_hash", sa.String(64), primary_key=True),
        sa.Column("model", sa.String(64), primary_key=True),
        sa.Column("embedding", postgresql.JSONB if is_postgres else sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("embedding_cache")
    op.drop_index("ix_jobs_workspace_created", table_name="ingest_jobs")
    op.drop_index("ix_jobs_document", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_chunks_content_tsv")
        op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv")
    op.drop_index("ix_chunks_text_hash", table_name="chunks")
    op.drop_index("ix_chunks_document", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_workspace_title", table_name="documents")
    op.drop_index("ix_documents_workspace_status", table_name="documents")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_table("documents")
