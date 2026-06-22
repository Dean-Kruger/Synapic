"""
Local provider configuration tab for Step 2.
"""

import customtkinter as ctk
import tkinter.messagebox as mb
from .provider_tab_base import ProviderTabBase
import logging
import os
import shutil

logger = logging.getLogger(__name__)


class LocalProviderTab(ProviderTabBase):
    """Local provider configuration tab."""

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        super().__init__(parent, session, worker, persist_preference_callback, filter_image_models_func)
        # Cache for models (not used for local, but keeping for interface compatibility)
        self._models_cache = []
        # Set up the local-specific UI
        self._setup_local_ui()

    def _get_provider_name(self) -> str:
        return "local"

    def _get_provider_display_name(self) -> str:
        return "Local Inference"

    def _get_default_model(self) -> str:
        # This will be set when a model is selected
        return self.session.engine.model_id or ""

    def _get_default_task(self) -> str:
        # Task will be determined from the selected model
        return self.session.engine.task or "image-classification"

    def _get_models_header_text(self) -> str:
        return f"{'Model ID':<40} | {'Capability':^15} | {'Size':>10}"

    def _setup_local_ui(self):
        """Set up the local provider specific UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # List area grows

        # Header with cache info
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="📦 Downloaded Models",
                     font=("Roboto", 16, "bold")).pack(side="left", padx=5)

        self.cache_count_label = ctk.CTkLabel(header, text="(0 models)",
                                              text_color="gray")
        self.cache_count_label.pack(side="left", padx=5)

        ctk.CTkButton(header, text="+ Find & Download Models",
                      command=self.open_download_manager,
                      width=180).pack(side="right", padx=5)

        # List of cached models ONLY
        self.local_list_frame = ctk.CTkScrollableFrame(
            self,
            label_text="Ready for Local Inference"
        )
        self.local_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # Add a header label for clarity
        header_text = self._get_models_header_text()
        self.list_header = ctk.CTkLabel(
            self.local_list_frame,
            text=header_text,
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        )
        self.list_header.pack(fill="x", pady=(5, 10), padx=5)

        # Selection and action
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(footer, text="Selected:").pack(side="left")
        self.local_model_var = ctk.StringVar(value=self.session.engine.model_id or "")
        ctk.CTkLabel(footer, textvariable=self.local_model_var,
                     font=("Roboto", 12, "bold")).pack(side="left", padx=10)

        ctk.CTkButton(footer, text="Use for Local Inference",
                      command=self.save_local).pack(side="right")

        # Load cached models
        self.refresh_local_cache()

    def _setup_api_key_section(self):
        """Local provider doesn't use API keys."""
        pass

    def _setup_tools_section(self):
        """Local provider doesn't need the standard tools section."""
        pass

    def _setup_models_list(self):
        """Model list is already set up in _setup_local_ui."""
        pass

    def _setup_selection_area(self):
        """Selection area is already set up in _setup_local_ui."""
        pass

    def open_download_manager(self):
        """Opens a separate dialog for browsing and downloading models."""
        from .step2_tagging import DownloadManagerDialog
        DownloadManagerDialog(self.parent, self.session)

    def refresh_local_cache(self):
        """Refresh the list of locally cached models."""
        for widget in self.local_list_frame.winfo_children():
            widget.destroy()

        try:
            from src.core import huggingface_utils
            # Get ALL local models, not filtered by task yet
            all_local = huggingface_utils.find_local_models()

            if not all_local:
                ctk.CTkLabel(
                    self.local_list_frame,
                    text="No models downloaded yet.\nClick '+ Find & Download Models' to browse the Hub.",
                    text_color="gray",
                    justify="center"
                ).pack(pady=20)
                self.cache_count_label.configure(text="(0 models, 0 B)")
            else:
                total_bytes = sum(m.get('size_bytes', 0) for m in all_local.values())
                total_str = huggingface_utils.format_size(total_bytes)
                self.cache_count_label.configure(text=f"({len(all_local)} models, {total_str})")

                # Sort models by size descending
                sorted_models = sorted(all_local.items(), key=lambda x: x[1].get('size_bytes', 0), reverse=True)

                for model_id, info in sorted_models:
                    self.add_cached_model_item(
                        model_id,
                        info.get('size_str', 'Unknown size'),
                        info.get('capability', 'Unknown')
                    )

        except Exception as e:
            ctk.CTkLabel(
                self.local_list_frame,
                text=f"Error scanning cache: {e}",
                text_color="red"
            ).pack()

    def add_cached_model_item(self, model_id, size_str, capability):
        """Add a cached model to the list."""
        frame = ctk.CTkFrame(self.local_list_frame)
        frame.pack(fill="x", pady=2)

        # Format the text with "columns" using padding/fixed width font if possible,
        # but for now a nice formatted string.
        display_text = f"✓ {model_id:<40} | {capability:^15} | {size_str:>10}"

        btn = ctk.CTkButton(
            frame,
            text=display_text,
            font=("Courier New", 12),
            fg_color="transparent",
            border_width=1,
            text_color="#2FA572",
            anchor="w",
            command=lambda m=model_id: self.select_local_model(m)
        )
        btn.pack(side="left", fill="x", expand=True)

        # Delete button
        ctk.CTkButton(
            frame,
            text="🗑️",
            width=30,
            fg_color="transparent",
            hover_color="red",
            command=lambda m=model_id: self.delete_cached_model(m)
        ).pack(side="right", padx=2)

    def select_local_model(self, model_id):
        """Handle local model selection."""
        self.local_model_var.set(model_id)

    def delete_cached_model(self, model_id):
        """Delete a cached model from disk."""
        # Simple confirmation using tkinter.messagebox if available, or just delete for now
        if mb.askyesno("Confirm Delete", f"Are you sure you want to delete {model_id} from local cache?\nThis will free up disk space."):
            try:
                from src.core import huggingface_utils
                path = huggingface_utils.get_model_cache_dir(model_id)
                if os.path.exists(path):
                    shutil.rmtree(path)
                    logger.info(f"Deleted model directory: {path}")

                self.refresh_local_cache()
            except Exception as e:
                mb.showerror("Error", f"Failed to delete model: {e}")

    def save_local(self):
        """Save the local provider configuration."""
        self.session.engine.provider = "local"
        self.session.engine.model_id = self.local_model_var.get()

        # Find task from cache
        try:
            from src.core import huggingface_utils
            local_models = huggingface_utils.find_local_models()
            model_info = local_models.get(self.session.engine.model_id)
            if model_info:
                # Use the newly added suggested_task from hf_utils
                self.session.engine.task = model_info.get('suggested_task', "image-classification")
                logger.debug(f"Setting task for {self.session.engine.model_id} to {self.session.engine.task}")
        except Exception as e:
            logger.debug(f"Could not determine task for local model: {e}")

        # Try to save config
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def _load_models(self):
        """Local provider doesn't load models from an API."""
        pass

    def _display_models(self, models):
        """Local provider display is handled by refresh_local_cache."""
        pass

    def _save_provider_config(self, model_id):
        """Local provider-specific config saving is handled by save_local."""
        pass

    def refresh(self):
        """Refresh the tab when it becomes visible."""
        # Update model entry
        if hasattr(self, 'local_model_var'):
            current_model = getattr(self.session.engine, "model_id", "") or ""
            self.local_model_var.set(current_model)


def create_local_tab(parent, session, worker, persist_preference_callback, filter_image_models_func):
    """Factory function to create a local provider tab."""
    return LocalProviderTab(
        parent, session, worker, persist_preference_callback, filter_image_models_func
    )