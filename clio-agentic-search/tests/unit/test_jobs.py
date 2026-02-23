"""Tests for async job queue and cancellation token."""

from __future__ import annotations

import asyncio

import pytest

from clio_agentic_search.jobs import (
    CancellationToken,
    JobCancelledError,
    JobQueue,
    JobStatus,
)


class TestCancellationToken:
    def test_not_cancelled_by_default(self) -> None:
        token = CancellationToken()
        assert not token.is_cancelled

    def test_cancel_sets_flag(self) -> None:
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled

    def test_check_raises_when_cancelled(self) -> None:
        token = CancellationToken()
        token.cancel()
        with pytest.raises(JobCancelledError):
            token.check()

    def test_check_passes_when_not_cancelled(self) -> None:
        token = CancellationToken()
        token.check()  # should not raise


class TestJobQueue:
    def test_submit_creates_pending_job(self) -> None:
        queue = JobQueue()
        job = queue.submit("local_fs")
        assert job.status == JobStatus.PENDING
        assert job.namespace == "local_fs"
        assert not job.full_rebuild

    def test_submit_with_full_rebuild(self) -> None:
        queue = JobQueue()
        job = queue.submit("local_fs", full_rebuild=True)
        assert job.full_rebuild

    def test_get_returns_job(self) -> None:
        queue = JobQueue()
        job = queue.submit("local_fs")
        fetched = queue.get(job.job_id)
        assert fetched is job

    def test_get_returns_none_for_unknown(self) -> None:
        queue = JobQueue()
        assert queue.get("nonexistent") is None

    def test_cancel_pending_job(self) -> None:
        queue = JobQueue()
        job = queue.submit("local_fs")
        assert queue.cancel(job.job_id)
        assert job.status == JobStatus.CANCELLED
        assert job.cancellation_token.is_cancelled

    def test_cancel_completed_job_returns_false(self) -> None:
        queue = JobQueue()
        job = queue.submit("local_fs")
        job.status = JobStatus.COMPLETED
        assert not queue.cancel(job.job_id)

    def test_cancel_unknown_job_returns_false(self) -> None:
        queue = JobQueue()
        assert not queue.cancel("nonexistent")

    def test_list_jobs(self) -> None:
        queue = JobQueue()
        queue.submit("ns1")
        queue.submit("ns2")
        assert len(queue.list_jobs()) == 2

    def test_mark_completed_does_not_override_cancelled(self) -> None:
        queue = JobQueue()
        job = queue.submit("local_fs")
        queue.cancel(job.job_id)
        queue.mark_completed(job.job_id, {"indexed_files": 1})
        assert job.status == JobStatus.CANCELLED
        assert job.result is None

    @pytest.mark.asyncio
    async def test_namespace_lock_reused_per_namespace(self) -> None:
        queue = JobQueue()
        lock_a = queue.namespace_lock("local_fs")
        lock_b = queue.namespace_lock("local_fs")
        assert lock_a is lock_b
        async with lock_a:
            assert lock_b.locked()

    @pytest.mark.asyncio
    async def test_start_runs_coroutine(self) -> None:
        queue = JobQueue()
        job = queue.submit("local_fs")
        completed = False

        async def _task() -> None:
            nonlocal completed
            completed = True

        queue.start(job.job_id, _task())
        await asyncio.sleep(0.05)
        assert completed
