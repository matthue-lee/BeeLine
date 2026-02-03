"""Quick utility to inspect configured cross-link news feeds."""
from __future__ import annotations

import argparse
import textwrap
from typing import Sequence

import feedparser
import requests

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from beeline_ingestor.config import AppConfig


def fetch_feed(url: str, session: requests.Session, timeout: float) -> tuple[int, list[dict]]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    items: list[dict] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        items.append({"title": title, "link": link, "summary": summary})
    return len(parsed.entries), items


def test_article_access(url: str, session: requests.Session, timeout: float) -> tuple[int | None, str | None]:
    if not url:
        return None, "missing url"
    try:
        response = session.get(url, timeout=timeout)
        return response.status_code, (response.text[:200] if response.text else "<empty>")
    except requests.RequestException as exc:
        return None, f"error: {exc}"


def inspect_feeds(feeds: Sequence[str], sample: int, timeout: float) -> None:
    session = requests.Session()
    for feed_url in feeds:
        print(f"\n=== {feed_url} ===")
        try:
            total, items = fetch_feed(feed_url, session, timeout)
        except requests.RequestException as exc:
            print(f"Failed to fetch feed: {exc}")
            continue

        print(f"Total entries reported: {total}")
        for idx, item in enumerate(items[:sample], start=1):
            status, snippet = test_article_access(item["link"], session, timeout)
            snippet_preview = textwrap.shorten(snippet or "", width=120, placeholder="...") if snippet else ""
            print(f"  [{idx}] {item['title']}")
            print(f"      url: {item['link']}")
            print(f"      article status: {status}")
            if snippet_preview:
                print(f"      preview: {snippet_preview}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect cross-link news feeds and article accessibility")
    parser.add_argument("--sample", type=int, default=3, help="number of articles to fetch per feed")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout per request in seconds")
    args = parser.parse_args()

    config = AppConfig.from_env()
    inspect_feeds(config.crosslink.feeds, sample=args.sample, timeout=args.timeout)


if __name__ == "__main__":
    main()
