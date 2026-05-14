"""Celery task definitions for the Lean4-Automata indexing pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.config import settings
from parser.scanner import FullScanner, _normalise_psycopg_dsn

logger = get_task_logger(__name__)


@shared_task(bind=True, name="lean4.full_scan", max_retries=2)
def full_scan_task(self, project_id: str | int, root_dir: str) -> dict[str, Any]:
    """Run a full scan of ``root_dir`` for the given project.

    Parameters
    ----------
    project_id:
        Integer project id (passed as string from the HTTP API; converted here).
    root_dir:
        Filesystem path to the Lean source root to index.
    """
    try:
        pid = int(project_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"project_id must be an integer, got {project_id!r}") from exc

    logger.info(
        "Starting full scan task=%s project=%s root=%s",
        self.request.id,
        pid,
        root_dir,
    )
    scanner = FullScanner(
        project_id=pid,
        root_dir=Path(root_dir),
        db_url=settings.DATABASE_URL,
        redis_url=settings.REDIS_URL,
    )
    return scanner.run()


@shared_task(bind=True, name="lean4.refresh_materialized_views")
def refresh_views_task(self) -> dict[str, Any]:
    """Refresh the aggregated metric materialized views.

    The Phase-1 schema does not declare unique indexes on the MVs, so a
    plain (non-CONCURRENT) refresh is required.
    """
    dsn = _normalise_psycopg_dsn(settings.DATABASE_URL)
    refreshed: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        for mv in ("dependency_stats", "module_metrics"):
            cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
            refreshed.append(mv)
    logger.info("Refreshed materialized views: %s", refreshed)
    return {"refreshed": refreshed, "task_id": self.request.id}


__all__ = ["full_scan_task", "refresh_views_task"]
