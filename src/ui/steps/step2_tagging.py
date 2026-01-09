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
        self.engine_var = ctk.StringVar(value="huggingface")
        
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
        ctk.CTkLabel(self.tab_local, text="Available Models:").pack(pady=10)
        # TODO: Listbox or OptionMenu for models
        ctk.CTkOptionMenu(self.tab_local, values=["vit-base-patch16-224", "resnet-50"]).pack(pady=10)
        ctk.CTkButton(self.tab_local, text="Download / Load", command=lambda: print("Load Model")).pack(pady=10)
        ctk.CTkLabel(self.tab_local, text="Status: Not Loaded", text_color="orange").pack(pady=20)

    def init_hf_tab(self):
        ctk.CTkLabel(self.tab_hf, text="API Key:").pack(pady=(20,5), anchor="w", padx=20)
        self.hf_key = ctk.CTkEntry(self.tab_hf, width=400, show="*")
        self.hf_key.pack(padx=20)
        
        ctk.CTkLabel(self.tab_hf, text="Model ID:").pack(pady=(20,5), anchor="w", padx=20)
        self.hf_model = ctk.CTkEntry(self.tab_hf, width=400)
        self.hf_model.insert(0, "google/vit-base-patch16-224")
        self.hf_model.pack(padx=20)
        
        ctk.CTkButton(self.tab_hf, text="Verify Key", command=lambda: print("Verify HF")).pack(pady=30)

    def init_or_tab(self):
        ctk.CTkLabel(self.tab_or, text="API Key:").pack(pady=(20,5), anchor="w", padx=20)
        self.or_key = ctk.CTkEntry(self.tab_or, width=400, show="*")
        self.or_key.pack(padx=20)
        
        ctk.CTkLabel(self.tab_or, text="Model ID:").pack(pady=(20,5), anchor="w", padx=20)
        self.or_model = ctk.CTkEntry(self.tab_or, width=400)
        self.or_model.pack(padx=20)
        
        ctk.CTkLabel(self.tab_or, text="System Prompt:").pack(pady=(20,5), anchor="w", padx=20)
        self.or_prompt = ctk.CTkTextbox(self.tab_or, height=100)
        self.or_prompt.pack(padx=20, fill="x")
