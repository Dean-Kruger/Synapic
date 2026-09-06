"""
Arbitrary-User-Keyword Scoring Core
====================================

Shared, dependency-free math and data structures for scoring a
user-supplied keyword list against an image.

This module defines the **result contract and deterministic
post-processing** shared by every scoring tier; tier-specific inference
lives in the integration layer (see ``docs/KEYWORD_SCORING_DESIGN.md``):

- Tier 1 (logprob): a prompted VLM/LLM returns a single option token and
  the caller extracts token logprobs -> ``softmax_from_logprobs``.
- Tier 2 (label confidence): the existing local
  ``run_local_logprob_inference`` path (pipeline per-label confidence).
- Tier 3 (semantic JSON): a prompted VLM returns JSON probabilities ->
  ``normalize_json_probabilities``.

Design goals:

- No new dependencies (``math`` only) so the core is unit-testable in CI.
- Every tier returns the same ``ScoreResult`` contract so downstream code
  (thresholding, logging, results export) never branches on tier.
- Calibration is explicit: ``ScoreResult.calibrated`` is True only for
  the logprob tier, whose scores form a true probability distribution
  over the candidate set. Label-confidence and semantic tiers are NOT
  calibrated and must say so.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# Tolerance for the sum-to-one invariant (mirrors the API design checklist
# in docs/PROBABILITY_SCORING_TAGGING.md).
SUM_TO_ONE_TOLERANCE = 1e-9


class SCORING_TIER(str, Enum):
    """Which scoring path produced a ScoreResult.

    - ``logprob``: true token logprobs over the candidate set, softmaxed
      into a calibrated distribution (sums to 1.0).
    - ``label_confidence``: pipeline per-label confidence for the model
      label each candidate matched. Relative confidence, NOT calibrated,
      and NOT a distribution over the candidate set.
    - ``embedding``: CLIP-style cosine similarity between the image and
      each candidate prompt, softmaxed over the candidate set. Semantic
      (arbitrary candidates allowed) but strongly dependent on the
      candidate set and prompt phrasing; NOT calibrated.
    - ``semantic_json``: VLM-generated JSON probabilities. Bounded
      [0, 1] and normalized to sum to 1.0, but reflects the model's
      self-reported calibration, not true logits.
    - ``unavailable``: scoring could not run (no compatible provider,
      inference failure). Scores list is empty.
    """

    LOGPROB = "logprob"
    LABEL_CONFIDENCE = "label_confidence"
    EMBEDDING = "embedding"
    SEMANTIC_JSON = "semantic_json"
    UNAVAILABLE = "unavailable"


@dataclass
class ScoredKeyword:
    """One user keyword and its score under a given tier."""

    keyword: str
    score: float
    # False when the keyword could not be attached to any evidence source
    # (no matching model label, absent from the VLM payload, ...).
    matched: bool = True
    # "exact" | "fuzzy" | "none" | "llm" | "semantic"
    match_type: str = "exact"
    note: str = ""


@dataclass
class ScoreResult:
    """Tier-agnostic result contract for keyword scoring."""

    scores: List[ScoredKeyword] = field(default_factory=list)
    tier: SCORING_TIER = SCORING_TIER.UNAVAILABLE
    # True ONLY when scores form a calibrated probability distribution
    # over the candidate set (currently: the logprob tier).
    calibrated: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def score_map(self) -> Dict[str, float]:
        """Plain {keyword: score} mapping in original candidate order."""
        return {s.keyword: s.score for s in self.scores}

    def to_plain_dict(self) -> dict:
        """JSON-serializable form for session.results entries / export."""
        return {
            "tier": self.tier.value,
            "calibrated": self.calibrated,
            "scores": [
                {
                    "keyword": s.keyword,
                    "score": s.score,
                    "matched": s.matched,
                    "match_type": s.match_type,
                    "note": s.note,
                }
                for s in self.scores
            ],
            "notes": list(self.notes),
        }


def softmax_from_logprobs(
    logprob_map: Dict[str, float], candidates: List[str]
) -> Dict[str, float]:
    """Softmax raw first-token logprobs into a calibrated distribution.

    Implements the API design (Method 1) from
    ``docs/PROBABILITY_SCORING_TAGGING.md`` with stdlib math instead of
    numpy:

    - candidates missing from ``logprob_map`` are treated as ``-inf``
      (probability 0.0);
    - the maximum logprob is subtracted before exponentiation for
      numerical stability;
    - when every candidate is ``-inf`` (the model picked a token outside
      the candidate set) the result falls back to a uniform distribution;
    - the returned values sum to 1.0 within ``SUM_TO_ONE_TOLERANCE``.

    Args:
        logprob_map: Mapping of candidate token to its raw logprob as
            reported by the API (e.g. ``{"A": -0.12, "B": -2.9}``).
        candidates: The full candidate token list defining the output.

    Returns:
        Dict mapping every candidate to a probability in [0.0, 1.0].
    """
    if not candidates:
        return {}

    filled = {c: float(logprob_map.get(c, float("-inf"))) for c in candidates}
    max_logprob = max(filled.values())

    if max_logprob == float("-inf"):
        # Model selected a token outside the candidate set (or the parser
        # found nothing): uniform fallback per the design checklist.
        uniform = 1.0 / len(candidates)
        return {c: uniform for c in candidates}

    exp_probs = {c: math.exp(v - max_logprob) for c, v in filled.items()}
    total = math.fsum(exp_probs.values())
    if total <= 0.0:  # Defensive; unreachable after the -inf guard.
        uniform = 1.0 / len(candidates)
        return {c: uniform for c in candidates}

    normalized = {c: v / total for c, v in exp_probs.items()}
    return _enforce_sum_to_one(normalized)


def softmax_from_similarities(
    similarities: Dict[str, float], candidates: List[str], temperature: float = 0.01
) -> Dict[str, float]:
    """Softmax CLIP-style cosine similarities over the candidate set.

    This is the standard contrastive zero-shot construction: cosine
    similarity between the image embedding and each candidate prompt
    embedding, scaled by ``1/temperature`` (CLIP's logit scale is the
    inverse temperature), then normalized into a distribution that sums
    to 1.0.

    Calibration caveat (why ``calibrated=False`` even though this sums to
    one): the values are relative to the candidate set actually supplied.
    Adding a nonsense candidate like "wallpaper" absorbs probability
    mass and shifts every remaining score without the image changing at
    all. Absolute thresholds are therefore NOT comparable across runs —
    rank ordering within a single candidate set is the meaningful signal.

    Args:
        similarities: Mapping of candidate -> cosine similarity in [-1, 1]
            (candidates missing from the map default to -1.0).
        candidates: The full candidate keyword list defining the output.
        temperature: Softmax temperature (default 0.01 approximates CLIP's
            learned logit scale for ViT-B/32; lower = sharper).

    Returns:
        Dict mapping every candidate to a probability in [0.0, 1.0].
    """
    if not candidates:
        return {}

    if temperature <= 0.0:
        temperature = 0.01

    sims = {c: float(similarities.get(c, -1.0)) for c in candidates}
    scaled = {c: s / temperature for c, s in sims.items()}
    max_scaled = max(scaled.values())
    # exp overflow guard via max-subtraction (sims are bounded so this is
    # safe, but the guard keeps the math identical to softmax_from_logprobs).
    exp_probs = {c: math.exp(v - max_scaled) for c, v in scaled.items()}
    total = math.fsum(exp_probs.values())
    if total <= 0.0:  # Defensive; unreachable with finite scaled values.
        uniform = 1.0 / len(candidates)
        return {c: uniform for c in candidates}

    normalized = {c: v / total for c, v in exp_probs.items()}
    return _enforce_sum_to_one(normalized)


def normalize_json_probabilities(
    raw: Dict[str, float], candidates: List[str]
) -> Dict[str, float]:
    """Normalize VLM self-reported JSON probabilities (Method 2 fallback).

    Models frequently violate bounds or the sum-to-one instruction, so:

    - missing candidates default to 0.0;
    - every value is clamped to [0.0, 1.0];
    - if the clamped total is 0.0 the result falls back to uniform;
    - otherwise values are renormalized to sum to 1.0.

    Note this is *not* calibrated in the logprob sense: it reflects the
    model's own claimed confidence (see ``ScoreResult.calibrated``).

    Args:
        raw: Parsed JSON payload mapping candidate keys to floats.
        candidates: The full candidate token list defining the output.

    Returns:
        Dict mapping every candidate to a probability in [0.0, 1.0].
    """
    if not candidates:
        return {}

    probs: Dict[str, float] = {}
    total = 0.0
    for c in candidates:
        try:
            val = float(raw.get(c, 0.0))
        except (TypeError, ValueError):
            val = 0.0
        val = max(0.0, min(1.0, val))
        probs[c] = val
        total += val

    if total <= 0.0:
        uniform = 1.0 / len(candidates)
        return {c: uniform for c in candidates}

    normalized = {c: v / total for c, v in probs.items()}
    return _enforce_sum_to_one(normalized)


def apply_threshold(
    score_map: Dict[str, float], threshold: float
) -> Dict[str, float]:
    """Inclusive threshold filter over a score map.

    Candidates with ``score >= threshold`` are kept. A threshold of
    ``0.0`` (or less) disables filtering and returns an equivalent map.
    Original candidate order is preserved.

    Args:
        score_map: Mapping of candidate keyword to score.
        threshold: Inclusive minimum score in [0.0, 1.0].

    Returns:
        Filtered mapping in the original candidate order.
    """
    if threshold is None or threshold <= 0.0:
        return dict(score_map)
    return {k: v for k, v in score_map.items() if v >= threshold}


def build_score_result(
    candidates: List[str],
    score_map: Dict[str, float],
    tier: SCORING_TIER,
    match_types: Optional[Dict[str, str]] = None,
    notes: Optional[List[str]] = None,
) -> ScoreResult:
    """Assemble a ScoreResult from a candidate list and a score map.

    Args:
        candidates: The user's candidate keywords, in the order they
            should appear in the result.
        score_map: Score per candidate. Missing candidates score 0.0.
        tier: The tier that produced the scores (sets ``calibrated``).
        match_types: Optional per-candidate match type
            ("exact"/"fuzzy"/"none"/"llm"/"semantic"). Candidates whose
            match type is ``"none"`` are marked unmatched.
        notes: Optional human-readable notes (fallback reasons, etc.).

    Returns:
        A ScoreResult whose ``calibrated`` flag is True only for
        ``SCORING_TIER.LOGPROB``.
    """
    match_types = match_types or {}
    scored: List[ScoredKeyword] = []
    for candidate in candidates:
        match_type = match_types.get(candidate, "exact")
        scored.append(
            ScoredKeyword(
                keyword=candidate,
                score=float(score_map.get(candidate, 0.0)),
                matched=match_type != "none",
                match_type=match_type,
            )
        )
    return ScoreResult(
        scores=scored,
        tier=tier,
        calibrated=(tier == SCORING_TIER.LOGPROB),
        notes=list(notes or []),
    )


def build_thresholded_view(result: ScoreResult, threshold: float) -> ScoreResult:
    """Return a copy of ``result`` with sub-threshold entries filtered out.

    Mirrors the pipeline's legacy behavior of storing the *post-threshold*
    score map (``session.results[i]["probabilities"]``). The returned copy
    keeps the original tier and calibration flags and appends a note that a
    threshold was applied, so a filtered view is never mistaken for the raw
    distribution. The input result is not mutated.
    """
    kept_scores = apply_threshold(result.score_map, threshold)
    filtered = ScoreResult(
        scores=[s for s in result.scores if s.keyword in kept_scores],
        tier=result.tier,
        calibrated=result.calibrated,
        notes=list(result.notes)
        + [f"Threshold {threshold:.3f} applied; sub-threshold entries removed."],
    )
    return filtered


def unavailable_result(reason: str, candidates: Optional[List[str]] = None) -> ScoreResult:
    """Build the explicit 'scoring could not run' result.

    Callers use this instead of raising when scoring is optional and the
    pipeline should continue (mirrors the 'hide on failure' rule of the
    existing probability pass).
    """
    return ScoreResult(
        scores=[
            ScoredKeyword(keyword=c, score=0.0, matched=False, match_type="none")
            for c in (candidates or [])
        ],
        tier=SCORING_TIER.UNAVAILABLE,
        calibrated=False,
        notes=[reason],
    )


def _enforce_sum_to_one(values: Dict[str, float]) -> Dict[str, float]:
    """Final float-safety pass guaranteeing the sum-to-one invariant."""
    total = math.fsum(values.values())
    if total > 0.0 and abs(total - 1.0) > SUM_TO_ONE_TOLERANCE:
        values = {k: v / total for k, v in values.items()}
    return values
