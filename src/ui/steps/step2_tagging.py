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
        
        self.create_engine_card(self.cards_frame, "Local Model", "local", 0)
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
        
        self.tab_local = self.tabview.add("Local Model")
        self.tab_hf = self.tabview.add("Hugging Face")
        self.tab_or = self.tabview.add("OpenRouter")
        
        # Init Tabs
        self.init_local_tab()
        self.init_hf_tab()
        self.init_or_tab()
        
        # Select current
        map_name = {"local": "Local Model", "huggingface": "Hugging Face", "openrouter": "OpenRouter"}
        self.tabview.set(map_name.get(initial_tab, "Hugging Face"))

    def init_local_tab(self):
        self.tab_local.grid_columnconfigure(0, weight=1)
        self.tab_local.grid_rowconfigure(2, weight=1) # List area grows

        # 1. Pipeline/Task Selection
        row1 = ctk.CTkFrame(self.tab_local, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkLabel(row1, text="Task:").pack(side="left", padx=5)
        self.task_var = ctk.StringVar(value="image-classification")
        self.task_menu = ctk.CTkOptionMenu(row1, variable=self.task_var, 
                                           values=["image-classification", "image-to-text", "zero-shot-image-classification"],
                                           width=200, command=self.on_task_change)
        self.task_menu.pack(side="left", padx=5)

        # 2. Search
        row2 = ctk.CTkFrame(self.tab_local, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.search_entry = ctk.CTkEntry(row2, placeholder_text="Search generic models (e.g. 'vit', 'blip')...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkButton(row2, text="Search Hub", width=100, command=self.start_search).pack(side="left", padx=5)

        # 3. Results List
        self.list_frame = ctk.CTkScrollableFrame(self.tab_local, label_text="Hub Models")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        # 4. Status / Progress
        self.status_frame = ctk.CTkFrame(self.tab_local, fg_color="transparent")
        self.status_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        
        self.lbl_status = ctk.CTkLabel(self.status_frame, text="Ready", text_color="gray")
        self.lbl_status.pack(side="left")
        
        self.progress = ctk.CTkProgressBar(self.status_frame)
        self.progress.pack(side="right", fill="x", expand=True, padx=10)
        self.progress.set(0)

        # 5. Selection Info & Save
        row4 = ctk.CTkFrame(self.tab_local, fg_color="transparent")
        row4.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 20))
        
        ctk.CTkLabel(row4, text="Selected:").pack(side="left")
        self.local_model_var = ctk.StringVar(value=self.session.engine.model_id or "")
        self.lbl_selected = ctk.CTkLabel(row4, textvariable=self.local_model_var, font=("Roboto", 12, "bold"))
        self.lbl_selected.pack(side="left", padx=10)
        
        ctk.CTkButton(row4, text="Download & Save", command=self.download_and_save).pack(side="right")
        
        # Initial population of local cache
        self.refresh_local_list()

    def on_task_change(self, choice):
        self.refresh_local_list()

    def refresh_local_list(self):
        # List locally cached models for the selected task first
        for widget in self.list_frame.winfo_children():
            widget.destroy()
            
        task = self.task_var.get()
        try:
            from src.core import huggingface_utils
            models = huggingface_utils.find_local_models_by_task(task)
            
            if not models:
                 ctk.CTkLabel(self.list_frame, text="(No local models found for this task)", text_color="gray").pack()
            
            for mid in models:
                self.add_model_item(mid, is_local=True)
                
        except Exception as e:
            print(f"Error scanning local: {e}")

    def add_model_item(self, model_id, is_local=False):
        f = ctk.CTkFrame(self.list_frame)
        f.pack(fill="x", pady=2)
        
        # Color code local models
        color = "green" if is_local else "white"
        txt = f"{model_id} (Cached)" if is_local else model_id
        
        btn = ctk.CTkButton(f, text=txt, fg_color="transparent", border_width=1, 
                            text_color=color, anchor="w",
                            command=lambda m=model_id: self.select_model(m))
        btn.pack(fill="x")

    def select_model(self, model_id):
        self.local_model_var.set(model_id)

    def start_search(self):
        query = self.search_entry.get()
        task = self.task_var.get()
        self.lbl_status.configure(text=f"Searching Hub for '{task}'...")
        
        # Run in thread
        import threading
        threading.Thread(target=self._search_worker, args=(query, task), daemon=True).start()

    def _search_worker(self, query, task):
        try:
            from src.core import huggingface_utils
            # We use the sync helper for simplicity in this thread
            # Or rename the worker function in utils to be callable
            
            # Use the 'find_models_by_task' but filtering manually for query if needed
            # The utils function is generic.
            # Let's use the explicit list_models via utils
            pass # TODO: Import properly
            
            # For now, let's call the utility function directly if available or mock it
            # calling internal helper
            from huggingface_hub import list_models
            # Filter by task
            models = list_models(filter=task, search=query, limit=10, sort="downloads", direction=-1)
            results = [m.id for m in models]
            
            self.after(0, lambda: self.show_search_results(results))
            
        except Exception as e:
            self.after(0, lambda: self.lbl_status.configure(text=f"Error: {e}"))

    def show_search_results(self, results):
        self.lbl_status.configure(text=f"Found {len(results)} models.")
        # Clear list
        for widget in self.list_frame.winfo_children():
            widget.destroy()
            
        # Add results
        for mid in results:
            self.add_model_item(mid, is_local=False)

    def download_and_save(self):
        mid = self.local_model_var.get()
        if not mid:
            return
            
        self.lbl_status.configure(text=f"Downloading {mid}...")
        self.progress.set(0)
        self.btn_config.configure(state="disabled") # Lock UI
        
        import threading
        threading.Thread(target=self._download_worker, args=(mid,), daemon=True).start()

    def _download_worker(self, model_id):
        try:
            from src.core import huggingface_utils
            import queue
            q = queue.Queue()
            
            # We use the existing load logic which downloads if needed
            # But we don't want to load it into memory fully, just ensure it's cached.
            # snapshot_download is better.
            
            # Using the utils 'load_model_with_progress' logic but adapted:
            from huggingface_hub import snapshot_download
            
            snapshot_download(repo_id=model_id)
            
            self.after(0, self.on_download_complete)
            
        except Exception as e:
            self.after(0, lambda: self.lbl_status.configure(text=f"Download failed: {e}"))

    def on_download_complete(self):
        self.lbl_status.configure(text="Download Complete!")
        self.progress.set(1.0)
        self.save_local()

    def init_hf_tab(self):
        self.tab_hf.grid_columnconfigure(0, weight=1)
        self.tab_hf.grid_rowconfigure(3, weight=1)

        # API Key
        row1 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(row1, text="API Key:").pack(side="left")
        self.hf_key = ctk.CTkEntry(row1, width=250, show="*")
        self.hf_key.insert(0, self.session.engine.api_key or "")
        self.hf_key.pack(side="left", padx=10, fill="x", expand=True)

        # Task Selection
        row2 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(row2, text="Task:").pack(side="left")
        self.hf_task_var = ctk.StringVar(value=self.session.engine.task or "image-classification")
        self.hf_task_menu = ctk.CTkOptionMenu(row2, variable=self.hf_task_var, 
                                           values=["image-classification", "image-to-text", "zero-shot-image-classification"],
                                           width=200)
        self.hf_task_menu.pack(side="left", padx=10)
        
        # Search
        row3 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row3.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self.hf_search = ctk.CTkEntry(row3, placeholder_text="Search generic models...")
        self.hf_search.pack(side="left", fill="x", expand=True, padx=(0,5))
        ctk.CTkButton(row3, text="Search", width=80, command=self.search_hf_online).pack(side="left")

        # List
        self.hf_list = ctk.CTkScrollableFrame(self.tab_hf, label_text="Recommended Models (Sorted by Downloads)")
        self.hf_list.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)

        # Selection
        row4 = ctk.CTkFrame(self.tab_hf, fg_color="transparent")
        row4.grid(row=4, column=0, sticky="ew", padx=10, pady=(5,20))
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
                self.after(0, lambda: self.show_hf_results([], error=str(e)))
        
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
                self.after(0, lambda: self.show_or_results([], error=str(e)))
                
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
