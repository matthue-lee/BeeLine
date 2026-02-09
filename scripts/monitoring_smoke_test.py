"""Smoke test utilities for the monitoring stack."""
from __future__ import annotations

import argparse
import os
import sys
import time

import requests
from sentry_sdk import capture_message, init as sentry_init


def check_metrics_endpoint(url: str, timeout: float = 5.0) -> bool:
    """Fetch the metrics endpoint and ensure required gauges are present."""

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    body = response.text
    required_metrics = ("beeline_releases_total", "beeline_ingestion_runs_total")
    missing = [metric for metric in required_metrics if metric not in body]
    if missing:
        print(f"Metrics endpoint responded but missing: {', '.join(missing)}")
        return False
    print(f"Metrics OK ({len(body)} bytes from {url})")
    return True


def emit_sentry_event(environment: str) -> bool:
    """Emit a simple Sentry marker event for validation."""

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        print("SENTRY_DSN is not configured; skipping Sentry event emission")
        return False

    sentry_init(dsn=dsn, environment=environment, traces_sample_rate=0.0)
    message = f"Monitoring smoke test at {time.time()}"
    capture_message(message)
    print("Synthetic Sentry event emitted")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate monitoring setup")
    parser.add_argument(
        "--metrics-url",
        default="http://localhost:58000/metrics",
        help="URL for the metrics endpoint (default: %(default)s)",
    )
    parser.add_argument(
        "--sentry-environment",
        default=os.getenv("SENTRY_ENVIRONMENT", "development"),
        help="Environment name for Sentry events",
    )
    parser.add_argument(
        "--emit-sentry-event",
        action="store_true",
        help="Emit a synthetic Sentry message for validation",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok = check_metrics_endpoint(args.metrics_url)
    if args.emit_sentry_event:
        ok = emit_sentry_event(args.sentry_environment) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
