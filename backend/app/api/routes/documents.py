from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_workspace_member
from app.db import models
from app.db.session import get_db
from app.schemas.document import DocumentOut, ReindexRequest
from app.services.storage import get_storage_provider
from app.tasks.ingestion_tasks import ingest_document_task

router = APIRouter(prefix="/documents", tags=["documents"])


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name.replace(" ", "_")
    return "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_", "."})


@router.get("", response_model=list[DocumentOut])
def list_documents(
    workspace_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    require_workspace_member(workspace_id, current_user, db)
    documents = (
        db.query(models.Document)
        .filter(models.Document.workspace_id == workspace_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )
    return [DocumentOut.model_validate(document) for document in documents]


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    require_workspace_member(workspace_id, current_user, db)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    document = models.Document(
        workspace_id=workspace_id,
        uploaded_by=current_user.id,
        title=file.filename,
        storage_key="",
        file_size=len(contents),
        status=models.DocumentStatus.UPLOADING,
    )
    db.add(document)
    db.flush()

    storage = get_storage_provider()
    filename = _sanitize_filename(file.filename)
    key = os.path.join(workspace_id, document.id, f"{uuid.uuid4()}-{filename}")

    try:
        storage.save_bytes(key, contents)
        document.storage_key = key
        document.status = models.DocumentStatus.PROCESSING
        db.add(document)
        db.commit()
        db.refresh(document)
        ingest_document_task.delay(document.id, workspace_id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload failed: {exc}") from exc

    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_document(
    document_id: str,
    workspace_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_workspace_member(workspace_id, current_user, db)

    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.workspace_id == workspace_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = get_storage_provider()
    storage.delete(document.storage_key)

    db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == document.id).delete(synchronize_session=False)
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/reindex", response_model=DocumentOut)
def reindex_document(
    document_id: str,
    payload: ReindexRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    require_workspace_member(payload.workspace_id, current_user, db)

    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.workspace_id == payload.workspace_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == document.id).delete(synchronize_session=False)
    document.status = models.DocumentStatus.PROCESSING
    document.error_message = None
    db.add(document)
    db.commit()
    db.refresh(document)

    ingest_document_task.delay(document.id, payload.workspace_id)
    return DocumentOut.model_validate(document)
