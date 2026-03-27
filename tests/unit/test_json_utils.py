from src.utils.json_utils import extract_dict_from_text, safe_parse_python_literal


def test_extract_dict_from_fenced_json():
    text = """Here is the result:

```json
{"description": "Blue sky", "category": "Nature", "keywords": ["sky", "blue"]}
```
"""

    parsed = extract_dict_from_text(text, expected_keys={"description", "category", "keywords"})

    assert parsed == {
        "description": "Blue sky",
        "category": "Nature",
        "keywords": ["sky", "blue"],
    }


def test_extract_dict_from_python_literal_text():
    text = "Model output: {'description': 'City street', 'keywords': ['night', 'lights']}"

    parsed = extract_dict_from_text(text, expected_keys={"description", "keywords"})

    assert parsed == {
        "description": "City street",
        "keywords": ["night", "lights"],
    }


def test_extract_dict_repairs_truncated_payload():
    text = 'Response: {"description": "Sunset", "category": "Nature", "keywords": ["orange", "sky"]'

    parsed = extract_dict_from_text(text, expected_keys={"description", "category", "keywords"})

    assert parsed == {
        "description": "Sunset",
        "category": "Nature",
        "keywords": ["orange", "sky"],
    }


def test_extract_dict_rejects_unrelated_objects():
    text = 'Prefix {"foo": "bar"} suffix'

    parsed = extract_dict_from_text(text, expected_keys={"description", "category", "keywords"})

    assert parsed is None


def test_safe_parse_python_literal_rejects_too_deep_input():
    text = "[" * 5 + "0" + "]" * 5

    try:
        safe_parse_python_literal(text, max_depth=2)
    except ValueError as exc:
        assert "Nesting depth exceeds limit" in str(exc)
    else:
        raise AssertionError("Expected safe_parse_python_literal to reject deep input")
