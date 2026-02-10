"""LLM client wrapper for summarization."""
from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Dict

from ..costs import CostTracker
from ..models import PromptTemplate
from ..schemas.summary import SummaryPayload, ClaimPayload
from ..summarization.guardrails import apply_guardrails


class LLMClient:
    def __init__(self, cost_tracker: CostTracker, model: str = None):
        self.cost_tracker = cost_tracker
        self.model = model or os.getenv("SUMMARY_MODEL", "gpt-4o-mini")

    def summarize(self, *, template: PromptTemplate, release_id: str, release_text: str, metadata: Dict[str, Any]) -> SummaryPayload:
        prompt_text = self._render_prompt(template.body, release_text=release_text, metadata=metadata)
        start = time.perf_counter()
        response = self._simulate_completion(release_id, release_text)
        payload = SummaryPayload(
            release_id=release_id,
            summary_short=response['summary_short'],
            summary_why_matters=response.get('summary_why_matters'),
            claims=[ClaimPayload(**claim) for claim in response.get('claims', [])],
        )
        payload.validate()
        payload = apply_guardrails(payload)
        duration_ms = int((time.perf_counter() - start) * 1000)
        prompt_tokens = self._estimate_tokens(prompt_text)
        completion_tokens = self._estimate_tokens(json.dumps(response))
        self.cost_tracker.record_llm_call(
            model=self.model,
            operation="summarize",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=duration_ms,
        )
        return payload

    def _render_prompt(self, template_body: str, **kwargs) -> str:
        metadata = kwargs.get('metadata') or {}
        release_text = kwargs.get('release_text') or ''
        data = {'release_text': release_text, **metadata}
        try:
            return template_body.format(**data)
        except KeyError:
            return f"Summarize the following text:\n{release_text}"

    def _simulate_completion(self, release_id: str, release_text: str) -> Dict[str, Any]:
        sentences = [s.strip() for s in release_text.split('.') if s.strip()]
        summary_short = '. '.join(sentences[:2])
        if not summary_short:
            summary_short = release_text[:280]
        why_matters = sentences[2] if len(sentences) > 2 else summary_short
        claim_text = sentences[0] if sentences else summary_short
        claim = {"text": claim_text, "citations": ["release"]}
        return {
            "summary_short": summary_short,
            "summary_why_matters": why_matters,
            "claims": [claim],
        }

    def _estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text.split()) / 0.75))
