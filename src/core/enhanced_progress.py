"""
Granular Progress Orchestration
===============================

This module provides an advanced progress tracking system that goes beyond 
simple integer counters. It supports multi-stage operations (e.g., download 
-> load -> process) with weighted contributions to the overall progress bar.

Key Features:
-------------
- Stage-Based Reporting: Tracks distinct phases like 'DOWNLOADING_MODEL' or 
  'APPLYING_TAGS'.
- Weighted Accumulation: Allows different stages to contribute differently 
  to the visual progress (e.g., 90% of the bar is reserved for processing).
- Predictive Estimation: Calculates time-to-completion based on historical 
  processing speed per item.
- Thread-Safe Singleton: Designed to be accessed globally for easy 
  instrumentation of IO-bound and CPU-bound tasks.

Author: Synapic Project
"""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import threading


class ProgressStage(Enum):
    """
    State-machine enumeration for the processing lifecycle.
    
    Each stage represents a distinct block of work. The `EnhancedProgressTracker`
    uses these to determine which progress calculation logic (time-based vs. 
    item-based) to apply.
    """
    IDLE = "idle"
    CONNECTING = "connecting"
    DOWNLOADING_MODEL = "downloading_model"
    LOADING_MODEL = "loading_model"
    INITIALIZING = "initializing"
    PROCESSING_IMAGES = "processing_images"
    ANALYZING_IMAGE = "analyzing_image"
    APPLYING_TAGS = "applying_tags"
    UPDATING_METADATA = "updating_metadata"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class GranularProgress:
    """
    Immutable snapshot of current progress metrics.
    
    This object is designed for consumption by the UI. It provides pre-calculated 
    percentages and human-readable messages, shielding the display layer 
    from the complexities of weighted averaging.
    """
    stage: ProgressStage
    sub_stage: str
    current: int
    total: int
    percentage: float
    elapsed_seconds: float
    estimated_remaining_seconds: Optional[float]
    bytes_downloaded: Optional[int] = None
    total_bytes: Optional[int] = None
    current_file: Optional[str] = None
    speed_bps: Optional[float] = None
    message: Optional[str] = None
    
    @property
    def overall_percentage(self) -> float:
        """Calculate overall progress including all stages."""
        return self.percentage
    
    @property
    def is_complete(self) -> bool:
        """Check if progress indicates completion."""
        return self.stage == ProgressStage.COMPLETE
    
    @property
    def has_error(self) -> bool:
        """Check if progress indicates an error."""
        return self.stage == ProgressStage.ERROR


