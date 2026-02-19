import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.processing import ProcessingManager
from src.core.session import Session

class TestMemoryCleanup(unittest.TestCase):
    @patch('src.core.processing.gc.collect')
    @patch('src.core.processing.torch.cuda.empty_cache')
    def test_cleanup_after_job(self, mock_empty_cache, mock_gc_collect):
        session = Session()
        session.engine.provider = "local"
        session.engine.device = "cuda"
        
        # Mock callbacks
        log_cb = MagicMock()
        prog_cb = MagicMock()
        
        manager = ProcessingManager(session, log_cb, prog_cb)
        manager.model = MagicMock() # Simulate loaded model
        
        # We need to mock _fetch_items to return empty list so it skips the loop but hits cleanup
        with patch.object(ProcessingManager, '_fetch_items', return_value=[]):
            manager._run_job()
            
        # Verify cleanup
        self.assertIsNone(manager.model)
        mock_gc_collect.assert_called()
        mock_empty_cache.assert_called()

if __name__ == '__main__':
    unittest.main()
