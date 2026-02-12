from __future__ import annotations

import io
import logging

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.db.session import SessionLocal
from app.services.chunking import chunk_text_with_tiktoken, clean_text, content_hash
from app.services.openai_service import openai_service
from app.services.storage import get_storage_provider
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)
settings = get_settings()


def _set_document_status(db: Session, document: models.Document, status: models.DocumentStatus, error: str | None = None) -> None:
    document.status = status
    document.error_message = error
    db.add(document)
    db.commit()


@celery.task(name="ingest_document_task")
def ingest_document_task(document_id: str, workspace_id: str) -> None:
    db = SessionLocal()
    storage = get_storage_provider()

    try:
        document = (
            db.query(models.Document)
            .filter(models.Document.id == document_id, models.Document.workspace_id == workspace_id)
            .first()
        )
        if not document:
            logger.error("Document %s not found for workspace %s", document_id, workspace_id)
            return

        _set_document_status(db, document, models.DocumentStatus.PROCESSING)
        file_bytes = storage.read_bytes(document.storage_key)

        reader = PdfReader(io.BytesIO(file_bytes))
        chunk_payloads: list[dict] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            extracted = page.extract_text() or ""
            page_text = clean_text(extracted)
            if not page_text:
                continue

            page_chunks = chunk_text_with_tiktoken(
                page_text,
                chunk_tokens=settings.chunk_tokens,
                overlap_tokens=settings.overlap_tokens,
            )
            for chunk in page_chunks:
                chunk_payloads.append(
                    {
                        "page": page_idx,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "content_hash": content_hash(chunk.content),
                    }
                )

        if not chunk_payloads:
            _set_document_status(db, document, models.DocumentStatus.FAILED, "No text extracted from PDF")
            return

        existing_hashes = {
            row[0]
            for row in db.query(models.DocumentChunk.content_hash)
            .filter(models.DocumentChunk.document_id == document_id)
            .all()
        }

        new_payloads = [payload for payload in chunk_payloads if payload["content_hash"] not in existing_hashes]

        if not new_payloads:
            _set_document_status(db, document, models.DocumentStatus.READY)
            return

        embeddings = openai_service.embed_texts([payload["content"] for payload in new_payloads])

        chunk_rows: list[models.DocumentChunk] = []
        for payload, vector in zip(new_payloads, embeddings):
            chunk_rows.append(
                models.DocumentChunk(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    page=payload["page"],
                    chunk_index=payload["chunk_index"],
                    content=payload["content"],
                    content_hash=payload["content_hash"],
                    embedding=vector,
                )
            )

        db.add_all(chunk_rows)
        db.commit()
        _set_document_status(db, document, models.DocumentStatus.READY)
        logger.info("Ingested document=%s chunks=%s", document_id, len(chunk_rows))

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        document = db.query(models.Document).filter(models.Document.id == document_id).first()
        if document:
            _set_document_status(db, document, models.DocumentStatus.FAILED, str(exc))
        logger.exception("Ingestion failed for document=%s: %s", document_id, exc)
    finally:
        db.close()
