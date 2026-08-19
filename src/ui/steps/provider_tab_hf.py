"""
Hugging Face provider configuration tab for Step 2.
"""

import customtkinter as ctk
from .provider_tab_base import ProviderTabBase
import logging

logger = logging.getLogger(__name__)


class HuggingFaceProviderTab(ProviderTabBase):
    """Hugging Face provider configuration tab."""

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        self.provider_name = "huggingface"
        self.provider_display_name = self._get_provider_display_name()
        super().__init__(parent, session, worker, persist_preference_callback, filter_image_models_func)

    def _get_provider_name(self) -> str:
        return "huggingface"

    def _get_provider_display_name(self) -> str:
        return "Hugging Face"

    def _get_default_model(self) -> str:
        return "Salesforce/blip-image-captioning-base"

    def _get_default_task(self) -> str:
        return "image-to-text"

    def _get_models_header_text(self) -> str:
        return f"{'Model ID':<40} | {'Capability':^15} | {'Size':>10}"

    def _setup_api_key_section(self):
        """Set up the Hugging Face API key configuration section."""
        api_key_frame = ctk.CTkFrame(self, fg_color="transparent")
        api_key_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        api_key_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(api_key_frame, text="API Key:").pack(side="left")
        self.api_key_var = ctk.StringVar(value=self.session.engine.api_key or "")
        self.api_key_entry = ctk.CTkEntry(
            api_key_frame,
            width=250,
            show="*",
            textvariable=self.api_key_var
        )
        self.api_key_entry.pack(side="left", padx=10, fill="x", expand=True)

        # Rate Limit Warning Banner
        warning_frame = ctk.CTkFrame(self, fg_color="#FF6B35", corner_radius=8)
        warning_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        warning_icon = ctk.CTkLabel(warning_frame, text="⚠️", font=("Roboto", 16))
        warning_icon.pack(side="left", padx=10)

        warning_text = ctk.CTkLabel(
            warning_frame,
            text="⚡ API Test Mode: Free tier has rate limits (~15 req/hour). Multi-modal models (Image+Text) are supported.",
            wraplength=500,
            font=("Roboto", 11)
        )
        warning_text.pack(side="left", padx=5, pady=8)

    def _setup_tools_section(self):
        """Set up the Hugging Face tools/search section."""
        # Call parent to set up refresh button, image only checkbox, and status label
        super()._setup_tools_section()

        # Add Hugging Face specific search tools
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)  # Override position
        search_frame.grid_columnconfigure(0, weight=1)

        # Move the refresh button and checkboxes to the search frame
        self.refresh_button.grid_forget()
        self.status_label.grid_forget()
        if hasattr(self, 'image_only_checkbox'):
            self.image_only_checkbox.grid_forget()

        # Search entry
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search multi-modal models (e.g. 'blip', 'vit-gpt2')..."
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.search_entry.bind("<Return>", lambda e: self.search_hf_online())

        ctk.CTkButton(search_frame, text="Search Hub", width=100, command=self.search_hf_online).pack(side="left")

        # Image only checkbox (re-added)
        if hasattr(self, 'image_only_checkbox'):
            self.image_only_checkbox.pack(side="left", padx=10)
        else:
            self.image_only_var = ctk.BooleanVar(
                value=getattr(self.session.engine, "huggingface_image_models_only", False)
            )
            self.image_only_checkbox = ctk.CTkCheckBox(
                search_frame,
                text="List image models only",
                variable=self.image_only_var,
                command=self._on_image_only_toggle
            )
            self.image_only_checkbox.pack(side="left", padx=10)

        # Refresh button (re-added)
        self.refresh_button = ctk.CTkButton(
            search_frame,
            text="Refresh Models",
            command=self._load_and_display_models,
            width=120
        )
        self.refresh_button.pack(side="left", padx=(10, 0))

        # Status label (re-added)
        self.status_label = ctk.CTkLabel(search_frame, text="", text_color="gray")
        self.status_label.pack(side="left", padx=10)

    def search_hf_online(self):
        """Search Hugging Face Hub based on search entry."""
        self._load_and_display_models()

    def _load_models(self):
        """Load models from Hugging Face Hub."""
        from huggingface_hub import list_models
        from src.core import huggingface_utils, config

        query = getattr(self, 'search_entry', None)
        query_text = query.get() if query else ""

        tasks = [
            config.MODEL_TASK_IMAGE_CLASSIFICATION,
            config.MODEL_TASK_IMAGE_TO_TEXT,
            config.MODEL_TASK_ZERO_SHOT,
            "visual-question-answering",
            "image-text-to-text"
        ]

        all_results = []
        for t in tasks:
            models = list_models(
                filter=t,
                search=query_text,
                limit=5,
                sort="downloads",
            )
            for m in models:
                all_results.append({
                    'id': m.id,
                    'task': t,
                    'capability': huggingface_utils.get_model_capability(t)
                })

        # Deduplicate
        seen = set()
        unique_results = []
        for r in all_results:
            if r['id'] not in seen:
                unique_results.append(r)
                seen.add(r['id'])

        # Filter out models that our local transformers runtime cannot actually load.
        unique_results = [
            r for r in unique_results
            if huggingface_utils.is_model_suitable_for_local_inference(r['id'], task=r['task'])
        ]

        # Fetch sizes
        results_with_details = []
        for item in unique_results:
            mid = item['id']
            size_bytes = huggingface_utils.get_remote_model_size(mid)
            item['size_str'] = huggingface_utils.format_size(size_bytes)
            results_with_details.append(item)

        self._models_cache = results_with_details

    def _display_models(self, models):
        """Display Hugging Face models in the models list."""
        # Clear existing widgets
        for widget in self.models_list.winfo_children():
            widget.destroy()

        # Re-add header
        header_text = self._get_models_header_text()
        ctk.CTkLabel(
            self.models_list,
            text=header_text,
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        ).pack(fill="x", pady=(5, 10), padx=5)

        if not models:
            ctk.CTkLabel(self.models_list, text="No models found.").pack()
            return

        for item in models:
            mid = item['id']
            size_str = item.get('size_str', 'Unknown')
            capability = item.get('capability', 'Unknown')

            display_text = f"{mid:<40} | {capability:^15} | {size_str:>10}"

            btn = ctk.CTkButton(
                self.models_list,
                text=display_text,
                font=("Courier New", 12),
                fg_color="transparent",
                border_width=1,
                anchor="w",
                command=lambda m=mid: self._select_model(m)
            )
            btn.pack(fill="x", pady=2)

    def _save_provider_config(self, model_id):
        """Save Hugging Face provider-specific configuration."""
        # Update API key from the entry field
        if self.api_key_var:
            self.session.engine.api_key = self.api_key_var.get().strip()

        # Try to infer task or default to image-to-text for multi-modal
        if any(x in model_id.lower() for x in ["vit-base-patch", "resnet-", "siglip-", "bits-"]):
            self.session.engine.task = "image-classification"
        else:
            self.session.engine.task = "image-to-text"


def create_huggingface_tab(parent, session, worker, persist_preference_callback, filter_image_models_func):
    """Factory function to create a Hugging Face provider tab."""
    return HuggingFaceProviderTab(
        parent, session, worker, persist_preference_callback, filter_image_models_func
    )