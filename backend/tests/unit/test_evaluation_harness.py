from __future__ import annotations

from app.eval.harness import EvaluationHarness
from app.eval.types import EvalCase
from app.services.retrieval import RetrievedChunk


def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="d1",
        title="Doc",
        page=1,
        content="release date is April 15",
        vector_score=1.0,
        keyword_score=1.0,
        hybrid_score=1.0,
        embedding=[0.1, 0.2],
    )


def test_evaluation_harness_reports_retrieval_and_citation_metrics(monkeypatch) -> None:
    harness = EvaluationHarness(db=None, top_k=4, mmr=True)

    monkeypatch.setattr(
        "app.eval.harness.RetrievalService.retrieve",
        lambda self, workspace_id, query, top_k, mmr: [_chunk("c1")],
    )

    async def fake_answer(system_prompt: str, user_prompt: str):
        return "The release date is April 15 [Doc p.1]", {"total_tokens": 20}

    monkeypatch.setattr("app.eval.harness.openai_service.generate_answer", fake_answer)

    cases = [
        EvalCase(
            workspace_id="w1",
            question="When do we release?",
            relevant_chunk_ids=["c1"],
            should_refuse=False,
        )
    ]

    report = harness.run(cases)

    assert report["recall_at_k"] == 1.0
    assert report["mrr"] == 1.0
    assert report["citation_correctness"] == 1.0
    assert report["refusal_rate"] == 0.0


def test_evaluation_harness_refusal_accuracy(monkeypatch) -> None:
    harness = EvaluationHarness(db=None, top_k=4, mmr=True)

    monkeypatch.setattr(
        "app.eval.harness.RetrievalService.retrieve",
        lambda self, workspace_id, query, top_k, mmr: [],
    )

    cases = [
        EvalCase(
            workspace_id="w1",
            question="Give me password",
            relevant_chunk_ids=[],
            should_refuse=True,
        )
    ]

    report = harness.run(cases)

    assert report["refusal_rate"] == 1.0
    assert report["refusal_accuracy"] == 1.0
    assert report["citation_correctness"] == 1.0
