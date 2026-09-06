"""Unit tests for run_local_logprob_inference (probability scoring helper)."""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from transformers import Pipeline

from src.core import huggingface_utils
from src.core.huggingface_utils import run_local_logprob_inference


class StubPipeline(Pipeline):
    """A concrete Pipeline stand-in used to verify the helper reuses loaded
    pipelines instead of constructing a new one per image."""

    def __init__(self, task="image-classification", num_labels=3, outputs=None):
        self.task = task
        self.model = SimpleNamespace(
            config=SimpleNamespace(num_labels=num_labels)
        )
        self.outputs = outputs if outputs is not None else []
        self.call_args_list = []

    # Abstract-method implementations required to be concrete.
    def _sanitize_parameters(self, **kwargs):
        return {}, {}, {}

    def preprocess(self, inputs):
        return inputs

    def _forward(self, model_inputs):
        return model_inputs

    def postprocess(self, model_outputs):
        return model_outputs

    def __call__(self, inputs, **kwargs):
        self.call_args_list.append((inputs, kwargs))
        return self.outputs


def test_run_local_logprob_inference_with_model_id():
    """A model id constructs an image-classification pipeline and requests
    every label (top_k) so candidates are not truncated by the default top 5."""
    model_id = "test-model"
    image_path = "test_image.jpg"
    candidates = ["cat", "dog", "bird"]
    device = 0

    mock_output = [
        {"label": "cat", "score": 0.7},
        {"label": "dog", "score": 0.2},
        {"label": "bird", "score": 0.1},
    ]

    with patch("src.core.huggingface_utils.pipeline") as mock_pipeline:
        mock_pipe_instance = Mock()
        mock_pipe_instance.return_value = mock_output
        mock_pipeline.return_value = mock_pipe_instance

        result = run_local_logprob_inference(model_id, image_path, candidates, device)

        mock_pipeline.assert_called_once_with(
            "image-classification",
            model=model_id,
            device=device,
        )
        # The helper must ask for all labels (top_k) rather than the default 5.
        mock_pipe_instance.assert_called_once_with(image_path, top_k=10_000)
        assert result == {"cat": 0.7, "dog": 0.2, "bird": 0.1}


def test_run_local_logprob_inference_reuses_loaded_pipeline():
    """An already-loaded pipeline must be reused directly — the pipeline
    factory must NOT be called (rebuilding reloads the model per image)."""
    outputs = [
        {"label": "cat", "score": 0.7},
        {"label": "dog", "score": 0.2},
        {"label": "bird", "score": 0.1},
    ]
    pipe = StubPipeline(task="image-classification", num_labels=3, outputs=outputs)

    with patch("src.core.huggingface_utils.pipeline") as mock_pipeline:
        result = run_local_logprob_inference(pipe, "test_image.jpg", ["cat", "dog", "bird"], device=-1)

    mock_pipeline.assert_not_called()
    assert len(pipe.call_args_list) == 1
    inputs, kwargs = pipe.call_args_list[0]
    assert inputs == "test_image.jpg"
    assert kwargs == {"top_k": 3}
    assert result == {"cat": 0.7, "dog": 0.2, "bird": 0.1}


def test_run_local_logprob_inference_top_k_uses_model_label_count():
    """top_k should be derived from the model's label count, not hardcoded."""
    pipe = StubPipeline(
        task="image-classification",
        num_labels=1_000,
        outputs=[{"label": "cat", "score": 0.9}],
    )
    result = run_local_logprob_inference(pipe, "img.jpg", ["cat"], device=-1)
    assert pipe.call_args_list[0][1] == {"top_k": 1_000}
    assert result == {"cat": 0.9}


def test_run_local_logprob_inference_rejects_non_classification_pipeline():
    """Passing a loaded pipeline whose task is not image-classification must
    raise so the caller can fall back gracefully (no probabilities available)."""
    pipe = StubPipeline(task="image-text-to-text", outputs=[{"generated_text": "n/a"}])
    with pytest.raises(ValueError, match="image-classification"):
        run_local_logprob_inference(pipe, "img.jpg", ["cat"], device=-1)


def test_run_local_logprob_inference_empty_candidates():
    """Empty candidates short-circuit without touching any pipeline."""
    with patch("src.core.huggingface_utils.pipeline") as mock_pipeline:
        result = run_local_logprob_inference("test-model", "test_image.jpg", [], 0)

    assert result == {}
    mock_pipeline.assert_not_called()


def test_run_local_logprob_inference_single_candidate():
    """Single-candidate case maps the score and defaults missing labels to 0.0."""
    model_id = "test-model"
    image_path = "test_image.jpg"
    candidates = ["cat"]
    device = 0

    mock_output = [{"label": "cat", "score": 0.95}]

    with patch("src.core.huggingface_utils.pipeline") as mock_pipeline:
        mock_pipe_instance = Mock()
        mock_pipe_instance.return_value = mock_output
        mock_pipeline.return_value = mock_pipe_instance

        result = run_local_logprob_inference(model_id, image_path, candidates, device)

        assert result == {"cat": 0.95}


def test_run_local_logprob_inference_missing_candidates_default_to_zero():
    """Candidates the model never outputs must map to 0.0, not KeyError."""
    pipe = StubPipeline(
        task="image-classification",
        num_labels=2,
        outputs=[{"label": "cat", "score": 0.9}, {"label": "dog", "score": 0.1}],
    )
    result = run_local_logprob_inference(pipe, "img.jpg", ["cat", "fox"], device=-1)
    assert result == {"cat": 0.9, "fox": 0.0}


