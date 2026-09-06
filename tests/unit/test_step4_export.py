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

# Also register the submodules that the steps package imports via
# ``import tkinter.messagebox as messagebox``. A bare MagicMock has no
# ``__path__``, so the import system cannot resolve real submodules behind
# it and headless environments (no real tkinter) fail during collection.
tkinter.messagebox = MagicMock()
tkinter.filedialog = MagicMock()
sys.modules["tkinter.messagebox"] = tkinter.messagebox
sys.modules["tkinter.filedialog"] = tkinter.filedialog

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
        # Header + one row per result (results without a scoring payload get
        # empty tier/calibrated/probability cells)
        assert rows[4] == ["Filename", "Status", "Tags", "Scoring Tier", "Calibrated", "Probabilities"]
        assert rows[5][:3] == ["a.jpg", "Success", "Cat: Nature, Kws: 2, Desc: ..."]
        assert rows[5][3:] == ["", "", ""]
        assert rows[6][:3] == ["b.jpg", "Write Failed", "Cat: , Kws: 0, Desc: [AI: No Result]..."]
        assert rows[6][3:] == ["", "", ""]
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
        assert rows[4] == ["Filename", "Status", "Tags", "Scoring Tier", "Calibrated", "Probabilities"]
        assert len(rows) == 5

    # -------------------------------------------------------------------
    # Tier badge + calibrated labeling (KEYWORD_SCORING_DESIGN.md integration)
    # -------------------------------------------------------------------

    def test_export_includes_tier_calibrated_and_probabilities(self, tmp_path):
        session = make_session()
        session.results = deque([
            {
                "filename": "scored.jpg",
                "status": "Success",
                "tags": "Cat: A, Kws: 2, Desc: ...",
                "probabilities": {"A": 0.7, "B": 0.2},
                "scoring": {
                    "tier": "label_confidence",
                    "calibrated": False,
                    "scores": [
                        {"keyword": "A", "score": 0.7, "matched": True, "match_type": "exact"},
                        {"keyword": "B", "score": 0.2, "matched": True, "match_type": "exact"},
                    ],
                    "notes": [],
                },
            },
            {
                "filename": "calibrated.jpg",
                "status": "Success",
                "tags": "Cat: X, Kws: 1, Desc: ...",
                "probabilities": {"X": 0.9},
                "scoring": {"tier": "logprob", "calibrated": True, "scores": [], "notes": []},
            },
        ])
        step = make_step(session)
        target = tmp_path / "tiers.csv"

        with patch.object(
            tkinter.filedialog, "asksaveasfilename", return_value=str(target)
        ), patch.object(tkinter.messagebox, "showinfo"):
            step.export_report()

        with open(target, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        assert rows[4] == ["Filename", "Status", "Tags", "Scoring Tier", "Calibrated", "Probabilities"]
        assert rows[5][:3] == ["scored.jpg", "Success", "Cat: A, Kws: 2, Desc: ..."]
        assert rows[5][3] == "label_confidence"
        assert rows[5][4] == "no"
        assert rows[5][5] == "A=0.700; B=0.200"
        assert rows[6][3] == "logprob"
        assert rows[6][4] == "yes"
        assert rows[6][5] == "X=0.900"

    def test_export_legacy_entries_without_scoring_get_blank_tier_columns(self, tmp_path):
        """Results from runs before the scoring contract export empty tier/
        calibrated cells and keep the legacy probabilities rendering."""
        session = make_session()
        session.results = deque([
            {
                "filename": "legacy.jpg",
                "status": "Success",
                "tags": "Cat: Nature, Kws: 1, Desc: ...",
                "probabilities": {"A": 0.5},
            },
            {"filename": "no-probs.jpg", "status": "Write Failed", "tags": "Cat: , Kws: 0, Desc: ..."},
        ])
        step = make_step(session)
        target = tmp_path / "legacy.csv"

        with patch.object(
            tkinter.filedialog, "asksaveasfilename", return_value=str(target)
        ), patch.object(tkinter.messagebox, "showinfo"):
            step.export_report()

        with open(target, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        assert rows[5][3] == ""
        assert rows[5][4] == ""
        assert rows[5][5] == "A=0.500"
        assert rows[6][3] == ""
        assert rows[6][4] == ""
        assert rows[6][5] == ""

    def test_format_probabilities_formats_and_tolerates_non_numeric(self):
        fmt = Step4Results._format_probabilities
        assert fmt({"A": 0.7, "B": 0.2}) == "A=0.700; B=0.200"
        assert fmt(None) == ""
        assert fmt({}) == ""
        assert fmt({"weird": "high"}) == "weird=high"

    def test_scoring_badge_labels_calibrated_vs_not(self):
        assert Step4Results.scoring_badge({"tier": "logprob"}) == (
            "logprob · calibrated", "green"
        )
        assert Step4Results.scoring_badge({"tier": "label_confidence"}) == (
            "label conf. · not calibrated", "orange"
        )
        assert Step4Results.scoring_badge({"tier": "semantic_json"}) == (
            "semantic JSON · not calibrated", "orange"
        )
        assert Step4Results.scoring_badge({"tier": "unavailable"}) == (
            "scoring unavailable", "gray"
        )

    def test_scoring_badge_is_none_for_legacy_entries_and_unknown_tiers(self):
        # Pre-scoring results: no badge rather than a misleading default.
        assert Step4Results.scoring_badge(None) is None
        assert Step4Results.scoring_badge("not-a-dict") is None
        assert Step4Results.scoring_badge({}) is None
        # Unknown tier from a newer payload: shown honestly, gray.
        assert Step4Results.scoring_badge({"tier": "quantum"}) == ("quantum", "gray")
