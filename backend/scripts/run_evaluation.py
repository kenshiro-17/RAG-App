from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.eval.dataset import load_eval_dataset
from app.eval.harness import EvaluationHarness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAG evaluation harness")
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--top-k", type=int, default=8, help="Retrieval top-k")
    parser.add_argument("--disable-mmr", action="store_true", help="Disable MMR reranking")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_eval_dataset(args.dataset)

    db = SessionLocal()
    try:
        harness = EvaluationHarness(db=db, top_k=args.top_k, mmr=not args.disable_mmr)
        report = harness.run(cases)
        print(json.dumps(report, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