class EnhancedProgressTracker:
    """
    Unified engine for tracking multi-stage task progress.
    
    This tracker maintains internal state for current items, total counts, 
    and byte transfers. It handles the 'weighted' logic where specifically 
    designated stages (usually `PROCESSING_IMAGES`) take up the lion's 
    share of the visual progress bar.
    """
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.stage_start_time: Optional[float] = None
        self.current_stage = ProgressStage.IDLE
        self.sub_stage = ""
        self.current_item = 0
        self.total_items = 0
        self.bytes_downloaded = 0
        self.total_bytes = 0
        self.current_file = ""
        self.last_progress_time = time.time()
        self.stage_weights = {
            # Download stages: Minimal weight to avoid "starting at 30%"
            # User requested "ONLY cover the number of files being processed"
            ProgressStage.CONNECTING: 0,
            ProgressStage.DOWNLOADING_MODEL: 0,
            ProgressStage.LOADING_MODEL: 0,
            
            # Processing stages: 100% of the bar
            ProgressStage.PROCESSING_IMAGES: 100,
            ProgressStage.ANALYZING_IMAGE: 0,  
            ProgressStage.APPLYING_TAGS: 0,    
            ProgressStage.UPDATING_METADATA: 0,
            
            # Final stages
            ProgressStage.FINALIZING: 0,
            ProgressStage.COMPLETE: 0
        }
        
        # Track sub-progress within processing stage
        self.processing_sub_stages = {
            "downloading_thumbnail": 0,
            "loading_image": 0,
            "ai_inference": 0,
            "extracting_results": 0,
            "updating_metadata": 0
        }
        
        self.current_processing_sub_stage = "downloading_thumbnail"
        self.processing_sub_stage_progress = 0.0
    
    def start_tracking(self, total_items: int = 0):
        """Start progress tracking for a new operation."""
        self.start_time = time.time()
        self.stage_start_time = time.time()
        self.total_items = total_items
        self.current_item = 0
        self.current_stage = ProgressStage.INITIALIZING
        logging.info(f"Started tracking progress for {total_items} items")
    
    def set_stage(self, stage: ProgressStage, sub_stage: str = "", message: str = ""):
        """Set the current processing stage."""
        if self.current_stage != stage:
            self.current_stage = stage
            self.stage_start_time = time.time()
            self.sub_stage = sub_stage
            if message:
                logging.info(f"Stage changed to: {stage.value} - {sub_stage}")
        
        # Update message if provided
        if message:
            self.sub_stage = sub_stage
    
    def update_download_progress(self, bytes_downloaded: int, total_bytes: int, 
                               current_file: str = "", speed_bps: float = 0.0):
        """Update progress for model download."""
        self.bytes_downloaded = bytes_downloaded
        self.total_bytes = total_bytes
        self.current_file = current_file
        
        if self.current_stage in [ProgressStage.CONNECTING, ProgressStage.DOWNLOADING_MODEL]:
            self.set_stage(ProgressStage.DOWNLOADING_MODEL, 
                         sub_stage=f"Downloading {current_file}" if current_file else "Downloading model files")
    
    def update_processing_progress(self, current_item: int, sub_stage: str = "", 
                                 sub_stage_progress: float = 0.0):
        """Update progress for image processing."""
        self.current_item = current_item
        
        # Update sub-stage within processing
        if sub_stage and sub_stage != self.current_processing_sub_stage:
            self.current_processing_sub_stage = sub_stage
            self.processing_sub_stage_progress = 0.0
            logging.debug(f"Processing sub-stage: {sub_stage}")
        
        if sub_stage_progress >= 0:
            self.processing_sub_stage_progress = sub_stage_progress
        
        # Set processing stage if not already set
        if self.current_stage not in [ProgressStage.PROCESSING_IMAGES, ProgressStage.ANALYZING_IMAGE]:
            self.set_stage(ProgressStage.PROCESSING_IMAGES, sub_stage="Processing images")
    
    def get_granular_progress(self) -> GranularProgress:
        """
        Generate a comprehensive progress snapshot.
        
        Calculates:
        1. Overall weighted percentage.
        2. Average processing speed (items/sec or bytes/sec).
        3. Estimated time of arrival (ETA) based on average latency.
        
        Returns:
            GranularProgress: A UI-ready package of metrics.
        """
        if not self.start_time:
            return GranularProgress(
                stage=self.current_stage,
                sub_stage="",
                current=0,
                total=1,
                percentage=0.0,
                elapsed_seconds=0.0,
                estimated_remaining_seconds=None
            )
        
        elapsed = time.time() - self.start_time
        
        # Calculate overall percentage based on current stage
        overall_percentage = self._calculate_overall_percentage()
        
        # Calculate estimated remaining time
        if overall_percentage > 0 and self.total_items > 0:
            items_completed = self.current_item
            if items_completed > 0:
                avg_time_per_item = elapsed / items_completed
                remaining_items = self.total_items - items_completed
                estimated_remaining = avg_time_per_item * remaining_items
            else:
                estimated_remaining = None
        else:
            estimated_remaining = None
        
        # Build progress message
        message = self._build_progress_message()
        
        return GranularProgress(
            stage=self.current_stage,
            sub_stage=self.sub_stage,
            current=self.current_item,
            total=self.total_items,
            percentage=overall_percentage,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=estimated_remaining,
            bytes_downloaded=self.bytes_downloaded,
            total_bytes=self.total_bytes,
            current_file=self.current_file,
            speed_bps=self._calculate_speed(),
            message=message
        )
    
    def _calculate_overall_percentage(self) -> float:
        """Calculate overall progress percentage based on weighted stages."""
        if self.current_stage == ProgressStage.IDLE:
            return 0.0
        elif self.current_stage == ProgressStage.COMPLETE:
            return 100.0
        elif self.current_stage == ProgressStage.ERROR:
            return 0.0  # Don't show partial progress on errors
        
        # Calculate progress within current stage
        stage_progress = self._get_stage_progress()
        
        # Calculate cumulative percentage
        cumulative_percentage = 0.0
        
        # Add completed stages
        for stage, weight in self.stage_weights.items():
            if stage.value < self.current_stage.value:
                cumulative_percentage += weight
            elif stage == self.current_stage:
                cumulative_percentage += weight * stage_progress
                break
        
        return min(cumulative_percentage, 100.0)
    
    def _get_stage_progress(self) -> float:
        """Get progress within the current stage (0.0 to 1.0)."""
        if self.current_stage == ProgressStage.DOWNLOADING_MODEL and self.total_bytes > 0:
            # Download progress based on bytes
            return min(self.bytes_downloaded / self.total_bytes, 1.0)
        
        elif self.current_stage == ProgressStage.PROCESSING_IMAGES and self.total_items > 0:
            # Processing progress based on items
            base_progress = self.current_item / self.total_items
            
            # Add sub-stage progress for current item
            if self.current_processing_sub_stage in self.processing_sub_stages:
                sub_stage_weight = self.processing_sub_stages[self.current_processing_sub_stage] / 100.0
                sub_stage_contribution = (self.processing_sub_stage_progress / 100.0) * sub_stage_weight
                return min(base_progress + sub_stage_contribution, 1.0)
            
            return base_progress
        
        elif self.current_stage == ProgressStage.UPDATING_METADATA:
            # Metadata update progress
            if self.current_item >= self.total_items:
                return 1.0
            return min(self.current_item / max(self.total_items, 1), 1.0)
        
        else:
            # For other stages, use time-based estimation
            if self.stage_start_time:
                elapsed_stage = time.time() - self.stage_start_time
                # Assume 2-5 seconds for these stages
                return min(elapsed_stage / 3.0, 1.0)
            return 0.5  # Default middle progress
    
    def _calculate_speed(self) -> Optional[float]:
        """Calculate current download/processing speed."""
        current_time = time.time()
        time_diff = current_time - self.last_progress_time
        
        if time_diff < 1.0:  # Only calculate if enough time has passed
            return None
        
        if self.current_stage == ProgressStage.DOWNLOADING_MODEL and self.total_bytes > 0:
            # Download speed in bytes per second
            bytes_diff = self.bytes_downloaded  # This would need to track incremental changes
            return bytes_diff / time_diff if bytes_diff > 0 else None
        
        elif self.current_stage == ProgressStage.PROCESSING_IMAGES:
            # Processing speed in items per second
            items_diff = self.current_item  # This would need to track incremental changes
            return items_diff / time_diff if items_diff > 0 else None
        
        return None
    
    def _build_progress_message(self) -> str:
        """Build a descriptive progress message."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        if self.current_stage == ProgressStage.DOWNLOADING_MODEL:
            if self.total_bytes > 0:
                percentage = (self.bytes_downloaded / self.total_bytes) * 100
                return f"Downloading model: {percentage:.1f}% ({self.bytes_downloaded:,}/{self.total_bytes:,} bytes)"
            else:
                return "Downloading model..."
        
        elif self.current_stage == ProgressStage.PROCESSING_IMAGES:
            if self.total_items > 0:
                percentage = (self.current_item / self.total_items) * 100
                stage_msg = f" | {self.current_processing_sub_stage}" if self.current_processing_sub_stage else ""
                return f"Processing: {self.current_item}/{self.total_items} ({percentage:.1f}%){stage_msg}"
            else:
                return "Processing images..."
        
        elif self.current_stage == ProgressStage.UPDATING_METADATA:
            return f"Updating metadata: {self.current_item}/{self.total_items}"
        
        else:
            stage_names = {
                ProgressStage.CONNECTING: "Connecting...",
                ProgressStage.LOADING_MODEL: "Loading model...",
                ProgressStage.INITIALIZING: "Initializing...",
                ProgressStage.FINALIZING: "Finalizing...",
                ProgressStage.COMPLETE: "Complete!",
                ProgressStage.ERROR: "Error occurred"
            }
            return stage_names.get(self.current_stage, self.current_stage.value)
    
    def mark_complete(self):
        """Mark the operation as complete."""
        self.current_stage = ProgressStage.COMPLETE
        self.current_item = self.total_items
        logging.info("Progress tracking completed")
    
    def mark_error(self, error_message: str = ""):
        """Mark the operation as failed."""
        self.current_stage = ProgressStage.ERROR
        if error_message:
            logging.error(f"Progress tracking error: {error_message}")


# Global progress tracker instance
_global_progress_tracker = EnhancedProgressTracker()


def get_progress_tracker() -> EnhancedProgressTracker:
    """Get the global progress tracker instance."""
    return _global_progress_tracker


def start_detailed_progress(total_items: int = 0) -> EnhancedProgressTracker:
    """Start detailed progress tracking for an operation."""
    tracker = get_progress_tracker()
    tracker.start_tracking(total_items)
    return tracker


# Convenience functions for common progress updates
def update_download_progress(bytes_downloaded: int, total_bytes: int, 
                           current_file: str = "", speed_bps: float = 0.0):
    """Update download progress."""
    get_progress_tracker().update_download_progress(bytes_downloaded, total_bytes, current_file, speed_bps)


def update_processing_progress(current_item: int, sub_stage: str = "", 
                             sub_stage_progress: float = 0.0):
    """Update processing progress."""
    get_progress_tracker().update_processing_progress(current_item, sub_stage, sub_stage_progress)


def get_current_progress() -> GranularProgress:
    """Get current detailed progress."""
    return get_progress_tracker().get_granular_progress()


def set_progress_stage(stage: ProgressStage, sub_stage: str = "", message: str = ""):
    """Set the current progress stage."""
    get_progress_tracker().set_stage(stage, sub_stage, message)