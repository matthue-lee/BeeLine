"""Background scheduler for release + news ingestion jobs."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Callable, Optional

from prometheus_client import start_http_server
from sqlalchemy import select

from ..config import AppConfig
from ..crosslink.news_ingestor import NewsIngestor
from ..db import Database
from ..ingestion import IngestionPipeline
from ..models import JobRun
from ..observability import (
    REGISTRY,
    init_sentry,
    record_scheduler_job_completion,
    record_scheduler_job_skip,
    record_scheduler_job_start,
)

logger = logging.getLogger(__name__)

JOB_RELEASE = "release_ingest"
JOB_NEWS = "news_ingest"


@dataclass(slots=True)
class ScheduledJob:
    """Runtime metadata for a scheduled job."""

    name: str
    interval_seconds: float
    initial_delay_seconds: float
    runner: Callable[[], dict]


class SchedulerService:
    """Executes configured jobs on cadences defined in `AppConfig.scheduler`."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.database = Database(config)
        self.database.create_all()
        self.pipeline: IngestionPipeline | None = None
        self.news_ingestor: NewsIngestor | None = None
        self.jobs: list[ScheduledJob] = []

        if config.scheduler.release_ingest.enabled:
            self.pipeline = IngestionPipeline(config)
            self.jobs.append(
                ScheduledJob(
                    name=JOB_RELEASE,
                    interval_seconds=config.scheduler.release_ingest.interval.total_seconds(),
                    initial_delay_seconds=config.scheduler.release_ingest.initial_delay.total_seconds(),
                    runner=self._run_release_ingestion,
                )
            )

        if config.scheduler.news_ingest.enabled:
            self.news_ingestor = NewsIngestor(config)
            self.jobs.append(
                ScheduledJob(
                    name=JOB_NEWS,
                    interval_seconds=config.scheduler.news_ingest.interval.total_seconds(),
                    initial_delay_seconds=config.scheduler.news_ingest.initial_delay.total_seconds(),
                    runner=self._run_news_ingestion,
                )
            )

    async def run(self) -> None:
        """Start the scheduler loops for enabled jobs."""

        if not self.config.scheduler.enabled:
            logger.info("Scheduler disabled via SCHEDULER_ENABLED=0; exiting")
            return

        start_http_server(self.config.scheduler.metrics_port, registry=REGISTRY)
        logger.info(
            "Scheduler metrics server listening on 0.0.0.0:%s",
            self.config.scheduler.metrics_port,
        )

        if not self.jobs:
            logger.warning("No scheduler jobs enabled; idling")
            stopper = asyncio.Event()
            await stopper.wait()
            return

        tasks = [asyncio.create_task(self._job_loop(job)) for job in self.jobs]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()

    async def _job_loop(self, job: ScheduledJob) -> None:
        if job.initial_delay_seconds > 0:
            await asyncio.sleep(job.initial_delay_seconds)

        while True:
            next_run_epoch = (datetime.now(timezone.utc) + timedelta(seconds=job.interval_seconds)).timestamp()
            await self._execute_job(job, next_run_epoch)
            await asyncio.sleep(job.interval_seconds)

    async def _execute_job(self, job: ScheduledJob, next_run_epoch: float) -> None:
        if self._has_running_instance(job.name):
            logger.warning("Job %s skipped because another run is active", job.name)
            record_scheduler_job_skip(job.name, "already_running", next_run_epoch)
            return

        params = {"interval_seconds": job.interval_seconds}
        run_record = self._create_job_run(job.name, params)
        status = "completed"
        error_message: Optional[str] = None
        result_payload: Optional[dict] = None
        started = perf_counter()
        record_scheduler_job_start(job.name, next_run_epoch)

        try:
            logger.info("Starting scheduled job %s", job.name)
            result_payload = await asyncio.to_thread(job.runner)
        except Exception as exc:  # pragma: no cover - defensive logging
            status = "failed"
            error_message = str(exc)
            logger.exception("Scheduled job %s failed", job.name)
        finally:
            duration = perf_counter() - started
            self._finalise_job_run(run_record, status, duration, result_payload, error_message)
            record_scheduler_job_completion(job.name, status, duration_seconds=duration)

    def _has_running_instance(self, job_type: str) -> bool:
        with self.database.session() as session:
            stmt = select(JobRun.id).where(JobRun.job_type == job_type, JobRun.status == "running")
            return session.execute(stmt).first() is not None

    def _create_job_run(self, job_type: str, params: dict) -> JobRun:
        run = JobRun(job_type=job_type, status="running", params=params)
        with self.database.session() as session:
            session.add(run)
            session.flush()
            session.refresh(run)
            return run

    def _finalise_job_run(
        self,
        run: JobRun,
        status: str,
        duration_seconds: float,
        result: Optional[dict],
        error_message: Optional[str],
    ) -> None:
        with self.database.session() as session:
            persisted = session.get(JobRun, run.id)
            if persisted is None:
                return
            persisted.status = status
            persisted.duration_ms = int(duration_seconds * 1000)
            persisted.finished_at = datetime.now(timezone.utc)
            persisted.result = result
            persisted.error_message = error_message

    def _run_release_ingestion(self) -> dict:
        if not self.pipeline:
            raise RuntimeError("Release ingestion pipeline not configured")
        lookback = self.config.scheduler.release_ingest.lookback
        since = datetime.now(timezone.utc) - lookback
        result = self.pipeline.run(since=since, source=self.config.scheduler.release_ingest.source_label)
        return {
            "run_id": result.run_id,
            "total": result.total_items,
            "inserted": result.inserted,
            "updated": result.updated,
            "skipped": result.skipped,
            "failed": result.failed,
        }

    def _run_news_ingestion(self) -> dict:
        if not self.news_ingestor:
            raise RuntimeError("News ingestion not configured")
        result = self.news_ingestor.run()
        return asdict(result)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    config = AppConfig.from_env()
    init_sentry(
        config.sentry_dsn,
        environment=config.sentry_environment,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
    )
    service = SchedulerService(config)
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown path
        logger.info("Scheduler interrupted; exiting")


if __name__ == "__main__":
    main()
