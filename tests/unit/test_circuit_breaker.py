import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.circuit_breaker import BudgetLimits, CircuitBreaker


class FakeRedis:
    def __init__(self):
        self.store = {}

    def incrbyfloat(self, key, amount):
        self.store[key] = float(self.store.get(key, 0.0)) + amount
        return self.store[key]

    def expire(self, key, seconds):
        return True

    def setex(self, key, ttl, value):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)

    def publish(self, channel, message):
        self.store.setdefault("pub", []).append((channel, message))


def test_circuit_breaker_opens_on_threshold(monkeypatch):
    fake = FakeRedis()

    def fake_from_url(*args, **kwargs):
        return fake

    monkeypatch.setattr('redis.Redis.from_url', lambda *args, **kwargs: fake)
    breaker = CircuitBreaker('test', redis_url='redis://localhost', limits=BudgetLimits(1.0, 2.0, 5.0))

    status = breaker.register_cost('summarize', 0.5)
    assert status == 'closed'
    status = breaker.register_cost('summarize', 0.6)
    assert status == 'open'
    assert breaker.is_open('summarize') is True
    breaker.reset('summarize')
    assert breaker.is_open('summarize') is False
