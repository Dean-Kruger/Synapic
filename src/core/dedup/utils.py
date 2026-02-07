"""
Deduplication Utilities
=======================

Utility functions for image metadata retrieval and formatting.

Adapted from: https://github.com/deanable/python-dedupe
"""

import os
from PIL import Image
from typing import Dict, Any


def get_image_metadata(image_path: str) -> Dict[str, Any]:
    """
    Retrieves metadata for an image file, including file size, modification time,
    dimensions, and format.
    Returns a dictionary with keys: 'file_size', 'mtime', 'width', 'height', 'format', 'mode'.
    """
    metadata = {}
    try:
        stat = os.stat(image_path)
        metadata['file_size'] = stat.st_size
        metadata['mtime'] = stat.st_mtime

        with Image.open(image_path) as img:
            metadata['width'] = img.width
            metadata['height'] = img.height
            metadata['format'] = img.format
            metadata['mode'] = img.mode

    except Exception as e:
        metadata['error'] = str(e)

    return metadata


def format_file_size(num_bytes: int) -> str:
    """
    Formats a file size in bytes to a human-readable string (e.g. '1.5 MB').
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def format_similarity_score(score: float) -> str:
    """
    Formats a similarity score (0-100) as a percentage string.
    """
    return f"{score:.2f}%"


def validate_image_format(image_path: str) -> bool:
    """
    Validates if the file at the given path is a supported image format.
    """
    try:
        with Image.open(image_path) as img:
            img.verify()
        return True
    except (IOError, SyntaxError):
        return False
