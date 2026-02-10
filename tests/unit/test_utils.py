from datetime import datetime, timezone
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.utils import compute_canonical_id, parse_datetime


def test_compute_canonical_id_stable():
    first = compute_canonical_id("Title", "https://example.com")
    second = compute_canonical_id("title  ", "https://EXAMPLE.com")
    assert first == second


def test_compute_canonical_id_uses_published_when_available():
    date_a = datetime(2024, 1, 1, tzinfo=timezone.utc)
    date_b = datetime(2024, 1, 2, tzinfo=timezone.utc)
    first = compute_canonical_id("Title", "https://example.com", published_at=date_a)
    second = compute_canonical_id("Different Title", "https://example.com", published_at=date_a)
    third = compute_canonical_id("Title", "https://example.com", published_at=date_b)
    assert first == second
    assert first != third


def test_parse_datetime_handles_timezone():
    dt = parse_datetime("2024-01-02T03:04:05+13:00")
    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2024-01-01T14:04:05+00:00"
