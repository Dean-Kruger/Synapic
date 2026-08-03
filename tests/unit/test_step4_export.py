"""
Tests for Step4Results.export_report CSV Export
===============================================

Covers the ``export_report`` implementation added in WR-02/IN-05. The test
replaces the CustomTkinter stack with mocks (mirroring ``tests/test_ui_dedup.py``)
so the module imports and runs in headless CI environments.

Scenarios covered:
- A real CSV file is written with the summary block, header, and one row per
  result, with a UTF-8 BOM (so Excel renders non-ASCII text).
- Cancelling the file dialog writes nothing and logs the cancellation.
- A write failure surfaces via ``messagebox.showerror`` and is logged.
"""

import csv
import sys
from collections import deque
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# MOCK UI LIBRARIES (headless-safe, same approach as tests/test_ui_dedup.py)
# ---------------------------------------------------------------------------
ctk_mock = MagicMock()


class MockCTkFrame:
    """Stand-in base class satisfying the widget API used by the module."""

    def __init__(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        pass

    def pack(self, *args, **kwargs):
        pass


ctk_mock.CTkFrame = MockCTkFrame
sys.modules["customtkinter"] = ctk_mock
sys.modules["tkinter"] = MagicMock()
# Bind ``tkinter`` so we can patch the *same object* export_report resolves at
# runtime (``from tkinter import filedialog, messagebox`` reads attributes off
# this mock). Patching by dotted string is unreliable here because another
# test module may have registered sys.modules["tkinter.messagebox"] as a
# separate mock, which import_module would resolve instead.
import tkinter  # noqa: E402

from src.ui.steps.step4_results import Step4Results, logger  # noqa: E402


def make_step(session):
    """Build a Step4Results instance without running the real UI constructor."""
    step = Step4Results.__new__(Step4Results)
    step.controller = MagicMock()
    step.controller.session = session
    return step


def make_session():
    from src.core.session import Session

    s = Session()
    s.processed_items = 2
    s.failed_items = 1
    s.results = deque([
        {"filename": "a.jpg", "status": "Success", "tags": "Cat: Nature, Kws: 2, Desc: ..."},
        {"filename": "b.jpg", "status": "Write Failed", "tags": "Cat: , Kws: 0, Desc: [AI: No Result]..."},
    ])
    return s


class TestExportReport:
    """Tests for export_report CSV export."""

    def test_writes_summary_block_and_rows(self, tmp_path):
        session = make_session()
        step = make_step(session)
        target = tmp_path / "report.csv"

        with patch.object(
            tkinter.filedialog, "asksaveasfilename", return_value=str(target)
        ), patch.object(tkinter.messagebox, "showinfo") as mock_showinfo:
            step.export_report()

        assert target.exists()
        with open(target, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        # Summary block
        assert rows[0] == ["Total Processed", "2"]
        assert rows[1] == ["Successful", "1"]
        assert rows[2] == ["Failed", "1"]
        assert rows[3] == []
        # Header + one row per result
        assert rows[4] == ["Filename", "Status", "Tags"]
        assert rows[5] == ["a.jpg", "Success", "Cat: Nature, Kws: 2, Desc: ..."]
        assert rows[6] == ["b.jpg", "Write Failed", "Cat: , Kws: 0, Desc: [AI: No Result]..."]
        assert len(rows) == 7

        # Success messagebox shown with the path
        mock_showinfo.assert_called_once()
        call_args = mock_showinfo.call_args[0]
        assert call_args[0] == "Export Complete"
        assert str(target) in call_args[1]

    def test_writes_utf8_bom_for_excel(self, tmp_path):
        session = make_session()
        session.results = deque([{"filename": "café.jpg", "status": "Success", "tags": "Été"}])
        step = make_step(session)
        target = tmp_path / "report.csv"

        with patch.object(
            tkinter.filedialog, "asksaveasfilename", return_value=str(target)
        ), patch.object(tkinter.messagebox, "showinfo"):
            step.export_report()

        raw = target.read_bytes()
        # UTF-8 BOM present so Excel renders non-ASCII correctly
        assert raw.startswith(b"\xef\xbb\xbf")
        assert "café.jpg".encode("utf-8") in raw

    def test_cancel_writes_no_file(self, tmp_path):
        session = make_session()
        step = make_step(session)
        target = tmp_path / "never.csv"

        with patch.object(
            tkinter.filedialog, "asksaveasfilename", return_value=""
        ), patch.object(logger, "info") as mock_info:
            step.export_report()

        assert not target.exists()
        mock_info.assert_called_once_with("Report export cancelled by user")

    def test_write_failure_surfaces_error(self, tmp_path, monkeypatch):
        session = make_session()
        step = make_step(session)
        target = tmp_path / "report.csv"

        def boom(*args, **kwargs):
            raise OSError("disk full")

        with patch.object(tkinter.filedialog, "asksaveasfilename", return_value=str(target)), \
             patch("builtins.open", side_effect=boom), \
             patch.object(logger, "error") as mock_error, \
             patch.object(tkinter.messagebox, "showerror") as mock_showerror:
            step.export_report()

        assert not target.exists()
        mock_showerror.assert_called_once()
        call_args = mock_showerror.call_args[0]
        assert call_args[0] == "Export Failed"
        assert "disk full" in call_args[1]
        # The error was logged with exc_info for the technical log
        _, kwargs = mock_error.call_args
        assert kwargs.get("exc_info") is True

    def test_empty_results_still_writes_summary_and_header(self, tmp_path):
        session = make_session()
        session.results = deque()
        step = make_step(session)
        target = tmp_path / "empty.csv"

        with patch.object(
            tkinter.filedialog, "asksaveasfilename", return_value=str(target)
        ), patch.object(tkinter.messagebox, "showinfo"):
            step.export_report()

        with open(target, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["Total Processed", "2"]
        assert rows[4] == ["Filename", "Status", "Tags"]
        assert len(rows) == 5
