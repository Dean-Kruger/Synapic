"""
Deduplication Module for Synapic
================================

This module provides image deduplication capabilities using perceptual and
cryptographic hashing algorithms. It can detect both exact duplicates and
visually similar images.

Copied and adapted from: https://github.com/deanable/python-dedupe

Usage:
------
    from src.core.dedup import ImageDeduplicator, KeepStrategy, generate_dedup_plan
    
    deduplicator = ImageDeduplicator(similarity_threshold=95.0)
    hash_map = deduplicator.build_hash_map(images, algorithm='phash')
    groups = deduplicator.find_similar_images(hash_map)
    decisions = generate_dedup_plan(groups, KeepStrategy.LARGEST)
"""

from src.core.dedup.hash_calculator import ImageHashCalculator, HashResult
from src.core.dedup.hash_comparison import (
    calculate_hamming_distance,
    calculate_similarity_percentage,
    are_hashes_similar,
    are_hashes_exact_match
)
from src.core.dedup.dedup_engine import ImageDeduplicator, DuplicateGroup
from src.core.dedup.dedup_strategies import (
    KeepStrategy,
    DedupDecision,
    select_item_to_keep,
    generate_dedup_plan
)
from src.core.dedup.hash_storage import (
    HashFormat,
    format_hash_for_storage,
    parse_hash_from_storage,
    validate_hash_format
)
from src.core.dedup.utils import (
    get_image_metadata,
    format_file_size,
    format_similarity_score,
    validate_image_format
)

__all__ = [
    # Hash calculation
    'ImageHashCalculator',
    'HashResult',
    
    # Hash comparison
    'calculate_hamming_distance',
    'calculate_similarity_percentage',
    'are_hashes_similar',
    'are_hashes_exact_match',
    
    # Deduplication engine
    'ImageDeduplicator',
    'DuplicateGroup',
    
    # Strategies
    'KeepStrategy',
    'DedupDecision',
    'select_item_to_keep',
    'generate_dedup_plan',
    
    # Storage
    'HashFormat',
    'format_hash_for_storage',
    'parse_hash_from_storage',
    'validate_hash_format',
    
    # Utilities
    'get_image_metadata',
    'format_file_size',
    'format_similarity_score',
    'validate_image_format',
]
