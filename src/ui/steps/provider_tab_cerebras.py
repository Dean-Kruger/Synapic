"""
Cerebras provider configuration tab for Step 2.
"""

import customtkinter as ctk
from .provider_tab_base import ProviderTabBase
import logging

logger = logging.getLogger(__name__)


class CerebrasProviderTab(ProviderTabBase):
    """Cerebras provider configuration tab."""

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        self.provider_name = "cerebras"
        self.provider_display_name = self._get_provider_display_name()
        super().__init__(parent, session, worker, persist_preference_callback, filter_image_models_func)

    def _get_provider_name(self) -> str:
        return "cerebras"

    def _get_provider_display_name(self) -> str:
        return "Cerebras"

    def _get_default_model(self) -> str:
        return "llama3.1-8b"

    def _get_default_task(self) -> str:
        return "image-to-text"

    def _get_models_header_text(self) -> str:
        return f"{'Model ID':<35} | {'Provider':^12} | {'Capability':>18}"

    def _setup_api_key_section(self):
        """Set up the Cerebras API key configuration section."""
        api_key_frame = ctk.CTkFrame(self, fg_color="transparent")
        api_key_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        api_key_frame.grid_columnconfigure(1, weight=1)

        # Info banner — Cerebras orange brand colour
        info_frame = ctk.CTkFrame(api_key_frame, fg_color="#E05C00", corner_radius=8)
        info_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0, 5))

        ctk.CTkLabel(
            info_frame,
            text=(
                "⚡ Cerebras — World's fastest LLM inference. "
                "Get your API key at cloud.cerebras.ai"
            ),
            wraplength=550,
            font=("Roboto", 11),
            text_color="white",
        ).grid(row=0, column=0, padx=10, pady=8)

        ctk.CTkLabel(api_key_frame, text="API Key:").grid(row=1, column=0, padx=(0, 5), sticky="w")
        self.api_key_var = ctk.StringVar(value=self.session.engine.cerebras_api_key or "")
        ctk.CTkEntry(api_key_frame, textvariable=self.api_key_var, show="*", width=250).grid(row=1, column=1, sticky="ew", padx=5)

        ctk.CTkButton(
            api_key_frame,
            text="Refresh Models",
            command=self._load_and_display_models,
            width=120
        ).grid(row=1, column=2, padx=(10, 0))

        self.status_label = ctk.CTkLabel(api_key_frame, text="", text_color="gray")
        self.status_label.grid(row=1, column=3, padx=10)

        # Image only checkbox
        self.image_only_var = ctk.BooleanVar(value=self.session.engine.cerebras_image_models_only)
        ctk.CTkCheckBox(
            api_key_frame,
            text="List image models only",
            variable=self.image_only_var,
            command=self._on_image_only_toggle
        ).grid(row=2, column=1, sticky="w", padx=5, pady=(6, 0))

    def _load_models(self):
        """Load models from Cerebras API."""
        from src.integrations.cerebras_client import CerebrasClient

        key = self.api_key_var.get().strip()
        client = CerebrasClient(api_key=key)

        if not client.has_sdk():
            self._models_cache = []
            if self.status_label:
                self.status_label.configure(
                    text="SDK missing: install cerebras_cloud_sdk",
                    text_color="orange",
                )
            return

        models = client.list_models(limit=40)
        self._models_cache = models

    def _display_models(self, models):
        """Display Cerebras models in the models list."""
        # Use the base class display method with custom model formatting
        super()._display_models(models)

    def _add_model_to_list(self, model):
        """Add a Cerebras model to the models list with custom formatting."""
        model_id = model.get("id", "")
        provider = model.get("provider", "Cerebras")
        capability = model.get("capability", "LLM")

        display_id = model_id[:33] + ".." if len(model_id) > 35 else model_id
        display_text = f"{display_id:<35} | {provider:^12} | {capability:>18}"

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
        """Save Cerebras provider-specific configuration."""
        key = self.api_key_var.get().strip()

        if not key:
            if self.status_label:
                self.status_label.configure(text="API key required", text_color="red")
            return

        if not model_id:
            if self.status_label:
                self.status_label.configure(text="Select a model", text_color="red")
            return

        self.session.engine.provider = "cerebras"
        self.session.engine.model_id = model_id
        self.session.engine.cerebras_api_key = key
        # Cerebras models are text-based (image sent as base64 data URL or text fallback)
        self.session.engine.task = "image-to-text"

        # Try to save config
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
        except Exception as e:
            logger.error(f"Error saving Cerebras config: {e}")

        status_text = f"Saved: {model_id}"
        status_color = "green"
        try:
            from src.integrations.cerebras_client import CerebrasClient

            client = CerebrasClient(api_key=key)
            availability_error = client.availability_error()
            if availability_error:
                status_text = f"{status_text} | {availability_error}"
                status_color = "orange"
        except Exception:
            pass

        if self.status_label:
            self.status_label.configure(text=status_text, text_color=status_color)

        # Apply config would typically update the parent step2_tagging
        # For now, we'll just note that the config was saved

    def refresh(self):
        """Refresh the tab when it becomes visible."""
        # Update API key field
        if self.api_key_var:
            self.api_key_var.set(getattr(self.session.engine, "cerebras_api_key", "") or "")

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


def create_cerebras_tab(parent, session, worker, persist_preference_callback, filter_image_models_func):
    """Factory function to create a Cerebras provider tab."""
    return CerebrasProviderTab(
        parent, session, worker, persist_preference_callback, filter_image_models_func
    )