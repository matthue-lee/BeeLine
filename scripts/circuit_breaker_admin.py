#!/usr/bin/env python
"""Circuit breaker admin CLI."""
from __future__ import annotations

import argparse
import os

from beeline_ingestor.circuit_breaker import BudgetLimits, CircuitBreaker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Circuit breaker admin commands")
    parser.add_argument("operation", help="Operation name, e.g., summarize")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("reset")
    open_parser = sub.add_parser("open")
    open_parser.add_argument("--reason", required=True)
    return parser.parse_args()


def breaker_from_env(operation: str) -> CircuitBreaker:
    limits = BudgetLimits(
        hourly_usd=float(os.getenv("CIRCUIT_BREAKER_HOURLY_USD", "50")),
        daily_usd=float(os.getenv("CIRCUIT_BREAKER_DAILY_USD", "600")),
        monthly_usd=float(os.getenv("CIRCUIT_BREAKER_MONTHLY_USD", "12000")),
    )
    return CircuitBreaker("cost", redis_url=os.getenv("COST_REDIS_URL") or os.getenv("REDIS_URL"), limits=limits)


def main() -> None:
    args = parse_args()
    breaker = breaker_from_env(args.operation)
    if args.command == "status":
        print(breaker.breaker_status(args.operation))
    elif args.command == "reset":
        breaker.reset(args.operation)
        print("breaker reset")
    elif args.command == "open":
        breaker.manual_open(args.operation, args.reason)
        print("breaker manually opened")


if __name__ == "__main__":
    main()
