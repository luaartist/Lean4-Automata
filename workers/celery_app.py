"""Celery application factory for the Lean4-Automata indexing workers."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "lean4_automata",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=3600,        # 1h hard limit
    task_soft_time_limit=3300,   # 55m soft limit (gives tasks a chance to clean up)
    result_expires=86400,        # 24h
)


__all__ = ["celery_app"]
