"""
Benchmark: Hash-Binning Dedup vs the Pre-Binning O(N^2) Scan
============================================================

Measures the wall-clock speedup of ``ImageDeduplicator.find_similar_images``
(now bucketed) against the original all-pairs implementation on synthetic
64-bit perceptual hashes.

Scope: the binning change only affects the *comparison* phase of a dedup
scan — hashing the images themselves is unchanged — so image hashing is out
of scope here.  Two datasets are used:

- ``sparse``: random 64-bit hashes plus a handful of near-duplicate clusters.
  Realistic for a typical library where most pairs are dissimilar.
- ``dense``: every item belongs to a cluster of 10 near-duplicates (base hash
  + up to 3 flipped bits).  A worst-case-ish workload where the pigeonhole
  bound actually bites.

It also reports the engine's own comparison counter, verifies that the
bucketed engine produces exactly the same groups as the all-pairs baseline,
and micro-benchmarks the per-pair cost (``int()`` + ``bin().count()`` vs a
precomputed-int + ``bit_count``).

Usage:
    python scripts/bench_dedup_binning.py [--threshold 95.0] [--max-n 32000]
"""

import argparse
import logging
import random
import sys
import time
from collections import defaultdict

sys.path.insert(0, ".")

from src.core.dedup.dedup_engine import ImageDeduplicator
from src.core.dedup.hash_calculator import HashResult

BITS = 64


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def _hr(hash_hex: str) -> HashResult:
    return HashResult(hash_value=hash_hex, algorithm="phash", timestamp=0.0, bit_length=BITS)


def build_sparse(n: int, seed: int, clusters: int = 50, cluster_size: int = 4) -> dict:
    """Random hashes plus ``clusters`` groups of ``cluster_size`` near-duplicates."""
    rng = random.Random(seed)
    hash_map = {}
    for i in range(n - clusters * cluster_size):
        hash_map[f"r{i}"] = _hr("%016x" % rng.getrandbits(BITS))
    for c in range(clusters):
        base = rng.getrandbits(BITS)
        for k in range(cluster_size):
            mask = rng.getrandbits(8) & 0b00000111  # flip up to 3 bits
            hash_map[f"c{c}_{k}"] = _hr("%016x" % (base ^ mask))
    return hash_map


def build_dense(n: int, seed: int, cluster_size: int = 10) -> dict:
    """Every item is a near-duplicate of one of ``n // cluster_size`` bases."""
    rng = random.Random(seed)
    hash_map = {}
    n_clusters = n // cluster_size
    idx = 0
    for c in range(n_clusters):
        base = rng.getrandbits(BITS)
        for k in range(cluster_size):
            mask = rng.getrandbits(8) & 0b00000111  # flip up to 3 bits
            hash_map[f"d{idx}"] = _hr("%016x" % (base ^ mask))
            idx += 1
    return hash_map


# ---------------------------------------------------------------------------
# Pre-binning baseline (faithful reconstruction of the old algorithm)
# ---------------------------------------------------------------------------

def baseline_find_similar(hash_map, threshold: float):
    """The O(N^2) algorithm: per-pair int() conversion + bin(xor).count('1')."""
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

    comparisons = 0
    for i, a in enumerate(items):
        ha = hash_map[a]
        for b in items[i + 1:]:
            hb = hash_map[b]
            if ha.algorithm != hb.algorithm or find(a) == find(b):
                continue
            try:
                xor = int(ha.hash_value, 16) ^ int(hb.hash_value, 16)
                dist = bin(xor).count("1")  # old popcount: string formatting per pair
            except ValueError:
                continue
            comparisons += 1
            sim = (1 - dist / ha.bit_length) * 100.0
            if sim >= threshold:
                union(a, b)

    groups = defaultdict(list)
    for item in items:
        groups[find(item)].append(item)
    return comparisons, {frozenset(g) for g in groups.values() if len(g) > 1}


# ---------------------------------------------------------------------------
# Engine wrapper + comparison-count capture
# ---------------------------------------------------------------------------

class _CountingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.comparisons = None

    def emit(self, record):
        msg = record.getMessage()
        if "[DEDUP COMPARE]" in msg:
            try:
                self.comparisons = int(msg.split("comparisons")[0].split()[-1])
            except (IndexError, ValueError):
                pass


