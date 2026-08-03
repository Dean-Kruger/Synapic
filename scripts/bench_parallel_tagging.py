"""
Benchmark: Parallel vs Sequential Tagging Throughput
====================================================

Measures how much wall-clock time the parallel tagging pipeline saves over
sequential processing.  It drives the *real* ``ProcessingManager._run_job``
machinery (item fetch, executor dispatch, ``as_completed`` loop, progress
callbacks, shutdown) with the only mock being the network-bound AI inference
call — a configurable latency sleep that models a cloud API round trip.

For each worker count it reports:

- best wall-clock time across ``--repeats`` runs
- throughput (items/sec)
- speedup relative to ``workers=1`` (the pre-parallelization behavior)
- the theoretical ideal ``latency * ceil(N / workers)``

It also verifies correctness after every run (all items processed, zero
failures).

Usage:
    python scripts/bench_parallel_tagging.py [--items 16] [--latency-ms 200]
        [--workers 1,2,4,8] [--repeats 2]
"""

import argparse
import logging
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, ".")

from src.core import config
from src.core.processing import ProcessingManager

logging.disable(logging.CRITICAL)  # keep the benchmark output clean


# ---------------------------------------------------------------------------
# Mock AI inference (the only mocked part — models a cloud API round trip)
# ---------------------------------------------------------------------------

CANNED_RESULT = [
    {"label": "Nature", "score": 0.99},
    {"label": "Outdoor", "score": 0.95},
    {"label": "Sky", "score": 0.88},
]


def make_mock_inference(latency_s: float):
    def mock_inference(model_id, image_path, task, token, parameters=None):
        time.sleep(latency_s)  # the simulated API round trip
        return CANNED_RESULT

    return mock_inference


# ---------------------------------------------------------------------------
# Session + manager construction
# ---------------------------------------------------------------------------

def _make_session(tmpdir: str):
    session = SimpleNamespace(
        datasource=SimpleNamespace(
            type="local",
            local_path=tmpdir,
            local_recursive=False,
            max_items=0,
        ),
        engine=SimpleNamespace(
            provider="huggingface",
            model_id="benchmark-model",
            task=config.MODEL_TASK_IMAGE_CLASSIFICATION,
            api_key="benchmark-key",
            confidence_threshold=50,
            device="cpu",
            system_prompt="",
        ),
        daminion_client=None,  # local source: no DAM client (read unconditionally)
        processed_items=0,
        failed_items=0,
        total_items=0,
        is_processing=False,
        results=[],
    )

    def reset_stats():
        session.processed_items = 0
        session.failed_items = 0
        session.total_items = 0

    session.reset_stats = reset_stats
    return session


def _make_image_files(tmpdir: str, n: int):
    """Create ``n`` tiny JPEGs so the real image-loading path runs."""
    img = Image.new("RGB", (8, 8), "white")
    for i in range(n):
        img.save(Path(tmpdir) / f"img_{i}.jpg", "JPEG")


def run_tagging(tmpdir: str, n_items: int, workers: int, latency_s: float) -> float:
    """Run the real pipeline with ``workers`` workers; returns wall-clock time."""
    session = _make_session(tmpdir)
    manager = ProcessingManager(
        session=session,
        log_callback=lambda *a, **kw: None,
        progress_callback=lambda *a, **kw: None,
        auto_paginate=False,
    )

    with patch.object(config, "PROCESSING_MAX_WORKERS", workers), \
         patch("src.core.huggingface_utils.run_inference_api",
               side_effect=make_mock_inference(latency_s)), \
         patch("src.core.image_processing.write_metadata", return_value=True):
        start = time.perf_counter()
        manager._run_job()
        elapsed = time.perf_counter() - start

    assert session.processed_items == n_items, (
        f"workers={workers}: processed {session.processed_items}/{n_items}"
    )
    assert session.failed_items == 0, f"workers={workers}: {session.failed_items} failures"
    return elapsed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=int, default=16, help="images to tag per run")
    parser.add_argument("--latency-ms", type=float, default=200.0,
                        help="simulated per-item API latency in milliseconds")
    parser.add_argument("--workers", default="1,2,4,8",
                        help="comma-separated worker counts to compare")
    parser.add_argument("--repeats", type=int, default=2,
                        help="runs per worker count (best time is reported)")
    args = parser.parse_args()

    workers = list(dict.fromkeys(int(w) for w in args.workers.split(",") if w.strip()))
    workers = [max(1, w) for w in workers]
    latency_s = args.latency_ms / 1000.0
    n_items = args.items

    print(f"items={n_items}  latency={args.latency_ms:g}ms  "
          f"workers={workers}  repeats={args.repeats}")
    print(f"{'workers':>7} | {'best time':>9} | {'items/s':>8} | "
          f"{'speedup':>8} | {'ideal':>9}")
    print("-" * 55)

    with tempfile.TemporaryDirectory() as tmpdir:
        _make_image_files(tmpdir, n_items)
        best_times = {}
        for w in workers:
            times = [run_tagging(tmpdir, n_items, w, latency_s) for _ in range(args.repeats)]
            best = min(times)
            best_times[w] = best
            throughput = n_items / best
            speedup = best_times[workers[0]] / best if w != workers[0] else 1.0
            ideal = latency_s * ((n_items + w - 1) // w)
            print(f"{w:>7} | {best:>8.3f}s | {throughput:>8.1f} | "
                  f"{speedup:>7.2f}x | {ideal:>8.3f}s")

        base = best_times[workers[0]]
        print("-" * 55)
        print(f"wall-clock speedup at {workers[-1]} workers: "
              f"{base / best_times[workers[-1]]:.1f}x "
              f"({base:.2f}s -> {best_times[workers[-1]]:.2f}s)")


if __name__ == "__main__":
    main()
