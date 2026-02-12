"""add keyword search gin index

Revision ID: 0002_keyword_search_index
Revises: 0001_initial
Create Date: 2026-02-12 00:20:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0002_keyword_search_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_content_tsv ON document_chunks "
        "USING GIN (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_tsv")
