"""Async job queue for background indexing operations."""

from __future__ import annotations

import asyncio
import enum
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any


class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CancellationToken:
    """Cooperative cancellation signal checked by long-running jobs."""

    _cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        """Raise if cancellation has been requested."""
        if self._cancelled:
            raise JobCancelledError("Job was cancelled")


class JobCancelledError(Exception):
    pass


@dataclass
class JobRecord:
    job_id: str
    namespace: str
    full_rebuild: bool
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)


class JobQueue:
    """In-memory async job queue for indexing operations."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._namespace_locks: dict[str, asyncio.Lock] = {}
        self._lock = threading.RLock()

    def submit(self, namespace: str, full_rebuild: bool = False) -> JobRecord:
        job_id = uuid.uuid4().hex[:12]
        job = JobRecord(job_id=job_id, namespace=namespace, full_rebuild=full_rebuild)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return False
            job.cancellation_token.cancel()
            task = self._tasks.get(job_id)
            if task is not None and not task.done():
                task.cancel()
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            return True

    def start(self, job_id: str, coro: Any) -> None:
        task: asyncio.Task[None] = asyncio.create_task(coro)
        with self._lock:
            self._tasks[job_id] = task
        task.add_done_callback(lambda _task: self._on_task_done(job_id))

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            return list(self._jobs.values())

    def mark_running(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return job
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            return job

    def mark_completed(self, job_id: str, result: dict[str, Any]) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status == JobStatus.CANCELLED:
                return job
            job.status = JobStatus.COMPLETED
            job.result = result
            job.error = None
            job.completed_at = time.time()
            return job

    def mark_failed(self, job_id: str, error: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status == JobStatus.CANCELLED:
                return job
            job.status = JobStatus.FAILED
            job.error = error
            job.completed_at = time.time()
            return job

    def mark_cancelled(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return job
            job.cancellation_token.cancel()
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            return job

    def namespace_lock(self, namespace: str) -> asyncio.Lock:
        with self._lock:
            lock = self._namespace_locks.get(namespace)
            if lock is None:
                lock = asyncio.Lock()
                self._namespace_locks[namespace] = lock
            return lock

    def shutdown(self) -> None:
        with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
            self._jobs.clear()
            self._namespace_locks.clear()
        for task in tasks:
            with suppress(Exception):
                if not task.done():
                    task.cancel()

    def _on_task_done(self, job_id: str) -> None:
        with self._lock:
            self._tasks.pop(job_id, None)


# Module-level singleton for use across the app.
_global_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    global _global_queue  # noqa: PLW0603
    if _global_queue is None:
        _global_queue = JobQueue()
    return _global_queue


def reset_job_queue() -> None:
    global _global_queue  # noqa: PLW0603
    if _global_queue is None:
        return
    _global_queue.shutdown()
    _global_queue = None
