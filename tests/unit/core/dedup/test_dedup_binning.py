"""
Unit Tests for the Hash-Binning Dedup Engine
=============================================

These tests cover the bucketed ``find_similar_images`` implementation that
replaced the O(N^2) all-pairs scan.  The core guarantee under test: binning
must produce *identical* duplicate groups to a brute-force all-pairs scan,
at every threshold — including the single-bucket fallback used when the
threshold is too low for the hash width.
"""

import logging
import random
from collections import defaultdict

import pytest

from src.core.dedup.dedup_engine import ImageDeduplicator
from src.core.dedup.hash_calculator import HashResult
from src.core.dedup.hash_comparison import (
    calculate_hamming_distance,
    calculate_similarity_percentage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hr(hash_hex: str, algorithm: str = "phash", bit_length: int = 64) -> HashResult:
    """Build a minimal HashResult with a deterministic timestamp."""
    return HashResult(
        hash_value=hash_hex,
        algorithm=algorithm,
        timestamp=0.0,
        bit_length=bit_length,
    )


def _brute_force_groups(hash_map, threshold: float):
    """
    Semantic oracle: union-find over *every* pair of items (ignoring identical
    hashes, since those always union).  Returns a set of frozensets covering
    all items (singletons included); callers filter out singletons.
    """
    items = list(hash_map)
    parent = {item: item for item in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, a in enumerate(items):
        ha = hash_map[a]
        for b in items[i + 1:]:
            hb = hash_map[b]
            if ha.algorithm != hb.algorithm or len(ha.hash_value) != len(hb.hash_value):
                continue
            try:
                dist = calculate_hamming_distance(ha.hash_value, hb.hash_value)
            except ValueError:
                continue  # invalid hex — engine skips these too
            sim = calculate_similarity_percentage(dist, ha.bit_length)
            if sim >= threshold:
                union(a, b)

    groups = defaultdict(list)
    for item in items:
        groups[find(item)].append(item)
    return {frozenset(g) for g in groups.values()}


def _engine_groups(hash_map, threshold: float):
    """Engine output as a set of frozensets, singletons dropped."""
    result = ImageDeduplicator(similarity_threshold=threshold).find_similar_images(
        hash_map
    )
    return {frozenset(g.items) for g in result if len(g.items) > 1}


def _random_hash_map(n_items: int, seed: int, with_cluster: bool = True):
    """Deterministic random hash map; optionally injects a near-duplicate cluster."""
    rng = random.Random(seed)
    hash_map = {
        f"item_{i}": _hr("%016x" % rng.getrandbits(64)) for i in range(n_items)
    }
    if with_cluster:
        base = rng.getrandbits(64)
        hash_map["dup_a0"] = _hr("%016x" % base)
        hash_map["dup_a1"] = _hr("%016x" % (base ^ (1 << 3)))
        hash_map["dup_a2"] = _hr("%016x" % (base ^ (1 << 10) ^ (1 << 20)))
    return hash_map


# ---------------------------------------------------------------------------
# Equivalence vs brute force
# ---------------------------------------------------------------------------


class TestBinningEquivalence:
    """The bucketed engine must agree with the all-pairs oracle exactly."""

    @pytest.mark.parametrize("threshold", [95.0, 90.0, 75.0])
    @pytest.mark.parametrize("seed", [1, 7, 42, 99])
    def test_groups_match_brute_force(self, threshold, seed):
        hash_map = _random_hash_map(80, seed=seed)
        assert _engine_groups(hash_map, threshold) == {
            g for g in _brute_force_groups(hash_map, threshold) if len(g) > 1
        }

    def test_duplicate_heavy_collection_matches_brute_force(self):
        """Many identical hashes must collapse to one group, matching the oracle."""
        hash_map = {
            f"dup_{i}": _hr("a1b2c3d4e5f60718") for i in range(10)
        }
        hash_map["near"] = _hr("a1b2c3d4e5f60719")  # 1 bit off
        assert _engine_groups(hash_map, 95.0) == {
            g for g in _brute_force_groups(hash_map, 95.0) if len(g) > 1
        }

    def test_low_threshold_fallback_engages(self, caplog):
        """Below ~77% on 64-bit hashes the engine falls back to all-pairs."""
        hash_map = {
            "a": _hr("0000000000000000"),
            "b": _hr("ffff000000000000"),  # 16 bits apart -> 75% similarity
        }
        with caplog.at_level(logging.WARNING, logger="src.core.dedup.dedup_engine"):
            _engine_groups(hash_map, 75.0)
        assert any("falling back to an all-pairs" in r.getMessage() for r in caplog.records)

    def test_high_threshold_uses_binning_without_warning(self, caplog):
        """At 95% (<= 3 bits) binning must be used — no fallback warning."""
        hash_map = _random_hash_map(30, seed=3, with_cluster=False)
        with caplog.at_level(logging.WARNING, logger="src.core.dedup.dedup_engine"):
            _engine_groups(hash_map, 95.0)
        assert not any(
            "falling back to an all-pairs" in r.getMessage() for r in caplog.records
        )


# ---------------------------------------------------------------------------
# Deterministic behavior
# ---------------------------------------------------------------------------


class TestFindSimilarImagesBehavior:
    def test_empty_hash_map_returns_empty(self):
        assert ImageDeduplicator().find_similar_images({}) == []

    def test_single_item_returns_empty(self):
        hash_map = {"only": _hr("0000000000000000")}
        assert ImageDeduplicator().find_similar_images(hash_map) == []

    def test_transitive_grouping_through_chain(self):
        """
        A~B (2 bits), B~C (2 bits), but A~C is 4 bits apart.  At 95% only A~B
        and B~C pass, yet all three must end up in one group (union-find).
        """
        hash_map = {
            "a": _hr("0000000000000000"),
            "b": _hr("0000000000000003"),  # bits 0,1 set
            "c": _hr("000000000000000f"),  # bits 0,1,2,3 set
        }
        groups = _engine_groups(hash_map, 95.0)
        assert groups == {frozenset(["a", "b", "c"])}

    def test_threshold_override_parameter(self):
        """A 4-bit difference (93.75%) fails at 95% but passes at 90%."""
        hash_map = {
            "a": _hr("0000000000000000"),
            "c": _hr("000000000000000f"),
        }
        assert _engine_groups(hash_map, 95.0) == set()
        assert _engine_groups(hash_map, 90.0) == {frozenset(["a", "c"])}

    def test_identical_hashes_collapse_into_single_group(self):
        hash_map = {
            "a": _hr("a1b2c3d4e5f60718"),
            "b": _hr("a1b2c3d4e5f60718"),  # identical to a
            "c": _hr("a1b2c3d4e5f60719"),  # 1 bit different
        }
        result = ImageDeduplicator().find_similar_images(hash_map)
        assert len(result) == 1
        group = result[0]
        assert set(group.items) == {"a", "b", "c"}
        assert group.hash_type == "phash"
        # Identical pair scores 100%; the 1-bit neighbor is 98.4375%.
        assert group.similarity_scores["b"] == 100.0
        assert abs(group.similarity_scores["c"] - 98.4375) < 1e-9

    def test_cross_algorithm_hashes_never_grouped(self):
        """Same hash string under different algorithms must not be grouped."""
        hash_map = {
            "a": _hr("0000000000000000", algorithm="phash"),
            "b": _hr("0000000000000000", algorithm="dhash"),
        }
        assert ImageDeduplicator().find_similar_images(hash_map) == []

    def test_invalid_hex_hash_skipped_without_error(self):
        hash_map = {
            "good": _hr("0000000000000000"),
            "bad": _hr("nothex000000000000"),  # int(..., 16) fails
        }
        # Only one comparable item remains -> no groups, and no exception.
        assert ImageDeduplicator().find_similar_images(hash_map) == []
