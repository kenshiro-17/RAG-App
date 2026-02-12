from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models import DocumentStatus


class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    uploaded_by: str | None
    title: str
    file_size: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReindexRequest(BaseModel):
    workspace_id: str
