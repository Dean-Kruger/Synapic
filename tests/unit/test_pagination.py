"""
Unit tests for Daminion auto-pagination in ProcessingManager.

Verifies that:
1. When auto_paginate=True and the first fetch returns exactly 500 items,
   ProcessingManager calls get_items_filtered a second time with start_index=500.
2. When auto_paginate=True and a subsequent fetch returns fewer than 500 items,
   the loop terminates correctly.
3. When auto_paginate=False, get_items_filtered is called exactly once regardless
   of page size.
4. get_items_filtered itself always returns at most one batch (single_page=True fix).
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.processing import ProcessingManager


def _make_dummy_items(count: int):
    """Return a list of minimal Daminion item dicts."""
    return [{"id": i, "fileName": f"img_{i}.jpg"} for i in range(count)]


def _make_manager(auto_paginate: bool):
    """Build a ProcessingManager wired to a fake Daminion session."""
    session = MagicMock()
    session.datasource.type = "daminion"
    session.datasource.daminion_scope = "all"
    session.datasource.daminion_saved_search_id = None
    session.datasource.daminion_saved_search = None
    session.datasource.daminion_collection_id = None
    session.datasource.daminion_catalog_id = None
    session.datasource.daminion_search_term = None
    session.datasource.daminion_untagged_keywords = False
    session.datasource.daminion_untagged_categories = False
    session.datasource.daminion_untagged_description = False
    session.datasource.status_filter = "all"
    session.datasource.max_items = 0

    session.engine.provider = "local"  # Avoid real model loading
    session.engine.model_id = "test-model"
    session.engine.task = "image-classification"
    session.engine.device = "cpu"

    session.daminion_client = MagicMock()
    session.processed_items = 0
    session.failed_items = 0
    session.total_items = 0

    def _reset_stats():
        session.processed_items = 0
        session.failed_items = 0
        session.total_items = 0

    session.reset_stats.side_effect = _reset_stats

    log_cb = MagicMock()
    progress_cb = MagicMock()

    manager = ProcessingManager(
        session=session,
        log_callback=log_cb,
        progress_callback=progress_cb,
        auto_paginate=auto_paginate,
    )
    return manager, session


class TestAutoPaginateManagerLoop(unittest.TestCase):
    """Verify ProcessingManager drives pagination across multiple pages."""

    def _run_fetch_only(self, auto_paginate: bool, page_sizes: list):
        """
        Simulate _run_job up to the fetch loop only (no real item processing).
        Returns the list of start_index values passed to get_items_filtered.
        """
        manager, session = _make_manager(auto_paginate)

        call_args_log = []

        def fake_get_items_filtered(**kwargs):
            start_index = kwargs.get("start_index", 0)
            call_args_log.append(start_index)
            idx = len(call_args_log) - 1
            size = page_sizes[idx] if idx < len(page_sizes) else 0
            return _make_dummy_items(size)

        session.daminion_client.get_items_filtered.side_effect = fake_get_items_filtered

        # Patch _process_single_item so we don't need a real model
        with patch.object(manager, '_process_single_item', return_value=None):
            with patch.object(manager, '_init_local_model', return_value=None):
                manager._run_job()

        return call_args_log

    def test_auto_paginate_calls_second_page_when_first_is_full(self):
        """With auto_paginate=True a full first page should trigger a second fetch."""
        offsets = self._run_fetch_only(
            auto_paginate=True,
            page_sizes=[500, 200],  # page 1 full → page 2 partial → done
        )
        self.assertEqual(offsets, [0, 500],
                         "Expected exactly two fetches: offset 0 then 500")

    def test_auto_paginate_three_full_pages_then_empty(self):
        """Three full pages followed by an empty response terminates cleanly."""
        offsets = self._run_fetch_only(
            auto_paginate=True,
            page_sizes=[500, 500, 500, 0],
        )
        self.assertEqual(offsets, [0, 500, 1000, 1500],
                         "Expected fetch at offsets 0, 500, 1000, then 1500 returns empty")

    def test_no_auto_paginate_stops_after_one_full_page(self):
        """With auto_paginate=False the loop should stop after the first page."""
        offsets = self._run_fetch_only(
            auto_paginate=False,
            page_sizes=[500, 200],  # second page should never be fetched
        )
        self.assertEqual(offsets, [0],
                         "Expected only one fetch (offset 0) when auto_paginate=False")

    def test_no_items_on_first_page_logs_and_exits(self):
        """Empty first page should exit cleanly without calling fetch again."""
        offsets = self._run_fetch_only(
            auto_paginate=True,
            page_sizes=[0],
        )
        self.assertEqual(offsets, [0],
                         "Expected exactly one fetch attempt even when empty")


class TestGetItemsFilteredSinglePage(unittest.TestCase):
    """Verify get_items_filtered itself never returns more than one batch."""

    def setUp(self):
        from src.core.daminion_client import DaminionClient
        self.client = DaminionClient.__new__(DaminionClient)
        self.client._tag_name_to_id = {}
        self.client._tag_id_to_name = {}
        self.client._tag_schema = []

        # Mock the underlying API layer
        self.mock_api = MagicMock()
        self.client._api = self.mock_api

    def _setup_search_returning(self, batch_sizes: list):
        """Configure the mock search to return given batch sizes in sequence."""
        results = iter([_make_dummy_items(n) for n in batch_sizes])

        def _search(*args, **kwargs):
            try:
                return next(results)
            except StopIteration:
                return []

        self.mock_api.media_items.search.side_effect = _search

    def test_always_returns_single_batch_on_first_call(self):
        """Even when the underlying API could return more, only one batch."""
        # Simulate API returning 500 items for every call
        self._setup_search_returning([500, 500, 500])

        items = self.client.get_items_filtered(scope="all", start_index=0)
        # Should have stopped after the first batch of 500
        self.assertEqual(len(items), 500)
        self.assertEqual(self.mock_api.media_items.search.call_count, 1,
                         "get_items_filtered should issue exactly one API call per invocation")

    def test_partial_batch_returned_correctly(self):
        """A partial batch (< 500) is returned as-is."""
        self._setup_search_returning([237])
        items = self.client.get_items_filtered(scope="all", start_index=0)
        self.assertEqual(len(items), 237)

    def test_second_page_offset_respected(self):
        """start_index=500 is forwarded to the API correctly."""
        self._setup_search_returning([300])
        self.client.get_items_filtered(scope="all", start_index=500)
        call_kwargs = self.mock_api.media_items.search.call_args
        # The API should have been told to start at index 500
        self.assertEqual(call_kwargs.kwargs.get("index", None), 500)


if __name__ == "__main__":
    unittest.main()
