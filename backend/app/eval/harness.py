from __future__ import annotations

import asyncio
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.eval.types import EvalCase, EvalCaseResult
from app.services.chat_policy import (
    REFUSAL_TEXT,
    build_user_prompt,
    enforce_answer_policy,
    is_refusal,
    select_citation_objects_for_answer,
    system_prompt,
)
from app.services.openai_service import openai_service
from app.services.retrieval import RetrievalService


class EvaluationHarness:
    def __init__(self, db: Session, top_k: int = 8, mmr: bool = True):
        self.db = db
        self.top_k = top_k
        self.mmr = mmr

    def run(self, cases: list[EvalCase]) -> dict:
        results: list[EvalCaseResult] = []

        for case in cases:
            results.append(asyncio.run(self._evaluate_case(case)))

        if not results:
            return {
                "total_cases": 0,
                "recall_at_k": 0.0,
                "mrr": 0.0,
                "citation_correctness": 0.0,
                "refusal_rate": 0.0,
                "refusal_accuracy": 0.0,
            }

        recall_at_k = sum(item.recall_hit for item in results) / len(results)
        mrr = sum(item.reciprocal_rank for item in results) / len(results)
        citation_correctness = sum(item.citation_correct for item in results) / len(results)
        refusal_rate = sum(1.0 if item.predicted_refusal else 0.0 for item in results) / len(results)
        refusal_accuracy = sum(item.refusal_correct for item in results) / len(results)

        return {
            "total_cases": len(results),
            "recall_at_k": round(recall_at_k, 4),
            "mrr": round(mrr, 4),
            "citation_correctness": round(citation_correctness, 4),
            "refusal_rate": round(refusal_rate, 4),
            "refusal_accuracy": round(refusal_accuracy, 4),
            "cases": [asdict(item) for item in results],
        }

    async def _evaluate_case(self, case: EvalCase) -> EvalCaseResult:
        retrieval = RetrievalService(self.db)
        retrieved = retrieval.retrieve(
            workspace_id=case.workspace_id,
            query=case.question,
            top_k=self.top_k,
            mmr=self.mmr,
        )

        ranked_ids = [chunk.chunk_id for chunk in retrieved]
        recall_hit = self._recall_hit(ranked_ids, case.relevant_chunk_ids)
        reciprocal_rank = self._reciprocal_rank(ranked_ids, case.relevant_chunk_ids)

        if not retrieved:
            predicted_answer = REFUSAL_TEXT
            citations = []
        else:
            raw_answer, _usage = await openai_service.generate_answer(
                system_prompt=system_prompt(),
                user_prompt=build_user_prompt(case.question, retrieved),
            )
            predicted_answer = enforce_answer_policy(raw_answer, retrieved)
            citations = [] if is_refusal(predicted_answer) else select_citation_objects_for_answer(predicted_answer, retrieved)

        predicted_refusal = is_refusal(predicted_answer)

        citation_correct = self._citation_correctness(
            predicted_refusal=predicted_refusal,
            citation_chunk_ids=[citation["chunk_id"] for citation in citations],
            relevant_chunk_ids=case.relevant_chunk_ids,
            should_refuse=case.should_refuse,
        )
        refusal_correct = 1.0 if predicted_refusal == case.should_refuse else 0.0

        return EvalCaseResult(
            recall_hit=recall_hit,
            reciprocal_rank=reciprocal_rank,
            citation_correct=citation_correct,
            refusal_correct=refusal_correct,
            predicted_refusal=predicted_refusal,
        )

    @staticmethod
    def _recall_hit(ranked_ids: list[str], relevant_ids: list[str]) -> float:
        if not relevant_ids:
            return 1.0
        return 1.0 if any(chunk_id in set(relevant_ids) for chunk_id in ranked_ids) else 0.0

    @staticmethod
    def _reciprocal_rank(ranked_ids: list[str], relevant_ids: list[str]) -> float:
        if not relevant_ids:
            return 1.0
        relevant = set(relevant_ids)
        for idx, chunk_id in enumerate(ranked_ids, start=1):
            if chunk_id in relevant:
                return 1.0 / idx
        return 0.0

    @staticmethod
    def _citation_correctness(
        predicted_refusal: bool,
        citation_chunk_ids: list[str],
        relevant_chunk_ids: list[str],
        should_refuse: bool,
    ) -> float:
        if should_refuse:
            return 1.0 if predicted_refusal else 0.0
        if predicted_refusal:
            return 0.0
        if not relevant_chunk_ids:
            return 1.0

        relevant = set(relevant_chunk_ids)
        return 1.0 if any(chunk_id in relevant for chunk_id in citation_chunk_ids) else 0.0
