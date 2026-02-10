
import unittest
import threading
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.concurrency import DaemonThreadPoolExecutor

class TestDaemonThreadPoolExecutor(unittest.TestCase):
    def test_daemon_submit(self):
        """Verify that submitted tasks run in daemon threads."""
        def check_daemon():
            return threading.current_thread().daemon
            
        with DaemonThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(check_daemon)
            is_daemon = future.result()
            self.assertTrue(is_daemon, "Worker thread should be a daemon thread")

    def test_daemon_map(self):
        """Verify that mapped tasks run in daemon threads."""
        def check_daemon_arg(x):
            return threading.current_thread().daemon
            
        with DaemonThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(check_daemon_arg, [1, 2, 3]))
            for is_daemon in results:
                self.assertTrue(is_daemon, "Mapped worker thread should be a daemon thread")

if __name__ == '__main__':
    unittest.main()
