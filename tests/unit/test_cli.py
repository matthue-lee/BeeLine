import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor import cli


class DummyPipeline:
    def __init__(self):
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)


def test_parse_datetime_handles_naive_input():
    value = cli._parse_datetime("2024-01-01T00:00:00")
    assert value.tzinfo == timezone.utc


def test_run_backfill_windows_iterates_windows(monkeypatch):
    pipeline = DummyPipeline()
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 3, tzinfo=timezone.utc)

    cli.run_backfill_windows(
        pipeline,
        start=start,
        end=end,
        window_days=1,
        sleep_seconds=0.0,
        limit=10,
    )

    assert len(pipeline.calls) == 2
    assert pipeline.calls[0]["source"] == "backfill"
    assert pipeline.calls[0]["limit"] == 10
