"""update embedding vector dimensions for hf embeddings

Revision ID: 0003_embedding_dimension_hf
Revises: 0002_keyword_search_index
Create Date: 2026-02-28 11:25:00.000000
"""

from __future__ import annotations

import os

from alembic import op


# revision identifiers, used by Alembic.
revision = "0003_embedding_dimension_hf"
down_revision = "0002_keyword_search_index"
branch_labels = None
depends_on = None


def _target_dim() -> int:
    raw = os.getenv("EMBEDDING_DIMENSIONS", "1024")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid EMBEDDING_DIMENSIONS value: {raw}") from exc
    if value <= 0:
        raise ValueError("EMBEDDING_DIMENSIONS must be > 0")
    return value


def upgrade() -> None:
    dim = _target_dim()
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.execute("TRUNCATE TABLE document_chunks")
    op.execute(f"ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector({dim})")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.execute("TRUNCATE TABLE document_chunks")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
