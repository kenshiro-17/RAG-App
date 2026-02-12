from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalCase:
    workspace_id: str
    question: str
    relevant_chunk_ids: list[str]
    should_refuse: bool


@dataclass
class EvalCaseResult:
    recall_hit: float
    reciprocal_rank: float
    citation_correct: float
    refusal_correct: float
    predicted_refusal: bool
