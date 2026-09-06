"""Regression tests for the harden-local-probability-scoring changes.

These tests focus on the new pre-flight candidate/label-space compatibility
helper and the improved failure messaging in run_local_logprob_inference.
"""

import sys

# Keep this test discoverable by pytest while still being importable from the repo root.
if "src.core" not in sys.modules:
    sys.path.insert(0, str(sys.path[0] or "."))

from src.core.huggingface_utils import (
    _candidate_compatibility_reason,
    _format_label_sample,
    summarize_candidate_compatibility,
)


def test_candidate_compatibility_all_exact():
    reason = _candidate_compatibility_reason(
        exact=["cat", "dog"],
        fuzzy=[],
        unmatched=[],
        model_labels=["cat", "dog", "bird"],
    )
    assert reason == "All candidate tokens match this model's labels exactly."


def test_candidate_compatibility_all_fuzzy_only():
    reason = _candidate_compatibility_reason(
        exact=[],
        fuzzy=["indoor", "urban"],
        unmatched=[],
        model_labels=["indoor office", "outdoor nature", "urban street"],
    )
    assert reason.startswith("No candidate matches this model's labels exactly.")


def test_candidate_compatibility_mixed_exact_fuzzy():
    reason = _candidate_compatibility_reason(
        exact=["cat"],
        fuzzy=["indoor"],
        unmatched=[],
        model_labels=["cat", "indoor office", "outdoor nature"],
    )
    assert "some matched only via fuzzy" in reason


def test_candidate_compatibility_mixed_unmatched():
    reason = _candidate_compatibility_reason(
        exact=["cat"],
        fuzzy=[],
        unmatched=["fox"],
        model_labels=["cat", "dog"],
    )
    assert "matched nothing" in reason
    assert "Unmatched candidates will score 0.0" in reason


def test_candidate_compatibility_all_unmatched_no_labels():
    reason = _candidate_compatibility_reason(
        exact=[],
        fuzzy=[],
        unmatched=["A", "B", "C"],
        model_labels=[],
    )
    assert "no classification label set" in reason


def test_candidate_compatibility_all_unmatched_with_labels():
    reason = _candidate_compatibility_reason(
        exact=[],
        fuzzy=[],
        unmatched=["A", "B", "C"],
        model_labels=["cat", "dog", "bird"],
    )
    assert "None of the candidate tokens match this model's labels" in reason
    assert "Model labels include:" in reason


def test_format_label_sample_truncates_long_label_lists():
    labels = [f"label{i}" for i in range(20)]
    assert _format_label_sample(labels, [], n=8) == "label0, label1, label2, label3, label4, label5, label6, label7..."


def test_format_label_sample_preserves_order_and_dedup():
    sample = _format_label_sample(["cat", "dog", "cat", "bird"], [], n=10)
    assert sample == "cat, dog, bird"


def test_format_label_sample_falls_back_when_unavailable():
    assert _format_label_sample([], [], n=8) == "(label list unavailable)"


def test_summarize_candidate_compatibility_empty_candidates():
    summary = summarize_candidate_compatibility([], ["cat", "dog"])
    assert summary["total"] == 0
    assert summary["exact"] == []
    assert summary["fuzzy"] == []
    assert summary["unmatched"] == []
    assert "No candidate tokens provided" in summary["reason"]


def test_summarize_candidate_compatibility_with_no_model_labels():
    summary = summarize_candidate_compatibility(["A", "B"], [])
    assert summary["unmatched"] == ["A", "B"]
    assert "no classification label set" in summary["reason"]


def test_summarize_candidate_compatibility_normalizes_case_and_whitespace():
    summary = summarize_candidate_compatibility(
        [" cat ", " DOG", "fish"],
        ["Cat", "Dog", "Bird"],
    )
    assert "cat" in summary["exact"] or " cat " in summary["exact"]
    assert "dog" in summary["exact"] or " DOG" in summary["exact"]
    assert "fish" in summary["unmatched"]


def test_summarize_candidate_compatibility_uses_fuzzy_for_close_labels():
    summary = summarize_candidate_compatibility(
        ["indoor", "urban"],
        ["indoor office", "outdoor nature", "urban street"],
    )
    assert "indoor" in summary["fuzzy"]
    assert "urban" in summary["fuzzy"]
    assert summary["unmatched"] == []
