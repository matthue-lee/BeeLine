"""HTML content cleaning utilities."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from ..utils import parse_datetime

logger = logging.getLogger(__name__)

PARAGRAPH_SEP = "\n\n"


@dataclass(slots=True)
class CleanResult:
    """Structured output from the cleaning stage."""

    text: Optional[str]
    word_count: int
    excerpt: Optional[str] = None
    removed_sections: list[str] = field(default_factory=list)
    metadata: dict[str, list[str]] = field(default_factory=dict)


class ContentCleaner:
    """Convert raw HTML into normalized plain text."""

    def __init__(self) -> None:
        self.removal_selectors = [
            "div.share",
            "div.sharing",
            "div.social-links",
            "div.tags",
            "ul.breadcrumb",
            "div.print-links",
            "div.block-share",
            "div.field--name-field-related-releases",
            "section.related-content",
        ]
        self.footer_patterns = [
            re.compile(r"Released by .+", re.IGNORECASE),
            re.compile(r"Media Contact", re.IGNORECASE),
            re.compile(r"ENDS$", re.IGNORECASE),
        ]
        self.metadata_selectors = {
            "ministers": [
                "div.field--name-field-minister",
                "div.field--name-field-ministers",
                "div.field--name-field-associated-ministers",
                "div.field.minister__title",
                ".minister__title",
            ],
            "tags": [
                "div.field--name-field-tags",
                "div.field--name-field-category",
                "div.field--name-field-categories",
                "div.tags",
                ".tag--portfolio",
                ".meta__tags",
            ],
        }
        self.date_selectors = [
            "div.field--name-field-date",
            "div.field--name-field-release-date",
            "div.field--name-field-date-of-release",
            "div.release-info__date",
            "div.release-date",
            "p.release-date",
            "span.date-display-single",
            "time.meta__date",
        ]
        self.date_meta_attributes = [
            {"property": "article:published_time"},
            {"property": "og:published_time"},
            {"name": "dcterms.available"},
            {"name": "DC.date.issued"},
        ]

    def clean(self, html: Optional[str]) -> CleanResult:
        """Return cleaned content and word count from HTML input."""

        if not html:
            return CleanResult(text=None, word_count=0)

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()

        article_node = soup.find("article")
        if article_node is None:
            candidates = soup.select("div.field--name-body, div.content, main, section")
            article_node = max(candidates, key=lambda c: len(c.get_text(" ").strip()), default=soup)

        removed_sections: list[str] = []
        metadata: dict[str, list[str]] = {}
        published_at = self._extract_published_at(article_node, soup)
        if published_at:
            metadata["published_at"] = [published_at.isoformat()]
        for key, selectors in self.metadata_selectors.items():
            items: list[str] = []
            for selector in selectors:
                for node in article_node.select(selector):
                    items.extend(_extract_items(node))
                    removed_sections.append(selector)
                    node.decompose()
            if items:
                metadata[key] = items
        for selector in self.removal_selectors:
            for node in article_node.select(selector):
                removed_sections.append(selector)
                node.decompose()

        # Remove inline styles that often contain navigation text.
        for attr in ("style", "class", "id"):
            for tag in article_node.find_all(attrs={attr: True}):
                if attr == "style":
                    del tag[attr]

        text = article_node.get_text("\n", strip=True)
        text = self._strip_footer(_normalise_whitespace(text))
        word_count = len(text.split()) if text else 0
        excerpt = None
        if text:
            excerpt = text.split(PARAGRAPH_SEP)[0][:400]
        return CleanResult(
            text=text if text else None,
            word_count=word_count,
            excerpt=excerpt,
            removed_sections=removed_sections,
            metadata=metadata,
        )

    def _strip_footer(self, value: str) -> str:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        while lines and any(pattern.search(lines[-1]) for pattern in self.footer_patterns):
            lines.pop()
        return PARAGRAPH_SEP.join(lines)

    def _extract_published_at(self, article_node, soup) -> datetime | None:
        """Detect the published timestamp from page metadata."""

        for attrs in self.date_meta_attributes:
            tag = soup.find("meta", attrs=attrs)
            value = tag.get("content") if tag else None
            parsed = parse_datetime(value)
            if parsed:
                return parsed

        for selector in ("time[datetime]", "time[itemprop='datePublished']", "time[property='article:published_time']"):
            for node in article_node.select(selector):
                parsed = parse_datetime(node.get("datetime"))
                if parsed:
                    return parsed

        for selector in self.date_selectors:
            for node in article_node.select(selector):
                text = node.get_text(" ", strip=True)
                parsed = parse_datetime(text)
                if parsed:
                    return parsed
        return None


def _normalise_whitespace(value: str) -> str:
    """Collapse repeated whitespace while preserving paragraph breaks."""

    # Replace carriage returns and non-breaking spaces for predictability.
    value = value.replace("\r", "\n").replace("\xa0", " ")
    # Collapse multiple line breaks to two newlines to preserve paragraphs.
    value = re.sub(r"\n{3,}", "\n\n", value)
    # Remove trailing spaces on each line.
    value = "\n".join(line.strip() for line in value.splitlines())
    # Collapse multiple spaces.
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def _extract_items(node) -> list[str]:
    items: list[str] = []
    for child in node.select(".field__item"):
        text = child.get_text(" ", strip=True)
        if text:
            items.append(text)
    if items:
        return items
    text = node.get_text(" ", strip=True)
    return [text] if text else []
