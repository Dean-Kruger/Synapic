import pytest
from src.core import image_processing

def test_extract_tags_returns_probabilities():
    dummy_result = [{"generated_text": "dummy"}]
    cat, kws, desc, probs = image_processing.extract_tags_from_result(
        dummy_result, "image-to-text", probabilities={"A": 0.7}
    )
    assert probs == {"A": 0.7}

def test_extract_tags_returns_empty_probabilities_when_none():
    dummy_result = [{"generated_text": "dummy"}]
    cat, kws, desc, probs = image_processing.extract_tags_from_result(
        dummy_result, "image-to-text"
    )
    assert probs == {}