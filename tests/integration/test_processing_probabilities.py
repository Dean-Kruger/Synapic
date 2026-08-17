"""
Integration tests for probability scoring through the real ProcessingManager path.

These tests exercise the actual wiring: the helper is NOT mocked, but the
transformers pipeline factory is — so they prove the processing pipeline hands
the already-loaded pipeline to run_local_logprob_inference and that the helper
reuses it (never constructing a fresh pipeline per image).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
from transformers import Pipeline

from src.core.processing import ProcessingManager
from src.core.session import DatasourceConfig, EngineConfig, Session


class StubClassificationPipeline(Pipeline):
    """Concrete Pipeline stand-in whose task is image-classification."""

    def __init__(self, num_labels=3, outputs=None):
        self.task = "image-classification"
        self.model = SimpleNamespace(
            config=SimpleNamespace(num_labels=num_labels)
        )
        self.outputs = outputs if outputs is not None else [
            {"label": "A", "score": 0.85},
            {"label": "B", "score": 0.10},
            {"label": "C", "score": 0.05},
        ]
        self.calls = []

    def _sanitize_parameters(self, **kwargs):
        return {}, {}, {}

    def preprocess(self, inputs):
        return inputs

    def _forward(self, model_inputs):
        return model_inputs

    def postprocess(self, model_outputs):
        return model_outputs

    def __call__(self, inputs, **kwargs):
        self.calls.append((inputs, kwargs))
        return self.outputs


def make_image(tmp_path, name):
    img_path = tmp_path / name
    Image.new("RGB", (1, 1), color="black").save(img_path)
    return img_path


def make_session():
    session = Session()
    session.datasource = DatasourceConfig(type="local", local_path=".")
    session.engine = EngineConfig(
        provider="local",
        model_id="stub-model",
        task="image-classification",
    )
    engine = session.engine
    engine.probability_enabled = True
    engine.probability_candidates = ["A", "B", "C"]
    engine.probability_threshold = 0.0
    return session


def test_probability_scoring_reuses_loaded_pipeline_across_batch(tmp_path):
    """The loaded pipeline must be reused for the probability pass — the
    transformers pipeline factory must never be invoked during processing."""
    session = make_session()
    logs = []
    manager = ProcessingManager(session, logs.append, MagicMock())
    # Simulate the model already loaded by _init_local_model()
    pipe = StubClassificationPipeline(num_labels=3)
    manager.model = pipe

    img1 = make_image(tmp_path, "one.jpg")
    img2 = make_image(tmp_path, "two.jpg")

    # If the helper ever tries to build a new pipeline, fail loudly.
    with patch(
        "src.core.huggingface_utils.pipeline",
        side_effect=AssertionError("pipeline factory must not be called per image"),
    ):
        manager._process_single_item(img1)
        manager._process_single_item(img2)

    # The pipeline object itself was called twice for classification, plus once
    # per image for the probability pass — never reconstructed.
    assert len(pipe.calls) == 4
    # The probability pass requests every label via top_k.
    prob_calls = [c for c in pipe.calls if isinstance(c[0], str)]
    assert len(prob_calls) == 2
    assert all(kwargs == {"top_k": 3} for _, kwargs in prob_calls)

    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    assert len(session.results) == 2
    for entry in session.results:
        assert entry["status"] == "Success"
        assert entry["probabilities"] == {"A": 0.85, "B": 0.10, "C": 0.05}
