from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.services.openai_service import openai_service
from app.services.prompt_safety import injection_risk_score, sanitize_retrieved_text


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    title: str
    page: int
    content: str
    vector_score: float
    keyword_score: float
    hybrid_score: float
    embedding: list[float]

    def to_debug(self) -> dict:
        payload = asdict(self)
        payload.pop("embedding", None)
        return payload


@dataclass
class _Candidate:
    chunk: models.DocumentChunk
    title: str
    vector_similarity: float
    keyword_rank: float


class RetrievalService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def retrieve(
        self,
        workspace_id: str,
        query: str,
        top_k: int = 8,
        mmr: bool = True,
        lambda_mult: float = 0.65,
    ) -> list[RetrievedChunk]:
        query_embedding = openai_service.embed_texts([query])[0]
        fetch_k = max(top_k * 4, top_k)

        candidates = self._hybrid_candidates(
            workspace_id=workspace_id,
            query=query,
            query_embedding=query_embedding,
            fetch_k=fetch_k,
        )
        if not candidates:
            return []

        scored = self._normalize_and_score(candidates)
        if not scored:
            return []

        if not mmr or len(scored) <= top_k:
            return scored[:top_k]

        return self._mmr_select(scored, top_k=top_k, lambda_mult=lambda_mult)

    def _hybrid_candidates(
        self,
        workspace_id: str,
        query: str,
        query_embedding: list[float],
        fetch_k: int,
    ) -> list[_Candidate]:
        keyword_lang = self.settings.retrieval_keyword_language
        ts_query = func.websearch_to_tsquery(keyword_lang, query)
        keyword_rank_expr = func.ts_rank_cd(func.to_tsvector(keyword_lang, models.DocumentChunk.content), ts_query)
        distance_expr = models.DocumentChunk.embedding.cosine_distance(query_embedding)

        base_query = (
            self.db.query(
                models.DocumentChunk,
                models.Document.title,
                distance_expr.label("distance"),
                keyword_rank_expr.label("keyword_rank"),
            )
            .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
            .filter(
                models.DocumentChunk.workspace_id == workspace_id,
                models.Document.status == models.DocumentStatus.READY,
            )
        )

        vector_rows = base_query.order_by(distance_expr.asc()).limit(fetch_k).all()
        keyword_rows = base_query.filter(keyword_rank_expr > 0).order_by(keyword_rank_expr.desc()).limit(fetch_k).all()

        merged: dict[str, _Candidate] = {}
        for row in [*vector_rows, *keyword_rows]:
            chunk, title, distance, keyword_rank = row
            vector_similarity = max(0.0, 1.0 - float(distance))
            keyword_rank_val = float(keyword_rank or 0.0)

            existing = merged.get(chunk.id)
            if existing is None:
                merged[chunk.id] = _Candidate(
                    chunk=chunk,
                    title=title,
                    vector_similarity=vector_similarity,
                    keyword_rank=keyword_rank_val,
                )
                continue

            existing.vector_similarity = max(existing.vector_similarity, vector_similarity)
            existing.keyword_rank = max(existing.keyword_rank, keyword_rank_val)

        return list(merged.values())

    def _normalize_and_score(self, candidates: list[_Candidate]) -> list[RetrievedChunk]:
        vectors = [candidate.vector_similarity for candidate in candidates]
        keywords = [candidate.keyword_rank for candidate in candidates]

        vec_min, vec_max = min(vectors), max(vectors)
        key_min, key_max = min(keywords), max(keywords)

        scored: list[RetrievedChunk] = []
        for candidate in candidates:
            if injection_risk_score(candidate.chunk.content) >= 0.95:
                continue

            sanitized = sanitize_retrieved_text(candidate.chunk.content)
            if not sanitized:
                continue

            vector_norm = self._min_max(candidate.vector_similarity, vec_min, vec_max)
            keyword_norm = self._min_max(candidate.keyword_rank, key_min, key_max)
            hybrid = (
                self.settings.retrieval_vector_weight * vector_norm
                + self.settings.retrieval_keyword_weight * keyword_norm
            )

            scored.append(
                RetrievedChunk(
                    chunk_id=candidate.chunk.id,
                    document_id=candidate.chunk.document_id,
                    title=candidate.title,
                    page=candidate.chunk.page,
                    content=sanitized,
                    vector_score=vector_norm,
                    keyword_score=keyword_norm,
                    hybrid_score=hybrid,
                    embedding=list(candidate.chunk.embedding),
                )
            )

        scored.sort(key=lambda item: item.hybrid_score, reverse=True)
        return scored

    def _mmr_select(
        self,
        candidates: list[RetrievedChunk],
        top_k: int,
        lambda_mult: float,
    ) -> list[RetrievedChunk]:
        selected: list[RetrievedChunk] = []
        remaining = candidates.copy()

        selected.append(remaining.pop(0))

        while remaining and len(selected) < top_k:
            best_item: RetrievedChunk | None = None
            best_score = -float("inf")

            for item in remaining:
                relevance = item.hybrid_score
                diversity_penalty = max(self._cosine_similarity(item.embedding, s.embedding) for s in selected)
                mmr_score = lambda_mult * relevance - (1 - lambda_mult) * diversity_penalty
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = item

            if best_item is None:
                break
            selected.append(best_item)
            remaining.remove(best_item)

        return selected

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _min_max(value: float, lower: float, upper: float) -> float:
        if upper == lower:
            return 1.0 if value > 0 else 0.0
        return (value - lower) / (upper - lower)
