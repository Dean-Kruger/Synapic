"""Unit tests for the arbitrary-user-keyword scoring core.

Covers the deterministic math shared by every tier:
- softmax_from_logprobs (calibrated logprob tier)
- normalize_json_probabilities (semantic/JSON fallback tier)
- apply_threshold (inclusive filtering)
- build_score_result / unavailable_result (result contract + calibration flags)
"""

import math
import sys

if "src.core" not in sys.modules:
    sys.path.insert(0, str(sys.path[0] or "."))

import pytest

from src.core.keyword_scoring import (
    SUM_TO_ONE_TOLERANCE,
    SCORING_TIER,
    apply_threshold,
    build_score_result,
    normalize_json_probabilities,
    softmax_from_logprobs,
    unavailable_result,
)


# ---------------------------------------------------------------------------
# softmax_from_logprobs (Method 1 — calibrated)
# ---------------------------------------------------------------------------


def test_softmax_from_logprobs_sums_to_one():
    candidates = ["A", "B", "C", "D"]
    logprobs = {"A": -0.12, "B": -2.9, "C": -4.1, "D": -6.2}
    result = softmax_from_logprobs(logprobs, candidates)
    total = sum(result.values())
    assert abs(total - 1.0) <= SUM_TO_ONE_TOLERANCE
    assert all(0.0 <= v <= 1.0 for v in result.values())


def test_softmax_from_logprobs_orders_correctly():
    candidates = ["A", "B", "C"]
    logprobs = {"A": -0.12, "B": -2.9, "C": -4.1}
    result = softmax_from_logprobs(logprobs, candidates)
    assert result["A"] > result["B"] > result["C"]


def test_softmax_missing_candidates_map_to_zero():
    """Candidates absent from the logprob payload get probability 0.0."""
    result = softmax_from_logprobs({"A": -0.1, "B": -3.0}, ["A", "B", "C", "D"])
    assert result["C"] == 0.0
    assert result["D"] == 0.0
    assert abs(sum(result.values()) - 1.0) <= SUM_TO_ONE_TOLERANCE


def test_softmax_all_missing_falls_back_to_uniform():
    """Model picked a token outside the candidate set -> uniform fallback."""
    result = softmax_from_logprobs({}, ["A", "B", "C"])
    expected = 1.0 / 3
    assert all(abs(v - expected) <= SUM_TO_ONE_TOLERANCE for v in result.values())


def test_softmax_numerical_stability_with_extreme_logprobs():
    """-1000 vs 0 must not overflow or produce NaN."""
    result = softmax_from_logprobs({"A": 0.0, "B": -1000.0}, ["A", "B"])
    assert result["A"] == 1.0
    assert result["B"] == 0.0
    assert all(math.isfinite(v) for v in result.values())


def test_softmax_empty_candidates_returns_empty():
    assert softmax_from_logprobs({"A": -1.0}, []) == {}


def test_softmax_matches_numpy_reference_values():
    """Hand-computed softmax([0, -1]) = [e0, e-1]/(e0 + e-1)."""
    e = math.exp(-1.0)
    expected_b = e / (1.0 + e)
    result = softmax_from_logprobs({"A": 0.0, "B": -1.0}, ["A", "B"])
    assert abs(result["A"] - (1.0 / (1.0 + e))) <= 1e-12
    assert abs(result["B"] - expected_b) <= 1e-12


# ---------------------------------------------------------------------------
# normalize_json_probabilities (Method 2 — semantic fallback)
# ---------------------------------------------------------------------------


def test_normalize_json_clamps_out_of_bounds():
    result = normalize_json_probabilities(
        {"A": 1.5, "B": -0.4, "C": 0.5}, ["A", "B", "C"]
    )
    assert result["A"] >= 0.0 and result["A"] <= 1.0
    assert result["B"] == 0.0
    assert abs(sum(result.values()) - 1.0) <= SUM_TO_ONE_TOLERANCE


def test_normalize_json_missing_candidates_default_zero():
    result = normalize_json_probabilities({"A": 1.0}, ["A", "B"])
    assert result["B"] == 0.0
    assert result["A"] == 1.0


