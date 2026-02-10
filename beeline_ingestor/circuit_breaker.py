"""Sliding-window circuit breaker for cost controls."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

import redis


@dataclass(slots=True)
class BudgetLimits:
    hourly_usd: float
    daily_usd: float
    monthly_usd: float


DEFAULT_LIMITS = BudgetLimits(hourly_usd=50.0, daily_usd=600.0, monthly_usd=12000.0)


class CircuitBreaker:
    """Tracks spend and opens a breaker when configured limits are exceeded."""

    def __init__(self, name: str, redis_url: Optional[str] = None, limits: BudgetLimits = DEFAULT_LIMITS):
        self.name = name
        self.redis_url = redis_url or os.getenv("COST_REDIS_URL") or os.getenv("REDIS_URL")
        if not self.redis_url:
            raise RuntimeError("CircuitBreaker requires REDIS_URL or COST_REDIS_URL")
        self.redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
        self.limits = limits
        self.cooldown_seconds = int(os.getenv("CB_COOLDOWN_SECONDS", "1800"))

    def is_open(self, operation: str) -> bool:
        key = self._breaker_key(operation)
        raw = self.redis.get(key)
        if not raw:
            return False
        if raw == "open":
            return True
        try:
            payload = json.loads(raw)
            return payload.get("status") == "open"
        except json.JSONDecodeError:
            return False

    def ensure_can_proceed(self, operation: str) -> None:
        if self.is_open(operation):
            raise CircuitOpenError(operation, f"breaker open for {operation}")

    def register_cost(self, operation: str, amount_usd: float) -> str:
        """Return breaker status after registering a cost event."""

        hour_total = self._increment_window(operation, "hour", amount_usd, expiry=3600)
        day_total = self._increment_window(operation, "day", amount_usd, expiry=86400)
        month_total = self._increment_window(operation, "month", amount_usd, expiry=86400 * 31)

        if hour_total >= self.limits.hourly_usd:
            self._open_breaker(operation, f"hourly limit exceeded: ${hour_total:.2f}")
            return "open"
        if day_total >= self.limits.daily_usd:
            self._open_breaker(operation, f"daily limit exceeded: ${day_total:.2f}")
            return "open"
        if month_total >= self.limits.monthly_usd:
            self._open_breaker(operation, f"monthly limit exceeded: ${month_total:.2f}")
            return "open"
        return "closed"

    def _increment_window(self, operation: str, window: str, amount: float, expiry: int) -> float:
        key = f"cost:{window}:{operation}:{self._window_suffix(window)}"
        new_total = self.redis.incrbyfloat(key, amount)
        self.redis.expire(key, expiry)
        return float(new_total)

    def _window_suffix(self, window: str) -> str:
        now = time.gmtime()
        if window == "hour":
            return time.strftime("%Y%m%d%H", now)
        if window == "day":
            return time.strftime("%Y%m%d", now)
        if window == "month":
            return time.strftime("%Y%m", now)
        raise ValueError(f"Unknown window {window}")

    def _breaker_key(self, operation: str) -> str:
        return f"breaker:{self.name}:{operation}"

    def _open_breaker(self, operation: str, reason: str) -> None:
        key = self._breaker_key(operation)
        payload = json.dumps({"status": "open", "reason": reason, "opened_at": time.time()})
        self.redis.setex(key, self.cooldown_seconds, payload)
        self.redis.publish("alerts", f"breaker_open:{self.name}:{operation}:{reason}")

    def reset(self, operation: str) -> None:
        key = self._breaker_key(operation)
        self.redis.delete(key)
        self.redis.publish("alerts", f"breaker_reset:{self.name}:{operation}")

    def manual_open(self, operation: str, reason: str) -> None:
        self._open_breaker(operation, reason)

    def breaker_status(self, operation: str) -> dict[str, str]:
        key = self._breaker_key(operation)
        raw = self.redis.get(key)
        if not raw:
            return {"status": "closed"}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"status": raw}
        return payload


class CircuitOpenError(RuntimeError):
    def __init__(self, operation: str, message: str):
        super().__init__(message)
        self.operation = operation
