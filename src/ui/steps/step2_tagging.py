import customtkinter as ctk

class Step2Tagging(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(self.container, text="Step 2: Tagging Engine", font=("Roboto", 24, "bold"))
        title.grid(row=0, column=0, pady=(20, 30))

        # Engine Selection
        self.engine_var = ctk.StringVar(value=self.controller.session.engine.provider or "huggingface")
        
        # Engine Cards (using Radio buttons for simplicity but styled)
        self.cards_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, pady=10)
        
        self.create_engine_card(self.cards_frame, "Local Inference", "local", 0)
        self.create_engine_card(self.cards_frame, "Hugging Face", "huggingface", 1)
        self.create_engine_card(self.cards_frame, "OpenRouter", "openrouter", 2)

        # Configure Button (renamed to "Select Engine")
        self.btn_config = ctk.CTkButton(self.container, text="Select Engine", command=self.open_config_dialog, width=200)
        self.btn_config.grid(row=2, column=0, pady=20)
        
        # === Model Info Section ===
        model_info_frame = ctk.CTkFrame(self.container, fg_color="#2B2B2B", corner_radius=10)
        model_info_frame.grid(row=3, column=0, pady=10, padx=40, sticky="ew")
        model_info_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            model_info_frame,
            text="Selected Model:",
            font=("Roboto", 12, "bold")
        ).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        self.model_info_label = ctk.CTkLabel(
            model_info_frame,
            text=self._get_model_display_text(),
            font=("Roboto", 12),
            text_color="#2FA572",
            anchor="w"
        )
        self.model_info_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        # === Global Settings Section ===
        settings_frame = ctk.CTkFrame(self.container, fg_color="#2B2B2B", corner_radius=10)
        settings_frame.grid(row=4, column=0, pady=10, padx=40, sticky="ew")
        
        ctk.CTkLabel(
            settings_frame,
            text="Global Settings",
            font=("Roboto", 14, "bold")
        ).pack(pady=(15, 10))
        
        # Device Toggle
        device_container = ctk.CTkFrame(settings_frame, fg_color="transparent")
        device_container.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            device_container,
            text="Inference Device:",
            font=("Roboto", 12)
        ).pack(side="left", padx=(0, 10))
        
        self.device_var = ctk.StringVar(value=self.controller.session.engine.device)
        self.device_switch = ctk.CTkSegmentedButton(
            device_container,
            values=["cpu", "cuda"],
            variable=self.device_var,
            command=self.on_device_change,
            width=140
        )
        self.device_switch.pack(side="left")
        
        # Confidence Threshold
        threshold_label_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        threshold_label_frame.pack(fill="x", padx=20, pady=(10, 5))
        
        ctk.CTkLabel(
            threshold_label_frame,
            text="Confidence Threshold:",
            font=("Roboto", 12, "bold")
        ).pack(side="left", padx=(0, 5))
        
        self.threshold_value_label = ctk.CTkLabel(
            threshold_label_frame,
            text=f"{self.controller.session.engine.confidence_threshold}%",
            font=("Roboto", 12),
            text_color="#2FA572"
        )
        self.threshold_value_label.pack(side="left", padx=5)
        
        ctk.CTkLabel(
            threshold_label_frame,
            text="(Filters out low-probability matches)",
            font=("Roboto", 9),
            text_color="gray"
        ).pack(side="left", padx=10)
        
        # Slider with precision level labels
        slider_container = ctk.CTkFrame(settings_frame, fg_color="transparent")
        slider_container.pack(fill="x", padx=20, pady=(0, 15))
        
        # Left label: Free
        ctk.CTkLabel(
            slider_container,
            text="Free",
            font=("Roboto", 10),
            text_color="gray"
        ).pack(side="left", padx=(0, 10))
        
        # Slider
        self.threshold_slider = ctk.CTkSlider(
            slider_container,
            from_=1,
            to=100,
            number_of_steps=99,
            command=self.on_threshold_change
        )
        self.threshold_slider.set(self.controller.session.engine.confidence_threshold)
        self.threshold_slider.pack(side="left", fill="x", expand=True)
        
        # Right label: Strict
        ctk.CTkLabel(
            slider_container,
            text="Strict",
            font=("Roboto", 10),
            text_color="gray"
        ).pack(side="left", padx=(10, 0))
        
        # Navigation Buttons
        nav_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        nav_frame.grid(row=5, column=0, pady=20, sticky="ew")
        
        ctk.CTkButton(nav_frame, text="Previous", command=lambda: self.controller.show_step("Step1Datasource"), width=150, fg_color="gray").pack(side="left", padx=20)
        ctk.CTkButton(nav_frame, text="Next Step", command=self.next_step, width=200, height=40).pack(side="right", padx=20)

        # Traces for color coding
        self.engine_var.trace_add("write", lambda *args: self.update_config_button_color())
        self.update_config_button_color()

    def _get_model_display_text(self):
        """Generate display text for selected model with capability info."""
        session = self.controller.session
        model_id = session.engine.model_id or "None"
        task = session.engine.task or "unknown"
        
        # Map task to capability description
        capability_map = {
            "image-classification": "Keywords",
            "zero-shot-image-classification": "Categories",
            "image-to-text": "Description",
            "image-text-to-text": "Multi-modal (Keywords, Categories, Description)"
        }
        
        capability = capability_map.get(task, "Unknown capability")
        
        if model_id == "None" or not model_id:
            return "No model selected"
        
        return f"{model_id} • {capability}"

    def on_threshold_change(self, value):
        """Update threshold value label and session when slider changes."""
        threshold_int = int(value)
        self.threshold_value_label.configure(text=f"{threshold_int}%")
        self.controller.session.engine.confidence_threshold = threshold_int

    def on_device_change(self, value):
        """Update session device setting when toggle changes."""
        self.controller.session.engine.device = value
        print(f"Device changed to: {value}")

    def update_config_button_color(self):
        engine = self.engine_var.get()
        is_ready = False
        
        if engine == "local":
            try:
                from src.core import huggingface_utils
                local_models = huggingface_utils.find_local_models()
                is_ready = len(local_models) > 0
            except:
                is_ready = False
        elif engine == "huggingface":
            # Check if key exists in session
            is_ready = bool(self.controller.session.engine.api_key)
        elif engine == "openrouter":
            is_ready = bool(self.controller.session.engine.api_key)
            
        if is_ready:
            self.btn_config.configure(fg_color="#2FA572", hover_color="#288E62") # Green
        else:
            self.btn_config.configure(fg_color="#E74C3C", hover_color="#C0392B") # Red

    def create_engine_card(self, parent, text, value, col):
        card = ctk.CTkRadioButton(parent, text=text, variable=self.engine_var, value=value, font=("Roboto", 16))
        card.grid(row=0, column=col, padx=20, pady=20)
        
    def open_config_dialog(self):
        engine = self.engine_var.get()
        # Pass session to dialog
        dialog = ConfigDialog(self, self.controller.session, initial_tab=engine)
        self.wait_window(dialog)
        self.update_config_button_color()
        self.update_model_info()
        
    def update_model_info(self):
        """Update the model info label after configuration changes."""
        self.model_info_label.configure(text=self._get_model_display_text())
        
    def next_step(self):
        # Update session
        self.controller.session.engine.provider = self.engine_var.get()
        
        # We need to retrieve values from the dialog if it was opened, or use defaults/session
        # This UI flow is a bit tricky because the dialog is modal.
        # Ideally, the dialog should update the session directly when "Save" is clicked (if we had a Save button)
        # Or we should have the inputs on the main card.
        
        # For now, let's assume the user configured it via the dialog which we will update to write to session.
        pass
        
        print(f"Selected Engine: {self.controller.session.engine.provider}")
        self.controller.show_step("Step3Process")

    def refresh_stats(self): # Called by App.show_step
        self.update_config_button_color()
        self.update_model_info()
        # Update device and threshold from session
        self.device_var.set(self.controller.session.engine.device)
        self.threshold_slider.set(self.controller.session.engine.confidence_threshold)
        self.threshold_value_label.configure(text=f"{self.controller.session.engine.confidence_threshold}%")



