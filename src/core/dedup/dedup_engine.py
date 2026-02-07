"""
Deduplication Engine
====================

Core engine for finding duplicate and similar images using
perceptual hashing. Uses Union-Find algorithm for efficient
grouping of transitively similar images.

Adapted from: https://github.com/deanable/python-dedupe
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from collections import defaultdict

from src.core.dedup.hash_calculator import ImageHashCalculator, HashResult
from src.core.dedup.hash_comparison import (
    are_hashes_similar,
    calculate_similarity_percentage,
    calculate_hamming_distance
)


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
                print(f"Error processing {image_path}: {e}")
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
                print(f"Error processing item {item_id}: {e}")
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
        """
        eff_threshold = threshold if threshold is not None else self.similarity_threshold

        items = list(hash_map.keys())
        uf = UnionFind(items)

        # Compare all pairs O(N^2)
        # This is a potential bottleneck for large datasets
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                id1 = items[i]
                id2 = items[j]

                res1 = hash_map[id1]
                res2 = hash_map[id2]

                # Check if algorithms match
                if res1.algorithm != res2.algorithm:
                    continue

                if are_hashes_similar(res1.hash_value, res2.hash_value, threshold=eff_threshold):
                    uf.union(id1, id2)

        # Build groups
        components = uf.get_components()
        duplicate_groups = []

        for root, group_items in components.items():
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
                        dist = calculate_hamming_distance(pivot_res.hash_value, item_res.hash_value)
                        bit_len = pivot_res.bit_length
                        sim = calculate_similarity_percentage(dist, bit_len)
                        scores[item] = sim

                duplicate_groups.append(DuplicateGroup(
                    items=group_items,
                    similarity_scores=scores,
                    hash_type=pivot_res.algorithm
                ))

        return duplicate_groups
