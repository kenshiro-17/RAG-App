from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    workspace_id: str
    message: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=20)
    debug: bool = False
    mmr: bool = True


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    page: int
    snippet: str


class ChatFinalPayload(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[dict] | None = None
