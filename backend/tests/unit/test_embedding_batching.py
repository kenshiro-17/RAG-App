from __future__ import annotations

from typing import Any

from app.services.openai_service import OpenAIService


class FakeEmbeddingsClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.failures_remaining = 0

    def create(self, model: str, input: list[str]) -> Any:  # noqa: A002
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise RuntimeError("temporary openai error")

        self.calls.append(input)

        class DataItem:
            def __init__(self, idx: int) -> None:
                self.embedding = [float(idx), 0.0, 0.0]

        class Response:
            data = [DataItem(i) for i in range(len(input))]

        return Response()


class FakeOpenAIClient:
    def __init__(self, embeddings_client: FakeEmbeddingsClient) -> None:
        self.embeddings = embeddings_client


def test_embedding_batching(monkeypatch) -> None:
    service = OpenAIService()
    service.settings.embedding_provider = "openai"
    fake_embeddings = FakeEmbeddingsClient()
    service.client = FakeOpenAIClient(fake_embeddings)  # type: ignore[assignment]

    vectors = service.embed_texts(["a", "b", "c", "d", "e"], batch_size=2)

    assert len(vectors) == 5
    assert len(fake_embeddings.calls) == 3
    assert fake_embeddings.calls[0] == ["a", "b"]


def test_embedding_retry(monkeypatch) -> None:
    service = OpenAIService()
    service.settings.embedding_provider = "openai"
    fake_embeddings = FakeEmbeddingsClient()
    fake_embeddings.failures_remaining = 2
    service.client = FakeOpenAIClient(fake_embeddings)  # type: ignore[assignment]

    vectors = service.embed_texts(["one"], batch_size=1, max_retries=4)

    assert len(vectors) == 1
    assert len(fake_embeddings.calls) == 1
