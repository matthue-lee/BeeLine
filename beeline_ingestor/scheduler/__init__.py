"""Scheduler package for periodic ingestion jobs."""

from .service import main as run_scheduler

__all__ = ["run_scheduler"]
