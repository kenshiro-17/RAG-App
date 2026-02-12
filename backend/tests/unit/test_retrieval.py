from __future__ import annotations

import uuid

from app.db import models
from app.services.retrieval import RetrievalService


def _vector(value: float) -> list[float]:
    vec = [0.0] * 1536
    vec[0] = value
    return vec


def test_hybrid_retrieval_filters_workspace_and_uses_keyword_rank(db_session, monkeypatch) -> None:
    user = models.User(id="u1", email="a@example.com", password_hash="x")
    workspace_a = models.Workspace(id=str(uuid.uuid4()), name="A", created_by=user.id)
    workspace_b = models.Workspace(id=str(uuid.uuid4()), name="B", created_by=user.id)
    db_session.add_all([user, workspace_a, workspace_b])

    doc_a = models.Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace_a.id,
        uploaded_by=user.id,
        title="Roadmap",
        storage_key="a",
        file_size=1,
        status=models.DocumentStatus.READY,
    )
    doc_b = models.Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace_b.id,
        uploaded_by=user.id,
        title="Other",
        storage_key="b",
        file_size=1,
        status=models.DocumentStatus.READY,
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    # Similar vectors but only first chunk contains keyword "deadline"
    chunk1 = models.DocumentChunk(
        workspace_id=workspace_a.id,
        document_id=doc_a.id,
        page=1,
        chunk_index=0,
        content="Project deadline is April 15 and release starts in May.",
        content_hash="h1",
        embedding=_vector(0.95),
    )
    chunk2 = models.DocumentChunk(
        workspace_id=workspace_a.id,
        document_id=doc_a.id,
        page=2,
        chunk_index=1,
        content="General product notes without the target term.",
        content_hash="h2",
        embedding=_vector(0.96),
    )
    chunk3 = models.DocumentChunk(
        workspace_id=workspace_b.id,
        document_id=doc_b.id,
        page=1,
        chunk_index=0,
        content="deadline for another workspace",
        content_hash="h3",
        embedding=_vector(0.99),
    )
    db_session.add_all([chunk1, chunk2, chunk3])
    db_session.commit()

    monkeypatch.setattr("app.services.retrieval.openai_service.embed_texts", lambda texts: [_vector(1.0)])

    service = RetrievalService(db_session)
    results = service.retrieve(workspace_id=workspace_a.id, query="What is the deadline?", top_k=2, mmr=False)

    assert len(results) == 2
    assert all(item.document_id == doc_a.id for item in results)
    assert results[0].chunk_id == chunk1.id
    assert results[0].keyword_score >= results[1].keyword_score
    assert results[0].hybrid_score >= results[1].hybrid_score


def test_mmr_returns_distinct_chunks(db_session, monkeypatch) -> None:
    user = models.User(id="u2", email="b@example.com", password_hash="x")
    workspace = models.Workspace(id=str(uuid.uuid4()), name="A", created_by=user.id)
    doc = models.Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        uploaded_by=user.id,
        title="Doc",
        storage_key="k",
        file_size=1,
        status=models.DocumentStatus.READY,
    )
    db_session.add_all([user, workspace, doc])
    db_session.flush()

    for idx, value in enumerate([0.99, 0.98, 0.60], start=1):
        db_session.add(
            models.DocumentChunk(
                workspace_id=workspace.id,
                document_id=doc.id,
                page=idx,
                chunk_index=idx,
                content=f"topic {idx} unique term {idx}",
                content_hash=f"hx{idx}",
                embedding=_vector(value),
            )
        )
    db_session.commit()

    monkeypatch.setattr("app.services.retrieval.openai_service.embed_texts", lambda texts: [_vector(1.0)])

    service = RetrievalService(db_session)
    results = service.retrieve(workspace_id=workspace.id, query="topic", top_k=2, mmr=True)

    assert len(results) == 2
    assert results[0].chunk_id != results[1].chunk_id
