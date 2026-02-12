from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db import models
from app.db.session import get_db
from app.main import app
from app.services.retrieval import RetrievedChunk


def test_chat_streams_and_returns_citations(db_session, monkeypatch) -> None:
    user = models.User(id=str(uuid.uuid4()), email="test@example.com", password_hash="hash")
    workspace = models.Workspace(id=str(uuid.uuid4()), name="Team", created_by=user.id)
    member = models.WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=models.WorkspaceRole.OWNER)
    db_session.add_all([user, workspace, member])
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(
        "app.api.routes.chat.TokenBucketRateLimiter.allow",
        lambda self, user_id, cost=1.0: type("R", (), {"allowed": True, "tokens_left": 10})(),
    )

    monkeypatch.setattr(
        "app.api.routes.chat.RetrievalService.retrieve",
        lambda self, workspace_id, query, top_k, mmr: [
            RetrievedChunk(
                chunk_id="c1",
                document_id="d1",
                title="Doc",
                page=2,
                content="The launch date is May 5.",
                vector_score=0.9,
                keyword_score=1.0,
                hybrid_score=0.95,
                embedding=[0.0],
            )
        ],
    )

    async def fake_stream(system_prompt: str, user_prompt: str):
        yield {"type": "token", "token": "The launch date is May 5 "}
        yield {"type": "token", "token": "[Doc p.2]"}
        yield {"type": "final", "answer": "The launch date is May 5 [Doc p.2]", "usage": {"total_tokens": 12}}

    monkeypatch.setattr("app.api.routes.chat.openai_service.stream_answer", fake_stream)

    client = TestClient(app)
    token = create_access_token(user.id)

    response = client.post(
        "/chat",
        json={"workspace_id": workspace.id, "message": "When is launch?", "debug": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.text
    assert "event: token" in body
    assert "event: final" in body
    assert '"citations"' in body

    app.dependency_overrides.clear()
