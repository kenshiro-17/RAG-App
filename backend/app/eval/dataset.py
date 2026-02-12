from __future__ import annotations

import json
from pathlib import Path

from app.eval.types import EvalCase


def load_eval_dataset(path: str | Path) -> list[EvalCase]:
    dataset_path = Path(path)
    cases: list[EvalCase] = []

    with dataset_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            cases.append(
                EvalCase(
                    workspace_id=payload["workspace_id"],
                    question=payload["question"],
                    relevant_chunk_ids=payload.get("relevant_chunk_ids", []),
                    should_refuse=bool(payload.get("should_refuse", False)),
                )
            )

    return cases
