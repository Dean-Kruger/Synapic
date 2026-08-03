"""
Unit Tests for DaemonThreadPoolExecutor
=======================================

These tests pin down the executor lifecycle guarantees that the parallel
processing pipeline relies on:

- ``shutdown(cancel_futures=True)`` cancels queued, not-yet-started work while
  letting already-running tasks finish (matching ``concurrent.futures``).
- ``shutdown()`` with the default ``cancel_futures=False`` drains everything.
- Shutdown is idempotent, and ``submit`` after shutdown raises.
- Task exceptions propagate through futures; ``map`` preserves order.
"""

import threading

import pytest

from src.utils.concurrency import DaemonThreadPoolExecutor


def _start_two_tasks(executor, n_items):
    """
    Submit ``n_items`` tasks to a 2-worker executor and block until exactly two
    are in flight.  Returns (futures, release_event).  Callers must set the
    release event before shutdown so the in-flight tasks can complete.
    """
    entered = []
    lock = threading.Lock()
    two_started = threading.Event()
    release = threading.Event()

    def work(x):
        with lock:
            entered.append(x)
            if len(entered) == 2:
                two_started.set()
        assert release.wait(timeout=10), "release event never set"
        return x

    futures = [executor.submit(work, i) for i in range(n_items)]
    assert two_started.wait(timeout=10), "workers never picked up tasks"
    return futures, release


class TestCancelFutures:
    def test_cancel_futures_cancels_queued_but_not_running(self):
        executor = DaemonThreadPoolExecutor(max_workers=2)
        futures, release = _start_two_tasks(executor, 6)
        try:
            release.set()  # unblock the two in-flight tasks
            executor.shutdown(wait=True, cancel_futures=True)

            # FIFO: items 0 and 1 were in flight; 2..5 were still queued.
            assert [f.cancelled() for f in futures] == [
                False, False, True, True, True, True,
            ]
            assert [f.result() for f in futures[:2]] == [0, 1]
        finally:
            release.set()
            executor.shutdown(wait=True)

    def test_cancel_futures_leaves_running_tasks_intact(self):
        executor = DaemonThreadPoolExecutor(max_workers=2)
        futures, release = _start_two_tasks(executor, 2)
        try:
            release.set()
            executor.shutdown(wait=True, cancel_futures=True)
            assert not futures[0].cancelled()
            assert not futures[1].cancelled()
            assert [f.result() for f in futures] == [0, 1]
        finally:
            release.set()
            executor.shutdown(wait=True)

    def test_cancel_futures_with_no_queued_work_is_a_noop(self):
        executor = DaemonThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(lambda: 42)
            assert future.result() == 42
            executor.shutdown(wait=True, cancel_futures=True)
            assert not future.cancelled()
        finally:
            executor.shutdown(wait=True)

    def test_cancel_futures_leaves_no_future_pending(self):
        """Every submitted future must end done() or cancelled() — never pending."""
        executor = DaemonThreadPoolExecutor(max_workers=2)
        # Block until exactly two tasks are in flight; the other 48 stay queued.
        futures, release = _start_two_tasks(executor, 50)
        try:
            release.set()
            executor.shutdown(wait=True, cancel_futures=True)
            # The two in-flight tasks completed; the 48 queued ones were cancelled.
            # (Note: Future.done() is True for cancelled futures too, so we
            # distinguish via cancelled()/result() instead.)
            assert sum(1 for f in futures if f.cancelled()) == 48
            completed = [f for f in futures if not f.cancelled()]
            assert [f.result() for f in completed] == [0, 1]
            assert all(f.done() for f in futures)
        finally:
            release.set()
            executor.shutdown(wait=True)


class TestExecutorLifecycle:
    def test_default_shutdown_drains_all_queued_work(self):
        executor = DaemonThreadPoolExecutor(max_workers=2)
        try:
            futures = [executor.submit(lambda x: x * 2, i) for i in range(5)]
            executor.shutdown(wait=True)  # cancel_futures defaults to False
            assert all(f.done() for f in futures)
            assert [f.result() for f in futures] == [0, 2, 4, 6, 8]
        finally:
            executor.shutdown(wait=True)

    def test_shutdown_is_idempotent(self):
        executor = DaemonThreadPoolExecutor(max_workers=2)
        try:
            executor.submit(lambda: None)
            executor.shutdown(wait=True)
            executor.shutdown(wait=True)  # second call must be a no-op
            executor.shutdown(wait=False, cancel_futures=True)  # still a no-op
        finally:
            executor.shutdown(wait=True)

    def test_submit_after_shutdown_raises(self):
        executor = DaemonThreadPoolExecutor(max_workers=1)
        executor.shutdown()
        with pytest.raises(RuntimeError):
            executor.submit(lambda: None)

    def test_exception_in_task_propagates_through_future(self):
        def boom():
            raise ValueError("boom")

        executor = DaemonThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(boom)
            with pytest.raises(ValueError, match="boom"):
                future.result()
        finally:
            executor.shutdown(wait=True)

    def test_map_preserves_input_order(self):
        executor = DaemonThreadPoolExecutor(max_workers=3)
        try:
            assert list(executor.map(lambda x: x * 2, [1, 2, 3, 4])) == [2, 4, 6, 8]
        finally:
            executor.shutdown(wait=True)
