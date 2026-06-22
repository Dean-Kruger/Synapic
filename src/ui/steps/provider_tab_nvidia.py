"""
NVIDIA provider configuration tab for Step 2.
"""

import customtkinter as ctk
from .provider_tab_base import ProviderTabBase
import logging

logger = logging.getLogger(__name__)


class NvidiaProviderTab(ProviderTabBase):
    """NVIDIA provider configuration tab."""

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        self.provider_name = "nvidia"
        self.provider_display_name = self._get_provider_display_name()
        super().__init__(parent, session, worker, persist_preference_callback, filter_image_models_func)

    def _get_provider_name(self) -> str:
        return "nvidia"

    def _get_provider_display_name(self) -> str:
        return "NVIDIA"

    def _get_default_model(self) -> str:
        return "mistralai/mistral-large-3-675b-instruct-2512"

    def _get_default_task(self) -> str:
        return "image-to-text"

    def _get_models_header_text(self) -> str:
        return f"{'Model ID':<40} | {'Provider':^15} | {'Capability':>15}"

    def _setup_api_key_section(self):
        """Set up the NVIDIA API key configuration section."""
        api_key_frame = ctk.CTkFrame(self, fg_color="transparent")
        api_key_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        api_key_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(api_key_frame, text="API Key:").grid(row=0, column=0, padx=(0, 5), sticky="w")
        self.api_key_var = ctk.StringVar(value=self.session.engine.nvidia_api_key or "")
        ctk.CTkEntry(api_key_frame, textvariable=self.api_key_var, show="*", width=250).grid(row=0, column=1, sticky="ew", padx=5)

        ctk.CTkButton(
            api_key_frame,
            text="Refresh Models",
            command=self._load_and_display_models,
            width=120
        ).grid(row=0, column=2, padx=(10, 0))

        self.status_label = ctk.CTkLabel(api_key_frame, text="", text_color="gray")
        self.status_label.grid(row=0, column=3, padx=10)

        # Image only checkbox
        self.image_only_var = ctk.BooleanVar(value=self.session.engine.nvidia_image_models_only)
        ctk.CTkCheckBox(
            api_key_frame,
            text="List image models only",
            variable=self.image_only_var,
            command=self._on_image_only_toggle
        ).grid(row=1, column=1, sticky="w", padx=5, pady=(6, 0))

    def _load_models(self):
        """Load models from NVIDIA NIM API."""
        from src.integrations.nvidia_client import NvidiaClient

        key = self.api_key_var.get().strip()
        client = NvidiaClient(api_key=key)

        if not client.is_available():
            self._models_cache = []
            return

        models = client.list_models()
        self._models_cache = models

    def _display_models(self, models):
        """Display NVIDIA models in the models list."""
        # Use the base class display method with custom model formatting
        super()._display_models(models)

    def _add_model_to_list(self, model):
        """Add an NVIDIA model to the models list with custom formatting."""
        model_id = model.get('id', '')
        provider = model.get('provider', 'NVIDIA')
        capability = model.get('capability', 'Vision')

        display_id = model_id[:38] + ".." if len(model_id) > 40 else model_id
        display_text = f"{display_id:<40} | {provider:^15} | {capability:>15}"

        btn = ctk.CTkButton(
            self.models_list,
            text=display_text,
            font=("Courier New", 12),
            fg_color="transparent",
            border_width=1,
            anchor="w",
            width=0,
            command=lambda m_id=model_id: self._select_model(m_id)
        )
        btn.pack(fill="x", pady=2)

    def _save_provider_config(self, model_id):
        """Save NVIDIA provider-specific configuration."""
        key = self.api_key_var.get().strip()

        if not model_id:
            if self.status_label:
                self.status_label.configure(text="Select a model", text_color="red")
            return

        self.session.engine.provider = "nvidia"
        self.session.engine.model_id = model_id
        self.session.engine.nvidia_api_key = key
        # NVIDIA vision models are multi-modal
        self.session.engine.task = "image-to-text"

        # Try to save config
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
        except Exception as e:
            logger.error(f"Error saving NVIDIA config: {e}")

        if self.status_label:
            self.status_label.configure(text=f"Saved: {model_id}", text_color="green")

        # Apply config would typically update the parent step2_tagging
        # For now, we'll just note that the config was saved

    def refresh(self):
        """Refresh the tab when it becomes visible."""
        # Update API key field
        if self.api_key_var:
            self.api_key_var.set(getattr(self.session.engine, "nvidia_api_key", "") or "")

        # Update model entry
        if self.model_entry:
            current_model = getattr(self.session.engine, "model_id", "") or ""
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, current_model)

        # Update image only checkbox
        if self.image_only_var:
            self.image_only_var.set(
                getattr(self.session.engine, f"{self.provider_name}_image_models_only", False)
            )


def create_nvidia_tab(parent, session, worker, persist_preference_callback, filter_image_models_func):
    """Factory function to create an NVIDIA provider tab."""
    return NvidiaProviderTab(
        parent, session, worker, persist_preference_callback, filter_image_models_func
    )