def engine_find_similar(hash_map, threshold: float):
    handler = _CountingHandler()
    logger = logging.getLogger("src.core.dedup.dedup_engine")
    logger.setLevel(logging.INFO)  # INFO records are needed to count comparisons
    logger.addHandler(handler)
    try:
        result = ImageDeduplicator(similarity_threshold=threshold).find_similar_images(hash_map)
        return handler.comparisons, {frozenset(g.items) for g in result}
    finally:
        logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# Timers
# ---------------------------------------------------------------------------

def timed(fn, *args):
    start = time.perf_counter()
    value = fn(*args)
    return value, time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=95.0)
    parser.add_argument("--max-n", type=int, default=32000, help="largest collection size")
    parser.add_argument("--baseline-cap", type=int, default=4000,
                        help="all-pairs baseline is capped here to bound runtime")
    args = parser.parse_args()

    threshold = args.threshold
    seed = 1234
    # dict.fromkeys dedupes while preserving order (max_n may equal a standard size)
    sizes = list(dict.fromkeys(
        n for n in (1000, 2000, 4000, 8000, 16000, args.max_n) if n <= args.max_n
    ))
    baseline_sizes = [n for n in sizes if n <= args.baseline_cap]

    print(f"threshold={threshold:.1f}%  max_n={args.max_n}  "
          f"(64-bit phash -> {int((1 - threshold / 100) * BITS)} bits max distance)")

    for name, builder in (("sparse", build_sparse), ("dense", build_dense)):
        print(f"\n=== dataset: {name} ===")
        print(f"{'N':>7} | {'baseline':>10} {'comparisons':>12} | "
              f"{'bucketed':>10} {'comparisons':>12} | {'speedup':>9} | groups")
        print("-" * 95)
        for n in sizes:
            hash_map = builder(n, seed)
            row = f"{n:>7} |"

            baseline_info = None
            if n in baseline_sizes:
                (b_comp, b_groups), b_time = timed(baseline_find_similar, hash_map, threshold)
                row += f" {b_time:>8.2f}s {b_comp:>12,} |"
                baseline_info = (b_comp, b_groups)
            else:
                row += f" {'(skipped)':>8} {'—':>12} |"

            (e_comp, e_groups), e_time = timed(engine_find_similar, hash_map, threshold)
            row += f" {e_time:>8.2f}s {e_comp:>12,} |"

            if baseline_info is not None:
                speedup = b_time / e_time if e_time > 0 else float("inf")
                row += f" {speedup:>8.1f}x | {len(e_groups):>6}"
                assert e_groups == baseline_info[1], f"GROUP MISMATCH at N={n}!"
            else:
                row += f" {'—':>9} | {len(e_groups):>6}"
            print(row)

    # Equivalence guard on a mid-size set for both datasets
    print("\n=== equivalence check (engine vs all-pairs baseline) ===")
    for name, builder in (("sparse", build_sparse), ("dense", build_dense)):
        hash_map = builder(2000, seed)
        (_, b_groups) = baseline_find_similar(hash_map, threshold)
        (_, e_groups) = engine_find_similar(hash_map, threshold)
        print(f"{name:>8}: groups equal -> {e_groups == b_groups} "
              f"(baseline={len(b_groups)}, bucketed={len(e_groups)})")

    # Per-pair inner-loop cost (the second half of the speedup)
    print("\n=== per-pair comparison cost (500k iterations) ===")
    h1, h2 = "a1b2c3d4e5f60718", "a1b2c3d4e5f60719"
    i1, i2 = int(h1, 16), int(h2, 16)
    N = 500_000

    start = time.perf_counter()
    for _ in range(N):
        _ = bin(int(h1, 16) ^ int(h2, 16)).count("1")
    old_cost = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(N):
        _ = (i1 ^ i2).bit_count()
    new_cost = time.perf_counter() - start

    print(f"  old (int() x2 + bin().count): {old_cost / N * 1e9:>8.1f} ns/pair")
    print(f"  new (precomputed int + bit_count): {new_cost / N * 1e9:>8.1f} ns/pair")
    print(f"  per-pair speedup: {old_cost / new_cost:.1f}x")


if __name__ == "__main__":
    main()
