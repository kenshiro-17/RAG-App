from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_workspace_member
from app.core.rate_limit import TokenBucketRateLimiter
from app.db import models
from app.db.session import get_db
from app.schemas.chat import ChatRequest
from app.services.chat_policy import (
    REFUSAL_TEXT,
    build_user_prompt,
    citation_objects,
    enforce_answer_policy,
    is_refusal,
    select_citation_objects_for_answer,
    system_prompt,
)
from app.services.openai_service import openai_service
from app.services.redis_client import get_redis_client
from app.services.retrieval import RetrievalService

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("", response_class=StreamingResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    require_workspace_member(payload.workspace_id, current_user, db)

    limiter = TokenBucketRateLimiter(get_redis_client())
    rate_limit_result = limiter.allow(current_user.id, cost=1.0)
    if not rate_limit_result.allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    retrieval = RetrievalService(db)
    retrieved = retrieval.retrieve(
        workspace_id=payload.workspace_id,
        query=payload.message,
        top_k=payload.top_k,
        mmr=payload.mmr,
    )

    request_id = getattr(request.state, "request_id", "-")
    start = time.perf_counter()

    async def event_generator() -> AsyncGenerator[str, None]:
        if not retrieved:
            yield _sse_event("token", {"token": REFUSAL_TEXT})
            yield _sse_event(
                "final",
                {
                    "answer": REFUSAL_TEXT,
                    "citations": [],
                    "retrieved_chunks": [] if payload.debug else None,
                },
            )
            return

        user_prompt = build_user_prompt(payload.message, retrieved)

        answer_text = ""
        usage = None
        async for event in openai_service.stream_answer(system_prompt(), user_prompt):
            if event["type"] == "token":
                answer_text += event["token"]
                yield _sse_event("token", {"token": event["token"]})
            elif event["type"] == "final":
                usage = event.get("usage")

        answer_text = enforce_answer_policy(answer_text, retrieved)
        citations = [] if is_refusal(answer_text) else select_citation_objects_for_answer(answer_text, retrieved)
        if not citations and not is_refusal(answer_text):
            citations = citation_objects(retrieved[:3])

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "chat_complete user_id=%s workspace_id=%s latency_ms=%.2f usage=%s",
            current_user.id,
            payload.workspace_id,
            elapsed_ms,
            usage,
            extra={"request_id": request_id},
        )

        yield _sse_event(
            "final",
            {
                "answer": answer_text,
                "citations": citations,
                "retrieved_chunks": [chunk.to_debug() for chunk in retrieved] if payload.debug else None,
            },
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
