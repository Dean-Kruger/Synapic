"""Unit tests for keyword scoring adapters and tier selection.

Covers:
- pick_scoring_tier ladder across providers/modes
- tier-1 logprob adapter (letter re-keying, uniform fallback, size limit)
- tier-2 label-confidence adapter (match typing via the real helper)
- tier-3 semantic JSON adapter (missing keys, parse failure, normalization)
- score_keywords orchestrator degradation (1 → 3 → 0) without raising
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

if "src.core" not in sys.modules:
    sys.path.insert(0, str(sys.path[0] or "."))

import pytest
from transformers import Pipeline

from src.core.keyword_scoring import SCORING_TIER
from src.core.keyword_scoring_adapters import (
    _letters_to_candidates,
    pick_scoring_tier,
    score_keywords,
    score_keywords_local_label_confidence,
    score_keywords_logprob,
    score_keywords_semantic_json,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_engine(provider="local", task="image-classification", mode="both",
                candidates=None, device="cpu"):
    return SimpleNamespace(
        provider=provider,
        task=task,
        probability_mode=mode,
        probability_candidates=candidates if candidates is not None else ["A", "B", "C"],
        probability_threshold=0.0,
        device=device,
    )


class StubLogprobClient:
    """chat_with_image_logprobs returning a canned letter->logprob map."""

    def __init__(self, logprobs=None, supports=True):
        self.logprobs = logprobs or {"A": -0.1, "B": -2.0, "C": -4.0}
        self.supports = supports
        self.calls = []

    def chat_with_image_logprobs(self, model_name, prompt, image_path):
        self.calls.append((model_name, prompt, image_path))
        return self.logprobs if self.supports else None


class StubVisionClient:
    """chat_with_image returning a canned JSON payload string."""

    def __init__(self, payload='{"A": 0.6, "B": 0.3, "C": 0.1}'):
        self.payload = payload
        self.calls = []

    def chat_with_image(self, model_name, prompt, image_path):
        self.calls.append((model_name, prompt, image_path))
        return self.payload


# ---------------------------------------------------------------------------
# pick_scoring_tier
# ---------------------------------------------------------------------------


def test_selector_local_classification_is_tier2():
    assert pick_scoring_tier(make_engine()) is SCORING_TIER.LABEL_CONFIDENCE


def test_selector_local_non_classification_is_none():
    assert pick_scoring_tier(make_engine(task="image-text-to-text")) is None


def test_selector_llm_mode_is_none():
    assert pick_scoring_tier(make_engine(mode="llm")) is None


def test_selector_no_candidates_is_none():
    assert pick_scoring_tier(make_engine(candidates=[])) is None


def test_selector_cloud_providers_are_tier1():
    for provider in ("groq_package", "openrouter", "ollama", "nvidia",
                     "google_ai", "cerebras", "huggingface"):
        assert pick_scoring_tier(make_engine(provider=provider)) is SCORING_TIER.LOGPROB


def test_selector_unknown_provider_is_none():
    assert pick_scoring_tier(make_engine(provider="blackhole")) is None


def test_selector_mode_probability_same_as_both():
    assert pick_scoring_tier(make_engine(mode="probability")) is SCORING_TIER.LABEL_CONFIDENCE


# ---------------------------------------------------------------------------
# Tier 1 — logprob adapter
# ---------------------------------------------------------------------------


def test_logprob_adapter_produces_calibrated_distribution():
    client = StubLogprobClient()
    result = score_keywords_logprob(client, "m", "img.jpg", ["A", "B", "C"])
    assert result.tier is SCORING_TIER.LOGPROB
    assert result.calibrated is True
    assert abs(sum(result.score_map.values()) - 1.0) < 1e-9
    assert result.score_map["A"] > result.score_map["B"] > result.score_map["C"]


def test_logprob_adapter_rekeys_letters_to_candidates():
    rekeyed = _letters_to_candidates({"a": -0.5, " C ": -2.0}, ["foo", "bar", "baz"])
    assert rekeyed == {"foo": -0.5, "baz": -2.0}
    assert "bar" not in rekeyed  # never returned by the model


def test_logprob_adapter_out_of_set_first_token_yields_uniform_with_note():
    client = StubLogprobClient(logprobs={"Z": -0.01})
    result = score_keywords_logprob(client, "m", "img.jpg", ["A", "B"])
    assert all(v == pytest.approx(0.5) for v in result.score_map.values())
    assert any("uniform fallback" in n for n in result.notes)


def test_logprob_adapter_raises_when_client_lacks_logprobs():
    client = StubLogprobClient(supports=False)
    with pytest.raises(ValueError, match="logprobs"):
        score_keywords_logprob(client, "m", "img.jpg", ["A", "B"])


def test_logprob_adapter_rejects_oversized_candidate_lists():
    with pytest.raises(RuntimeError, match="exceed the logprob prompt limit"):
        score_keywords_logprob(
            StubLogprobClient(), "m", "img.jpg", [f"c{i}" for i in range(30)]
        )


def test_logprob_adapter_prompt_contains_all_candidates():
    client = StubLogprobClient()
    score_keywords_logprob(client, "m", "img.jpg", ["cat", "dog"])
    _, prompt, _ = client.calls[0]
    assert "cat" in prompt and "dog" in prompt
    assert "Respond with ONLY" in prompt


# ---------------------------------------------------------------------------
# Tier 2 — label confidence adapter (uses the real matcher helpers)
# ---------------------------------------------------------------------------


class StubPipeline(Pipeline):
    """Concrete Pipeline stand-in (same pattern as test_logprob_helper.py)
    so run_local_logprob_inference takes the reuse branch, not the factory."""

    def __init__(self, labels, outputs):
        self.task = "image-classification"
        self.model = SimpleNamespace(
            config=SimpleNamespace(num_labels=len(labels), id2label=labels)
        )
        self.outputs = outputs

    def _sanitize_parameters(self, **kwargs):
        return {}, {}, {}

    def preprocess(self, inputs):
        return inputs

    def _forward(self, model_inputs):
        return model_inputs

    def postprocess(self, model_outputs):
        return model_outputs

    def __call__(self, inputs, **kwargs):
        return self.outputs


def _stub_pipe(labels, outputs):
    return StubPipeline(labels, outputs)


def test_label_confidence_adapter_types_exact_matches():
    pipe = _stub_pipe({0: "cat", 1: "dog"}, [{"label": "cat", "score": 0.9},
                                             {"label": "dog", "score": 0.1}])
    result = score_keywords_local_label_confidence(pipe, "img.jpg", ["cat", "dog"])
    assert result.tier is SCORING_TIER.LABEL_CONFIDENCE
    assert result.calibrated is False
    assert result.scores[0].match_type == "exact"
    assert result.scores[0].matched is True


def test_label_confidence_adapter_types_fuzzy_matches_with_note():
    pipe = _stub_pipe(
        {0: "indoor office", 1: "outdoor nature", 2: "urban street"},
        [{"label": "indoor office", "score": 0.8},
         {"label": "outdoor nature", "score": 0.15},
         {"label": "urban street", "score": 0.05}],
    )
    result = score_keywords_local_label_confidence(pipe, "img.jpg", ["indoor", "urban"])
    assert result.scores[0].match_type == "fuzzy"
    assert result.scores[0].score == 0.8
    assert any("Fuzzy-matched" in n for n in result.notes)


def test_label_confidence_adapter_marks_unmatched_and_delegates_errors():
    pipe = _stub_pipe({0: "cat", 1: "dog"}, [{"label": "cat", "score": 0.9},
                                             {"label": "dog", "score": 0.1}])
    with pytest.raises(ValueError, match="none of the candidate tokens matched"):
        score_keywords_local_label_confidence(pipe, "img.jpg", ["A", "B", "C"])


def test_label_confidence_adapter_empty_candidates_is_tier0():
    result = score_keywords_local_label_confidence(MagicMock(), "img.jpg", [])
    assert result.tier is SCORING_TIER.UNAVAILABLE
    assert result.calibrated is False


# ---------------------------------------------------------------------------
# Tier 3 — semantic JSON adapter
# ---------------------------------------------------------------------------


def test_semantic_json_adapter_normalizes_payload():
    client = StubVisionClient(payload='{"cat": 0.6, "dog": 0.6}')  # sums to 1.2
    result = score_keywords_semantic_json(client, "m", "img.jpg", ["cat", "dog"])
    assert result.tier is SCORING_TIER.SEMANTIC_JSON
    assert result.calibrated is False
    assert abs(sum(result.score_map.values()) - 1.0) < 1e-9
    assert all(s.match_type == "semantic" for s in result.scores)


def test_semantic_json_adapter_marks_missing_keys_unmatched():
    client = StubVisionClient(payload='{"cat": 1.0}')
    result = score_keywords_semantic_json(client, "m", "img.jpg", ["cat", "dog", "fox"])
    assert result.score_map["cat"] == 1.0
    assert result.score_map["dog"] == 0.0 and result.score_map["fox"] == 0.0
    dog = next(s for s in result.scores if s.keyword == "dog")
    assert dog.matched is False and dog.match_type == "none"
    assert any("did not return scores" in n for n in result.notes)


def test_semantic_json_adapter_case_insensitive_keys():
    client = StubVisionClient(payload='{"Cat": 0.7, "DOG": 0.3}')
    result = score_keywords_semantic_json(client, "m", "img.jpg", ["cat", "dog"])
    assert result.score_map == {"cat": 0.7, "dog": 0.3}


def test_semantic_json_adapter_parse_failure_raises():
    client = StubVisionClient(payload="I cannot do that.")
    with pytest.raises(ValueError, match="JSON probability payload"):
        score_keywords_semantic_json(client, "m", "img.jpg", ["cat"])


def test_semantic_json_adapter_tolerates_fenced_markdown():
    client = StubVisionClient(payload='```json\n{"cat": 0.9}\n```')
    result = score_keywords_semantic_json(client, "m", "img.jpg", ["cat"])
    assert result.score_map["cat"] == pytest.approx(1.0)


def test_semantic_json_adapter_non_numeric_values_score_zero():
    client = StubVisionClient(payload='{"cat": "high", "dog": 0.4}')
    result = score_keywords_semantic_json(client, "m", "img.jpg", ["cat", "dog"])
    assert result.score_map["cat"] == 0.0
    assert result.score_map["dog"] == 1.0  # renormalized


# ---------------------------------------------------------------------------
# Orchestrator: tier ladder and degradation
# ---------------------------------------------------------------------------


def test_orchestrator_tier1_via_factory():
    engine = make_engine(provider="groq_package")
    result = score_keywords(
        engine, "img.jpg",
        logprob_client_factory=lambda: (StubLogprobClient(), "llama-vision"),
    )
    assert result.tier is SCORING_TIER.LOGPROB
    assert result.calibrated is True


def test_orchestrator_falls_back_to_tier3_when_no_logprob_factory():
    engine = make_engine(provider="ollama")
    result = score_keywords(
        engine, "img.jpg", vision_client_factory=lambda: (StubVisionClient(), "llava"),
    )
    assert result.tier is SCORING_TIER.SEMANTIC_JSON


def test_orchestrator_falls_back_to_tier3_on_logprob_unavailable():
    """Tier 1 raising ValueError degrades to tier 3, recorded in notes path."""
    engine = make_engine(provider="google_ai")

    def bad_factory():
        return StubLogprobClient(supports=False), "gemini"

    result = score_keywords(
        engine, "img.jpg",
        logprob_client_factory=bad_factory,
        vision_client_factory=lambda: (StubVisionClient(), "gemini"),
    )
    assert result.tier is SCORING_TIER.SEMANTIC_JSON
    assert result.calibrated is False


def test_orchestrator_tier3_failure_is_explicit_tier0():
    engine = make_engine(provider="nvidia")
    result = score_keywords(
        engine, "img.jpg",
        vision_client_factory=lambda: (StubVisionClient(payload="no json"), "m"),
    )
    assert result.tier is SCORING_TIER.UNAVAILABLE
    assert result.notes and "Semantic JSON scoring failed" in result.notes[0]


def test_orchestrator_tier2_uses_local_pipeline_and_degrades_on_error():
    engine = make_engine()
    result = score_keywords(engine, "img.jpg", local_pipeline=MagicMock(task="vqa"))
    assert result.tier is SCORING_TIER.UNAVAILABLE
    assert "Label-confidence scoring failed" in result.notes[0]


def test_orchestrator_tier2_without_pipeline_is_tier0():
    result = score_keywords(make_engine(), "img.jpg", local_pipeline=None)
    assert result.tier is SCORING_TIER.UNAVAILABLE
    assert "No local pipeline" in result.notes[0]


def test_orchestrator_none_tier_is_unavailable_not_exception():
    result = score_keywords(make_engine(mode="llm"), "img.jpg")
    assert result.tier is SCORING_TIER.UNAVAILABLE
    assert result.score_map == {"A": 0.0, "B": 0.0, "C": 0.0}


def test_orchestrator_never_raises_for_provider_failures():
    """Even exploding factories degrade to tier 0 (programming errors aside)."""

    def exploding_factory():
        raise ConnectionError("network down")

    engine = make_engine(provider="cerebras")
    result = score_keywords(
        engine, "img.jpg",
        logprob_client_factory=exploding_factory,
        vision_client_factory=exploding_factory,
    )
    assert result.tier is SCORING_TIER.UNAVAILABLE


# ---------------------------------------------------------------------------
# ProcessingManager wiring: legacy key + new tier-annotated key
# ---------------------------------------------------------------------------


def test_processing_result_carries_scoring_key_and_legacy_probabilities(tmp_path, monkeypatch):
    # The CLIP rescue must not fire inside these pipeline tests (no model
    # downloads, no real inference during unit runs). monkeypatch restores
    # the flag after the test so it cannot leak into other test files.
    from src.core import keyword_scoring_adapters as _adapters

    monkeypatch.setattr(_adapters, "EMBEDDING_TIER_DISABLED", True)
    """Through the real _process_single_item path, the session result entry
    keeps the legacy post-threshold 'probabilities' map AND gains a tier-
    annotated 'scoring' payload."""
    from PIL import Image

    img_path = tmp_path / "wired.jpg"
    Image.new("RGB", (1, 1), color="black").save(img_path)

    session = SimpleNamespace(
        datasource=SimpleNamespace(type="local", local_path="."),
        engine=make_engine(),
        daminion_client=None,
        is_processing=False,
        results=[],
        processed_items=0,
        failed_items=0,
    )
    # Read later in the pipeline (tag extraction stage).
    session.engine.confidence_threshold = 50
    session.engine.system_prompt = ""

    from src.core.processing import ProcessingManager

    manager = ProcessingManager(session, lambda _m: None, MagicMock())
    manager.model = MagicMock()
    manager.model.task = "image-classification"
    manager.model.return_value = [{"label": "cat", "score": 0.9}]

    with patch(
        "src.core.huggingface_utils.run_local_logprob_inference",
        return_value={"A": 0.7, "B": 0.2, "C": 0.1},
    ):
        manager._process_single_item(img_path)

    assert len(session.results) == 1
    entry = session.results[0]
    # Legacy contract intact (existing export/tests depend on it).
    assert entry["probabilities"] == {"A": 0.7, "B": 0.2, "C": 0.1}
    # New tier-annotated contract.
    assert entry["scoring"]["tier"] == "label_confidence"
    assert entry["scoring"]["calibrated"] is False
    assert entry["scoring"]["scores"][0]["keyword"] == "A"


def test_processing_legacy_enabled_flag_reaches_scoring_pass(tmp_path, monkeypatch):
    # The CLIP rescue must not fire inside these pipeline tests.
    from src.core import keyword_scoring_adapters as _adapters

    monkeypatch.setattr(_adapters, "EMBEDDING_TIER_DISABLED", True)
    """A config with probability_mode='llm' + probability_enabled=True (legacy
    'both') must still run the scoring pass — the selector applies the same
    legacy normalization as the pipeline."""
    from PIL import Image

    img_path = tmp_path / "legacy.jpg"
    Image.new("RGB", (1, 1), color="black").save(img_path)

    session = SimpleNamespace(
        datasource=SimpleNamespace(type="local", local_path="."),
        engine=make_engine(mode="llm"),
        daminion_client=None,
        is_processing=False,
        results=[],
        processed_items=0,
        failed_items=0,
    )
    session.engine.probability_enabled = True
    # Read later in the pipeline (tag extraction stage).
    session.engine.confidence_threshold = 50
    session.engine.system_prompt = ""

    from src.core.processing import ProcessingManager

    manager = ProcessingManager(session, lambda _m: None, MagicMock())
    manager.model = MagicMock()
    manager.model.task = "image-classification"
    manager.model.return_value = [{"label": "cat", "score": 0.9}]

    with patch(
        "src.core.huggingface_utils.run_local_logprob_inference",
        return_value={"A": 0.5, "B": 0.3, "C": 0.2},
    ) as mock_inf:
        manager._process_single_item(img_path)

    mock_inf.assert_called_once()
    assert session.results[0]["scoring"]["tier"] == "label_confidence"
    assert session.results[0]["probabilities"] == {"A": 0.5, "B": 0.3, "C": 0.2}
