"""Cost tracking utilities for LLM and external API calls."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import redis
from sqlalchemy import select

from .db import Database
from .models import DailyCost, LLMCall
from .circuit_breaker import CircuitBreaker, BudgetLimits, CircuitOpenError


@dataclass(slots=True)
class ModelPricing:
    """Model pricing in USD per 1k tokens."""
    prompt_cost_per_1k: float
    completion_cost_per_1k: float
    cached_prompt_cost_per_1k: float = 0.0


def _per_million_to_per_1k(x: float) -> float:
    """Convert $/1M tokens to $/1k tokens."""
    return x / 1000.0


# Minimal sensible set (no images):
# - gpt-5-nano: ultra-cheap routing/classification
# - gpt-5-mini: cheap workhorse
# - gpt-5: high-quality general
# - gpt-4o-mini: cheap UI/chat/fallback
# - o3: mid-priced reasoning specialist
DEFAULT_MODEL_PRICING: dict[str, ModelPricing] = {
    "gpt-5-nano": ModelPricing(
        prompt_cost_per_1k=_per_million_to_per_1k(0.05),
        cached_prompt_cost_per_1k=_per_million_to_per_1k(0.005),
        completion_cost_per_1k=_per_million_to_per_1k(0.40),
    ),
    "gpt-5-mini": ModelPricing(
        prompt_cost_per_1k=_per_million_to_per_1k(0.25),
        cached_prompt_cost_per_1k=_per_million_to_per_1k(0.025),
        completion_cost_per_1k=_per_million_to_per_1k(2.00),
    ),
    "gpt-5": ModelPricing(
        prompt_cost_per_1k=_per_million_to_per_1k(1.25),
        cached_prompt_cost_per_1k=_per_million_to_per_1k(0.125),
        completion_cost_per_1k=_per_million_to_per_1k(10.00),
    ),
    "gpt-4o-mini": ModelPricing(
        prompt_cost_per_1k=_per_million_to_per_1k(0.15),
        cached_prompt_cost_per_1k=_per_million_to_per_1k(0.075),
        completion_cost_per_1k=_per_million_to_per_1k(0.60),
    ),
    "o3": ModelPricing(
        prompt_cost_per_1k=_per_million_to_per_1k(2.00),
        cached_prompt_cost_per_1k=_per_million_to_per_1k(0.50),
        completion_cost_per_1k=_per_million_to_per_1k(8.00),
    ),
}


class CostTracker:
    """Persist per-call cost data and publish aggregated counters."""

    def __init__(self, database: Database, redis_url: Optional[str] = None):
        self.database = database
        self.redis_url = redis_url or os.getenv("COST_REDIS_URL") or os.getenv("REDIS_URL")
        self.redis: redis.Redis | None = None
        if self.redis_url:
            self.redis = redis.Redis.from_url(self.redis_url, decode_responses=True)

        breaker_enabled = os.getenv("ENABLE_COST_BREAKER", "1") == "1"
        self.breaker: CircuitBreaker | None = None
        if breaker_enabled and self.redis_url:
            limits = BudgetLimits(
                hourly_usd=float(os.getenv("CIRCUIT_BREAKER_HOURLY_USD", "50")),
                daily_usd=float(os.getenv("CIRCUIT_BREAKER_DAILY_USD", "600")),
                monthly_usd=float(os.getenv("CIRCUIT_BREAKER_MONTHLY_USD", "12000")),
            )
            self.breaker = CircuitBreaker("cost", redis_url=self.redis_url, limits=limits)

        # Optional overrides via env var.
        # Format: {"model-name": {"prompt": 0.001, "completion": 0.002, "cached_prompt": 0.0001}}
        # Values are USD per 1k tokens.
        pricing_override = os.getenv("MODEL_PRICING_JSON")
        if pricing_override:
            try:
                overrides = json.loads(pricing_override)
                self.model_pricing = DEFAULT_MODEL_PRICING.copy()
                for model, prices in overrides.items():
                    self.model_pricing[model] = ModelPricing(
                        prompt_cost_per_1k=float(prices["prompt"]),
                        completion_cost_per_1k=float(prices.get("completion", prices["prompt"])),
                        cached_prompt_cost_per_1k=float(prices.get("cached_prompt", 0.0)),
                    )
            except json.JSONDecodeError:
                self.model_pricing = DEFAULT_MODEL_PRICING
        else:
            self.model_pricing = DEFAULT_MODEL_PRICING

    def record_llm_call(
        self,
        *,
        model: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        job_run_id: Optional[int] = None,
        cost_usd_override: Optional[float] = None,
        cached_prompt_tokens: int = 0,
    ) -> float:
        """Persist call metadata and update aggregates."""

        if self.breaker:
            self.breaker.ensure_can_proceed(operation)

        cost_usd = cost_usd_override or self._estimate_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
        )
        total_tokens = prompt_tokens + completion_tokens
        created_at = datetime.now(timezone.utc)

        with self.database.session() as session:
            call = LLMCall(
                job_run_id=job_run_id,
                model=model,
                operation=operation,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )
            session.add(call)
            self._upsert_daily_cost(session, created_at.date(), operation, cost_usd, total_tokens)

        self._increment_redis_counters(operation, cost_usd, created_at)

        if self.breaker:
            status = self.breaker.register_cost(operation, cost_usd)
            if status == "open":
                raise CircuitOpenError(operation, f"Breaker opened for {operation}")

        return cost_usd

    def record_external_call(
        self,
        *,
        provider: str,
        operation: str,
        cost_usd: float,
        latency_ms: int,
        job_run_id: Optional[int] = None,
    ) -> None:
        """Record costs for non-LLM APIs (e.g., News API)."""

        with self.database.session() as session:
            call = LLMCall(
                job_run_id=job_run_id,
                model=provider,
                operation=operation,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )
            session.add(call)
            self._upsert_daily_cost(session, datetime.now(timezone.utc).date(), operation, cost_usd, 0)

        now = datetime.now(timezone.utc)
        self._increment_redis_counters(operation, cost_usd, now)

        if self.breaker:
            status = self.breaker.register_cost(operation, cost_usd)
            if status == "open":
                raise CircuitOpenError(operation, f"Breaker opened for {operation}")

    def _estimate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int = 0,
    ) -> float:
        pricing = self.model_pricing.get(model)
        if not pricing:
            return 0.0

        # Clamp to avoid negative values
        prompt = max(0, int(prompt_tokens))
        completion = max(0, int(completion_tokens))
        cached = max(0, int(cached_prompt_tokens))

        # If cached tokens are reported, they are typically a subset of prompt tokens.
        # Avoid double charging by billing (prompt - cached) at prompt rate.
        billable_prompt = max(0, prompt - cached)

        prompt_cost = (billable_prompt / 1000) * pricing.prompt_cost_per_1k
        cached_cost = (cached / 1000) * pricing.cached_prompt_cost_per_1k
        completion_cost = (completion / 1000) * pricing.completion_cost_per_1k

        return round(prompt_cost + cached_cost + completion_cost, 6)

    def _upsert_daily_cost(
        self,
        session,
        date_key,
        operation: str,
        cost_usd: float,
        total_tokens: int,
    ) -> None:
        record = session.get(DailyCost, (date_key, operation))
        if record:
            record.total_calls += 1
            record.total_tokens += total_tokens
            record.total_cost_usd += cost_usd
        else:
            record = DailyCost(
                date=date_key,
                operation=operation,
                total_calls=1,
                total_tokens=total_tokens,
                total_cost_usd=cost_usd,
            )
            session.add(record)

    def _increment_redis_counters(self, operation: str, amount: float, timestamp: datetime) -> None:
        if not self.redis or amount == 0:
            return
        hour_key = f"cost:hour:{operation}:{timestamp.strftime('%Y%m%d%H')}"
        day_key = f"cost:day:{operation}:{timestamp.strftime('%Y%m%d')}"
        pipe = self.redis.pipeline()
        pipe.incrbyfloat(hour_key, amount)
        pipe.expire(hour_key, 60 * 60 * 2)
        pipe.incrbyfloat(day_key, amount)
        pipe.expire(day_key, 60 * 60 * 48)
        pipe.execute()

    def list_recent_costs(self, limit: int = 50):
        with self.database.session() as session:
            stmt = select(LLMCall).order_by(LLMCall.id.desc()).limit(limit)
            return session.execute(stmt).scalars().all()

    def close(self) -> None:
        if self.redis:
            self.redis.close()