def test_normalize_json_total_zero_falls_back_to_uniform():
    result = normalize_json_probabilities({"A": 0.0, "B": 0.0}, ["A", "B"])
    assert result["A"] == 0.5 and result["B"] == 0.5


def test_normalize_json_non_numeric_values_treated_as_zero():
    result = normalize_json_probabilities({"A": "high", "B": 1.0}, ["A", "B"])
    assert result["A"] == 0.0
    assert result["B"] == 1.0


def test_normalize_json_renormalizes_off_by_one_sums():
    """Model claims values summing to 1.2 -> renormalized to exactly 1.0."""
    result = normalize_json_probabilities({"A": 0.6, "B": 0.6}, ["A", "B"])
    assert abs(sum(result.values()) - 1.0) <= SUM_TO_ONE_TOLERANCE
    assert result["A"] == pytest.approx(result["B"])


def test_normalize_json_empty_candidates_returns_empty():
    assert normalize_json_probabilities({"A": 1.0}, []) == {}


# ---------------------------------------------------------------------------
# apply_threshold
# ---------------------------------------------------------------------------


def test_apply_threshold_inclusive_boundary():
    scores = {"A": 0.10, "B": 0.11, "C": 0.5}
    result = apply_threshold(scores, 0.1)
    # Inclusive: exactly-at-threshold candidates pass.
    assert set(result) == {"A", "B", "C"}


def test_apply_threshold_filters_below():
    scores = {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
    assert apply_threshold(scores, 0.1) == {"A": 0.7, "B": 0.2}


def test_apply_threshold_zero_disables_filtering():
    scores = {"A": 0.01, "B": 0.0}
    assert apply_threshold(scores, 0.0) == scores


def test_apply_threshold_preserves_candidate_order():
    scores = {"B": 0.9, "A": 0.8, "C": 0.3}
    assert list(apply_threshold(scores, 0.1)) == ["B", "A", "C"]


# ---------------------------------------------------------------------------
# Result contract: build_score_result / unavailable_result
# ---------------------------------------------------------------------------


def test_build_score_result_logprob_is_calibrated():
    result = build_score_result(
        ["A", "B"], {"A": 0.8, "B": 0.2}, SCORING_TIER.LOGPROB
    )
    assert result.calibrated is True
    assert result.tier is SCORING_TIER.LOGPROB
    assert result.score_map == {"A": 0.8, "B": 0.2}


def test_build_score_result_label_confidence_is_not_calibrated():
    result = build_score_result(
        ["cat"], {"cat": 0.9}, SCORING_TIER.LABEL_CONFIDENCE
    )
    assert result.calibrated is False


def test_build_score_result_semantic_json_is_not_calibrated():
    result = build_score_result(
        ["cat"], {"cat": 0.9}, SCORING_TIER.SEMANTIC_JSON
    )
    assert result.calibrated is False


def test_build_score_result_marks_unmatched_candidates():
    result = build_score_result(
        ["cat", "zzz"],
        {"cat": 0.9, "zzz": 0.0},
        SCORING_TIER.LABEL_CONFIDENCE,
        match_types={"cat": "exact", "zzz": "none"},
    )
    assert result.scores[0].matched is True
    assert result.scores[1].matched is False
    assert result.scores[1].score == 0.0


def test_build_score_result_defaults_missing_scores_to_zero():
    result = build_score_result(["A", "B"], {"A": 0.5}, SCORING_TIER.LOGPROB)
    assert result.score_map["B"] == 0.0


def test_unavailable_result_lists_all_candidates_as_unmatched():
    result = unavailable_result("no logprob support", ["A", "B"])
    assert result.tier is SCORING_TIER.UNAVAILABLE
    assert result.calibrated is False
    assert result.notes == ["no logprob support"]
    assert all(s.matched is False and s.score == 0.0 for s in result.scores)
    assert result.score_map == {"A": 0.0, "B": 0.0}


def test_score_result_to_plain_dict_is_serializable():
    import json

    result = build_score_result(
        ["A"], {"A": 0.9}, SCORING_TIER.LOGPROB, notes=["ok"]
    )
    payload = json.loads(json.dumps(result.to_plain_dict()))
    assert payload["tier"] == "logprob"
    assert payload["calibrated"] is True
    assert payload["scores"][0]["keyword"] == "A"
    assert payload["notes"] == ["ok"]
