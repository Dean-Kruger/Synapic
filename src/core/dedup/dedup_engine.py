"""
Deduplication Engine
====================

Core engine for finding duplicate and similar images using
perceptual hashing. Uses Union-Find algorithm for efficient
grouping of transitively similar images.

Adapted from: https://github.com/deanable/python-dedupe
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from collections import defaultdict

from src.core.dedup.hash_calculator import ImageHashCalculator, HashResult
from src.core.dedup.hash_comparison import (
    are_hashes_similar,
    calculate_similarity_percentage,
    calculate_hamming_distance,
    hamming_distance_between_ints,
)

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """
    Represents a group of duplicate or similar images.
    """
    items: List[str]  # List of image identifiers/paths
    similarity_scores: Dict[str, float]  # Map of item -> similarity score (relative to representative)
    hash_type: str


class UnionFind:
    """
    Helper class for Union-Find data structure to manage connected components.
    """
    def __init__(self, elements):
        self.parent = {e: e for e in elements}

    def find(self, item):
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, item1, item2):
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 != root2:
            self.parent[root1] = root2

    def get_components(self) -> Dict[str, List[str]]:
        """
        Returns a dictionary mapping root -> list of items in that component.
        """
        components = defaultdict(list)
        for item in self.parent:
            root = self.find(item)
            components[root].append(item)
        return components


def _hash_bins(hash_value: str, bin_count: int) -> List[str]:
    """
    Split a hex hash string into at least ``bin_count`` contiguous chunks.

    Two hashes differing in at most ``bin_count - 1`` bits are guaranteed to
    share at least one identical chunk (pigeonhole principle), so comparing
    only within bins preserves full recall for that Hamming-distance bound.
    Floor-dividing the chunk size guarantees the number of produced bins is
    never smaller than ``bin_count``.
    """
    hex_len = len(hash_value)
    if hex_len <= 1 or bin_count <= 1:
        # Single shared bucket — every item lands in the same bin, so all
        # pairs get compared (the brute-force fallback).
        return [""]
    chunk = max(1, hex_len // bin_count)
    return [hash_value[i:i + chunk] for i in range(0, hex_len, chunk)]


class ImageDeduplicator:
    """
    Engine for finding exact and similar duplicate images.
    """
    def __init__(self, similarity_threshold: float = 95.0):
        self.similarity_threshold = similarity_threshold
        self.calculator = ImageHashCalculator()

    def build_hash_map(self, images: List[str], algorithm: str = 'phash') -> Dict[str, HashResult]:
        """
        Generates a hash map for the given list of images (file paths).
        Returns a dictionary mapping image_path -> HashResult.
        """
        hash_map = {}
        for image_path in images:
            try:
                # Read file bytes once to handle both perceptual and crypto hashes efficiently
                with open(image_path, 'rb') as f:
                    file_bytes = f.read()

                algo_lower = algorithm.lower()

                if algo_lower in self.calculator.SUPPORTED_PERCEPTUAL_ALGOS:
                    img = self.calculator.load_image_from_bytes(file_bytes)
                    hash_result = self.calculator.calculate_perceptual_hash(img, algorithm=algorithm)
                elif algo_lower in self.calculator.SUPPORTED_CRYPTO_ALGOS:
                    hash_result = self.calculator.calculate_cryptographic_hash(file_bytes, algorithm=algorithm)
                else:
                    raise ValueError(f"Unsupported algorithm: {algorithm}")

                hash_map[image_path] = hash_result

            except Exception as e:
                # Skip images that fail to load or hash
                logger.warning(f"Error processing {image_path}: {e}")
                continue

        return hash_map

    def build_hash_map_from_bytes(
        self,
        items: Dict[str, bytes],
        algorithm: str = 'phash'
    ) -> Dict[str, HashResult]:
        """
        Generates a hash map from a dictionary of item_id -> image_bytes.
        This is useful for API-based workflows where images are fetched as bytes.
        
        Args:
            items: Dictionary mapping item IDs to image bytes
            algorithm: Hash algorithm to use
            
        Returns:
            Dictionary mapping item_id -> HashResult
        """
        hash_map = {}
        for item_id, image_bytes in items.items():
            try:
                algo_lower = algorithm.lower()
                
                if algo_lower in self.calculator.SUPPORTED_PERCEPTUAL_ALGOS:
                    img = self.calculator.load_image_from_bytes(image_bytes)
                    hash_result = self.calculator.calculate_perceptual_hash(img, algorithm=algorithm)
                elif algo_lower in self.calculator.SUPPORTED_CRYPTO_ALGOS:
                    hash_result = self.calculator.calculate_cryptographic_hash(image_bytes, algorithm=algorithm)
                else:
                    raise ValueError(f"Unsupported algorithm: {algorithm}")
                
                hash_map[item_id] = hash_result
                
            except Exception as e:
                logger.warning(f"Error processing item {item_id}: {e}")
                continue
        
        return hash_map

    def find_exact_duplicates(self, hash_map: Dict[str, HashResult]) -> List[DuplicateGroup]:
        """
        Finds groups of exact duplicates based on hash values.
        """
        # Group by hash value
        groups_by_hash = defaultdict(list)
        hash_algo = None

        for item_id, result in hash_map.items():
            groups_by_hash[result.hash_value].append(item_id)
            if hash_algo is None:
                hash_algo = result.algorithm

        duplicate_groups = []
        for hash_val, items in groups_by_hash.items():
            if len(items) > 1:
                # Exact duplicates have 100% similarity
                scores = {item: 100.0 for item in items}
                duplicate_groups.append(DuplicateGroup(
                    items=items,
                    similarity_scores=scores,
                    hash_type=hash_algo if hash_algo else "unknown"
                ))

        return duplicate_groups

    def find_similar_images(self, hash_map: Dict[str, HashResult], threshold: Optional[float] = None) -> List[DuplicateGroup]:
        """
        Finds groups of similar images using the configured threshold (or override).
        Uses Union-Find to group transitively similar items.

        Instead of an O(N^2) all-pairs scan, hashes are bucketed by contiguous
        sub-chunks (see ``_hash_bins``). For a 64-bit pHash at a 95% threshold
        (<= 3 differing bits) four bins are enough to guarantee similar images
        share at least one bin, cutting comparisons by ~4x with identical
        results. Identical hashes are also collapsed to one representative
        before comparing, so duplicate-heavy collections don't re-compare
        exact matches.
        """
        import logging
        _logger = logging.getLogger(__name__)

        eff_threshold = threshold if threshold is not None else self.similarity_threshold

        items = list(hash_map.keys())
        if not items:
            return []

        # Log sample hash values for diagnostics
        sample_size = min(5, len(items))
        for idx in range(sample_size):
            item_id = items[idx]
            hr = hash_map[item_id]
            _logger.debug(f"[DEDUP HASH SAMPLE] item={item_id}, hash={hr.hash_value}, algo={hr.algorithm}, bits={hr.bit_length}")

        # Precompute integer hashes so the hot loop is int-XOR + popcount only.
        int_by_item: Dict[str, int] = {}
        for item_id in items:
            try:
                int_by_item[item_id] = int(hash_map[item_id].hash_value, 16)
            except (ValueError, TypeError):
                # Invalid hashes can't be compared (matches old ValueError-skip behavior).
                continue

        comparable = [i for i in items if i in int_by_item]
        if len(comparable) < 2:
            return []

        # Collapse identical (algorithm, hash) pairs to a single representative
        # before comparing, so duplicate-heavy collections don't re-compare
        # exact matches. Keying by algorithm too preserves the old behavior of
        # never grouping cross-algorithm hashes.
        groups_by_hash: Dict[tuple, List[str]] = defaultdict(list)
        for item_id in comparable:
            hr = hash_map[item_id]
            groups_by_hash[(hr.algorithm, hr.hash_value)].append(item_id)
        rep_by_hash: Dict[tuple, str] = {
            key: group[0] for key, group in groups_by_hash.items()
        }
        reps = sorted(set(rep_by_hash.values()))

        # Reference bit length to derive the threshold's max Hamming distance.
        ref = hash_map[reps[0]]
        bit_length = ref.bit_length
        max_distance = (
            max(0, int((1.0 - eff_threshold / 100.0) * bit_length))
            if bit_length else 0
        )
        # The pigeonhole guarantee needs more bins than max_distance. For very
        # low thresholds that's impossible with the available hex characters
        # (e.g. 64-bit hashes below ~77%), so fall back to an all-pairs scan.
        required_bins = max_distance + 1
        bin_count = required_bins if required_bins <= len(ref.hash_value) else 1
        if bin_count == 1 and len(reps) > 1:
            _logger.warning(
                "Similarity threshold %.1f%% requires more comparison bins "
                "than the hash width provides; falling back to an all-pairs "
                "scan (slower on large collections).",
                eff_threshold,
            )

        uf = UnionFind(reps)

        # Bucket representatives; compare only within shared bins.
        bins: Dict[tuple, List[str]] = defaultdict(list)
        for rep in reps:
            hr = hash_map[rep]
            for chunk in _hash_bins(hr.hash_value, bin_count):
                bins[(hr.algorithm, chunk)].append(rep)

        comparisons = 0
        matches = 0
        max_similarity = 0.0
        max_sim_pair = (None, None)

        for (_algo, _chunk), group in bins.items():
            for i in range(len(group)):
                id1 = group[i]
                for j in range(i + 1, len(group)):
                    id2 = group[j]
                    # Already in the same component — no need to re-evaluate.
                    if uf.find(id1) == uf.find(id2):
                        continue

                    comparisons += 1
                    dist = hamming_distance_between_ints(
                        int_by_item[id1], int_by_item[id2]
                    )
                    sim = calculate_similarity_percentage(dist, hash_map[id1].bit_length)
                    if sim > max_similarity:
                        max_similarity = sim
                        max_sim_pair = (id1, id2)
                    if sim >= eff_threshold:
                        matches += 1
                        uf.union(id1, id2)

        _logger.info(f"[DEDUP COMPARE] {comparisons} comparisons, {matches} matches at threshold={eff_threshold}%")
        _logger.info(f"[DEDUP COMPARE] Highest similarity: {max_similarity:.1f}% between items {max_sim_pair[0]} and {max_sim_pair[1]}")

        # Build groups from the representative union-find, then expand each
        # component back to all items sharing a hash with its representatives.
        components = uf.get_components()
        duplicate_groups = []

        for _root, rep_group in components.items():
            group_items: List[str] = []
            for rep in rep_group:
                hr = hash_map[rep]
                group_items.extend(groups_by_hash[(hr.algorithm, hr.hash_value)])

            if len(group_items) > 1:
                # Calculate scores relative to the first item (pivot)
                # Sort group items to ensure deterministic pivot
                group_items.sort()
                pivot = group_items[0]
                pivot_res = hash_map[pivot]

                scores = {}
                for item in group_items:
                    if item == pivot:
                        scores[item] = 100.0
                    else:
                        item_res = hash_map[item]
                        # Recalculate similarity to pivot
                        dist = hamming_distance_between_ints(
                            int_by_item[item], int_by_item[pivot]
                        )
                        bit_len = pivot_res.bit_length
                        sim = calculate_similarity_percentage(dist, bit_len)
                        scores[item] = sim

                duplicate_groups.append(DuplicateGroup(
                    items=group_items,
                    similarity_scores=scores,
                    hash_type=pivot_res.algorithm
                ))

        return duplicate_groups
