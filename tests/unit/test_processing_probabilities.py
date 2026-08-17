import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PIL import Image
from src.core.session import Session, EngineConfig, DatasourceConfig
from src.core.processing import ProcessingManager

def make_test_session():
    session = Session()
    session.datasource = DatasourceConfig(type="local", local_path=".")
    session.engine = EngineConfig(provider="local", model_id="test", task="image-to-text")
    return session

def test_processing_logs_probabilities(monkeypatch, tmp_path):
    # Create a tiny valid image file (1x1 black JPEG)
    img_path = tmp_path / "dummy.jpg"
    img = Image.new('RGB', (1, 1), color='black')
    img.save(img_path)

    session = make_test_session()
    engine = session.engine
    engine.provider = "local"
    engine.probability_enabled = True
    engine.probability_candidates = ["A", "B", "C", "D"]
    engine.probability_threshold = 0.0

    logs = []
    def log_cb(msg):
        logs.append(msg)

    progress_cb = MagicMock()
    manager = ProcessingManager(session, log_cb, progress_cb)

    # Set up a mock model so that the probability scoring code can access it
    manager.model = MagicMock()
    manager.model.task = engine.task

    # Mock the helper to avoid heavy loading
    with patch('src.core.huggingface_utils.run_local_logprob_inference') as mock_inf:
        mock_inf.return_value = {"A": 0.7, "B": 0.2, "C": 0.08, "D": 0.02}
        # We don't need to actually run the model, just ensure the helper is called
        manager._process_single_item(img_path)

    # Verify that a probability line was logged
    assert any("Probabilities:" in m for m in logs), f"No probability log found in {logs}"
    # Verify the helper was called with correct args
    mock_inf.assert_called_once()
    args, kwargs = mock_inf.call_args
    assert str(args[1]) == str(img_path)
    assert args[2] == ["A", "B", "C", "D"]