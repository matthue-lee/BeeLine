"""Evidence retrieval utilities for claim verification."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List


SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+")
WORD_REGEX = re.compile(r"[A-Za-z']+")


@dataclass(slots=True)
class EvidenceSentence:
    sentence_index: int
    text: str
    score: float


class EvidenceRetriever:
    """Naïve hybrid retrieval (keyword overlap + order) for release sentences."""

    def __init__(self, max_sentences: int = 5):
        self.max_sentences = max(1, max_sentences)

    def retrieve(self, claim_text: str, release_text: str) -> list[EvidenceSentence]:
        sentences = self._split_sentences(release_text)
        claim_terms = self._tokenize(claim_text)
        scored: list[EvidenceSentence] = []
        for idx, text in enumerate(sentences):
            sentence_terms = self._tokenize(text)
            if not sentence_terms:
                continue
            overlap = len(claim_terms & sentence_terms)
            if overlap == 0:
                continue
            score = overlap / math.sqrt(len(sentence_terms))
            scored.append(EvidenceSentence(sentence_index=idx, text=text.strip(), score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: self.max_sentences]

    def _split_sentences(self, text: str) -> list[str]:
        cleaned = text.strip()
        if not cleaned:
            return []
        raw = SENTENCE_SPLIT_REGEX.split(cleaned)
        normalized = []
        for sentence in raw:
            snippet = sentence.strip()
            if snippet:
                normalized.append(snippet)
        return normalized

    def _tokenize(self, text: str) -> set[str]:
        terms = set()
        for match in WORD_REGEX.finditer(text.lower()):
            token = match.group(0)
            if len(token) >= 3:
                terms.add(token)
        return terms
