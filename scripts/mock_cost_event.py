#!/usr/bin/env python
"""Emit a synthetic cost event for development/testing."""
from __future__ import annotations

import argparse

from beeline_ingestor.config import AppConfig
from beeline_ingestor.costs import CostTracker
from beeline_ingestor.db import Database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record a synthetic LLM cost event")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--operation", default="summarize")
    parser.add_argument("--prompt-tokens", type=int, default=500)
    parser.add_argument("--completion-tokens", type=int, default=200)
    parser.add_argument("--latency-ms", type=int, default=1200)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig.from_env()
    database = Database(config)
    database.create_all()
    tracker = CostTracker(database)
    cost = tracker.record_llm_call(
        model=args.model,
        operation=args.operation,
        prompt_tokens=args.prompt_tokens,
        completion_tokens=args.completion_tokens,
        latency_ms=args.latency_ms,
    )
    print(f"Recorded cost event for {args.operation}: ${cost:.4f}")


if __name__ == "__main__":
    main()
