"""
Safe Literal and JSON Parsing Helpers
=====================================

This module contains defensive parsing helpers for model responses and other
loosely structured text inputs.

Why these helpers matter:
- LLM output may look like JSON, Python literals, or a mixture of both.
- `ast.literal_eval` is safer than `eval`, but deeply nested input can still
  cause excessive resource usage.
- Centralising the parsing rules keeps the rest of the codebase free from
  repeated ad-hoc `try/except` parsing logic.

The main entry point, `safe_parse_python_literal`, applies a layered strategy:
1. Reject obviously dangerous input sizes.
2. Reject unreasonable nesting depth before parsing.
3. Attempt standard JSON parsing first.
4. Fall back to `ast.literal_eval` for Python-style literals.
"""

import ast
import json
import logging
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

def safe_parse_python_literal(text: str, max_depth: int = 100, max_length: int = 100000) -> Any:
    """
    Safely parse a string that might be a Python literal (e.g., from an LLM) or JSON.

    This function provides a safer alternative to ast.literal_eval by:
    1. Limiting the total length of the input string.
    2. Limiting the nesting depth of structures (dicts, lists, tuples).
    3. Attempting standard JSON parsing first.

    Args:
        text: The string to parse.
        max_depth: Maximum allowed nesting depth of brackets and braces.
        max_length: Maximum allowed length of the input string.

    Returns:
        The parsed data (typically a dict or list).

    Raises:
        ValueError: If the input is too long, too deep, or cannot be parsed.
    """
    if not text:
        return None

    if not isinstance(text, str):
        return text

    if len(text) > max_length:
        logger.warning(f"Rejected parsing of string: length {len(text)} exceeds limit of {max_length}")
        raise ValueError(f"Input length exceeds limit of {max_length}")

    # 1. Check nesting depth to prevent Denial of Service via deeply nested structures
    if not _check_nesting_depth(text, max_depth):
        logger.warning(f"Rejected parsing of string: nesting depth exceeds limit of {max_depth}")
        raise ValueError(f"Nesting depth exceeds limit of {max_depth}")

    # 2. Try standard JSON first (it's the most robust and preferred)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Use ast.literal_eval as a fallback for Python-style literals
    # In modern Python (3.9+), ast.literal_eval is relatively safe but still vulnerable to DoS.
    # Our depth check above mitigates the DoS risk.
    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError, MemoryError) as e:
        logger.debug(f"Failed to parse literal: {e}")
        raise ValueError(f"Failed to parse literal: {e}")


def extract_dict_from_text(
    text: str,
    *,
    expected_keys: Optional[Iterable[str]] = None,
    max_depth: int = 100,
    max_length: int = 100000,
) -> Optional[dict]:
    """
    Extract the first useful dictionary payload embedded in free-form text.
    """
    if not text or not isinstance(text, str):
        return None

    key_set = {key for key in (expected_keys or []) if key}

    for candidate in _iter_candidate_dict_strings(text):
        parsed = _parse_candidate_dict(
            candidate,
            expected_keys=key_set,
            max_depth=max_depth,
            max_length=max_length,
        )
        if parsed is not None:
            return parsed

    repaired_candidate = _repair_truncated_dict_candidate(text)
    if repaired_candidate:
        return _parse_candidate_dict(
            repaired_candidate,
            expected_keys=key_set,
            max_depth=max_depth,
            max_length=max_length,
        )

    return None


def _parse_candidate_dict(
    candidate: str,
    *,
    expected_keys: set[str],
    max_depth: int,
    max_length: int,
) -> Optional[dict]:
    try:
        parsed = safe_parse_python_literal(candidate, max_depth=max_depth, max_length=max_length)
    except ValueError as e:
        logger.debug(f"Failed to parse candidate payload: {e}")
        return None

    if not isinstance(parsed, dict):
        return None

    if expected_keys and not any(key in parsed for key in expected_keys):
        logger.debug("Rejected parsed dict because it did not contain any expected keys")
        return None

    return parsed


def _iter_candidate_dict_strings(text: str):
    for block in _iter_fenced_code_blocks(text):
        stripped = block.strip()
        if stripped:
            yield stripped

    yield from _iter_balanced_dict_strings(text)


def _iter_fenced_code_blocks(text: str):
    fence = "```"
    start = 0

    while True:
        block_start = text.find(fence, start)
        if block_start == -1:
            return

        content_start = block_start + len(fence)
        newline_index = text.find("\n", content_start)
        if newline_index == -1:
            return

        block_end = text.find(fence, newline_index + 1)
        if block_end == -1:
            return

        yield text[newline_index + 1:block_end]
        start = block_end + len(fence)


def _iter_balanced_dict_strings(text: str):
    start_idx = None
    stack = []
    in_string = False
    quote_char = None
    escaped = False

    for idx, char in enumerate(text):
        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char in "\"'":
            if not in_string:
                in_string = True
                quote_char = char
            elif char == quote_char:
                in_string = False
                quote_char = None
            continue

        if in_string:
            continue

        if char in "{[":
            if start_idx is None and char == "{":
                start_idx = idx
            if start_idx is not None:
                stack.append(char)
            continue

        if char in "}]":
            if start_idx is None or not stack:
                continue

            opener = stack[-1]
            if (opener, char) not in {("{", "}"), ("[", "]")}:
                start_idx = None
                stack.clear()
                continue

            stack.pop()
            if start_idx is not None and not stack:
                yield text[start_idx:idx + 1]
                start_idx = None


def _repair_truncated_dict_candidate(text: str) -> Optional[str]:
    start_idx = text.find("{")
    if start_idx == -1:
        return None

    candidate = text[start_idx:].strip()
    if not candidate:
        return None

    closers = []
    in_string = False
    quote_char = None
    escaped = False

    for char in candidate:
        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char in "\"'":
            if not in_string:
                in_string = True
                quote_char = char
            elif char == quote_char:
                in_string = False
                quote_char = None
            continue

        if in_string:
            continue

        if char == "{":
            closers.append("}")
        elif char == "[":
            closers.append("]")
        elif char in "}]":
            if not closers or closers[-1] != char:
                return None
            closers.pop()

    if not closers:
        return None

    logger.debug("Attempting to repair truncated dictionary candidate")
    return candidate + "".join(reversed(closers))

def _check_nesting_depth(text: str, max_depth: int) -> bool:
    """
    Estimate bracket nesting depth without fully parsing the payload.

    The check is intentionally lightweight and string-aware so quoted JSON
    fragments do not falsely increase the measured structural depth.
    """
    depth = 0
    in_string = False
    quote_char = None
    escaped = False

    for char in text:
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if char in '"\'':
            if not in_string:
                in_string = True
                quote_char = char
            elif char == quote_char:
                in_string = False
                quote_char = None
            continue

        if not in_string:
            if char in '[{(':
                depth += 1
                if depth > max_depth:
                    return False
            elif char in ']})':
                depth -= 1

    # We don't strictly require depth == 0 here as ast.literal_eval
    # will handle unbalanced structures by raising a SyntaxError.
    return True
