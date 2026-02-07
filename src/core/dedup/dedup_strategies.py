"""
Deduplication Strategies
========================

Keep strategies for deciding which item to retain when
duplicates are found. Supports LARGEST, OLDEST, NEWEST,
FIRST, and MANUAL strategies.

Adapted from: https://github.com/deanable/python-dedupe
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Union
import os
import time

from src.core.dedup.dedup_engine import DuplicateGroup


class KeepStrategy(Enum):
    LARGEST = "largest"
    OLDEST = "oldest"
    NEWEST = "newest"
    MANUAL = "manual"
    FIRST = "first"


@dataclass
class DedupDecision:
    keep_item: Optional[str]
    remove_items: List[str]
    reason: str


def get_file_metadata(file_path: str) -> Dict[str, Union[int, float]]:
    """Get file size and modification time."""
    try:
        stat = os.stat(file_path)
        return {
            'size': stat.st_size,
            'mtime': stat.st_mtime
        }
    except Exception:
        # On error, return values that deprioritize the file
        return {'size': 0, 'mtime': time.time()}


def apply_keep_first(group: DuplicateGroup) -> DedupDecision:
    if not group.items:
        return DedupDecision(keep_item=None, remove_items=[], reason="Empty group")

    keep = group.items[0]
    remove = group.items[1:]
    return DedupDecision(keep_item=keep, remove_items=remove, reason="Keep first item")


def apply_keep_largest(group: DuplicateGroup) -> DedupDecision:
    if not group.items:
        return DedupDecision(keep_item=None, remove_items=[], reason="Empty group")

    sorted_items = sorted(group.items, key=lambda x: get_file_metadata(x)['size'], reverse=True)
    keep = sorted_items[0]
    remove = [item for item in group.items if item != keep]

    return DedupDecision(keep_item=keep, remove_items=remove, reason="Keep largest file")


def apply_keep_oldest(group: DuplicateGroup) -> DedupDecision:
    if not group.items:
        return DedupDecision(keep_item=None, remove_items=[], reason="Empty group")

    # Sort by mtime ascending (oldest first)
    sorted_items = sorted(group.items, key=lambda x: get_file_metadata(x)['mtime'])
    keep = sorted_items[0]
    remove = [item for item in group.items if item != keep]

    return DedupDecision(keep_item=keep, remove_items=remove, reason="Keep oldest file")


def apply_keep_newest(group: DuplicateGroup) -> DedupDecision:
    if not group.items:
        return DedupDecision(keep_item=None, remove_items=[], reason="Empty group")

    # Sort by mtime descending (newest first)
    sorted_items = sorted(group.items, key=lambda x: get_file_metadata(x)['mtime'], reverse=True)
    keep = sorted_items[0]
    remove = [item for item in group.items if item != keep]

    return DedupDecision(keep_item=keep, remove_items=remove, reason="Keep newest file")


def select_item_to_keep(group: DuplicateGroup, strategy: KeepStrategy) -> DedupDecision:
    """Select which item to keep based on the strategy."""
    if strategy == KeepStrategy.FIRST:
        return apply_keep_first(group)
    elif strategy == KeepStrategy.LARGEST:
        return apply_keep_largest(group)
    elif strategy == KeepStrategy.OLDEST:
        return apply_keep_oldest(group)
    elif strategy == KeepStrategy.NEWEST:
        return apply_keep_newest(group)
    elif strategy == KeepStrategy.MANUAL:
        # Manual strategy implies no automatic decision
        return DedupDecision(keep_item=None, remove_items=[], reason="Manual review required")
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def generate_dedup_plan(groups: List[DuplicateGroup], strategy: KeepStrategy) -> List[DedupDecision]:
    """
    Generates a list of decisions for the given groups using the specified strategy.
    """
    decisions = []
    for group in groups:
        decision = select_item_to_keep(group, strategy)
        decisions.append(decision)
    return decisions
