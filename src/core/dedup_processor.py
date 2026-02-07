"""
Daminion Deduplication Processor
================================

Integrates the dedup engine with the Daminion API to detect and manage
duplicate images in Daminion collections and searches.

Usage:
------
    from src.core.dedup_processor import DaminionDedupProcessor
    
    processor = DaminionDedupProcessor(daminion_client, similarity_threshold=95.0)
    groups = processor.scan_for_duplicates(items, algorithm='phash', progress_callback=callback)
    results = processor.apply_dedup_action(decisions, action='tag')
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional, Any
from enum import Enum

from src.core.dedup import (
    ImageDeduplicator,
    DuplicateGroup,
    KeepStrategy,
    DedupDecision,
    generate_dedup_plan,
    ImageHashCalculator,
    HashResult
)

logger = logging.getLogger(__name__)


class DedupAction(Enum):
    """Actions that can be applied to duplicate items."""
    TAG = "tag"               # Add "Duplicate" tag to duplicates
    COLLECTION = "collection" # Move duplicates to a collection
    DELETE = "delete"         # Delete duplicates from Daminion
    NONE = "none"             # Just report, no action


@dataclass
class DaminionDedupItem:
    """Represents a Daminion item with its dedup-related data."""
    item_id: int
    thumbnail_bytes: Optional[bytes] = None
    hash_result: Optional[HashResult] = None
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __str__(self):
        return str(self.item_id)


@dataclass
class DedupScanResult:
    """Result of a deduplication scan."""
    total_items: int
    items_hashed: int
    duplicate_groups: List[DuplicateGroup]
    errors: List[str]
    algorithm: str
    threshold: float


class DaminionDedupProcessor:
    """
    Processes Daminion items for duplicate detection.
    
    This class integrates the dedup engine with the Daminion API,
    handling thumbnail fetching, hash calculation, and applying
    deduplication actions.
    """
    
    def __init__(
        self,
        daminion_client,
        similarity_threshold: float = 95.0,
        duplicate_tag_name: str = "Duplicate"
    ):
        """
        Initialize the processor.
        
        Args:
            daminion_client: Connected DaminionClient instance
            similarity_threshold: Minimum similarity percentage (0-100)
            duplicate_tag_name: Tag name to use when marking duplicates
        """
        self.client = daminion_client
        self.threshold = similarity_threshold
        self.duplicate_tag_name = duplicate_tag_name
        self.deduplicator = ImageDeduplicator(similarity_threshold=similarity_threshold)
        self.calculator = ImageHashCalculator()
        
        # Cache for item data during processing
        self._item_cache: Dict[str, DaminionDedupItem] = {}
        self._abort_requested = False
    
    def abort(self):
        """Request abort of current operation."""
        self._abort_requested = True
    
    def reset(self):
        """Reset state for a new operation."""
        self._abort_requested = False
        self._item_cache.clear()
    
    def scan_for_duplicates(
        self,
        items: List[Dict],
        algorithm: str = 'phash',
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        thumbnail_size: int = 300
    ) -> DedupScanResult:
        """
        Scan Daminion items for duplicates.
        
        Args:
            items: List of Daminion item dicts (must have 'Id' or 'id' key)
            algorithm: Hash algorithm ('phash', 'dhash', 'ahash', 'whash')
            progress_callback: Callback(message, current, total) for progress updates
            thumbnail_size: Size of thumbnails to fetch for hashing
            
        Returns:
            DedupScanResult with duplicate groups and statistics
        """
        self.reset()
        
        total = len(items)
        errors = []
        hash_map: Dict[str, HashResult] = {}
        
        logger.info(f"Starting dedup scan: {total} items, algorithm={algorithm}, threshold={self.threshold}%")
        
        if progress_callback:
            progress_callback("Preparing items...", 0, total)
        
        # Process each item
        for idx, item in enumerate(items):
            if self._abort_requested:
                logger.info("Dedup scan aborted by user")
                break
            
            item_id = item.get('Id') or item.get('id')
            if not item_id:
                errors.append(f"Item at index {idx} has no ID")
                continue
            
            item_key = str(item_id)
            
            if progress_callback:
                progress_callback(f"Hashing item {item_id}...", idx + 1, total)
            
            try:
                # Fetch thumbnail bytes
                thumbnail_bytes = self.client.get_thumbnail(
                    item_id,
                    width=thumbnail_size,
                    height=thumbnail_size
                )
                
                if not thumbnail_bytes:
                    errors.append(f"No thumbnail for item {item_id}")
                    continue
                
                # Calculate hash
                img = self.calculator.load_image_from_bytes(thumbnail_bytes)
                hash_result = self.calculator.calculate_perceptual_hash(img, algorithm=algorithm)
                
                hash_map[item_key] = hash_result
                
                # Cache item data for later use
                self._item_cache[item_key] = DaminionDedupItem(
                    item_id=item_id,
                    thumbnail_bytes=thumbnail_bytes,
                    hash_result=hash_result,
                    metadata=item
                )
                
            except Exception as e:
                error_msg = f"Error processing item {item_id}: {e}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
        
        if progress_callback:
            progress_callback("Finding duplicates...", total, total)
        
        # Find duplicate groups
        duplicate_groups = self.deduplicator.find_similar_images(hash_map, threshold=self.threshold)
        
        logger.info(f"Scan complete: {len(hash_map)} hashed, {len(duplicate_groups)} duplicate groups, {len(errors)} errors")
        
        return DedupScanResult(
            total_items=total,
            items_hashed=len(hash_map),
            duplicate_groups=duplicate_groups,
            errors=errors,
            algorithm=algorithm,
            threshold=self.threshold
        )
    
    def get_item_thumbnail(self, item_id: str) -> Optional[bytes]:
        """Get cached thumbnail bytes for an item."""
        item_key = str(item_id)
        if item_key in self._item_cache:
            return self._item_cache[item_key].thumbnail_bytes
        return None
    
    def get_item_metadata(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get cached metadata for an item."""
        item_key = str(item_id)
        if item_key in self._item_cache:
            return self._item_cache[item_key].metadata
        return None
    
    def generate_decisions(
        self,
        groups: List[DuplicateGroup],
        strategy: KeepStrategy
    ) -> List[DedupDecision]:
        """
        Generate deduplication decisions for the groups.
        
        Note: For Daminion items (accessed via API), the FIRST and MANUAL
        strategies are most appropriate since file-based strategies
        (LARGEST, OLDEST, etc.) require filesystem access.
        """
        return generate_dedup_plan(groups, strategy)
    
    
    def apply_dedup_action(
        self,
        decisions: List[DedupDecision],
        action: DedupAction = DedupAction.TAG,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        collection_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply deduplication actions to items.
        
        Args:
            decisions: List of DedupDecision objects
            action: Action to apply (TAG, COLLECTION, DELETE, NONE)
            progress_callback: Callback for progress updates
            collection_id: Target collection ID (for COLLECTION action)
            
        Returns:
            Dict with counts and lists: {'tagged': N, 'moved': N, 'deleted': N, 'errors': N, 'deleted_ids': [...]}
        """
        self._abort_requested = False
        
        results = {'tagged': 0, 'moved': 0, 'deleted': 0, 'errors': 0, 'skipped': 0, 'deleted_ids': []}
        
        if action == DedupAction.NONE:
            logger.info("No action requested, skipping application")
            return results
        
        # Collect all items to process (remove_items from each decision)
        items_to_process = []
        for decision in decisions:
            for item_id in decision.remove_items:
                items_to_process.append(item_id)
        
        total = len(items_to_process)
        logger.info(f"Applying {action.value} action to {total} duplicate items")
        
        for idx, item_id in enumerate(items_to_process):
            if self._abort_requested:
                logger.info("Dedup action aborted by user")
                break
            
            if progress_callback:
                progress_callback(f"Processing item {item_id}...", idx + 1, total)
            
            try:
                int_item_id = int(item_id)
                
                if action == DedupAction.TAG:
                    # Add "Duplicate" tag to the item
                    success = self.client.update_item_tags(
                        int_item_id,
                        {'Keywords': [self.duplicate_tag_name]}
                    )
                    if success:
                        results['tagged'] += 1
                    else:
                        results['errors'] += 1
                
                elif action == DedupAction.COLLECTION:
                    # Move to collection (if API supports it)
                    logger.warning(f"Collection action not yet implemented for item {item_id}")
                    results['skipped'] += 1
                
                elif action == DedupAction.DELETE:
                    # Delete from Daminion catalog
                    # WARNING: This is destructive!
                    try:
                        self.client._api.media_items.delete_items([int_item_id])
                        results['deleted'] += 1
                        results['deleted_ids'].append(item_id)
                        logger.info(f"Deleted item {item_id} from catalog")
                    except Exception as del_err:
                        logger.error(f"Failed to delete item {item_id}: {del_err}")
                        results['errors'] += 1
                
            except Exception as e:
                logger.error(f"Error applying action to item {item_id}: {e}")
                results['errors'] += 1
        
        logger.info(f"Action complete: {results}")
        return results
    
    def get_supported_algorithms(self) -> List[str]:
        """Return list of supported hash algorithms."""
        return list(self.calculator.SUPPORTED_PERCEPTUAL_ALGOS.keys())
    
    def get_supported_strategies(self) -> List[KeepStrategy]:
        """Return list of supported keep strategies."""
        # For API-based items, only FIRST and MANUAL make sense
        # unless we have file path access
        return [KeepStrategy.FIRST, KeepStrategy.MANUAL]