class ConfigDialog(ctk.CTkToplevel):
    def __init__(self, parent, session, initial_tab="huggingface"):
        super().__init__(parent)
        self.session = session
        self.title("Select Engine")
        self.geometry("700x550")
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.tab_local = self.tabview.add("Local Inference")
        self.tab_hf = self.tabview.add("Hugging Face")
        self.tab_or = self.tabview.add("OpenRouter")
        
        # Init Tabs
        self.init_local_tab()
        self.init_hf_tab()
        self.init_or_tab()
        
        # Select current
        map_name = {"local": "Local Inference", "huggingface": "Hugging Face", "openrouter": "OpenRouter"}
        self.tabview.set(map_name.get(initial_tab, "Hugging Face"))

    def init_local_tab(self):
        self.tab_local.grid_columnconfigure(0, weight=1)
        self.tab_local.grid_rowconfigure(1, weight=1)  # List area grows

        # Header with cache info
        header = ctk.CTkFrame(self.tab_local, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
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
            self.tab_local, 
            label_text="Ready for Local Inference"
        )
        self.local_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Add a header label for clarity
        header_text = f"{'Model ID':<40} | {'Capability':^15} | {'Size':>10}"
        self.list_header = ctk.CTkLabel(
            self.local_list_frame, 
            text=header_text, 
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        )
        self.list_header.pack(fill="x", pady=(5, 10), padx=5)
        
        # Selection and action
        footer = ctk.CTkFrame(self.tab_local, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(footer, text="Selected:").pack(side="left")
        self.local_model_var = ctk.StringVar(value=self.session.engine.model_id or "")
        ctk.CTkLabel(footer, textvariable=self.local_model_var, 
                     font=("Roboto", 12, "bold")).pack(side="left", padx=10)
        
        ctk.CTkButton(footer, text="Use for Local Inference", 
                      command=self.save_local).pack(side="right")
        
        # Load cached models
        self.refresh_local_cache()

    def open_download_manager(self):
        """Opens a separate dialog for browsing and downloading models."""
        DownloadManagerDialog(self, self.session)

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
            font=("Courier New", 12), # Using monospace for column-like look
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
        self.local_model_var.set(model_id)

    def delete_cached_model(self, model_id):
        """Delete a cached model from disk."""
        # Simple confirmation using tkinter.messagebox if available, or just delete for now
        import tkinter.messagebox as mb
        if mb.askyesno("Confirm Delete", f"Are you sure you want to delete {model_id} from local cache?\nThis will free up disk space."):
            try:
                from src.core import huggingface_utils
                import shutil
                import os
                
                path = huggingface_utils.get_model_cache_dir(model_id)
                if os.path.exists(path):
                    shutil.rmtree(path)
                    print(f"Deleted model directory: {path}")
                
                self.refresh_local_cache()
            except Exception as e:
                mb.showerror("Error", f"Failed to delete model: {e}")

    def save_local(self):
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
                print(f"Setting task for {self.session.engine.model_id} to {self.session.engine.task}")
        except:
            pass
        self.destroy()

    def validate_model_id(self, model_id, provider):
        """Basic validation to prevent using OR models with HF engine and vice versa."""
        if provider == "huggingface":
            if ":" in model_id and not "/" in model_id.split(":")[0]:
                # Looks like 'google/gemini...:free' or similar
                import tkinter.messagebox as mb
                return mb.askyesno("Potential Error", 
                                  f"The model ID '{model_id}' looks like it might be an OpenRouter model.\n\n"
                                  "Are you sure you want to use it with the Hugging Face engine?")
        elif provider == "openrouter":
            if "/" in model_id and ":" not in model_id:
                # Looks like 'org/model' without a suffix, which is common for HF
                # OpenRouter also uses org/model but often has suffixes or specific names
                pass
        return True

    def init_hf_tab(self):
        self.tab_hf.grid_columnconfigure(0, weight=1)
        self.tab_hf.grid_rowconfigure(4, weight=1)  # List area grows

        # API Key
        row1 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(row1, text="API Key:").pack(side="left")
        self.hf_key = ctk.CTkEntry(row1, width=250, show="*")
        self.hf_key.insert(0, self.session.engine.api_key or "")
        self.hf_key.pack(side="left", padx=10, fill="x", expand=True)

        # Rate Limit Warning Banner
        warning_frame = ctk.CTkFrame(self.tab_hf, fg_color="#FF6B35", corner_radius=8)
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

        # Search Tools (Mirroring OR style)
        row3 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row3.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self.hf_search = ctk.CTkEntry(row3, placeholder_text="Search multi-modal models (e.g. 'blip', 'vit-gpt2')...")
        self.hf_search.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.hf_search.bind("<Return>", lambda e: self.search_hf_online())
        ctk.CTkButton(row3, text="Search Hub", width=100, command=self.search_hf_online).pack(side="left")

        # List
        self.hf_list = ctk.CTkScrollableFrame(self.tab_hf, label_text="Recommended Multi-modal Models")
        self.hf_list.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)

        # Add header
        header_text = f"{'Model ID':<40} | {'Capability':^15} | {'Size':>10}"
        self.hf_list_header = ctk.CTkLabel(
            self.hf_list, 
            text=header_text, 
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        )
        self.hf_list_header.pack(fill="x", pady=(5, 10), padx=5)

        # Selection
        row4 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row4.grid(row=4, column=0, sticky="ew", padx=10, pady=(10,20))
        
        ctk.CTkLabel(row4, text="Selected:").pack(side="left")
        self.hf_model = ctk.CTkEntry(row4, width=250)
        self.hf_model.insert(0, self.session.engine.model_id or "Salesforce/blip-image-captioning-base")
        self.hf_model.pack(side="left", padx=10, fill="x", expand=True)
        
        btn_save_config = ctk.CTkButton(row4, text="Save Config", width=100, command=self.save_hf)
        btn_save_config.pack(side="right", padx=5)
        
        btn_download = ctk.CTkButton(row4, text="Download for Local Use", width=150, fg_color="#2FA572", command=self.download_selected_hf_for_local)
        btn_download.pack(side="right", padx=5)

    def download_selected_hf_for_local(self):
        model_id = self.hf_model.get()
        if not model_id: return
        
        # Open download manager directly for this model
        dm = DownloadManagerDialog(self, self.session)
        dm.search_entry.delete(0, "end")
        dm.search_entry.insert(0, model_id)
        dm.start_search()

    def search_hf_online(self):
        query = self.hf_search.get()
        # Clear list
        for w in self.hf_list.winfo_children(): w.destroy()
        ctk.CTkLabel(self.hf_list, text="Searching Hub...", text_color="gray").pack(pady=10)
        
        def worker():
            try:
                from huggingface_hub import list_models
                from src.core import huggingface_utils, config
                
                tasks = [
                    config.MODEL_TASK_IMAGE_CLASSIFICATION,
                    config.MODEL_TASK_IMAGE_TO_TEXT,
                    config.MODEL_TASK_ZERO_SHOT,
                    "visual-question-answering",
                    "image-text-to-text"
                ]
                
                all_results = []
                for t in tasks:
                    models = list_models(filter=t, search=query, limit=5, sort="downloads", direction=-1)
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
                
                # Fetch sizes
                results_with_details = []
                for item in unique_results:
                    mid = item['id']
                    size_bytes = huggingface_utils.get_remote_model_size(mid)
                    item['size_str'] = huggingface_utils.format_size(size_bytes)
                    results_with_details.append(item)

                self.after(0, lambda: self.show_hf_results(results_with_details))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self.show_hf_results([], error=error_msg))
        
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def show_hf_results(self, results, error=None):
        for w in self.hf_list.winfo_children(): w.destroy()
        
        # Re-add header
        header_text = f"{'Model ID':<40} | {'Capability':^15} | {'Size':>10}"
        ctk.CTkLabel(self.hf_list, text=header_text, font=("Courier New", 12, "bold"), text_color="gray", anchor="w").pack(fill="x", pady=(5, 10), padx=5)

        if error:
            ctk.CTkLabel(self.hf_list, text=f"Error: {error}", text_color="red").pack()
            return

        if not results:
            ctk.CTkLabel(self.hf_list, text="No models found.").pack()
            return

        for item in results:
            mid = item['id']
            size_str = item.get('size_str', 'Unknown')
            capability = item.get('capability', 'Unknown')
            
            display_text = f"{mid:<40} | {capability:^15} | {size_str:>10}"
            
            btn = ctk.CTkButton(
                self.hf_list, 
                text=display_text, 
                font=("Courier New", 12),
                fg_color="transparent", 
                border_width=1, 
                anchor="w", 
                command=lambda m=mid: self.select_hf_model(m)
            )
            btn.pack(fill="x", pady=2)

    def select_hf_model(self, mid):
        self.hf_model.delete(0, "end")
        self.hf_model.insert(0, mid)

    def init_or_tab(self):
        self.tab_or.grid_columnconfigure(0, weight=1)
        self.tab_or.grid_rowconfigure(2, weight=1)

        # API Key
        row1 = ctk.CTkFrame(self.tab_or, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(row1, text="API Key:").pack(side="left")
        self.or_key = ctk.CTkEntry(row1, width=250, show="*")
        self.or_key.insert(0, self.session.engine.api_key or "")
        self.or_key.pack(side="left", padx=10, fill="x", expand=True)
        
        # Tools
        row2 = ctk.CTkFrame(self.tab_or, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkButton(row2, text="Fetch Available Models", command=self.fetch_or_models).pack(side="left")
        
        # List
        self.or_list = ctk.CTkScrollableFrame(self.tab_or, label_text="OpenRouter Vision Models")
        self.or_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Selection
        row4 = ctk.CTkFrame(self.tab_or, fg_color="transparent")
        row4.grid(row=3, column=0, sticky="ew", padx=10, pady=(5,20))
        ctk.CTkLabel(row4, text="Selected:").pack(side="left")
        self.or_model = ctk.CTkEntry(row4, width=300)
        self.or_model.insert(0, self.session.engine.model_id or "openai/gpt-4-vision-preview")
        self.or_model.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(row4, text="Save Config", command=self.save_or).pack(side="right")

    def fetch_or_models(self):
        for w in self.or_list.winfo_children(): w.destroy()
        ctk.CTkLabel(self.or_list, text="Fetching...", text_color="gray").pack()
        
        def worker():
            try:
                from src.core import openrouter_utils
                # We can't really filter by 'task' in the same way, but OR utils handles 'image' modality check
                models, _ = openrouter_utils.find_models_by_task("image-to-text", limit=100)
                self.after(0, lambda: self.show_or_results(models))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self.show_or_results([], error=error_msg))
                
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def show_or_results(self, results, error=None):
        for w in self.or_list.winfo_children(): w.destroy()
        if error:
            ctk.CTkLabel(self.or_list, text=f"Error: {error}\n(Check internet?)", text_color="red").pack()
            return
        
        if not results:
            ctk.CTkLabel(self.or_list, text="No generic vision models found.").pack()
            return
            
        for mid in results:
             btn = ctk.CTkButton(self.or_list, text=mid, fg_color="transparent", border_width=1, 
                                anchor="w", command=lambda m=mid: self.select_or_model(m))
             btn.pack(fill="x", pady=2)

    def select_or_model(self, mid):
        self.or_model.delete(0, "end")
        self.or_model.insert(0, mid)

    def save_hf(self):
        model_id = self.hf_model.get()
        if not self.validate_model_id(model_id, "huggingface"):
            return

        self.session.engine.provider = "huggingface"
        self.session.engine.api_key = self.hf_key.get().strip()
        self.session.engine.model_id = model_id
        
        # Try to infer task or default to image-to-text for multi-modal
        # Classification models often have 'vit', 'resnet', 'siglip' but no 'caption' or 'desc'
        if any(x in model_id.lower() for x in ["vit-base-patch", "resnet-", "siglip-", "bits-"]):
             self.session.engine.task = "image-classification"
        else:
             self.session.engine.task = "image-to-text"
             
        self.destroy()

    def save_or(self):
        model_id = self.or_model.get()
        if not self.validate_model_id(model_id, "openrouter"):
            return

        self.session.engine.provider = "openrouter"
        self.session.engine.api_key = self.or_key.get().strip()
        self.session.engine.model_id = model_id
        # OpenRouter is primarily chat/generation -> image-to-text task in our logical mapping
        # But could be zero-shot if we prompt it right. For now, default to image-to-text (captioning/describe)
        self.session.engine.task = "image-to-text" 
        self.destroy()

class DownloadManagerDialog(ctk.CTkToplevel):
    """Separate dialog for browsing Hub and downloading models."""
    
    def __init__(self, parent, session):
        super().__init__(parent)
        self.parent = parent
        self.session = session
        self.title("Download Models from Hugging Face Hub")
        self.geometry("800x600")
        
        # Make the dialog modal or at least ensuring it stays on top
        self.transient(parent)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Search header
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Task dropdown removed to simplify for average user - focusing on multi-modal
        self.task_var = ctk.StringVar(value="image-to-text")
        
        self.search_entry = ctk.CTkEntry(header, placeholder_text="Search multi-modal models (e.g. 'blip', 'vit', 'qwen')...", width=350)
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda e: self.start_search())
        
        ctk.CTkButton(header, text="Search Hub", command=self.start_search, width=120).pack(side="left", padx=5)

        # Results area
        self.results_frame = ctk.CTkScrollableFrame(self, label_text="Hugging Face Hub Results")
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Add a header label
        header_text = f"{'Model ID':<40} | {'Capability':^15} | {'Size':>10}"
        self.results_header = ctk.CTkLabel(
            self.results_frame, 
            text=header_text, 
            font=("Courier New", 12, "bold"),
            text_color="gray",
            anchor="w"
        )
        self.results_header.pack(fill="x", pady=(5, 10), padx=5)
        
        # Status footer
        self.footer = ctk.CTkFrame(self)
        self.footer.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        self.lbl_status = ctk.CTkLabel(self.footer, text="Enter a query and click Search", text_color="gray")
        self.lbl_status.pack(side="left", padx=5)
        
        self.progress = ctk.CTkProgressBar(self.footer)
        self.progress.pack(side="right", padx=10, fill="x", expand=True)
        self.progress.set(0)

    def start_search(self):
        query = self.search_entry.get()
        task = self.task_var.get()
        self.lbl_status.configure(text=f"Searching Hub for '{task}'...")
        
        # Clear results
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        
        import threading
        threading.Thread(target=self._search_worker, args=(query, task), daemon=True).start()

    def _search_worker(self, query, task):
        try:
            from huggingface_hub import list_models
            from src.core import huggingface_utils, config
            
            # search across all relevant image tasks to be helpful
            tasks = [
                config.MODEL_TASK_IMAGE_CLASSIFICATION,
                config.MODEL_TASK_IMAGE_TO_TEXT,
                config.MODEL_TASK_ZERO_SHOT,
                "visual-question-answering",
                "image-text-to-text"
            ]
            
            all_results = []
            for t in tasks:
                models = list_models(filter=t, search=query, limit=10, sort="downloads", direction=-1)
                for m in models:
                    all_results.append({
                        'id': m.id,
                        'task': t,
                        'capability': huggingface_utils.get_model_capability(t)
                    })
            
            # Deduplicate by ID, keeping the first task found
            seen = set()
            unique_results = []
            for r in all_results:
                if r['id'] not in seen:
                    unique_results.append(r)
                    seen.add(r['id'])
            
            # Fetch sizes concurrently to avoid UI lag
            from concurrent.futures import ThreadPoolExecutor
            
            def fetch_size(item):
                mid = item['id']
                try:
                    size_bytes = huggingface_utils.get_remote_model_size(mid)
                    item['size_str'] = huggingface_utils.format_size(size_bytes)
                except Exception:
                    item['size_str'] = "Unknown"
                return item

            with ThreadPoolExecutor(max_workers=5) as executor:
                results_with_details = list(executor.map(fetch_size, unique_results))

            self.after(0, lambda: self.show_search_results(results_with_details))
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self.lbl_status.configure(text=f"Error: {error_msg}", text_color="red"))

    def show_search_results(self, results):
        self.lbl_status.configure(text=f"Found {len(results)} models.", text_color="gray")
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        # Re-add header
        header_text = f"{'Model ID':<40} | {'Capability':^15} | {'Size':>10}"
        ctk.CTkLabel(self.results_frame, text=header_text, font=("Courier New", 12, "bold"), text_color="gray", anchor="w").pack(fill="x", pady=(5, 10), padx=5)

        if not results:
             ctk.CTkLabel(self.results_frame, text="No models found matching your query.", text_color="gray").pack(pady=20)
             return
             
        for item in results:
            self.add_result_item(item['id'], item['size_str'], item['capability'])

    def add_result_item(self, model_id, size_str, capability):
        frame = ctk.CTkFrame(self.results_frame)
        frame.pack(fill="x", pady=2, padx=5)
        
        # Consistent column-like look
        display_text = f"{model_id:<40} | {capability:^15} | {size_str:>10}"
        
        ctk.CTkLabel(
            frame, 
            text=display_text, 
            font=("Courier New", 12), 
            anchor="w"
        ).pack(side="left", padx=10, fill="x", expand=True)
        
        # Buttons
        btn_test = ctk.CTkButton(frame, text="Test via API", width=100, fg_color="#3B8ED0", 
                                 command=lambda m=model_id: self.test_via_api(m))
        btn_test.pack(side="right", padx=5)
        
        btn_download = ctk.CTkButton(frame, text="Download", width=100, fg_color="#2FA572",
                                     command=lambda m=model_id: self.start_download(m))
        btn_download.pack(side="right", padx=5)

    def test_via_api(self, model_id):
        # Switch to HF tab in parent and select model
        self.parent.tabview.set("Hugging Face")
        self.parent.hf_model.delete(0, "end")
        self.parent.hf_model.insert(0, model_id)
        # self.parent.hf_task_var.set(self.task_var.get()) # Task var removed from HF tab
        self.lbl_status.configure(text=f"Selected {model_id} for API testing. Switch to 'Hugging Face' tab.")
        # Optional: focus parent
        self.parent.focus_set()

    def start_download(self, model_id):
        self.lbl_status.configure(text=f"Downloading {model_id}...", text_color="gray")
        self.progress.set(0)
        
        import queue
        from src.core import huggingface_utils
        
        self.download_queue = queue.Queue()
        import threading
        threading.Thread(
            target=huggingface_utils.download_model_worker, 
            args=(model_id, self.download_queue), 
            daemon=True
        ).start()
        
        self.poll_download_queue()

    def poll_download_queue(self):
        try:
            while True:
                msg_type, data = self.download_queue.get_nowait()
                
                if msg_type == "model_download_progress":
                    downloaded, total = data
                    if total > 0:
                        self.progress.set(downloaded / total)
                        # Optional: Update status with %
                        # self.lbl_status.configure(text=f"Downloading... {downloaded/total*100:.1f}%")
                
                elif msg_type == "status_update":
                    self.lbl_status.configure(text=data, text_color="gray")
                
                elif msg_type == "download_complete":
                    self.on_download_complete(data)
                    return # Stop polling
                
                elif msg_type == "error":
                    self.lbl_status.configure(text=f"Download failed: {data}", text_color="red")
                    return # Stop polling
                    
        except queue.Empty:
            # Continue polling if not closed
            if self.winfo_exists():
                self.after(100, self.poll_download_queue)

    def on_download_complete(self, model_id):
        self.lbl_status.configure(text=f"Download complete: {model_id}!", text_color="green")
        self.progress.set(1.0)
        # Refresh parent cache
        self.parent.refresh_local_cache()
