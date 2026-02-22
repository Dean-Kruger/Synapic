import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.processing import ProcessingManager
from src.core.session import Session


class TestMemoryCleanup(unittest.TestCase):
    """Tests for memory cleanup in the processing pipeline."""

    @patch('src.core.processing.gc.collect')
    def test_cleanup_after_local_job(self, mock_gc_collect):
        """Model is unloaded and gc.collect called after local job."""
        session = Session()
        session.engine.provider = "local"
        session.engine.device = "cpu"  # Avoid CUDA path which imports torch locally

        log_cb = MagicMock()
        prog_cb = MagicMock()

        manager = ProcessingManager(session, log_cb, prog_cb)
        manager.model = MagicMock()  # Simulate loaded model

        with patch.object(ProcessingManager, '_fetch_items', return_value=[]), \
             patch.object(ProcessingManager, '_init_local_model'):
            manager._run_job()

        # Verify model unloaded
        self.assertIsNone(manager.model)
        # Verify gc.collect called at end of job
        mock_gc_collect.assert_called()

    @patch('src.core.processing.gc.collect')
    def test_api_client_created_once_and_closed(self, mock_gc_collect):
        """API client is created once in _run_job and closed after job completes."""
        session = Session()
        session.engine.provider = "nvidia"
        session.engine.nvidia_api_key = "test-key-123"

        log_cb = MagicMock()
        prog_cb = MagicMock()

        manager = ProcessingManager(session, log_cb, prog_cb)

        mock_client = MagicMock()
        mock_client.is_available.return_value = True

        with patch('src.core.processing.NvidiaClient', return_value=mock_client) as MockClass, \
             patch.object(ProcessingManager, '_fetch_items', return_value=[]):
            manager._run_job()

        # Client created exactly once (not per item)
        MockClass.assert_called_once_with(api_key="test-key-123")
        # Client closed at end of job
        mock_client.close.assert_called_once()
        # API client reference cleared
        self.assertIsNone(manager._api_client)
        # gc.collect called
        mock_gc_collect.assert_called()

    @patch('src.core.processing.gc.collect')
    def test_periodic_gc_collect_per_item(self, mock_gc_collect):
        """gc.collect is called periodically during item processing."""
        session = Session()
        session.engine.provider = "nvidia"
        session.engine.nvidia_api_key = "test-key-123"

        log_cb = MagicMock()
        prog_cb = MagicMock()

        manager = ProcessingManager(session, log_cb, prog_cb)

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.chat_with_image.return_value = '{"description":"test","category":"Test","keywords":["a"]}'

        # Create 10 fake items (triggers gc.collect at item 10)
        from pathlib import Path
        fake_items = [Path(f"fake_{i}.jpg") for i in range(10)]

        with patch('src.core.processing.NvidiaClient', return_value=mock_client), \
             patch.object(ProcessingManager, '_fetch_items', return_value=fake_items), \
             patch('src.core.processing.image_processing') as mock_ip, \
             patch('src.core.processing.Image'):
            mock_ip.extract_tags_from_result.return_value = ("Test", ["a"], "test desc")
            mock_ip.write_metadata.return_value = True
            manager._run_job()

        # gc.collect should have been called multiple times:
        # once per 10 items in the finally block, plus once at end of job
        self.assertGreaterEqual(mock_gc_collect.call_count, 2)

    @patch('src.core.processing.gc.collect')
    def test_groq_client_reused_across_items(self, mock_gc_collect):
        """Groq client is created once and reused, not per-item."""
        session = Session()
        session.engine.provider = "groq_package"
        session.engine.groq_api_keys = "test-key-123"

        log_cb = MagicMock()
        prog_cb = MagicMock()

        manager = ProcessingManager(session, log_cb, prog_cb)

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.chat_with_image.return_value = '{"description":"test","category":"Test","keywords":["a"]}'

        from pathlib import Path
        fake_items = [Path(f"fake_{i}.jpg") for i in range(3)]

        with patch('src.core.processing.GroqPackageClient', return_value=mock_client) as MockClass, \
             patch.object(ProcessingManager, '_fetch_items', return_value=fake_items), \
             patch('src.core.processing.image_processing') as mock_ip, \
             patch('src.core.processing.Image'):
            mock_ip.extract_tags_from_result.return_value = ("Test", ["a"], "test desc")
            mock_ip.write_metadata.return_value = True
            manager._run_job()

        # Client created once, not 3 times
        MockClass.assert_called_once()
        # Client closed at end
        mock_client.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
