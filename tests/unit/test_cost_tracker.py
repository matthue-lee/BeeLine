import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from beeline_ingestor.config import AppConfig
from beeline_ingestor.costs import CostTracker
from beeline_ingestor.db import Database
from beeline_ingestor.models import DailyCost, LLMCall


def make_config(tmp_path):
    config = AppConfig()
    config.database.uri = f"sqlite+pysqlite:///{tmp_path}/costs.db"
    config.database.echo = False
    return config


def test_cost_tracker_records_llm_call(tmp_path):
    config = make_config(tmp_path)
    db = Database(config)
    db.create_all()
    tracker = CostTracker(db)

    cost = tracker.record_llm_call(
        model="gpt-4o-mini",
        operation="summarize",
        prompt_tokens=1000,
        completion_tokens=500,
        latency_ms=800,
    )

    assert cost > 0
    with db.session() as session:
        call = session.execute(select(LLMCall).order_by(LLMCall.id.desc())).scalars().first()
        assert call is not None
        assert call.total_tokens == 1500
        daily = session.get(DailyCost, (call.created_at.date(), "summarize"))
        assert daily is not None
        assert daily.total_cost_usd >= cost
