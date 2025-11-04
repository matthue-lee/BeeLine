"""HTML content cleaning utilities."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PARAGRAPH_SEP = "\n\n"


@dataclass(slots=True)
class CleanResult:
    """Structured output from the cleaning stage."""

    text: Optional[str]
    word_count: int


class ContentCleaner:
    """Convert raw HTML into normalized plain text."""

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

        text = article_node.get_text("\n", strip=True)
        text = _normalise_whitespace(text)
        word_count = len(text.split()) if text else 0
        return CleanResult(text=text if text else None, word_count=word_count)


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
