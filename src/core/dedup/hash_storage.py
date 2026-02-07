"""
Hash Storage Utilities
======================

Functions for serializing and deserializing hash results
to/from various storage formats (JSON, delimited, dict).

Adapted from: https://github.com/deanable/python-dedupe
"""

from enum import Enum
import json
from typing import Dict, Union, Any

from src.core.dedup.hash_calculator import HashResult


class HashFormat(Enum):
    JSON = "json"
    DELIMITED = "delimited"
    SEPARATE_FIELDS = "separate_fields"


def format_hash_for_storage(hash_results: Dict[str, HashResult], format: HashFormat = HashFormat.JSON) -> Union[str, Dict[str, Any]]:
    """
    Formats hash results for storage based on the specified format.
    """
    # Convert HashResult objects to dicts for serialization
    data = {}
    for algo, result in hash_results.items():
        data[algo] = {
            'hash_value': result.hash_value,
            'algorithm': result.algorithm,
            'timestamp': result.timestamp,
            'bit_length': result.bit_length,
            'metadata': result.metadata
        }

    if format == HashFormat.JSON:
        return json.dumps(data)

    elif format == HashFormat.DELIMITED:
        # Format: algo:hash_value|algo:hash_value
        parts = []
        # Sort keys for deterministic output
        for algo in sorted(data.keys()):
            hash_val = data[algo]['hash_value']
            parts.append(f"{algo}:{hash_val}")
        return "|".join(parts)

    elif format == HashFormat.SEPARATE_FIELDS:
        return data

    else:
        raise ValueError(f"Unsupported format: {format}")


def parse_hash_from_storage(stored_value: Union[str, Dict[str, Any]], format: HashFormat = HashFormat.JSON) -> Dict[str, Any]:
    """
    Parses stored hash data back into a dictionary.
    Returns a dictionary of dicts, not HashResult objects.
    """
    if format == HashFormat.JSON:
        if not isinstance(stored_value, str):
            raise ValueError("Stored value must be a string for JSON format.")
        try:
            return json.loads(stored_value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    elif format == HashFormat.DELIMITED:
        if not isinstance(stored_value, str):
            raise ValueError("Stored value must be a string for DELIMITED format.")
        data = {}
        if not stored_value:
            return {}

        parts = stored_value.split('|')
        for part in parts:
            if ':' not in part:
                continue
            algo, hash_val = part.split(':', 1)
            data[algo] = {
                'hash_value': hash_val,
                'algorithm': algo,
                'timestamp': None,
                'bit_length': None,
                'metadata': {}
            }
        return data

    elif format == HashFormat.SEPARATE_FIELDS:
        if not isinstance(stored_value, dict):
            raise ValueError("Stored value must be a dict for SEPARATE_FIELDS format.")
        return stored_value

    else:
        raise ValueError(f"Unsupported format: {format}")


def validate_hash_format(stored_value: Any, format: HashFormat = HashFormat.JSON) -> bool:
    """
    Validates if the stored value matches the expected format.
    """
    try:
        parse_hash_from_storage(stored_value, format)
        return True
    except (ValueError, TypeError, AttributeError):
        return False
