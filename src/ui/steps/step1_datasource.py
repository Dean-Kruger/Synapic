import customtkinter as ctk

class Step1Datasource(ctk.CTkFrame):
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
        title = ctk.CTkLabel(self.container, text="Step 1: Datasource", font=("Roboto", 24, "bold"))
        title.grid(row=0, column=0, pady=(20, 30))

        # Source Selection (Radio Buttons)
        self.source_var = ctk.StringVar(value="local")
        self.rb_frame = ctk.CTkFrame(self.container)
        self.rb_frame.grid(row=1, column=0, pady=10)
        
        r1 = ctk.CTkRadioButton(self.rb_frame, text="Local Folder", variable=self.source_var, value="local", command=self.toggle_source_view)
        r1.pack(side="left", padx=20, pady=10)
        
        r2 = ctk.CTkRadioButton(self.rb_frame, text="Daminion Server", variable=self.source_var, value="daminion", command=self.toggle_source_view)
        r2.pack(side="left", padx=20, pady=10)

        # Content Area (Dynamic)
        self.content_area = ctk.CTkFrame(self.container, fg_color="transparent")
        self.content_area.grid(row=2, column=0, sticky="nsew", pady=20, padx=20)
        
        # Initialize Frames
        self.init_local_frame()
        self.init_daminion_frame()
        
        # Show default
        self.toggle_source_view()

        # Navigation Buttons
        nav_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        nav_frame.grid(row=3, column=0, pady=20, sticky="ew")
        
        ctk.CTkButton(nav_frame, text="Next Step", command=self.next_step, width=200, height=40).pack(pady=10)

    def init_local_frame(self):
        self.local_frame = ctk.CTkFrame(self.content_area)
        
        # Folder Selection
        ctk.CTkLabel(self.local_frame, text="Select Image Folder:", font=("Roboto", 16)).pack(anchor="w", pady=(10, 5), padx=20)
        
        path_frame = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=20)
        
        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="No folder selected...")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(path_frame, text="Browse", width=100, command=self.browse_folder).pack(side="right")
        
        # File Filters
        ctk.CTkLabel(self.local_frame, text="File Types:", font=("Roboto", 16)).pack(anchor="w", pady=(20, 5), padx=20)
        
        filter_frame = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20)
        
        self.chk_jpg = ctk.CTkCheckBox(filter_frame, text="JPG/JPEG")
        self.chk_jpg.select()
        self.chk_jpg.pack(side="left", padx=(0, 20))
        
        self.chk_png = ctk.CTkCheckBox(filter_frame, text="PNG")
        self.chk_png.select()
        self.chk_png.pack(side="left", padx=20)
        
        self.chk_tiff = ctk.CTkCheckBox(filter_frame, text="TIFF/TIF")
        self.chk_tiff.pack(side="left", padx=20)

    def init_daminion_frame(self):
        self.daminion_frame = ctk.CTkFrame(self.content_area)
        
        # Connection Config
        grid_kws = {"padx": 20, "pady": 10, "sticky": "ew"}
        self.daminion_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.daminion_frame, text="Host URL:").grid(row=0, column=0, **grid_kws)
        self.entry_host = ctk.CTkEntry(self.daminion_frame, placeholder_text="http://localhost:8080")
        self.entry_host.grid(row=0, column=1, **grid_kws)
        
        ctk.CTkLabel(self.daminion_frame, text="Username:").grid(row=1, column=0, **grid_kws)
        self.entry_user = ctk.CTkEntry(self.daminion_frame)
        self.entry_user.grid(row=1, column=1, **grid_kws)
        
        ctk.CTkLabel(self.daminion_frame, text="Password:").grid(row=2, column=0, **grid_kws)
        self.entry_pass = ctk.CTkEntry(self.daminion_frame, show="*")
        self.entry_pass.grid(row=2, column=1, **grid_kws)
        
        ctk.CTkButton(self.daminion_frame, text="Connect", fg_color="green", command=self.connect_daminion).grid(row=3, column=1, pady=20, sticky="e", padx=20)
        
        # Scope Selection (Hidden until connected)
        self.scope_frame = ctk.CTkFrame(self.daminion_frame)
        # Placeholder for post-connect UI
        ctk.CTkLabel(self.scope_frame, text="Catalog Scope (Connect first)", text_color="gray").pack(pady=20)
        self.scope_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=20, pady=10)

    def toggle_source_view(self):
        # Clear content area
        for widget in self.content_area.winfo_children():
            widget.pack_forget()
            
        if self.source_var.get() == "local":
            self.local_frame.pack(fill="both", expand=True)
        else:
            self.daminion_frame.pack(fill="both", expand=True)

    def browse_folder(self):
        directory = ctk.filedialog.askdirectory()
        if directory:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)

    def connect_daminion(self):
        host = self.entry_host.get()
        user = self.entry_user.get()
        pwd = self.entry_pass.get()
        
        if not host or not user:
            print("Error: detailed error handling to be added") 
            return

        # Update Session
        self.controller.session.datasource.type = "daminion"
        self.controller.session.datasource.daminion_url = host
        self.controller.session.datasource.daminion_user = user
        self.controller.session.datasource.daminion_pass = pwd
        
        # Connect
        success = self.controller.session.connect_daminion()
        if success:
            print("Connected!")
            # TODO: Show scopes
            for widget in self.scope_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.scope_frame, text="Connected!", text_color="green").pack()
            # In a real impl, we'd fetch catalogs here
        else:
            print("Failed to connect.")
            
    def next_step(self):
        # Save state
        mode = self.source_var.get()
        self.controller.session.datasource.type = mode
        
        if mode == "local":
            path = self.path_entry.get()
            if not path:
                # TODO: Alert
                print("Select a folder!")
                return
            self.controller.session.datasource.local_path = path
        
        # Proceed
        self.controller.show_step("Step2Tagging")
