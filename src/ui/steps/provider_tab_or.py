"""
OpenRouter provider configuration tab for Step 2.
"""

import customtkinter as ctk
from .provider_tab_base import ProviderTabBase
import logging

logger = logging.getLogger(__name__)


class OpenRouterProviderTab(ProviderTabBase):
    """OpenRouter provider configuration tab."""

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        self.provider_name = "openrouter"
        self.provider_display_name = self._get_provider_display_name()
        self.var_show_paid = None
        super().__init__(parent, session, worker, persist_preference_callback, filter_image_models_func)

    def _get_provider_name(self) -> str:
        return "openrouter"

    def _get_provider_display_name(self) -> str:
        return "OpenRouter"

    def _get_default_model(self) -> str:
        return "openai/gpt-4-vision-preview"

    def _get_default_task(self) -> str:
        return "image-to-text"

    def _get_models_header_text(self) -> str:
        return f"{'Model ID':<40} | {'Capability':^15} | {'Cost':>15}"

    def _setup_api_key_section(self):
        """Set up the OpenRouter API key configuration section."""
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

    def _setup_tools_section(self):
        """Set up the OpenRouter tools section."""
        # Call parent to set up refresh button, image only checkbox, and status label
        super()._setup_tools_section()

        # Add OpenRouter specific tools
        tools_frame = self.refresh_button.master  # Get the tools frame we created in parent
        self.refresh_button.grid_forget()
        self.status_label.grid_forget()
        if hasattr(self, 'image_only_checkbox'):
            self.image_only_checkbox.grid_forget()

        # Add Fetch button
        ctk.CTkButton(tools_frame, text="Fetch Available Models", command=self.fetch_or_models).pack(side="left")

        # Show Paid Models checkbox
        self.var_show_paid = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(tools_frame, text="Show Paid Models", variable=self.var_show_paid,
                        command=self.fetch_or_models).pack(side="left", padx=10)

        # Image only checkbox (re-added)
        if hasattr(self, 'image_only_checkbox'):
            self.image_only_checkbox.pack(side="left", padx=10)
        else:
            self.image_only_var = ctk.BooleanVar(
                value=getattr(self.session.engine, "openrouter_image_models_only", False)
            )
            self.image_only_checkbox = ctk.CTkCheckBox(
                tools_frame,
                text="List image models only",
                variable=self.image_only_var,
                command=self._on_image_only_toggle
            )
            self.image_only_checkbox.pack(side="left", padx=10)

        # Refresh button (re-added)
        self.refresh_button = ctk.CTkButton(
            tools_frame,
            text="Refresh Models",
            command=self._load_and_display_models,
            width=120
        )
        self.refresh_button.pack(side="left", padx=(10, 0))

        # Status label (re-added)
        self.status_label = ctk.CTkLabel(tools_frame, text="", text_color="gray")
        self.status_label.pack(side="left", padx=10)

    def _load_models(self):
        """Load models from OpenRouter API."""
        from src.core import openrouter_utils

        # Get the show paid setting
        show_paid = self.var_show_paid.get() if self.var_show_paid else False

        # We can't really filter by 'task' in the same way, but OR utils handles 'image' modality check
        model_ids, _ = openrouter_utils.find_models_by_task(
            "image-to-text",
            limit=100,
            include_paid=show_paid
        )
        models = [{"id": mid, "capability": "Vision", "cost": "Unknown"} for mid in model_ids]
        self._models_cache = models

    def _display_models(self, models):
        """Display OpenRouter models in the models list."""
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
            ctk.CTkLabel(self.models_list, text="No generic vision models found.").pack()
            return

        for item in models:
            mid = item.get("id", "")
            capability = item.get("capability", "Vision")
            cost_str = item.get("cost", "Unknown")

            display_text = f"{mid:<40} | {capability:^15} | {cost_str:>15}"

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
        """Save OpenRouter provider-specific configuration."""
        # Update API key from the entry field
        if self.api_key_var:
            self.session.engine.api_key = self.api_key_var.get().strip()

        # OpenRouter is primarily chat/generation -> image-to-text task in our logical mapping
        self.session.engine.task = "image-to-text"

    def fetch_or_models(self):
        """Fetch OpenRouter models."""
        # Clear including header
        for w in self.models_list.winfo_children():
            w.destroy()

        # Re-add header
        header_text = self._get_models_header_text()
        ctk.CTkLabel(
            self.models_list,
            text=header_text,
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        ).pack(fill="x", pady=(5, 10), padx=5)

        ctk.CTkLabel(self.models_list, text="Fetching...", text_color="gray").pack()

        def worker():
            try:
                from src.core import openrouter_utils
                show_paid = self.var_show_paid.get() if self.var_show_paid else False
                model_ids, _ = openrouter_utils.find_models_by_task(
                    "image-to-text",
                    limit=100,
                    include_paid=show_paid
                )
                models = [{"id": mid, "capability": "Vision", "cost": "Unknown"} for mid in model_ids]
                # UI updates must run on the Tk main thread
                if self.winfo_exists():
                    self.after(0, lambda: self._display_models(models))
            except Exception as e:
                error_msg = str(e)
                if self.winfo_exists():
                    self.after(0, lambda: self._display_models([], error=error_msg))

        self._worker.submit_replacing("or_fetch", worker)

    def _display_models(self, models, update_cache=True, error=None):
        """Display models in the scrollable list, with error handling."""
        if not self.winfo_exists() or not hasattr(self, "models_list"):
            return

        if error:
            # Clear existing widgets
            for widget in self.models_list.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.models_list, text=f"Error: {error}\n(Check internet?)", text_color="red").pack()
            return

        # Call the parent display method
        super()._display_models(models, update_cache)


def create_openrouter_tab(parent, session, worker, persist_preference_callback, filter_image_models_func):
    """Factory function to create an OpenRouter provider tab."""
    return OpenRouterProviderTab(
        parent, session, worker, persist_preference_callback, filter_image_models_func
    )