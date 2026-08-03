"""
Base class for AI provider configuration tabs in Step 2.
This reduces code duplication by extracting common UI patterns.
"""

import customtkinter as ctk
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class ProviderTabBase(ctk.CTkFrame, ABC):
    """
    Base class for AI provider configuration tabs.
    Handles common UI elements and behaviors for provider configuration.
    """

    def __init__(self, parent, session, worker, persist_preference_callback, filter_image_models_func):
        """
        Initialize the provider tab base.

        Args:
            parent: Parent widget
            session: Application session object
            worker: Background worker for async operations
            persist_preference_callback: Callback to persist UI preferences
            filter_image_models_func: Function to filter models for image capability
        """
        super().__init__(parent, fg_color="transparent")
        self.session = session
        self._worker = worker
        self._persist_image_filter_preference = persist_preference_callback
        self._filter_image_models = filter_image_models_func

        # Cache for models
        self._models_cache = []

        # UI elements that subclasses will set up
        self.api_key_var = None
        self.api_key_entry = None
        self.refresh_button = None
        self.status_label = None
        self.image_only_var = None
        self.models_list = None
        self.model_entry = None
        self.save_button = None

        # Set up the_common UI layout
        self._setup_common_ui()

    def _setup_common_ui(self):
        """Set up the common UI structure for provider tabs."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # List area grows

        # API Key Configuration (except for Local provider which is handled separately)
        self._setup_api_key_section()

        # Tools/Search section
        self._setup_tools_section()

        # Models list
        self._setup_models_list()

        # Selection and action
        self._setup_selection_area()

    def _setup_api_key_section(self):
        """Set up the API key configuration section."""
        # Override in subclasses for provider-specific API key handling
        pass

    def _setup_tools_section(self):
        """Set up the tools/search section with refresh button and filters."""
        tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        tools_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        tools_frame.grid_columnconfigure(0, weight=1)

        # Refresh button
        self.refresh_button = ctk.CTkButton(
            tools_frame,
            text="Refresh Models",
            command=self._load_and_display_models,
            width=120
        )
        self.refresh_button.grid(row=0, column=2, padx=(10, 0), sticky="e")

        # Image models only checkbox
        self.image_only_var = ctk.BooleanVar(
            value=getattr(self.session.engine, f"{self.provider_name}_image_models_only", False)
        )
        self.image_only_checkbox = ctk.CTkCheckBox(
            tools_frame,
            text="List image models only",
            variable=self.image_only_var,
            command=self._on_image_only_toggle
        )
        self.image_only_checkbox.grid(row=0, column=1, padx=10, sticky="w")

        # Status label
        self.status_label = ctk.CTkLabel(tools_frame, text="", text_color="gray")
        self.status_label.grid(row=0, column=0, sticky="w")

    def _setup_models_list(self):
        """Set up the models list display area."""
        self.models_list = ctk.CTkScrollableFrame(
            self,
            label_text=f"Available {self.provider_display_name} Models"
        )
        self.models_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Add header
        header_text = self._get_models_header_text()
        ctk.CTkLabel(
            self.models_list,
            text=header_text,
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        ).pack(fill="x", pady=(5, 10), padx=5)

    def _setup_selection_area(self):
        """Set up the model selection and save area."""
        selection_frame = ctk.CTkFrame(self, fg_color="transparent")
        selection_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 20))
        selection_frame.grid_columnconfigure(0, weight=1)

        # Model selection label and entry
        ctk.CTkLabel(selection_frame, text="Selected:").grid(row=0, column=0, sticky="w")
        self.model_entry = ctk.CTkEntry(selection_frame, width=300)
        self.model_entry.grid(row=0, column=1, sticky="ew", padx=10)

        # Save button
        self.save_button = ctk.CTkButton(
            selection_frame,
            text="Save Config",
            command=self._save_config
        )
        self.save_button.grid(row=0, column=2, sticky="e")

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the provider name (e.g., 'huggingface', 'openrouter')."""
        pass

    @abstractmethod
    def _get_provider_display_name(self) -> str:
        """Return the provider display name (e.g., 'Hugging Face', 'OpenRouter')."""
        pass

    @abstractmethod
    def _get_default_model(self) -> str:
        """Return the default model ID for this provider."""
        pass

    @abstractmethod
    def _get_default_task(self) -> str:
        """Return the default task for this provider."""
        pass

    @abstractmethod
    def _get_models_header_text(self) -> str:
        """Return the header text for the models list."""
        pass

    @abstractmethod
    def _load_models(self):
        """Load models from the provider's API. Should populate self._models_cache."""
        pass

    @abstractmethod
    def _display_models(self, models):
        """Display models in the models list."""
        pass

    @abstractmethod
    def _save_provider_config(self, model_id):
        """Save the provider-specific configuration."""
        pass

    def _on_image_only_toggle(self):
        """Handle the image models only checkbox toggle."""
        preference_name = f"{self.provider_name}_image_models_only"
        self._persist_image_filter_preference(preference_name, self.image_only_var.get())
        self._display_models(self._models_cache, update_cache=False)

    def _load_and_display_models(self):
        """Load and display models from the provider."""
        if self.status_label:
            self.status_label.configure(text="Connecting...", text_color="gray")

        def worker():
            try:
                self._load_models()
                # UI updates must run on the Tk main thread
                if self.winfo_exists():
                    self.after(0, lambda: self._display_models(self._models_cache))
            except Exception as e:
                logger.error(f"Error loading models for {self.provider_name}: {e}")
                if self.winfo_exists() and self.status_label:
                    self.after(0, lambda: self.status_label.configure(
                        text=f"Error: {str(e)}", text_color="red"
                    ))

        self._worker.submit_replacing(f"{self.provider_name}_models", worker)

    def _display_models(self, models, update_cache=True):
        """Display models in the scrollable list."""
        if not self.winfo_exists() or not hasattr(self, "models_list"):
            return

        if update_cache:
            self._models_cache = list(models or [])

        raw_models = list(self._models_cache)
        filtered_models = self._filter_image_models(raw_models, self.image_only_var.get())

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

        if not raw_models:
            self._show_no_models_message()
            return

        if not filtered_models:
            ctk.CTkLabel(
                self.models_list,
                text="No image-capable models matched the current filter.",
                text_color="gray",
                justify="center"
            ).pack(pady=20)
            if self.status_label:
                self.status_label.configure(text="0 image models shown", text_color="orange")
            return

        if self.status_label:
            self.status_label.configure(
                text=(
                    f"{len(filtered_models)} of {len(raw_models)} models shown"
                    if self.image_only_var.get()
                    else f"{len(filtered_models)} models found"
                ),
                text_color="#2FA572"
            )

        # Display each model
        for model in filtered_models:
            self._add_model_to_list(model)

    def _show_no_models_message(self):
        """Show a message when no models are found."""
        ctk.CTkLabel(
            self.models_list,
            text="No models found. Check your API key or connection.",
            text_color="gray",
            justify="center"
        ).pack(pady=20)
        if self.status_label:
            self.status_label.configure(text="Connection Failed", text_color="red")

    def _add_model_to_list(self, model):
        """Add a model to the models list. Override in subclasses for custom display."""
        # Default implementation - subclasses should override for custom formatting
        model_id = model.get('id', '')
        capability = model.get('capability', 'Unknown')

        display_text = f"{model_id:<40} | {capability:^15} | {'':>10}"

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

    def _select_model(self, model_id):
        """Handle model selection."""
        if self.model_entry:
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, model_id)

    def _save_config(self):
        """Save the configuration for this provider."""
        model_id = self.model_entry.get().strip()
        if not model_id:
            if self.status_label:
                self.status_label.configure(text="Select a model", text_color="red")
            return

        # Update session
        self.session.engine.provider = self.provider_name
        self.session.engine.model_id = model_id
        self.session.engine.task = self._get_default_task()

        # Provider-specific config saving
        self._save_provider_config(model_id)

        # Save to persistent storage
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

        if self.status_label:
            self.status_label.configure(text=f"Saved: {model_id}", text_color="green")

        # Apply config to update UI
        # This would typically call a method on the parent step2_tagging
        # For now, we'll just note that the config was saved

    def refresh(self):
        """Refresh the tab when it becomes visible."""
        # Update API key field if applicable
        if self.api_key_var:
            self.api_key_var.set(getattr(self.session.engine, f"{self.provider_name}_api_key", "") or "")

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