def test_matches_candidates_case_insensitively_and_strips_whitespace():
    """Candidate matching must ignore case and surrounding whitespace."""
    pipe = StubPipeline(
        task="image-classification",
        num_labels=2,
        outputs=[{"label": "Cat", "score": 0.9}, {"label": "Dog", "score": 0.1}],
    )
    result = run_local_logprob_inference(pipe, "img.jpg", ["cat", " DOG "], device=-1)
    assert result == {"cat": 0.9, " DOG ": 0.1}


def test_fuzzy_matches_close_labels():
    """Candidates that are close to a model label (e.g. 'indoor' vs 'indoor
    office') fall back to a fuzzy match instead of scoring 0.0."""
    pipe = StubPipeline(
        task="image-classification",
        num_labels=3,
        outputs=[
            {"label": "indoor office", "score": 0.8},
            {"label": "outdoor nature", "score": 0.15},
            {"label": "urban street", "score": 0.05},
        ],
    )
    result = run_local_logprob_inference(pipe, "img.jpg", ["indoor", "urban"], device=-1)
    assert result == {"indoor": 0.8, "urban": 0.05}


def test_all_unmatched_candidates_raise_instead_of_silent_zeros():
    """A candidate set that matches nothing (e.g. the UI default A,B,C,D
    against an ImageNet model) must raise loudly rather than return all zeros."""
    pipe = StubPipeline(
        task="image-classification",
        num_labels=2,
        outputs=[{"label": "cat", "score": 0.9}, {"label": "dog", "score": 0.1}],
    )
    with pytest.raises(ValueError, match="none of the candidate tokens matched the selected model"):
        run_local_logprob_inference(pipe, "img.jpg", ["A", "B", "C", "D"], device=-1)


def test_partial_match_keeps_zero_for_unmatched_candidates():
    """When only some candidates match, the others stay 0.0 and the call succeeds."""
    pipe = StubPipeline(
        task="image-classification",
        num_labels=2,
        outputs=[{"label": "cat", "score": 0.9}, {"label": "dog", "score": 0.1}],
    )
    result = run_local_logprob_inference(pipe, "img.jpg", ["cat", "A"], device=-1)
    assert result == {"cat": 0.9, "A": 0.0}


# ---------------------------------------------------------------------------
# get_model_label_tokens (candidate preloading from the local cache)
# ---------------------------------------------------------------------------


def _make_cached_model(tmp_path, model_id="org/model", id2label=None, raw_config=None):
    """Create a fake Hugging Face cache entry for a model in tmp_path."""
    model_dir = tmp_path / f"models--{model_id.replace('/', '--')}"
    snapshot = model_dir / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    config = dict(raw_config or {})
    if id2label is not None:
        config["id2label"] = id2label
    (snapshot / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


def test_get_model_label_tokens_dict_id2label(tmp_path):
    """A dict id2label yields its ordered values as candidate tokens."""
    cache = _make_cached_model(tmp_path, id2label={0: "cat", 1: "dog", 2: "bird"})
    with patch.object(huggingface_utils, "HUGGINGFACE_HUB_CACHE", str(cache)):
        labels = huggingface_utils.get_model_label_tokens("org/model")
    assert labels == ["cat", "dog", "bird"]


def test_get_model_label_tokens_dedupes_and_strips(tmp_path):
    """Duplicates and empty labels are dropped; whitespace is stripped."""
    cache = _make_cached_model(
        tmp_path, id2label={0: " cat ", 1: "cat", 2: "", 3: "dog", 4: "dog"}
    )
    with patch.object(huggingface_utils, "HUGGINGFACE_HUB_CACHE", str(cache)):
        labels = huggingface_utils.get_model_label_tokens("org/model")
    assert labels == ["cat", "dog"]


def test_get_model_label_tokens_list_id2label(tmp_path):
    """A list-shaped id2label is returned as-is (deduped)."""
    cache = _make_cached_model(tmp_path, id2label=["a", "b", "a"])
    with patch.object(huggingface_utils, "HUGGINGFACE_HUB_CACHE", str(cache)):
        labels = huggingface_utils.get_model_label_tokens("org/model")
    assert labels == ["a", "b"]


def test_get_model_label_tokens_no_labels(tmp_path):
    """Models without an id2label (e.g. captioning VLMs) return []."""
    cache = _make_cached_model(tmp_path, raw_config={"architectures": ["Qwen2VL"]})
    with patch.object(huggingface_utils, "HUGGINGFACE_HUB_CACHE", str(cache)):
        labels = huggingface_utils.get_model_label_tokens("org/model")
    assert labels == []


def test_get_model_label_tokens_missing_model(tmp_path):
    """A model not present in the cache returns [] without raising."""
    with patch.object(huggingface_utils, "HUGGINGFACE_HUB_CACHE", str(tmp_path)):
        labels = huggingface_utils.get_model_label_tokens("org/unknown")
    assert labels == []


def test_get_model_label_tokens_corrupt_config(tmp_path):
    """A corrupt config.json returns [] without raising."""
    model_dir = tmp_path / "models--org--model" / "snapshots" / "abc123"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{not json", encoding="utf-8")
    with patch.object(huggingface_utils, "HUGGINGFACE_HUB_CACHE", str(tmp_path)):
        labels = huggingface_utils.get_model_label_tokens("org/model")
    assert labels == []
