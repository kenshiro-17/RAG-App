from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any

from huggingface_hub import InferenceClient
from openai import AsyncOpenAI, OpenAI

from app.core.config import get_settings


class OpenAIService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)
        self.hf_client = InferenceClient(api_key=settings.openai_api_key) if settings.embedding_provider == "huggingface" else None

    def embed_texts(
        self,
        texts: list[str],
        model: str | None = None,
        batch_size: int | None = None,
        max_retries: int = 5,
    ) -> list[list[float]]:
        if not texts:
            return []

        model_name = model or self.settings.embedding_model
        size = batch_size or self.settings.embedding_batch_size
        vectors: list[list[float]] = []

        for i in range(0, len(texts), size):
            batch = texts[i : i + size]
            vectors.extend(self._embed_batch_with_retry(batch, model_name, max_retries=max_retries))

        return vectors

    def _embed_batch_with_retry(self, batch: list[str], model: str, max_retries: int = 5) -> list[list[float]]:
        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                if self.settings.embedding_provider == "huggingface":
                    return self._embed_batch_with_huggingface(batch, model)
                response = self.client.embeddings.create(model=model, input=batch)
                return [item.embedding for item in response.data]
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt == max_retries - 1:
                    break
                time.sleep(delay)
                delay = min(delay * 2, 16.0)

        raise RuntimeError(f"Embedding request failed after retries: {last_exc}")

    def _embed_batch_with_huggingface(self, batch: list[str], model: str) -> list[list[float]]:
        if self.hf_client is None:
            self.hf_client = InferenceClient(api_key=self.settings.openai_api_key)

        vectors: list[list[float]] = []
        for text in batch:
            output = self.hf_client.feature_extraction(text, model=model)
            vector: list[float] | None = None
            if isinstance(output, list):
                if output and isinstance(output[0], (int, float)):
                    vector = [float(x) for x in output]
                elif output and isinstance(output[0], list):
                    vector = [float(x) for x in output[0]]
            if not vector:
                raise RuntimeError("Unexpected Hugging Face embedding response format")
            if len(vector) != self.settings.embedding_dimensions:
                raise RuntimeError(
                    f"Embedding dimension mismatch: got {len(vector)} expected {self.settings.embedding_dimensions}. "
                    "Update EMBEDDING_DIMENSIONS or choose a compatible embedding model."
                )
            vectors.append(vector)
        return vectors

    async def stream_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_retries: int = 4,
    ) -> AsyncGenerator[dict[str, Any], None]:
        model_name = model or self.settings.response_model
        delay = 1.0
        for attempt in range(max_retries):
            try:
                async with self.async_client.responses.stream(
                    model=model_name,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                ) as stream:
                    answer_parts: list[str] = []
                    async for event in stream:
                        if event.type == "response.output_text.delta":
                            delta = event.delta or ""
                            if delta:
                                answer_parts.append(delta)
                                yield {"type": "token", "token": delta}
                    final_response = await stream.get_final_response()
                    usage = self._usage_to_dict(getattr(final_response, "usage", None))
                    answer_text = "".join(answer_parts).strip()

                    if not answer_text:
                        answer_text = self._extract_text_from_response(final_response)
                        if answer_text:
                            yield {"type": "token", "token": answer_text}

                    yield {"type": "final", "answer": answer_text, "usage": usage}
                    return
            except Exception as exc:  # noqa: BLE001
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Response streaming failed: {exc}") from exc
                await asyncio.sleep(delay)
                delay = min(delay * 2, 16.0)

    async def generate_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_retries: int = 4,
    ) -> tuple[str, dict[str, int] | None]:
        model_name = model or self.settings.response_model
        delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self.async_client.responses.create(
                    model=model_name,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                answer = self._extract_text_from_response(response)
                usage = self._usage_to_dict(getattr(response, "usage", None))
                return answer, usage
            except Exception as exc:  # noqa: BLE001
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Response generation failed: {exc}") from exc
                await asyncio.sleep(delay)
                delay = min(delay * 2, 16.0)

        return "", None

    @staticmethod
    def _usage_to_dict(usage: Any) -> dict[str, int] | None:
        if usage is None:
            return None
        data: dict[str, int] = {}
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(usage, field, None)
            if isinstance(value, int):
                data[field] = value
        return data or None

    @staticmethod
    def _extract_text_from_response(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str):
            return output_text

        parts: list[str] = []
        output = getattr(response, "output", None)
        if isinstance(output, list):
            for item in output:
                content = getattr(item, "content", None)
                if isinstance(content, list):
                    for c in content:
                        if getattr(c, "type", "") == "output_text":
                            text = getattr(c, "text", "")
                            if text:
                                parts.append(text)
        return "".join(parts).strip()


openai_service = OpenAIService()
