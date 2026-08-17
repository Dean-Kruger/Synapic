import pytest
from unittest.mock import Mock, patch
from src.core.huggingface_utils import run_local_logprob_inference


def test_run_local_logprob_inference():
    """Test the run_local_logprob_inference function."""
    # Mock inputs
    model_id = "test-model"
    image_path = "test_image.jpg"
    candidates = ["cat", "dog", "bird"]
    device = 0

    # Mock the pipeline output with scores
    mock_output = [
        {"label": "cat", "score": 0.7},
        {"label": "dog", "score": 0.2},
        {"label": "bird", "score": 0.1}
    ]

    with patch('src.core.huggingface_utils.pipeline') as mock_pipeline:
        # Setup mock pipeline to return scores
        mock_pipe_instance = Mock()
        mock_pipe_instance.return_value = mock_output
        mock_pipeline.return_value = mock_pipe_instance

        # Call the function
        result = run_local_logprob_inference(model_id, image_path, candidates, device)

        # Verify pipeline was called with correct parameters
        mock_pipeline.assert_called_once_with(
            "image-classification",
            model=model_id,
            device=device,
            return_all_scores=True
        )

        # Verify the function was called with the image
        mock_pipe_instance.assert_called_once_with(image_path)

        # Verify result mapping
        expected = {"cat": 0.7, "dog": 0.2, "bird": 0.1}
        assert result == expected


def test_run_local_logprob_inference_empty_candidates():
    """Test with empty candidates list."""
    model_id = "test-model"
    image_path = "test_image.jpg"
    candidates = []
    device = 0

    with patch('src.core.huggingface_utils.pipeline') as mock_pipeline:
        mock_pipe_instance = Mock()
        mock_pipe_instance.return_value = []
        mock_pipeline.return_value = mock_pipe_instance

        result = run_local_logprob_inference(model_id, image_path, candidates, device)

        assert result == {}


def test_run_local_logprob_inference_single_candidate():
    """Test with single candidate."""
    model_id = "test-model"
    image_path = "test_image.jpg"
    candidates = ["cat"]
    device = 0

    mock_output = [{"label": "cat", "score": 0.95}]

    with patch('src.core.huggingface_utils.pipeline') as mock_pipeline:
        mock_pipe_instance = Mock()
        mock_pipe_instance.return_value = mock_output
        mock_pipeline.return_value = mock_pipe_instance

        result = run_local_logprob_inference(model_id, image_path, candidates, device)

        assert result == {"cat": 0.95}