"""
Groq provider configuration tab for Step 2.
"""

import customtkinter as ctk
from .provider_tab_base import ProviderTabBase
import logging

logger = logging.getLogger(__name__)


class GroqProviderTab(ProviderTabBase):
    """Groq provider configuration tab with multi-key support."""

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        self.provider_name = "groq_package"
        self.provider_display_name = self._get_provider_display_name()
        super().__init__(parent, session, worker, persist_preference_callback, filter_image_models_func)

    def _get_provider_name(self) -> str:
        return "groq_package"

    def _get_provider_display_name(self) -> str:
        return "Groq"

    def _get_default_model(self) -> str:
        return "llama2-70b-4096"

    def _get_default_task(self) -> str:
        return "image-to-text"

    def _setup_models_list(self):
        """Set up the Groq models list display area."""
        self._groq_models_list = ctk.CTkScrollableFrame(
            self,
            label_text=f"Available {self.provider_display_name} Models"
        )
        self._groq_models_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Add header
        header_text = self._get_models_header_text()
        ctk.CTkLabel(
            self._groq_models_list,
            text=header_text,
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        ).pack(fill="x", pady=(5, 10), padx=5)

    def _get_models_header_text(self) -> str:
        return f"{'Model ID':<40} | {'Capability':^15} | {'Cost':>15}"

    def _setup_api_key_section(self):
        """Set up the Groq API key configuration section with multi-key support."""
        # Main key frame
        key_frame = ctk.CTkFrame(self, fg_color="transparent")
        key_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        key_frame.grid_columnconfigure(0, weight=1)

        # Header row with label, count badge, and refresh button
        header_row = ctk.CTkFrame(key_frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(header_row, text="API Keys (one per line):").pack(side="left")

        self.groq_key_count_label = ctk.CTkLabel(
            header_row, text="0 keys", font=("Roboto", 10), text_color="gray"
        )
        self.groq_key_count_label.pack(side="left", padx=10)

        ctk.CTkButton(
            header_row,
            text="Refresh Models",
            command=self._load_and_display_groq_models,
            width=120
        ).pack(side="right")

        # Multi-line textbox for API keys
        existing_keys = self.session.engine.groq_api_keys or ""
        self.groq_api_keys_textbox = ctk.CTkTextbox(
            key_frame,
            height=70,
            font=("Courier New", 11),
            wrap="none",
            fg_color="#1E1E1E",
            border_width=1,
            border_color="#444"
        )
        self.groq_api_keys_textbox.pack(fill="x", pady=(0, 5))
        if existing_keys:
            self.groq_api_keys_textbox.insert("1.0", existing_keys)

        # Helper hint
        ctk.CTkLabel(
            key_frame,
            text="💡 Enter multiple Groq API keys (one per line) for automatic rotation when quota is exceeded.",
            font=("Roboto", 9),
            text_color="#888",
            anchor="w",
            wraplength=600
        ).pack(fill="x", pady=(0, 5))

        # Update key count on any change
        self.groq_api_keys_textbox.bind("<KeyRelease>", lambda e: self._update_groq_key_count())
        self._update_groq_key_count()

    def _setup_tools_section(self):
        """Set up the Groq tools/search section."""
        # Tools frame
        tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        tools_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        tools_frame.grid_columnconfigure(0, weight=1)

        # Status label (left side)
        self.status_label = ctk.CTkLabel(tools_frame, text="", text_color="gray")
        self.status_label.grid(row=0, column=0, sticky="w")

        # Groq specific status
        self.groq_status = ctk.CTkLabel(tools_frame, text="", text_color="gray")
        self.groq_status.grid(row=0, column=1, padx=10, sticky="w")

        # Image only checkbox
        self.groq_image_only_var = ctk.BooleanVar(value=self.session.engine.groq_image_models_only)
        self.groq_image_only_checkbox = ctk.CTkCheckBox(
            tools_frame,
            text="List image models only",
            variable=self.groq_image_only_var,
            command=self._on_image_only_toggle
        )
        self.groq_image_only_checkbox.grid(row=0, column=2, padx=10, sticky="e")

        # Refresh button
        self.refresh_button = ctk.CTkButton(
            tools_frame,
            text="Refresh Models",
            command=self._load_and_display_groq_models,
            width=120
        )
        self.refresh_button.grid(row=0, column=3, padx=(10, 0), sticky="e")

        # Note: Selection area is handled by _setup_selection_area() in the base class

    def _load_models(self):
        """Load models from Groq API."""
        from src.integrations.groq_package_client import GroqPackageClient
        api_key = self._get_groq_api_key_for_refresh()
        client = GroqPackageClient(api_key=api_key)

        try:
            models = client.list_models(limit=40)
            self._models_cache = models
        except Exception as e:
            logger.error(f"Error loading Groq models: {e}")
            self._models_cache = []

    def _get_groq_api_key_for_refresh(self):
        """Get the first API key from the textbox for model listing."""
        text = self.groq_api_keys_textbox.get("1.0", "end-1c")
        keys = [k.strip() for k in text.splitlines() if k.strip()]
        return keys[0] if keys else ""

    def _update_groq_key_count(self):
        """Update the key count label based on current textbox content."""
        if not hasattr(self, 'groq_api_keys_textbox'):
            return
        text = self.groq_api_keys_textbox.get("1.0", "end-1c")
        keys = [k.strip() for k in text.splitlines() if k.strip()]
        count = len(keys)
        if count == 0:
            self.groq_key_count_label.configure(text="0 keys", text_color="gray")
        elif count == 1:
            self.groq_key_count_label.configure(text="1 key", text_color="#2FA572")
        else:
            self.groq_key_count_label.configure(text=f"{count} keys (rotation enabled)", text_color="#2FA572")

    def _display_models(self, models):
        """Display Groq models in the models list."""
        # Clear existing widgets
        for widget in self._groq_models_list.winfo_children():
            widget.destroy()

        # Re-add header
        header_text = self._get_models_header_text()
        ctk.CTkLabel(
            self._groq_models_list,
            text=header_text,
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        ).pack(fill="x", pady=(5, 10), padx=5)

        if not models:
            ctk.CTkLabel(self._groq_models_list, text="No Groq models found (check API key?).", text_color="gray").pack()
            return

        # Apply image only filter
        filtered_models = self._filter_image_models(models, self.groq_image_only_var.get())
        if not filtered_models:
            ctk.CTkLabel(
                self._groq_models_list,
                text="No image-capable Groq models matched the current filter.",
                text_color="gray"
            ).pack()
            return

        for m in models:
            mid = m.get('id') or m.get('model_id') or ''
            cap = m.get('capability') or m.get('task') or 'Groq'
            cost = m.get('token_cost') or m.get('token_cost_per_inference') or m.get('cost')
            cost_text = f"{cost} tokens" if cost is not None else "Unknown"

            display_text = f"{mid:<40} | {cap:^15} | {cost_text:>15}"

            btn = ctk.CTkButton(
                self._groq_models_list,
                text=display_text,
                font=("Courier New", 12),
                fg_color="transparent",
                border_width=1,
                anchor="w",
                width=0,
                command=lambda m_id=mid: self._select_groq_model(m_id)
            )
            btn.pack(fill="x", pady=2)

    def _select_groq_model(self, model_id):
        """Handle Groq model selection."""
        if hasattr(self, 'groq_model'):
            self.groq_model.delete(0, "end")
            self.groq_model.insert(0, model_id)
        elif self.model_entry:
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, model_id)

    def _save_provider_config(self, model_id):
        """Save Groq provider-specific configuration."""
        # Update API keys from the textbox
        if hasattr(self, 'groq_api_keys_textbox'):
            api_keys_text = self.groq_api_keys_textbox.get("1.0", "end-1c").strip()

            # Validate: at least one key
            keys = [k.strip() for k in api_keys_text.splitlines() if k.strip()]
            if not keys:
                if hasattr(self, 'groq_status'):
                    self.groq_status.configure(text="At least one API Key required", text_color="red")
                return

            self.session.engine.provider = "groq_package"
            self.session.engine.groq_api_keys = api_keys_text
            self.session.engine.groq_current_key_index = 0  # Reset rotation on save
            self.session.engine.model_id = model_id
            # Groq vision models are multi-modal usually or LLMs.
            self.session.engine.task = "image-to-text"

            # Try to save config
            try:
                from src.utils.config_manager import save_config
                save_config(self.session)
            except Exception as e:
                logger.error(f"Error saving Groq config: {e}")

            key_info = f"{len(keys)} key{'s' if len(keys) > 1 else ''}"
            if hasattr(self, 'groq_status'):
                self.groq_status.configure(text=f"Groq config saved ({key_info})", text_color="green")

            # Apply config
            self._apply_config()

    def _load_and_display_groq_models(self):
        """Load and display Groq models."""
        if hasattr(self, 'groq_status'):
            self.groq_status.configure(text="Connecting...", text_color="gray")

        def worker():
            try:
                from src.integrations.groq_package_client import GroqPackageClient
                api_key = self._get_groq_api_key_for_refresh()
                client = GroqPackageClient(api_key=api_key)

                models = client.list_models(limit=40)
                # UI updates must run on the Tk main thread
                if self.winfo_exists():
                    self.after(0, lambda m=models: self._display_groq_models(m))
            except Exception as e:
                logger.error(f"Error loading Groq models: {e}")
                if self.winfo_exists() and hasattr(self, 'groq_status'):
                    self.after(0, lambda: self.groq_status.configure(
                        text=f"Error: {str(e)}", text_color="red"
                    ))

        self._worker.submit_replacing("groq_models", worker)

    def _display_groq_models(self, models, update_cache=True):
        """Display Groq models in the scrollable list."""
        if not self.winfo_exists() or not hasattr(self._groq_models_list, 'winfo_children'):
            return

        if update_cache:
            self._groq_models_cache = list(models or [])
        raw_models = list(self._groq_models_cache)
        models = self._filter_image_models(raw_models, self.groq_image_only_var.get())

        # Clear existing widgets
        for widget in self._groq_models_list.winfo_children():
            widget.destroy()

        # Re-add header
        header_text = self._get_models_header_text()
        ctk.CTkLabel(
            self._groq_models_list,
            text=header_text,
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        ).pack(fill="x", pady=(5, 10), padx=5)

        if not raw_models:
            ctk.CTkLabel(self._groq_models_list, text="No Groq models found (check API key?).", text_color="gray").pack()
            return
        if not models:
            ctk.CTkLabel(
                self._groq_models_list,
                text="No image-capable Groq models matched the current filter.",
                text_color="gray"
            ).pack()
            return

        self.groq_status.configure(
            text=(
                f"{len(models)} of {len(raw_models)} models shown"
                if self.groq_image_only_var.get()
                else f"{len(models)} models found"
            ),
            text_color="#2FA572"
        )

        for m in models:
            mid = m.get('id') or m.get('model_id') or ''
            cap = m.get('capability') or m.get('task') or 'Groq'
            cost = m.get('token_cost') or m.get('token_cost_per_inference') or m.get('cost')
            cost_text = f"{cost} tokens" if cost is not None else "Unknown"

            display_text = f"{mid:<40} | {cap:^15} | {cost_text:>15}"

            btn = ctk.CTkButton(
                self._groq_models_list,
                text=display_text,
                font=("Courier New", 12),
                fg_color="transparent",
                border_width=1,
                anchor="w",
                width=0,
                command=lambda m_id=mid: self._select_groq_model(m_id)
            )
            btn.pack(fill="x", pady=2)

    def save_groq_config(self):
        """Save Groq configuration."""
        model_id = self.groq_model.get().strip() if hasattr(self, 'groq_model') else ""
        api_keys_text = self.groq_api_keys_textbox.get("1.0", "end-1c").strip() if hasattr(self, 'groq_api_keys_textbox') else ""

        # Validate: at least one key
        keys = [k.strip() for k in api_keys_text.splitlines() if k.strip()]
        if not keys:
            if hasattr(self, 'groq_status'):
                self.groq_status.configure(text="At least one API Key required", text_color="red")
            return

        self.session.engine.provider = "groq_package"
        self.session.engine.groq_api_keys = api_keys_text
        self.session.engine.groq_current_key_index = 0  # Reset rotation on save
        self.session.engine.model_id = model_id
        # Groq vision models are multi-modal usually or LLMs.
        self.session.engine.task = "image-to-text"

        # Try to save config
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
        except Exception as e:
            logger.error(f"Error saving Groq config: {e}")

        key_info = f"{len(keys)} key{'s' if len(keys) > 1 else ''}"
        if hasattr(self, 'groq_status'):
            self.groq_status.configure(text=f"Groq config saved ({key_info})", text_color="green")

        # Apply config
        self._apply_config()

    def _apply_config(self):
        """Apply the configuration to update the UI."""
        # This would typically call a method on the parent step2_tagging
        # For now, we'll just update the model info if we can access it
        pass


def create_groq_tab(parent, session, worker, persist_preference_callback, filter_image_models_func):
    """Factory function to create a Groq provider tab."""
    return GroqProviderTab(
        parent, session, worker, persist_preference_callback, filter_image_models_func
    )