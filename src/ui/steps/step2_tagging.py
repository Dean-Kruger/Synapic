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

        # Configure Button
        self.btn_config = ctk.CTkButton(self.container, text="Configure Selected Engine", command=self.open_config_dialog, width=250)
        self.btn_config.grid(row=2, column=0, pady=30)
        
        # Navigation Buttons
        nav_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        nav_frame.grid(row=3, column=0, pady=20, sticky="ew")
        
        ctk.CTkButton(nav_frame, text="Previous", command=lambda: self.controller.show_step("Step1Datasource"), width=150, fg_color="gray").pack(side="left", padx=20)
        ctk.CTkButton(nav_frame, text="Next Step", command=self.next_step, width=200, height=40).pack(side="right", padx=20)

    def create_engine_card(self, parent, text, value, col):
        card = ctk.CTkRadioButton(parent, text=text, variable=self.engine_var, value=value, font=("Roboto", 16))
        card.grid(row=0, column=col, padx=20, pady=20)
        
    def open_config_dialog(self):
        engine = self.engine_var.get()
        # Pass session to dialog
        dialog = ConfigDialog(self, self.controller.session, initial_tab=engine)
        
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


class ConfigDialog(ctk.CTkToplevel):
    def __init__(self, parent, session, initial_tab="huggingface"):
        super().__init__(parent)
        self.session = session
        self.title("Engine Configuration")
        self.geometry("600x500")
        
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
        
        ctk.CTkButton(header, text="+ Download New Model", 
                      command=self.open_download_manager, 
                      width=150).pack(side="right", padx=5)

        # List of cached models ONLY
        self.local_list_frame = ctk.CTkScrollableFrame(
            self.tab_local, 
            label_text="Ready for Local Inference"
        )
        self.local_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
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
                    text="No models downloaded yet.\nClick '+ Download New Model' to browse the Hub.",
                    text_color="gray",
                    justify="center"
                ).pack(pady=20)
                self.cache_count_label.configure(text="(0 models)")
            else:
                self.cache_count_label.configure(text=f"({len(all_local)} models)")
                
                for model_id in all_local.keys():
                    self.add_cached_model_item(model_id)
                    
        except Exception as e:
            ctk.CTkLabel(
                self.local_list_frame, 
                text=f"Error scanning cache: {e}",
                text_color="red"
            ).pack()

    def add_cached_model_item(self, model_id):
        """Add a cached model to the list."""
        frame = ctk.CTkFrame(self.local_list_frame)
        frame.pack(fill="x", pady=2)
        
        btn = ctk.CTkButton(
            frame, 
            text=f"✓ {model_id}", 
            fg_color="transparent", 
            border_width=1,
            text_color="green",
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
                self.session.engine.task = model_info['config'].get("pipeline_tag", "image-classification")
        except:
            pass
        self.destroy()

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
            text="⚡ API Test Mode: Free tier has rate limits (~15 req/hour). Test models before downloading for local use.",
            wraplength=500,
            font=("Roboto", 11)
        )
        warning_text.pack(side="left", padx=5, pady=8)

        # Task Selection
        row2 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row2.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(row2, text="Task:").pack(side="left")
        self.hf_task_var = ctk.StringVar(value=self.session.engine.task or "image-classification")
        self.hf_task_menu = ctk.CTkOptionMenu(row2, variable=self.hf_task_var, 
                                           values=["image-classification", "image-to-text", "zero-shot-image-classification"],
                                           width=200)
        self.hf_task_menu.pack(side="left", padx=10)
        
        # Search
        row3 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row3.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.hf_search = ctk.CTkEntry(row3, placeholder_text="Search generic models...")
        self.hf_search.pack(side="left", fill="x", expand=True, padx=(0,5))
        ctk.CTkButton(row3, text="Search", width=80, command=self.search_hf_online).pack(side="left")

        # List
        self.hf_list = ctk.CTkScrollableFrame(self.tab_hf, label_text="Recommended Models (Sorted by Downloads)")
        self.hf_list.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)

        # Selection
        row4 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row4.grid(row=5, column=0, sticky="ew", padx=10, pady=(5,20))
        ctk.CTkLabel(row4, text="Selected:").pack(side="left")
        self.hf_model = ctk.CTkEntry(row4, width=300)
        self.hf_model.insert(0, self.session.engine.model_id or "google/vit-base-patch16-224")
        self.hf_model.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(row4, text="Save Config", command=self.save_hf).pack(side="right")

    def search_hf_online(self):
        query = self.hf_search.get()
        task = self.hf_task_var.get()
        
        # Clear list
        for w in self.hf_list.winfo_children(): w.destroy()
        ctk.CTkLabel(self.hf_list, text="Searching...", text_color="gray").pack()
        
        def worker():
            try:
                from huggingface_hub import list_models
                # Filter strictly by task
                models = list_models(filter=task, search=query, limit=15, sort="downloads", direction=-1)
                results = [m.id for m in models]
                self.after(0, lambda: self.show_hf_results(results))
            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self.show_hf_results([], error=error_msg))
        
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def show_hf_results(self, results, error=None):
        for w in self.hf_list.winfo_children(): w.destroy()
        
        if error:
            ctk.CTkLabel(self.hf_list, text=f"Error: {error}", text_color="red").pack()
            return

        if not results:
            ctk.CTkLabel(self.hf_list, text="No models found.").pack()
            return

        for mid in results:
            btn = ctk.CTkButton(self.hf_list, text=mid, fg_color="transparent", border_width=1, 
                                anchor="w", command=lambda m=mid: self.select_hf_model(m))
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
        self.session.engine.provider = "huggingface"
        self.session.engine.api_key = self.hf_key.get()
        self.session.engine.model_id = self.hf_model.get()
        self.session.engine.task = self.hf_task_var.get()
        self.destroy()

    def save_or(self):
        self.session.engine.provider = "openrouter"
        self.session.engine.api_key = self.or_key.get()
        self.session.engine.model_id = self.or_model.get()
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
        
        ctk.CTkLabel(header, text="Task:").pack(side="left", padx=5)
        self.task_var = ctk.StringVar(value="image-classification")
        self.task_menu = ctk.CTkOptionMenu(header, variable=self.task_var, 
                                           values=["image-classification", "image-to-text", "zero-shot-image-classification"],
                                           width=180)
        self.task_menu.pack(side="left", padx=5)
        
        self.search_entry = ctk.CTkEntry(header, placeholder_text="Search models (e.g. 'vit', 'blip')...", width=300)
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda e: self.start_search())
        
        ctk.CTkButton(header, text="Search Hub", command=self.start_search, width=100).pack(side="left", padx=5)

        # Results area
        self.results_frame = ctk.CTkScrollableFrame(self, label_text="Hugging Face Hub Results")
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
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
            models = list_models(filter=task, search=query, limit=15, sort="downloads", direction=-1)
            results = [m.id for m in models]
            self.after(0, lambda: self.show_search_results(results))
        except Exception as e:
            self.after(0, lambda: self.lbl_status.configure(text=f"Error: {e}", text_color="red"))

    def show_search_results(self, results):
        self.lbl_status.configure(text=f"Found {len(results)} models.", text_color="gray")
        if not results:
             ctk.CTkLabel(self.results_frame, text="No models found matching your query.", text_color="gray").pack(pady=20)
             return
             
        for mid in results:
            self.add_result_item(mid)

    def add_result_item(self, model_id):
        frame = ctk.CTkFrame(self.results_frame)
        frame.pack(fill="x", pady=5, padx=5)
        
        ctk.CTkLabel(frame, text=model_id, font=("Roboto", 12, "bold"), anchor="w").pack(side="left", padx=10, fill="x", expand=True)
        
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
        self.parent.hf_task_var.set(self.task_var.get())
        self.lbl_status.configure(text=f"Selected {model_id} for API testing. Switch to 'Hugging Face' tab.")
        # Optional: focus parent
        self.parent.focus_set()

    def start_download(self, model_id):
        self.lbl_status.configure(text=f"Downloading {model_id}...", text_color="gray")
        self.progress.set(0)
        import threading
        threading.Thread(target=self._download_worker, args=(model_id,), daemon=True).start()

    def _download_worker(self, model_id):
        try:
            from huggingface_hub import snapshot_download
            # In a real app, we'd want to track progress better, but let's keep it simple for now
            snapshot_download(repo_id=model_id)
            self.after(0, lambda: self.on_download_complete(model_id))
        except Exception as e:
            self.after(0, lambda: self.lbl_status.configure(text=f"Download failed: {e}", text_color="red"))

    def on_download_complete(self, model_id):
        self.lbl_status.configure(text=f"Download complete: {model_id}!", text_color="green")
        self.progress.set(1.0)
        # Refresh parent cache
        self.parent.refresh_local_cache()
