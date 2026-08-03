"""
Ollama provider configuration tab for Step 2.
"""

import customtkinter as ctk
import tkinter.messagebox as mb
from .provider_tab_base import ProviderTabBase
import logging

logger = logging.getLogger(__name__)


class OllamaProviderTab(ProviderTabBase):
    """Ollama provider configuration tab."""

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        self.provider_name = "ollama"
        self.provider_display_name = self._get_provider_display_name()
        super().__init__(parent, session, worker, persist_preference_callback, filter_image_models_func)

    def _get_provider_name(self) -> str:
        return "ollama"

    def _get_provider_display_name(self) -> str:
        return "Ollama"

    def _get_default_model(self) -> str:
        return "llama3:latest"

    def _get_default_task(self) -> str:
        return "image-to-text"

    def _get_models_header_text(self) -> str:
        return f"{'Model ID':<40} | {'Family':^12} | {'Type':^10} | {'Size':>10}"

    def _setup_api_key_section(self):
        """Set up the Ollama API key configuration section."""
        api_key_frame = ctk.CTkFrame(self, fg_color="transparent")
        api_key_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        api_key_frame.grid_columnconfigure(1, weight=1)

        # Host URL
        ctk.CTkLabel(api_key_frame, text="Host URL:").grid(row=0, column=0, padx=(0, 5), sticky="w")
        self.host_var = ctk.StringVar(value=self.session.engine.ollama_host or "http://localhost:11434")
        ctk.CTkEntry(api_key_frame, textvariable=self.host_var, width=200).grid(row=0, column=1, sticky="ew", padx=5)

        # Host shortcuts
        shortcut_frame = ctk.CTkFrame(api_key_frame, fg_color="transparent")
        shortcut_frame.grid(row=0, column=2, padx=5)
        ctk.CTkButton(
            shortcut_frame, text="Cloud", width=55, height=26,
            font=("Roboto", 10), fg_color="#4B4B4B", hover_color="#5B5B5B",
            command=lambda: self._set_ollama_host_mode("cloud")
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            shortcut_frame, text="Local", width=55, height=26,
            font=("Roboto", 10), fg_color="#4B4B4B", hover_color="#5B5B5B",
            command=lambda: self._set_ollama_host_mode("local")
        ).pack(side="left", padx=2)

        # API Key
        self._api_key_label = ctk.CTkLabel(api_key_frame, text="API Key:")
        self._api_key_label.grid(row=1, column=0, padx=(0, 5), pady=(6, 0), sticky="w")
        self.api_key_var = ctk.StringVar(value=self.session.engine.ollama_api_key or "")
        self.api_key_entry = ctk.CTkEntry(api_key_frame, textvariable=self.api_key_var, show="*", width=200)
        self.api_key_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(6, 0))

        # API Key buttons
        self._api_key_btn_frame = ctk.CTkFrame(api_key_frame, fg_color="transparent")
        self._api_key_btn_frame.grid(row=1, column=2, padx=5, pady=(6, 0))
        ctk.CTkButton(
            self._api_key_btn_frame, text="Refresh",
            command=self._load_and_display_models, width=80
        ).pack(side="left", padx=2)
        self.status_label = ctk.CTkLabel(self._api_key_btn_frame, text="", text_color="gray")
        self.status_label.pack(side="left", padx=6)

        # Image only checkbox
        self.image_only_var = ctk.BooleanVar(value=self.session.engine.ollama_image_models_only)
        ctk.CTkCheckBox(
            api_key_frame,
            text="List image models only",
            variable=self.image_only_var,
            command=self._on_image_only_toggle
        ).grid(row=2, column=1, sticky="w", padx=5, pady=(6, 0))

        self.host_var.trace_add("write", lambda *_: self._update_ollama_auth_visibility())
        self._update_ollama_auth_visibility()

    def _load_models(self):
        """Load models from Ollama API."""
        from src.integrations.ollama_client import OllamaClient

        host = self.host_var.get().strip()
        key = "" if self._is_local_ollama_host(host) else self.api_key_var.get().strip()

        client = OllamaClient(host=host, api_key=key)

        if not client.is_available():
            self._models_cache = []
            return

        models = client.list_models()
        self._models_cache = models

    def _display_models(self, models):
        """Display Ollama models in the models list."""
        # Use the base class display method with custom model formatting
        super()._display_models(models)

    def _add_model_to_list(self, model):
        """Add an Ollama model to the models list with custom formatting."""
        model_id = model.get('id', '')
        family = model.get('family', 'unknown')
        capability = model.get('capability', 'LLM')
        size = model.get('size', '')

        display_id = model_id[:38] + ".." if len(model_id) > 40 else model_id
        display_text = f"{display_id:<40} | {family:^12} | {capability:^10} | {size:>10}"

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
        """Save Ollama provider-specific configuration."""
        host = self.host_var.get().strip()
        key = "" if self._is_local_ollama_host(host) else self.api_key_var.get().strip()

        if not model_id:
            if self.status_label:
                self.status_label.configure(text="Select a model", text_color="red")
            return

        self.session.engine.provider = "ollama"
        self.session.engine.model_id = model_id
        self.session.engine.ollama_host = host
        self.session.engine.ollama_api_key = key
        # Assume image-to-text (VLM or description prompt)
        self.session.engine.task = "image-to-text"

        # Try to save config
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
        except Exception as e:
            logger.error(f"Error saving Ollama config: {e}")

        if self.status_label:
            self.status_label.configure(text=f"Saved: {model_id}", text_color="green")

        # Apply config would typically update the parent step2_tagging
        # For now, we'll just note that the config was saved

    def _is_local_ollama_host(self, host: str) -> bool:
        """Return True when the configured Ollama endpoint looks like a local instance."""
        normalized = (host or "").strip().lower()
        return any(token in normalized for token in ("localhost", "127.0.0.1", "::1"))

    def _update_ollama_auth_visibility(self):
        """Hide the API key row when Ollama is configured to use a local host."""
        if not hasattr(self, "_api_key_label"):
            return

        if self._is_local_ollama_host(self.host_var.get()):
            self._api_key_label.grid_remove()
            self.api_key_entry.grid_remove()
            self._api_key_btn_frame.grid_remove()
            self.status_label.configure(text="Local instance detected", text_color="gray")
        else:
            self._api_key_label.grid()
            self.api_key_entry.grid()
            self._api_key_btn_frame.grid()

    def refresh(self):
        """Refresh the tab when it becomes visible."""
        # Update host field
        if hasattr(self, 'host_var'):
            self.host_var.set(getattr(self.session.engine, "ollama_host", "") or "")

        # Update API key field
        if self.api_key_var:
            self.api_key_var.set(getattr(self.session.engine, "ollama_api_key", "") or "")

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


def create_ollama_tab(parent, session, worker, persist_preference_callback, filter_image_models_func):
    """Factory function to create an Ollama provider tab."""
    return OllamaProviderTab(
        parent, session, worker, persist_preference_callback, filter_image_models_func
    )