from src.core import image_processing


def test_extract_tags_returns_probabilities():
    dummy_result = [{"generated_text": "dummy"}]
    _cat, _kws, _desc, probs = image_processing.extract_tags_from_result(
        dummy_result, "image-to-text", probabilities={"A": 0.7}
    )
    assert probs == {"A": 0.7}


def test_extract_tags_returns_empty_probabilities_when_none():
    dummy_result = [{"generated_text": "dummy"}]
    _cat, _kws, _desc, probs = image_processing.extract_tags_from_result(
        dummy_result, "image-to-text"
    )
    assert probs == {}


def test_extract_tags_with_semantics_handles_four_tuple():
    """extract_tags_with_semantics must survive the 4-tuple return of
    extract_tags_from_result (regression: used to unpack only 3 values)."""
    result = [
        {"label": "cat", "score": 0.9},
        {"label": "dog", "score": 0.1},
    ]
    _cat, kws, _desc, semantic = image_processing.extract_tags_with_semantics(
        result, "image-classification", threshold=0.0
    )
    assert kws == ["Cat", "Dog"]
    assert isinstance(semantic, dict)
