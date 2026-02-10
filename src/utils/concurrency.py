
import threading
import queue
from concurrent.futures import Executor, Future

class DaemonThreadPoolExecutor(Executor):
    """
    A ThreadPoolExecutor-like class that guarantees worker threads are daemons.
    This ensures that the executor does not prevent the Python process from exiting.
    
    It implements a subset of the concurrent.futures.Executor interface needed for
    Synapic, specifically context management and `map`.
    """
    def __init__(self, max_workers=None, thread_name_prefix='DaemonWorker'):
        """
        Initializes the executor with a maximum number of daemon worker threads.
        """
        if max_workers is None:
            max_workers = 5  # Default
            
        self._max_workers = max_workers
        self._thread_name_prefix = thread_name_prefix
        self._work_queue = queue.Queue()
        self._threads = []
        self._shutdown = False
        self._lock = threading.Lock()

    def submit(self, fn, *args, **kwargs):
        """
        Submits a callable to be executed with the given arguments.
        Returns a Future object (simplified implementation).
        """
        if self._shutdown:
            raise RuntimeError('cannot schedule new futures after shutdown')
            
        f = Future()
        
        # Package the work item
        work_item = (fn, args, kwargs, f)
        self._work_queue.put(work_item)
        
        # Ensure enough threads are running
        self._adjust_thread_count()
        
        return f

    def _adjust_thread_count(self):
        with self._lock:
            # If we haven't reached max workers, spawn a new one if needed
            # We just ensure we have max_workers running if queue is not empty, 
            # or just eagerly start them.
            # Eager start is simpler and robust for this use case.
            if len(self._threads) < self._max_workers:
                t = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name=f"{self._thread_name_prefix}-{len(self._threads)}"
                )
                t.start()
                self._threads.append(t)

    def _worker_loop(self):
        while True:
            try:
                item = self._work_queue.get()
                if item is None:
                    # Sentinel
                    break
                
                fn, args, kwargs, future = item
                
                if not future.set_running_or_notify_cancel():
                    self._work_queue.task_done()
                    continue

                try:
                    result = fn(*args, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self._work_queue.task_done()
                    
            except Exception:
                # Should not happen in loop logic but catching to keep thread alive
                pass

    def shutdown(self, wait=True, cancel_futures=False):
        with self._lock:
            self._shutdown = True
            
        # Send sentinel to all threads
        for _ in self._threads:
            self._work_queue.put(None)
            
        if wait:
            for t in self._threads:
                t.join()

    def map(self, fn, *iterables, timeout=None, chunksize=1):
        """
        Returns an iterator equivalent to map(fn, *iterables).
        
        This iterator yields the results of func call as each future completes.
        (Simplified implementation: waits for all tasks to be submitted and collects results)
        """
        if timeout is not None:
            raise NotImplementedError("timeout not supported in DaemonThreadPoolExecutor.map yet")
            
        # Collect all items
        items = list(zip(*iterables))
        futures = []
        
        for args in items:
            f = self.submit(fn, *args)
            futures.append(f)
            
        # Yield results as they complete (in order)
        for f in futures:
            yield f.result()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
