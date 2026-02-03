"""Parallel batch processor for entity extraction jobs."""
from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Iterable, List

from .config import EntityExtractionConfig
from .datatypes import EntityExtractionResult, ExtractionJob
from .service import EntityExtractionService

logger = logging.getLogger(__name__)


class EntityExtractionBatchProcessor:
    """Execute extraction jobs concurrently with bounded resources."""

    def __init__(self, service: EntityExtractionService | None = None, config: EntityExtractionConfig | None = None):
        self.config = config or (service.config if service else EntityExtractionConfig())
        self.service = service or EntityExtractionService(self.config)

    def process(self, jobs: Iterable[ExtractionJob]) -> list[EntityExtractionResult]:
        job_list = list(jobs)
        if not job_list:
            return []

        results: list[EntityExtractionResult] = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_map: dict[Future[EntityExtractionResult], ExtractionJob] = {}
            for job in job_list:
                future = executor.submit(self.service.extract, job.text, job.source_id, job.source_type)
                future_map[future] = job

            for future in as_completed(future_map):
                job = future_map[future]
                try:
                    results.append(future.result())
                except Exception:
                    logger.exception("Entity extraction failed for %s %s", job.source_type, job.source_id)
                    results.append(
                        EntityExtractionResult(
                            source_id=job.source_id,
                            source_type=job.source_type,
                            text_length=len(job.text or ""),
                            entities=[],
                            skipped=True,
                            notes="error",
                        )
                    )
        return results
