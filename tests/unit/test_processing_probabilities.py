from unittest.mock import MagicMock, patch

from PIL import Image

import src.core.processing as processing_module
from src.core.processing import ProcessingManager
from src.core.session import DatasourceConfig, EngineConfig, Session


def make_test_session():
    session = Session()
    session.datasource = DatasourceConfig(type="local", local_path=".")
    session.engine = EngineConfig(provider="local", model_id="test", task="image-classification")
    return session


def make_image(tmp_path, name="dummy.jpg"):
    img_path = tmp_path / name
    img = Image.new("RGB", (1, 1), color="black")
    img.save(img_path)
    return img_path


def make_manager(session, tmp_path):
    logs = []
    def log_cb(msg):
        logs.append(msg)

    manager = ProcessingManager(session, log_cb, MagicMock())
    # Set up a mock model so that the probability scoring code can access it
    manager.model = MagicMock()
    manager.model.task = session.engine.task
    manager.model.return_value = [
        {"label": "cat", "score": 0.7},
        {"label": "dog", "score": 0.2},
        {"label": "bird", "score": 0.1},
    ]
    return manager, logs


def test_processing_logs_probabilities(monkeypatch, tmp_path):
    # Create a tiny valid image file (1x1 black JPEG)
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_enabled = True
    engine.probability_candidates = ["A", "B", "C", "D"]
    engine.probability_threshold = 0.0

    manager, logs = make_manager(session, tmp_path)

    # Mock the helper to avoid heavy loading
    with patch("src.core.huggingface_utils.run_local_logprob_inference") as mock_inf:
        mock_inf.return_value = {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
        manager._process_single_item(img_path)

    # Verify each candidate was logged with its score and PASS status
    # (threshold 0.0 means every candidate passes)
    assert "  A: 0.700 PASS" in logs
    assert "  B: 0.200 PASS" in logs
    assert "  C: 0.080 PASS" in logs
    assert "  D: 0.020 PASS" in logs
    # Verify the helper was called with correct args
    mock_inf.assert_called_once()
    args, _kwargs = mock_inf.call_args
    assert str(args[1]) == str(img_path)
    assert args[2] == ["A", "B", "C", "D"]

    # The item must complete end-to-end and carry the probability map into results
    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    assert len(session.results) == 1
    entry = session.results[0]
    assert entry["status"] == "Success"
    assert entry["probabilities"] == {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}


def test_processing_probability_threshold_filters_map(monkeypatch, tmp_path):
    """A configured threshold filters the probability map stored in results."""
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_enabled = True
    engine.probability_candidates = ["A", "B", "C", "D"]
    engine.probability_threshold = 0.1

    manager, logs = make_manager(session, tmp_path)

    with patch("src.core.huggingface_utils.run_local_logprob_inference") as mock_inf:
        mock_inf.return_value = {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
        manager._process_single_item(img_path)

    # The log lists every candidate with PASS/FAIL against the 0.1 threshold
    assert "  A: 0.700 PASS" in logs
    assert "  B: 0.200 PASS" in logs
    assert "  C: 0.080 FAIL" in logs
    assert "  D: 0.020 FAIL" in logs

    assert not any("Failed" in m for m in logs)
    entry = session.results[0]
    assert entry["probabilities"] == {"A": 0.7, "B": 0.2}


def test_processing_helper_failure_falls_back_to_normal_flow(monkeypatch, tmp_path):
    """If probability inference raises (e.g. unsupported model), the item still
    completes through the normal caption flow (requirement: hide on failure)."""
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_enabled = True
    engine.probability_candidates = ["A", "B", "C", "D"]
    engine.probability_threshold = 0.0

    manager, logs = make_manager(session, tmp_path)

    with patch(
        "src.core.huggingface_utils.run_local_logprob_inference",
        side_effect=ValueError("unsupported pipeline task"),
    ) as mock_inf:
        manager._process_single_item(img_path)

    mock_inf.assert_called_once()
    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    assert len(session.results) == 1
    assert session.results[0]["status"] == "Success"
    assert session.results[0]["probabilities"] == {}


def test_processing_llm_only_mode_skips_probability(monkeypatch, tmp_path):
    """LLM-only mode never calls the probability helper."""
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_mode = "llm"
    engine.probability_enabled = False
    engine.probability_candidates = ["A", "B", "C", "D"]

    manager, logs = make_manager(session, tmp_path)

    with patch(
        "src.core.huggingface_utils.run_local_logprob_inference",
        side_effect=AssertionError("probability helper must not run in LLM-only mode"),
    ) as mock_inf:
        manager._process_single_item(img_path)

    mock_inf.assert_not_called()
    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    assert len(session.results) == 1
    assert session.results[0]["status"] == "Success"
    assert session.results[0]["probabilities"] == {}


def test_processing_probability_only_mode_tags_from_scores(monkeypatch, tmp_path):
    """Probability-only mode derives tags from the candidate scores and skips
    the model inference entirely."""
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_mode = "probability"
    engine.probability_candidates = ["A", "B", "C", "D"]
    engine.probability_threshold = 0.0

    manager, logs = make_manager(session, tmp_path)
    manager.model.reset_mock()

    with patch("src.core.huggingface_utils.run_local_logprob_inference") as mock_inf:
        mock_inf.return_value = {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
        manager._process_single_item(img_path)

    # The model itself was never called for caption/LLM inference
    manager.model.assert_not_called()
    # Per-candidate PASS lines still logged
    assert "  A: 0.700 PASS" in logs
    assert "  D: 0.020 PASS" in logs
    # A summary line names the derived category and keywords
    assert any("Probability tagging:" in m for m in logs)

    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    assert len(session.results) == 1
    entry = session.results[0]
    assert entry["status"] == "Success"
    assert entry["probabilities"] == {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
    assert "Kws: 4" in entry["tags"]
    assert "Cat: A" in entry["tags"]


def test_processing_probability_only_mode_threshold_filters_keywords(monkeypatch, tmp_path):
    """In probability-only mode, candidates below the threshold are excluded
    from the derived keywords."""
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_mode = "probability"
    engine.probability_candidates = ["A", "B", "C", "D"]
    engine.probability_threshold = 0.1

    manager, logs = make_manager(session, tmp_path)
    manager.model.reset_mock()

    with patch("src.core.huggingface_utils.run_local_logprob_inference") as mock_inf:
        mock_inf.return_value = {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
        manager._process_single_item(img_path)

    manager.model.assert_not_called()
    assert "  C: 0.080 FAIL" in logs
    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    entry = session.results[0]
    assert entry["probabilities"] == {"A": 0.7, "B": 0.2}
    assert "Kws: 2" in entry["tags"]
    assert "Cat: A" in entry["tags"]


def test_processing_legacy_enabled_flag_maps_to_both(monkeypatch, tmp_path):
    """Configs that only set probability_enabled=True (no mode field) behave
    like 'both': probability scores plus the normal LLM flow."""
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_enabled = True
    engine.probability_candidates = ["A", "B", "C", "D"]
    engine.probability_threshold = 0.0

    manager, logs = make_manager(session, tmp_path)

    with patch("src.core.huggingface_utils.run_local_logprob_inference") as mock_inf:
        mock_inf.return_value = {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
        manager._process_single_item(img_path)

    mock_inf.assert_called_once()
    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    assert len(session.results) == 1
    entry = session.results[0]
    assert entry["status"] == "Success"
    # The caption path still ran: model was called for classification
    assert entry["probabilities"] == {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}


def test_processing_fallback_extraction_still_works(monkeypatch, tmp_path):
    """Regression: the 3-tuple fallback unpack of extract_tags_from_result in
    processing.py must be a 4-tuple unpack now that the function returns four
    values."""
    img_path = make_image(tmp_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_enabled = False

    manager, logs = make_manager(session, tmp_path)

    # Force the fallback path by making the primary extractor unavailable
    with patch.object(
        processing_module.image_processing,
        "extract_tags_with_semantics",
        side_effect=AttributeError("semantics unavailable"),
    ):
        manager._process_single_item(img_path)

    assert not any("Failed" in m for m in logs), f"Item failed: {logs}"
    assert len(session.results) == 1
    assert session.results[0]["status"] == "Success"
