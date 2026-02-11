"""
Step Dedup: Deduplication Wizard Step
=====================================

This module provides the UI for detecting and managing duplicate images
in Daminion collections and searches. Users can:
- Configure hash algorithm and similarity threshold
- Scan for duplicates with visual progress
- Review duplicate groups with thumbnail previews
- Select keep strategy and apply deduplication actions

Author: Synapic Project
"""

import customtkinter as ctk
import logging
import io
from PIL import Image, ImageTk
from typing import Optional, List, Dict, Any, Callable
import threading

from src.core.dedup_processor import DaminionDedupProcessor, DedupAction, DedupScanResult
from src.core.dedup import DuplicateGroup, KeepStrategy, DedupDecision

logger = logging.getLogger(__name__)


class DuplicateGroupFrame(ctk.CTkFrame):
    """
    A frame displaying a single duplicate group with thumbnails.
    """
    
    def __init__(
        self,
        parent,
        group: DuplicateGroup,
        group_index: int,
        processor: DaminionDedupProcessor,
        on_selection_changed: Optional[Callable] = None
    ):
        super().__init__(parent, fg_color=("gray85", "gray20"), corner_radius=8)
        
        self.group = group
        self.group_index = group_index
        self.processor = processor
        self.on_selection_changed = on_selection_changed
        
        # Track which item is selected to keep
        self.keep_item = ctk.StringVar(value=group.items[0] if group.items else "")
        
        # Track if this is a false positive (keep all)
        self.keep_all = ctk.BooleanVar(value=False)
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))
        
        similarity = min(group.similarity_scores.values()) if group.similarity_scores else 0
        title_text = f"Group {group_index + 1}: {len(group.items)} items ({similarity:.1f}% similar)"
        
        title_label = ctk.CTkLabel(
            header,
            text=title_text,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(side="left")
        
        # Keep All checkbox (false positive)
        self.keep_all_cb = ctk.CTkCheckBox(
            header,
            text="Keep All (Not duplicates)",
            variable=self.keep_all,
            command=self._on_keep_all_changed,
            font=ctk.CTkFont(size=11),
            text_color=("orange", "#FFA500")
        )
        self.keep_all_cb.pack(side="right", padx=10)
        
        algo_label = ctk.CTkLabel(
            header,
            text=f"[{group.hash_type.upper()}]",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        algo_label.pack(side="right")
        
        # Thumbnails container
        thumbnails_frame = ctk.CTkFrame(self, fg_color="transparent")
        thumbnails_frame.pack(fill="x", padx=10, pady=10)
        
        self.thumbnail_widgets = []
        
        for item_id in group.items:
            item_frame = self._create_item_widget(thumbnails_frame, item_id)
            item_frame.pack(side="left", padx=5)
            self.thumbnail_widgets.append(item_frame)
    
    def _create_item_widget(self, parent, item_id: str) -> ctk.CTkFrame:
        """Create a widget for a single item with thumbnail and selection."""
        frame = ctk.CTkFrame(parent, fg_color=("gray80", "gray25"), corner_radius=6)
        
        # Get thumbnail
        thumbnail_bytes = self.processor.get_item_thumbnail(item_id)
        if thumbnail_bytes:
            try:
                img = Image.open(io.BytesIO(thumbnail_bytes))
                img.thumbnail((100, 100))
                photo = ctk.CTkImage(img, size=(100, 100))
                
                img_label = ctk.CTkLabel(frame, image=photo, text="")
                img_label.image = photo  # Keep reference
                img_label.pack(padx=5, pady=5)
            except Exception as e:
                logger.warning(f"Failed to load thumbnail for {item_id}: {e}")
                placeholder = ctk.CTkLabel(frame, text="[No Image]", width=100, height=100)
                placeholder.pack(padx=5, pady=5)
        else:
            placeholder = ctk.CTkLabel(frame, text="[No Image]", width=100, height=100)
            placeholder.pack(padx=5, pady=5)
        
        # Item ID
        id_label = ctk.CTkLabel(
            frame,
            text=f"ID: {item_id}",
            font=ctk.CTkFont(size=10)
        )
        id_label.pack()
        
        # Similarity score
        similarity = self.group.similarity_scores.get(item_id, 0)
        sim_label = ctk.CTkLabel(
            frame,
            text=f"{similarity:.1f}%",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60")
        )
        sim_label.pack()
        
        # Radio button to select keep
        radio = ctk.CTkRadioButton(
            frame,
            text="Keep",
            variable=self.keep_item,
            value=item_id,
            command=self._on_selection_changed,
            font=ctk.CTkFont(size=11)
        )
        radio.pack(pady=5)
        
        return frame
    
    def _on_selection_changed(self):
        """Called when the keep selection changes."""
        if self.on_selection_changed:
            self.on_selection_changed(self.group_index, self.keep_item.get())
    
    def _on_keep_all_changed(self):
        """Called when keep all checkbox changes."""
        if self.on_selection_changed:
            self.on_selection_changed(self.group_index, self.keep_item.get())
    
    def select_by_strategy(self, strategy: str):
        """Auto-select item based on strategy."""
        logger.info(f"[DEDUP GROUP {self.group_index}] Applying strategy: '{strategy}', items: {self.group.items}")
        
        if not self.group.items:
            logger.warning(f"[DEDUP GROUP {self.group_index}] No items in group, skipping")
            return
        
        metadata_map = {}
        for item_id in self.group.items:
            meta = self.processor.get_item_metadata(item_id)
            if meta:
                metadata_map[item_id] = meta
                logger.debug(f"[DEDUP GROUP {self.group_index}] Item {item_id} metadata: FileSize={meta.get('FileSize')}, Created={meta.get('Created')}, DateTimeOriginal={meta.get('DateTimeOriginal')}")
            else:
                logger.warning(f"[DEDUP GROUP {self.group_index}] No metadata found for item {item_id}")
        
        selected = self.group.items[0]  # Default
        
        if strategy == "oldest":
            # Sort by date (ascending) - oldest first
            sorted_items = sorted(
                self.group.items,
                key=lambda x: metadata_map.get(x, {}).get('DateTimeOriginal', '') or metadata_map.get(x, {}).get('Created', '') or '9999'
            )
            selected = sorted_items[0]
            logger.info(f"[DEDUP GROUP {self.group_index}] Oldest strategy selected: {selected}")
        elif strategy == "newest":
            sorted_items = sorted(
                self.group.items,
                key=lambda x: metadata_map.get(x, {}).get('DateTimeOriginal', '') or metadata_map.get(x, {}).get('Created', '') or '',
                reverse=True
            )
            selected = sorted_items[0]
            logger.info(f"[DEDUP GROUP {self.group_index}] Newest strategy selected: {selected}")
        elif strategy == "largest":
            sorted_items = sorted(
                self.group.items,
                key=lambda x: metadata_map.get(x, {}).get('FileSize', 0) or 0,
                reverse=True
            )
            selected = sorted_items[0]
            logger.info(f"[DEDUP GROUP {self.group_index}] Largest strategy selected: {selected} (size: {metadata_map.get(selected, {}).get('FileSize', 'N/A')})")
        elif strategy == "smallest":
            sorted_items = sorted(
                self.group.items,
                key=lambda x: metadata_map.get(x, {}).get('FileSize', 0) or float('inf')
            )
            selected = sorted_items[0]
            logger.info(f"[DEDUP GROUP {self.group_index}] Smallest strategy selected: {selected} (size: {metadata_map.get(selected, {}).get('FileSize', 'N/A')})")
        
        
        # Ensure we have a valid selection before setting
        if selected:
            logger.info(f"[DEDUP GROUP {self.group_index}] Setting keep_item to: {selected}")
            self.keep_item.set(str(selected))
            self._on_selection_changed()
            
            # Force UI update by triggering the widget update
            # CustomTkinter radio buttons don't auto-update when variable changes programmatically
            self.update_idletasks()
        else:
            logger.warning(f"[DEDUP GROUP {self.group_index}] Strategy '{strategy}' failed to find a valid item")
    
    def get_decision(self) -> DedupDecision:
        """Get the dedup decision for this group based on user selection."""
        # If keep_all is checked, return empty remove list (false positive)
        if self.keep_all.get():
            return DedupDecision(
                keep_item=None,
                remove_items=[],
                reason="False positive - keep all"
            )
        
        keep = self.keep_item.get()
        remove = [item for item in self.group.items if item != keep]
        return DedupDecision(
            keep_item=keep,
            remove_items=remove,
            reason="User selection"
        )


class StepDedup(ctk.CTkFrame):
    """
    Deduplication wizard step.
    
    Allows users to scan for duplicates in their Daminion selection
    and apply deduplication actions.
    """
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.session = controller.session
        self.logger = logging.getLogger(__name__)
        
        self.processor: Optional[DaminionDedupProcessor] = None
        self.scan_result: Optional[DedupScanResult] = None
        self.group_frames: List[DuplicateGroupFrame] = []
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the deduplication UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Results area expands
        
        # ===== Header =====
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        title = ctk.CTkLabel(
            header_frame,
            text="🔍 Duplicate Detection",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(side="left")
        
        back_btn = ctk.CTkButton(
            header_frame,
            text="← Back",
            width=80,
            command=self._go_back
        )
        back_btn.pack(side="right")
        
        # ===== Settings Panel =====
        settings_frame = ctk.CTkFrame(self)
        settings_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        
        # Algorithm selection
        algo_label = ctk.CTkLabel(settings_frame, text="Algorithm:")
        algo_label.grid(row=0, column=0, padx=(15, 5), pady=10)
        
        self.algorithm_var = ctk.StringVar(value="phash")
        self.algorithm_dropdown = ctk.CTkOptionMenu(
            settings_frame,
            values=["phash", "dhash", "ahash", "whash"],
            variable=self.algorithm_var,
            width=120
        )
        self.algorithm_dropdown.grid(row=0, column=1, padx=5, pady=10)
        
        # Threshold slider
        threshold_label = ctk.CTkLabel(settings_frame, text="Threshold:")
        threshold_label.grid(row=0, column=2, padx=(20, 5), pady=10)
        
        self.threshold_var = ctk.DoubleVar(value=95.0)
        self.threshold_slider = ctk.CTkSlider(
            settings_frame,
            from_=50,
            to=100,
            variable=self.threshold_var,
            width=150,
            command=self._on_threshold_change
        )
        self.threshold_slider.grid(row=0, column=3, padx=5, pady=10)
        
        self.threshold_value_label = ctk.CTkLabel(settings_frame, text="95%", width=50)
        self.threshold_value_label.grid(row=0, column=4, padx=5, pady=10)
        
        # Action dropdown
        action_label = ctk.CTkLabel(settings_frame, text="Action:")
        action_label.grid(row=0, column=5, padx=(20, 5), pady=10)
        
        self.action_var = ctk.StringVar(value="Tag as Duplicate")
        self.action_dropdown = ctk.CTkOptionMenu(
            settings_frame,
            values=["Tag as Duplicate", "Delete from Catalog", "Manual Review Only"],
            variable=self.action_var,
            width=160
        )
        self.action_dropdown.grid(row=0, column=6, padx=5, pady=10)
        
        # Scan button
        self.scan_btn = ctk.CTkButton(
            settings_frame,
            text="Scan for Duplicates",
            command=self._start_scan,
            fg_color=("green", "darkgreen"),
            hover_color=("darkgreen", "green"),
            width=160
        )
        self.scan_btn.grid(row=0, column=7, padx=(20, 15), pady=10)
        
        # ===== Progress Bar =====
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=5)
        self.progress_frame.grid_remove()  # Hidden initially
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=400)
        self.progress_bar.pack(side="left", padx=10, fill="x", expand=True)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Scanning...")
        self.progress_label.pack(side="left", padx=10)
        
        self.abort_btn = ctk.CTkButton(
            self.progress_frame,
            text="Abort",
            width=80,
            fg_color=("red", "darkred"),
            command=self._abort_scan
        )
        self.abort_btn.pack(side="right", padx=10)
        
        # ===== Results Area =====
        results_container = ctk.CTkFrame(self)
        results_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        results_container.grid_columnconfigure(0, weight=1)
        results_container.grid_rowconfigure(0, weight=1)
        
        # Scrollable frame for duplicate groups
        self.results_scroll = ctk.CTkScrollableFrame(results_container)
        self.results_scroll.grid(row=0, column=0, sticky="nsew")
        
        # Initial message
        self.initial_label = ctk.CTkLabel(
            self.results_scroll,
            text="Select your scan settings and click 'Scan for Duplicates' to begin.\n\n"
                 "The scan will analyze images from your current Daminion selection.",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
            justify="center"
        )
        self.initial_label.pack(pady=50)
        
        # ===== Footer =====
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 20))
        
        self.stats_label = ctk.CTkLabel(
            footer_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        self.stats_label.pack(side="left")
        
        # Auto-select buttons frame
        self.select_btns_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        self.select_btns_frame.pack(side="left", padx=20)
        
        select_label = ctk.CTkLabel(self.select_btns_frame, text="Select all:", font=ctk.CTkFont(size=11))
        select_label.pack(side="left", padx=(0, 5))
        
        for strategy, label in [("oldest", "Oldest"), ("newest", "Newest"), ("largest", "Largest"), ("smallest", "Smallest")]:
            btn = ctk.CTkButton(
                self.select_btns_frame,
                text=label,
                width=70,
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color=("gray60", "gray40"),
                hover_color=("gray50", "gray30"),
                command=lambda s=strategy: self._select_all_by_strategy(s)
            )
            btn.pack(side="left", padx=2)
        
        self.apply_btn = ctk.CTkButton(
            footer_frame,
            text="Apply Deduplication",
            command=self._apply_dedup,
            state="disabled",
            width=160
        )
        self.apply_btn.pack(side="right")
    
    def _on_threshold_change(self, value):
        """Update threshold label when slider changes."""
        self.threshold_value_label.configure(text=f"{int(value)}%")
    
    def _go_back(self):
        """Navigate back to Step 1."""
        self.controller.show_step("Step1Datasource")
    
    def _start_scan(self):
        """Start the duplicate scan in a background thread."""
        # Check if Daminion is connected
        if not self.session.daminion_client or not self.session.daminion_client.authenticated:
            messagebox.showerror("Error", "Please connect to Daminion first.")
            return
        
        # Check if there are items to scan
        # We need to get items from the session's current selection
        if not hasattr(self.session, 'dedup_items') or not self.session.dedup_items:
            messagebox.showerror("Error", "No items selected for deduplication.\n\n"
                               "Please select a collection or search first.")
            return
        
        # Initialize processor
        self.processor = DaminionDedupProcessor(
            self.session.daminion_client,
            similarity_threshold=self.threshold_var.get()
        )
        
        # Show progress
        self.progress_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=5)
        self.scan_btn.configure(state="disabled")
        
        # Clear previous results
        for frame in self.group_frames:
            frame.destroy()
        self.group_frames.clear()
        self.initial_label.pack_forget()
        
        # Start scan thread
        thread = threading.Thread(target=self._run_scan, daemon=True)
        thread.start()
    
    def _run_scan(self):
        """Run the scan in background thread."""
        try:
            algorithm = self.algorithm_var.get()
            items = self.session.dedup_items
            
            def progress_callback(message, current, total):
                self.after(0, lambda: self._update_progress(message, current, total))
            
            self.scan_result = self.processor.scan_for_duplicates(
                items,
                algorithm=algorithm,
                progress_callback=progress_callback
            )
            
            self.after(0, self._on_scan_complete)
            
        except Exception as e:
            self.logger.error(f"Scan failed: {e}", exc_info=True)
            self.after(0, lambda: self._on_scan_error(str(e)))
    
    def _update_progress(self, message: str, current: int, total: int):
        """Update progress bar and label."""
        self.progress_label.configure(text=message)
        if total > 0:
            self.progress_bar.set(current / total)
    
    def _abort_scan(self):
        """Abort the current scan."""
        if self.processor:
            self.processor.abort()
    
    def _on_scan_complete(self):
        """Called when scan completes successfully."""
        self.progress_frame.grid_remove()
        self.scan_btn.configure(state="normal")
        
        if not self.scan_result:
            return
        
        result = self.scan_result
        
        # Update stats
        self.stats_label.configure(
            text=f"Scanned {result.items_hashed}/{result.total_items} items | "
                 f"Found {len(result.duplicate_groups)} duplicate groups | "
                 f"Algorithm: {result.algorithm.upper()} | "
                 f"Threshold: {result.threshold:.0f}%"
        )
        
        if not result.duplicate_groups:
            no_dupes_label = ctk.CTkLabel(
                self.results_scroll,
                text="✓ No duplicates found!",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color=("green", "lightgreen")
            )
            no_dupes_label.pack(pady=50)
            self.apply_btn.configure(state="disabled")
            return
        
        # Display duplicate groups
        for idx, group in enumerate(result.duplicate_groups):
            group_frame = DuplicateGroupFrame(
                self.results_scroll,
                group,
                idx,
                self.processor
            )
            group_frame.pack(fill="x", padx=10, pady=5)
            self.group_frames.append(group_frame)
        
        self.apply_btn.configure(state="normal")
    
    def _select_all_by_strategy(self, strategy: str):
        """Apply a selection strategy to all duplicate groups."""
        logger.info(f"[DEDUP UI] Strategy button clicked: '{strategy}', group_frames count: {len(self.group_frames)}")
        
        if not self.group_frames:
            logger.warning("[DEDUP UI] No group frames to apply strategy to")
            return
        
        for group_frame in self.group_frames:
            group_frame.select_by_strategy(strategy)
        
        # Update status to show strategy was applied
        self.stats_label.configure(
            text=f"Strategy '{strategy.capitalize()}' applied to {len(self.group_frames)} groups | "
                 f"Review selections and click 'Apply Deduplication' to proceed"
        )
        logger.info(f"[DEDUP UI] Strategy '{strategy}' applied to {len(self.group_frames)} groups")
    
    def _on_scan_error(self, error_message: str):
        """Called when scan fails with an error."""
        self.progress_frame.grid_remove()
        self.scan_btn.configure(state="normal")
        # Show error in initial label
        self.initial_label.configure(text=f"Scan Error:\n{error_message}", text_color="red")
        self.initial_label.pack(pady=50)

    
    def _reset_apply_button(self):
        """Reset the apply button to its default state."""
        try:
            default_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        except Exception:
            default_color = ["#3a7ebf", "#1f538d"]
        self.apply_btn.configure(text="Apply Deduplication", fg_color=default_color)
    
    def _apply_dedup(self):
        """Apply deduplication actions based on user selections."""
        logger.info(f"[DEDUP APPLY] Apply button clicked. Processor: {self.processor is not None}, Group frames: {len(self.group_frames) if self.group_frames else 0}")
        
        if not self.processor or not self.group_frames:
            logger.warning(f"[DEDUP APPLY] Early return - processor={self.processor is not None}, group_frames={len(self.group_frames) if self.group_frames else 0}")
            return
        
        # Collect decisions from all group frames
        decisions = [frame.get_decision() for frame in self.group_frames]
        logger.info(f"[DEDUP APPLY] Collected {len(decisions)} decisions")
        
        # Count items to be affected
        total_remove = sum(len(d.remove_items) for d in decisions)
        logger.info(f"[DEDUP APPLY] Total items to remove: {total_remove}")
        
        # Get action
        action_text = self.action_var.get()
        logger.info(f"[DEDUP APPLY] Action selected: '{action_text}'")
        if action_text == "Tag as Duplicate":
            action = DedupAction.TAG
            action_desc = f"tag {total_remove} items as 'Duplicate'"
        elif action_text == "Delete from Catalog":
            action = DedupAction.DELETE
            action_desc = f"DELETE {total_remove} items from the catalog"
            # Extra warning for delete
            logger.info("[DEDUP APPLY] Showing delete warning dialog")
            
            # Use CTkMessagebox for better visibility
        # Two-step confirmation logic
        current_btn_text = self.apply_btn.cget("text")
        confirm_text = f"Confirm {action_text}?"
        
        if current_btn_text != confirm_text:
            # First click: Change text to confirm
            logger.info(f"[DEDUP APPLY] Requesting confirmation for action: {action_text}")
            self.apply_btn.configure(text=confirm_text, fg_color="red" if action == DedupAction.DELETE else "orange")
            
            # Optional: Reset button after 5 seconds if not clicked
            self.after(5000, lambda: self._reset_apply_button())
            return
            
        # Second click: Proceed
        logger.info(f"[DEDUP APPLY] Action confirmed via button click - proceeding with {action.value}")
        
        # Reset button appearance immediately (will be disabled by _start_apply)
        self._reset_apply_button()
        
        # Proceed with action
        # Show progress
        self.progress_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=5)
        self.progress_label.configure(text="Applying changes...")
        self.progress_bar.set(0)
        self.apply_btn.configure(state="disabled")
        
        # Start apply thread
        thread = threading.Thread(
            target=self._run_apply_dedup,
            args=(decisions, action),
            daemon=True
        )
        thread.start()

    def _run_apply_dedup(self, decisions, action):
        """Run dedup application in background."""
        try:
            def progress_callback(message, current, total):
                self.after(0, lambda: self._update_progress(message, current, total))

            results = self.processor.apply_dedup_action(
                decisions, 
                action,
                progress_callback=progress_callback
            )
            
            self.after(0, lambda: self._on_apply_complete(results))
            
        except Exception as e:
            self.logger.error(f"Apply dedup failed: {e}", exc_info=True)
            self.after(0, lambda: self._on_apply_error(str(e)))

    def _on_apply_complete(self, results):
        """Called when dedup application completes."""
        self.progress_frame.grid_remove()
        self.apply_btn.configure(state="normal")
        
        msg = f"Deduplication complete!\n\n"
        if results['tagged'] > 0:
            msg += f"• Tagged: {results['tagged']} items\n"
        if results['deleted'] > 0:
            msg += f"• Deleted: {results['deleted']} items\n"
        if results['errors'] > 0:
            msg += f"• Errors: {results['errors']} items\n"
        if results['skipped'] > 0:
            msg += f"• Skipped: {results['skipped']} items\n"
        
        # Show completion message in initial label
        self.initial_label.configure(text=msg, text_color=("gray10", "gray90"))
        
        # Remove deleted items from the session list so they don't reappear in scans
        if results.get('deleted_ids'):
            deleted_ids = set(str(pid) for pid in results['deleted_ids'])
            if hasattr(self.session, 'dedup_items'):
                # Filter out deleted items
                original_count = len(self.session.dedup_items)
                self.session.dedup_items = [
                    item for item in self.session.dedup_items
                    if str(item.get('Id') or item.get('id')) not in deleted_ids
                ]
                new_count = len(self.session.dedup_items)
                logger.info(f"Removed {original_count - new_count} deleted items from session list")
                
                # Clear results if deletions happened, forcing a rescan to be safe
                if new_count < original_count and self.group_frames:
                     # Clear previous results
                    for frame in self.group_frames:
                        frame.destroy()
                    self.group_frames.clear()
                    self.initial_label.pack(pady=50)
                    self.apply_btn.configure(state="disabled")
                    self.stats_label.configure(text=f"Items updated. Please rescan.")

    def _on_apply_error(self, error_message):
        """Called if apply fails."""
        self.progress_frame.grid_remove()
        self.apply_btn.configure(state="normal")
        # Show error in initial label
        self.initial_label.configure(text=f"Error applying deduplication:\n\n{error_message}", text_color="red")
        self.initial_label.pack(pady=50)
    
    def set_items(self, items: List[Dict]):
        """Set the items to scan for deduplication."""
        self.session.dedup_items = items
        
        # Update initial label
        self.initial_label.configure(
            text=f"Ready to scan {len(items)} items for duplicates.\n\n"
                 "Configure settings above and click 'Scan for Duplicates' to begin."
        )
        self.initial_label.pack(pady=50)
    
    def refresh(self):
        """Refresh the step when navigated to."""
        # Check if we have items
        if hasattr(self.session, 'dedup_items') and self.session.dedup_items:
            count = len(self.session.dedup_items)
            self.initial_label.configure(
                text=f"Ready to scan {count} items for duplicates.\n\n"
                     "Configure settings above and click 'Scan for Duplicates' to begin."
            )
    
    def shutdown(self):
        """Clean up on application shutdown."""
        if self.processor:
            self.processor.abort()
