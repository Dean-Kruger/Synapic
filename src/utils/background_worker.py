"""
Background Worker Utility
=========================

This module provides a thread-safe task queue worker for executing background
operations without creating new threads for each task. It solves the memory
growth problem caused by fire-and-forget threading patterns.

Key Features:
-------------
- Single Persistent Thread: One worker thread handles all submitted tasks
- Task Queue: FIFO queue with optional task replacement for debounced operations
- Cancellation Support: Pending tasks can be cancelled without affecting running task
- Graceful Shutdown: Properly drains queue and joins thread on exit

Usage:
------
    >>> from src.utils.background_worker import BackgroundWorker
    >>> 
    >>> worker = BackgroundWorker()
    >>> worker.submit(some_function, arg1, arg2, kwarg1=value)
    >>> 
    >>> # For debounced operations (only latest task runs):
    >>> worker.submit_replacing("search", search_function, query)
    >>> 
    >>> # Cleanup when done:
    >>> worker.shutdown()

Author: Synapic Project
"""

import threading
import queue
import logging
from typing import Callable, Any, Optional, Dict


class BackgroundWorker:
    """
    Single-thread task executor with queue management.
    
    This class provides a reusable worker that processes tasks from a queue
    using a single persistent thread. It eliminates the overhead and memory
    impact of creating new threads for each background operation.
    
    The worker supports two submission modes:
    1. `submit()` - Standard FIFO queue (all tasks run in order)
    2. `submit_replacing()` - Replaces pending task with same ID (for debouncing)
    
    Attributes:
        name: Identifier for logging purposes
        _queue: Thread-safe task queue
        _thread: The persistent worker thread
        _running: Flag to signal shutdown
        _pending_replaceable: Dict tracking replaceable tasks by ID
    
    Example:
        >>> worker = BackgroundWorker(name="SearchWorker")
        >>> 
        >>> # Multiple rapid searches - only the last one executes
        >>> worker.submit_replacing("search", do_search, "a")
        >>> worker.submit_replacing("search", do_search, "ab")
        >>> worker.submit_replacing("search", do_search, "abc")  # Only this runs
        >>> 
        >>> worker.shutdown()
    """
    
    def __init__(self, name: str = "BackgroundWorker"):
        """
        Initialize the background worker.
        
        Args:
            name: Identifier for logging (e.g., "SearchWorker", "CountWorker")
        """
        self.name = name
        self.logger = logging.getLogger(__name__)
        
        # Task queue for pending work
        self._queue: queue.Queue = queue.Queue()
        
        # Control flag for graceful shutdown
        self._running = True
        
        # Lock for thread-safe operations on shared state
        self._lock = threading.Lock()
        
        # Track replaceable tasks by ID
        # Maps task_id -> task_marker (allows detecting if task was replaced)
        self._pending_replaceable: Dict[str, int] = {}
        self._marker_counter = 0
        
        # Start the persistent worker thread
        self._thread = threading.Thread(
            target=self._process_queue,
            name=f"{name}-Thread",
            daemon=True
        )
        self._thread.start()
        self.logger.debug(f"BackgroundWorker '{name}' started")
    
    def submit(self, task: Callable, *args, **kwargs) -> None:
        """
        Submit a task to the work queue.
        
        The task will be executed in FIFO order after any pending tasks complete.
        
        Args:
            task: The callable to execute
            *args: Positional arguments to pass to the task
            **kwargs: Keyword arguments to pass to the task
        """
        if not self._running:
            self.logger.warning(f"Worker '{self.name}' is shut down, ignoring task submission")
            return
        
        self._queue.put(("standard", None, None, task, args, kwargs))
    
    def submit_replacing(self, task_id: str, task: Callable, *args, **kwargs) -> None:
        """
        Submit a task that replaces any pending task with the same ID.
        
        Use this for debounced operations like search-while-typing, where only
        the latest submission should execute. If a task with the same ID is
        already pending (not yet started), it will be skipped when dequeued.
        
        Args:
            task_id: Unique identifier for this type of replaceable task
            task: The callable to execute
            *args: Positional arguments to pass to the task
            **kwargs: Keyword arguments to pass to the task
        
        Example:
            >>> # Rapid typing - only searches for "hello" (the last one)
            >>> worker.submit_replacing("search", search, "h")
            >>> worker.submit_replacing("search", search, "he")
            >>> worker.submit_replacing("search", search, "hel")
            >>> worker.submit_replacing("search", search, "hell")
            >>> worker.submit_replacing("search", search, "hello")
        """
        if not self._running:
            self.logger.warning(f"Worker '{self.name}' is shut down, ignoring task submission")
            return
        
        with self._lock:
            # Generate a unique marker for this submission
            self._marker_counter += 1
            marker = self._marker_counter
            
            # Update the pending marker - any previous task with this ID will
            # see that its marker doesn't match and skip execution
            self._pending_replaceable[task_id] = marker
        
        self._queue.put(("replaceable", task_id, marker, task, args, kwargs))
    
    def cancel_all(self) -> None:
        """
        Cancel all pending tasks.
        
        Tasks already in execution will complete, but pending tasks will be
        skipped when dequeued. This is useful when closing a dialog to avoid
        processing stale work.
        """
        with self._lock:
            # Clear the queue
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break
            
            # Invalidate all replaceable task markers
            self._pending_replaceable.clear()
            self._marker_counter = 0
        
        self.logger.debug(f"Worker '{self.name}' cancelled all pending tasks")
    
    def shutdown(self, timeout: float = 2.0) -> None:
        """
        Gracefully shut down the worker.
        
        Signals the worker thread to stop, waits for it to complete, and
        cleans up resources.
        
        Args:
            timeout: Maximum seconds to wait for the thread to join
        """
        if not self._running:
            return
        
        self.logger.debug(f"Worker '{self.name}' shutting down...")
        
        # Signal thread to stop
        self._running = False
        
        # Put a sentinel to unblock the queue.get() if it's waiting
        self._queue.put(None)
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                self.logger.warning(f"Worker '{self.name}' thread did not terminate within {timeout}s")
        
        self.logger.debug(f"Worker '{self.name}' shutdown complete")
    
    def _process_queue(self) -> None:
        """
        Main loop for the worker thread.
        
        Continuously processes tasks from the queue until shutdown is signaled.
        Handles both standard and replaceable tasks appropriately.
        """
        while self._running:
            try:
                # Wait for a task with timeout to allow checking _running flag
                item = self._queue.get(timeout=0.1)
                
                if item is None:
                    # Sentinel received, shutdown in progress
                    break
                
                task_type, task_id, marker, task, args, kwargs = item
                
                # For replaceable tasks, check if this is still the latest
                if task_type == "replaceable":
                    with self._lock:
                        current_marker = self._pending_replaceable.get(task_id)
                        if current_marker != marker:
                            # This task was replaced, skip it
                            self._queue.task_done()
                            continue
                
                # Execute the task
                try:
                    task(*args, **kwargs)
                except Exception as e:
                    self.logger.error(
                        f"Worker '{self.name}' task failed: {type(e).__name__}: {e}",
                        exc_info=True
                    )
                finally:
                    self._queue.task_done()
                    
                    # Clean up marker if this was a replaceable task
                    if task_type == "replaceable":
                        with self._lock:
                            # Only remove if it's still our marker (not replaced)
                            if self._pending_replaceable.get(task_id) == marker:
                                del self._pending_replaceable[task_id]
                
            except queue.Empty:
                # Timeout, just loop to check _running flag
                continue
            except Exception as e:
                self.logger.error(f"Worker '{self.name}' unexpected error: {e}", exc_info=True)
    
    def is_alive(self) -> bool:
        """Check if the worker thread is still running."""
        return self._thread and self._thread.is_alive()
    
    @property
    def pending_count(self) -> int:
        """Get the approximate number of pending tasks."""
        return self._queue.qsize()
