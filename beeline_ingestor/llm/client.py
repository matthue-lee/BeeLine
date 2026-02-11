"""LLM client wrapper for summarization."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
    from openai import APIError
except Exception:  # pragma: no cover - openai not installed
    OpenAI = None  # type: ignore[assignment]
    APIError = Exception  # type: ignore[assignment]

from pydantic import BaseModel, Field

from ..costs import CostTracker
from ..models import PromptTemplate
from ..schemas.summary import SummaryPayload
from ..summarization.guardrails import apply_guardrails

logger = logging.getLogger(__name__)


class ClaimResponseModel(BaseModel):
    text: str
    citations: list[str] = Field(default_factory=list)


class SummaryResponseModel(BaseModel):
    summary_short: str
    summary_why_matters: Optional[str] = None
    claims: list[ClaimResponseModel] = Field(default_factory=list)


@dataclass(slots=True)
class SummaryGenerationResult:
    payload: SummaryPayload
    raw_response: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    cost_usd: float | None


class SummaryValidationError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cost_tracker: CostTracker, model: str | None = None):
        self.cost_tracker = cost_tracker
        self.model = model or os.getenv("SUMMARY_MODEL", "gpt-4o-mini")
        self._client: Optional[OpenAI] = None
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        force_mock = os.getenv("LLM_MODE", "auto").lower() == "mock"
        self._simulate = force_mock or not api_key or OpenAI is None
        if not self._simulate:
            try:
                self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            except Exception:  # pragma: no cover - network config errors
                logger.exception("Unable to initialise OpenAI client, falling back to simulator")
                self._simulate = True

    def summarize(
        self,
        *,
        template: PromptTemplate,
        release_id: str,
        release_text: str,
        metadata: Dict[str, Any],
    ) -> SummaryGenerationResult:
        prompt_text = self._render_prompt(template.body, release_text=release_text, metadata=metadata)
        params = self._extract_parameters(template.metadata_json or {})
        start = perf_counter()
        if self._simulate:
            raw_response = self._simulate_completion(release_id, release_text)
            prompt_tokens = self._estimate_tokens(prompt_text)
            completion_tokens = self._estimate_tokens(json.dumps(raw_response))
            latency_ms = int((perf_counter() - start) * 1000)
        else:
            raw_response, prompt_tokens, completion_tokens, latency_ms = self._call_openai(
                prompt_text,
                template_metadata=template.metadata_json or {},
                params=params,
            )

        payload = self._parse_payload(raw_response, release_id)
        payload = apply_guardrails(payload)
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self.cost_tracker.record_llm_call(
            model=self.model,
            operation="summarize",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )
        return SummaryGenerationResult(
            payload=payload,
            raw_response=raw_response,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )

    def _render_prompt(self, template_body: str, **kwargs) -> str:
        metadata = kwargs.get('metadata') or {}
        release_text = kwargs.get('release_text') or ''
        data = {'release_text': release_text, **metadata}
        try:
            return template_body.format(**data)
        except KeyError:
            return f"Summarize the following text:\n{release_text}"

    def _extract_parameters(self, metadata: dict[str, Any]) -> dict[str, Any]:
        params = metadata.get('parameters') or {}
        return {
            'temperature': float(params.get('temperature', 0.2)),
            'max_output_tokens': int(params.get('max_output_tokens', 600)),
        }

    def _call_openai(
        self,
        prompt_text: str,
        *,
        template_metadata: dict[str, Any],
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], int, int, int]:
        if not self._client:
            raise RuntimeError("OpenAI client not initialised")
        system_prompt = template_metadata.get('system_prompt') or "You create factual, cite-backed policy summaries."
        call_start = perf_counter()
        try:
            response = self._client.responses.parse(
                model=self.model,
                temperature=params['temperature'],
                max_output_tokens=params['max_output_tokens'],
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text},
                ],
                text_format=SummaryResponseModel,
            )
        except APIError as exc:  # pragma: no cover - network error path
            logger.exception("LLM call failed")
            raise SummaryValidationError(f"LLM call failed: {exc}")
        latency_ms = int(getattr(response, "response_ms", None) or ((perf_counter() - call_start) * 1000))
        parsed_model: SummaryResponseModel = response.output_parsed  # type: ignore[assignment]
        raw = parsed_model.model_dump()
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", None)
        completion_tokens = getattr(usage, "output_tokens", None)
        if prompt_tokens is None:
            prompt_tokens = self._estimate_tokens(prompt_text)
        if completion_tokens is None:
            completion_tokens = self._estimate_tokens(json.dumps(raw))
        return raw, int(prompt_tokens), int(completion_tokens), int(latency_ms)

    def _simulate_completion(self, release_id: str, release_text: str) -> Dict[str, Any]:
        sentences = [s.strip() for s in release_text.split('.') if s.strip()]
        summary_short = '. '.join(sentences[:2])
        if not summary_short:
            summary_short = release_text[:280]
        why_matters = sentences[2] if len(sentences) > 2 else summary_short
        claim_text = sentences[0] if sentences else summary_short
        claim = {"text": claim_text, "citations": [f"{release_id}:0"]}
        return {
            "summary_short": summary_short,
            "summary_why_matters": why_matters,
            "claims": [claim],
        }

    def _estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text.split()) / 0.75))

    def _parse_payload(self, response: dict[str, Any], release_id: str) -> SummaryPayload:
        merged = {"release_id": release_id, **response}
        try:
            payload = SummaryPayload.from_dict(merged)
        except ValueError as exc:
            raise SummaryValidationError(str(exc)) from exc
        return payload
