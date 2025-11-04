from datetime import timezone

from beeline_ingestor.utils import compute_canonical_id, parse_datetime


def test_compute_canonical_id_stable():
    first = compute_canonical_id("Title", "https://example.com")
    second = compute_canonical_id("title  ", "https://EXAMPLE.com")
    assert first == second


def test_parse_datetime_handles_timezone():
    dt = parse_datetime("2024-01-02T03:04:05+13:00")
    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2024-01-01T14:04:05+00:00"
