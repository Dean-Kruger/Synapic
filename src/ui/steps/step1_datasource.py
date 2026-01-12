import customtkinter as ctk
import logging
from tkinter import messagebox

class Step1Datasource(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.logger = logging.getLogger(__name__)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(2, weight=1)

        # Title
        title = ctk.CTkLabel(self.container, text="Step 1: Datasource", font=("Roboto", 24, "bold"))
        title.grid(row=0, column=0, pady=(20, 30))

        # Source Selection (Radio Buttons)
        ds = self.controller.session.datasource
        self.source_var = ctk.StringVar(value=ds.type or "local")
        
        self.rb_frame = ctk.CTkFrame(self.container)
        self.rb_frame.grid(row=1, column=0, pady=10)
        
        r1 = ctk.CTkRadioButton(self.rb_frame, text="Local Folder", variable=self.source_var, value="local", command=self.toggle_source_view)
        r1.pack(side="left", padx=20, pady=10)
        
        r2 = ctk.CTkRadioButton(self.rb_frame, text="Daminion Server", variable=self.source_var, value="daminion", command=self.toggle_source_view)
        r2.pack(side="left", padx=20, pady=10)

        # Count Label (global for datasource)
        self.lbl_total_count = ctk.CTkLabel(self.container, text="", font=("Roboto", 14, "italic"), text_color="gray")
        self.lbl_total_count.grid(row=1, column=0, sticky="e", padx=40)

        # Content Area (Dynamic)
        self.canvas = ctk.CTkCanvas(self.container, bg="#2b2b2b", highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(self.container, orientation="vertical", command=self.canvas.yview)
        self.content_area = ctk.CTkFrame(self.canvas, fg_color="transparent")
        
        self.content_area.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.content_area, anchor="nw", width=700) # Fixed width for scrollable area
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.grid(row=2, column=0, sticky="nsew", pady=20, padx=(20, 5))
        self.scrollbar.grid(row=2, column=0, sticky="nse", pady=20, padx=(0, 20))
        
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
        ds = self.controller.session.datasource
        self.local_frame = ctk.CTkFrame(self.content_area)
        
        # Folder Selection
        ctk.CTkLabel(self.local_frame, text="Select Image Folder:", font=("Roboto", 16, "bold")).pack(anchor="w", pady=(10, 5), padx=20)
        
        path_frame = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=20)
        
        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="No folder selected...")
        if ds.local_path:
            self.path_entry.insert(0, ds.local_path)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(path_frame, text="Browse", width=100, command=self.browse_folder).pack(side="right")
        
        # Recursive Checkbox
        self.chk_recursive = ctk.CTkCheckBox(self.local_frame, text="Include subfolders (Recursive scan)")
        if ds.local_recursive:
            self.chk_recursive.select()
        self.chk_recursive.pack(anchor="w", padx=20, pady=10)
        
        # File Filters
        ctk.CTkLabel(self.local_frame, text="File Types:", font=("Roboto", 16, "bold")).pack(anchor="w", pady=(20, 5), padx=20)
        
        filter_frame = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.chk_jpg = ctk.CTkCheckBox(filter_frame, text="JPG/JPEG")
        self.chk_jpg.select()
        self.chk_jpg.pack(side="left", padx=(0, 20))
        
        self.chk_png = ctk.CTkCheckBox(filter_frame, text="PNG")
        self.chk_png.select()
        self.chk_png.pack(side="left", padx=20)
        
        self.chk_tiff = ctk.CTkCheckBox(filter_frame, text="TIFF/TIF")
        self.chk_tiff.pack(side="left", padx=20)

    def init_daminion_frame(self):
        ds = self.controller.session.datasource
        self.daminion_frame = ctk.CTkFrame(self.content_area)
        
        # 1. Connection Config Area
        grid_kws = {"padx": 20, "pady": 5, "sticky": "ew"}
        self.config_container = ctk.CTkFrame(self.daminion_frame)
        self.config_container.grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 15), sticky="ew")
        self.config_container.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.config_container, text="Daminion Server Configuration", font=("Roboto", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=(10, 15), padx=20, sticky="w")
        
        ctk.CTkLabel(self.config_container, text="Host URL:").grid(row=1, column=0, **grid_kws)
        self.entry_host = ctk.CTkEntry(self.config_container, placeholder_text="http://localhost:8080")
        if ds.daminion_url:
            self.entry_host.insert(0, ds.daminion_url)
        self.entry_host.grid(row=1, column=1, **grid_kws)
        
        ctk.CTkLabel(self.config_container, text="Username:").grid(row=2, column=0, **grid_kws)
        self.entry_user = ctk.CTkEntry(self.config_container)
        if ds.daminion_user:
            self.entry_user.insert(0, ds.daminion_user)
        self.entry_user.grid(row=2, column=1, **grid_kws)
        
        ctk.CTkLabel(self.config_container, text="Password:").grid(row=3, column=0, **grid_kws)
        self.entry_pass = ctk.CTkEntry(self.config_container, show="*")
        if ds.daminion_pass:
            self.entry_pass.insert(0, ds.daminion_pass)
        self.entry_pass.grid(row=3, column=1, **grid_kws)
        
        self.btn_connect = ctk.CTkButton(self.config_container, text="Connect", fg_color="green", command=self.connect_daminion)
        self.btn_connect.grid(row=4, column=1, pady=10, sticky="e", padx=20)

        # 2. Connection Status / Disconnect Area (Hidden by default)
        self.status_container = ctk.CTkFrame(self.daminion_frame, fg_color="transparent")
        # grid will be managed in toggle_config
        
        # 3. Advanced Filters Area
        self.filters_container = ctk.CTkFrame(self.daminion_frame, fg_color="transparent")
        self.filters_container.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(10, 20))
        self.filters_container.grid_columnconfigure(0, weight=1)
        
        if self.controller.session.daminion_client and self.controller.session.daminion_client.authenticated:
             self.show_connected_view()
        else:
             ctk.CTkLabel(self.filters_container, text="Connect to see filtering options", text_color="gray", font=("Roboto", 12, "italic")).pack(pady=20)

    def toggle_source_view(self):
        # Clear content area
        for widget in self.content_area.winfo_children():
            widget.pack_forget()
            
        if self.source_var.get() == "local":
            self.local_frame.pack(fill="both", expand=True)
            self.canvas.yview_moveto(0)
            self.controller.session.datasource.type = "local"
        else:
            self.daminion_frame.pack(fill="both", expand=True)
            self.canvas.yview_moveto(0)
            self.controller.session.datasource.type = "daminion"

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
            messagebox.showerror("Error", "Host URL and Username are required.")
            return

        self.btn_connect.configure(state="disabled", text="Connecting...")
        
        # Update Session
        ds = self.controller.session.datasource
        ds.daminion_url = host
        ds.daminion_user = user
        ds.daminion_pass = pwd
        ds.type = "daminion" # Ensure type is set explicitly before connecting
        
        def _bg_connect():
            success = self.controller.session.connect_daminion()
            self.after(0, lambda: self._on_connected(success))
            
        import threading
        threading.Thread(target=_bg_connect, daemon=True).start()

    def _on_connected(self, success):
        self.btn_connect.configure(state="normal", text="Connect")
        if success:
            self.show_connected_view()
        else:
            messagebox.showerror("Connection Failed", "Could not connect to Daminion server. Check URL and credentials.")

    def disconnect_daminion(self):
        self.controller.session.daminion_client = None
        self.status_container.grid_forget()
        self.config_container.grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 15), sticky="ew")
        
        # Clear filters
        for widget in self.filters_container.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.filters_container, text="Connect to see filtering options", text_color="gray", font=("Roboto", 12, "italic")).pack(pady=20)

    def show_connected_view(self):
        # Hide config
        self.config_container.grid_forget()
        
        # Show status/disconnect
        for widget in self.status_container.winfo_children():
            widget.destroy()
            
        self.status_container.grid(row=0, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
        
        status_frame = ctk.CTkFrame(self.status_container, fg_color="#1a1a1a")
        status_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(status_frame, text=f"Connected to Daminion as {self.entry_user.get()}", font=("Roboto", 14, "bold"), text_color="green").pack(side="left", padx=20, pady=10)
        ctk.CTkButton(status_frame, text="Disconnect", fg_color="#990000", hover_color="#660000", width=100, command=self.disconnect_daminion).pack(side="right", padx=20, pady=10)
        
        self.show_advanced_daminion_filters()

    def show_advanced_daminion_filters(self):
        # Clear container
        for widget in self.filters_container.winfo_children():
            widget.destroy()
            
        self.search_map = {}
        self.col_map = {}
        
        ds = self.controller.session.datasource
        client = self.controller.session.daminion_client
        
        # 1. Tabbed Target Scope
        self.tabview = ctk.CTkTabview(self.filters_container, height=150, command=self.update_count)
        self.tabview.pack(fill="x", padx=20, pady=10)
        
        self.tabview.add("All Items")
        self.tabview.add("Saved Searches")
        self.tabview.add("Shared Collections")

        # Map current scope to tab
        scope_map = {"all": "All Items", "saved_search": "Saved Searches", "collection": "Shared Collections"}
        current_tab = scope_map.get(ds.daminion_scope, "All Items")
        self.tabview.set(current_tab)

        # Content for All Items
        ctk.CTkLabel(self.tabview.tab("All Items"), text="Processing all items (limited to 100 for safety during full scan).", text_color="gray").pack(pady=20)


        # Content for Saved Searches
        try:
            searches = client.get_saved_searches()
            search_names = [s.get('value') or s.get('name') for s in searches] if searches else []
            self.search_map = {s.get('value') or s.get('name'): s.get('id') for s in searches} if searches else {}
            
            self.saved_search_var = ctk.StringVar(value=ds.daminion_saved_search or (search_names[0] if search_names else "None"))
            
            ss_frame = self.tabview.tab("Saved Searches")
            ctk.CTkLabel(ss_frame, text="Select Saved Search:").pack(pady=(10, 5))
            self.opt_search = ctk.CTkOptionMenu(ss_frame, variable=self.saved_search_var, values=search_names if search_names else ["No Saved Searches Found"], width=300, command=self.update_count)
            self.opt_search.pack(pady=10)
        except Exception as e:
            self.logger.error(f"Failed to fetch saved searches: {e}")
            ctk.CTkLabel(self.tabview.tab("Saved Searches"), text="Failed to load saved searches").pack()


        # Content for Shared Collections
        try:
            collections = client.get_shared_collections()
            col_names = [c.get('name') or c.get('title') for c in collections] if collections else []
            self.col_map = {c.get('name') or c.get('title'): c.get('code') or c.get('id') for c in collections} if collections else {}
            
            self.collection_var = ctk.StringVar(value=ds.daminion_catalog_id or (col_names[0] if col_names else "None"))
            
            sc_frame = self.tabview.tab("Shared Collections")
            ctk.CTkLabel(sc_frame, text="Select Shared Collection:").pack(pady=(10, 5))
            self.opt_col = ctk.CTkOptionMenu(sc_frame, variable=self.collection_var, values=col_names if col_names else ["No Collections Found"], width=300, command=self.update_count)
            self.opt_col.pack(pady=10)
        except Exception as e:
            self.logger.error(f"Failed to fetch collections: {e}")
            ctk.CTkLabel(self.tabview.tab("Shared Collections"), text="Failed to load shared collections").pack()


        # 3. Untagged Filters
        ctk.CTkLabel(self.filters_container, text="Target Only Untagged Fields:", font=("Roboto", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 5))
        
        untagged_frame = ctk.CTkFrame(self.filters_container, fg_color="transparent")
        untagged_frame.pack(fill="x", padx=20)
        
        self.chk_untagged_kws = ctk.CTkCheckBox(untagged_frame, text="Keywords", command=self.update_count)
        if ds.daminion_untagged_keywords: self.chk_untagged_kws.select()
        self.chk_untagged_kws.pack(side="left", padx=(0, 20))
        
        self.chk_untagged_cats = ctk.CTkCheckBox(untagged_frame, text="Categories", command=self.update_count)
        if ds.daminion_untagged_categories: self.chk_untagged_cats.select()
        self.chk_untagged_cats.pack(side="left", padx=20)
        
        self.chk_untagged_desc = ctk.CTkCheckBox(untagged_frame, text="Description", command=self.update_count)
        if ds.daminion_untagged_description: self.chk_untagged_desc.select()
        self.chk_untagged_desc.pack(side="left", padx=20)

        # 4. Filter by Status
        ctk.CTkLabel(self.filters_container, text="Filter by Status:", font=("Roboto", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 5))
        
        self.status_var = ctk.StringVar(value=ds.status_filter)
        status_frame = ctk.CTkFrame(self.filters_container, fg_color="transparent")
        status_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkRadioButton(status_frame, text="Any", variable=self.status_var, value="all", command=self.update_count).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(status_frame, text="Flagged", variable=self.status_var, value="approved", command=self.update_count).pack(side="left", padx=20)
        ctk.CTkRadioButton(status_frame, text="Rejected", variable=self.status_var, value="rejected", command=self.update_count).pack(side="left", padx=20)
        ctk.CTkRadioButton(status_frame, text="Unflagged", variable=self.status_var, value="unassigned", command=self.update_count).pack(side="left", padx=20)

        # Triger initial count
        self.update_count()


    def update_count(self, *args):
        if not self.controller.session.daminion_client or not self.controller.session.daminion_client.authenticated:
            self.lbl_total_count.configure(text="")
            return

        self.lbl_total_count.configure(text="Counting...")
        
        import threading
        def _bg_count():
            try:
                # 1. Gather state
                tab = self.tabview.get()
                tab_map = {"All Items": "all", "Saved Searches": "saved_search", "Shared Collections": "collection"}
                scope = tab_map[tab]
                
                status = self.status_var.get()
                
                untagged = []
                if hasattr(self, 'chk_untagged_kws'):
                    if self.chk_untagged_kws.get(): untagged.append("Keywords")
                if hasattr(self, 'chk_untagged_cats'):
                    if self.chk_untagged_cats.get(): untagged.append("Categories")
                if hasattr(self, 'chk_untagged_desc'):
                    if self.chk_untagged_desc.get(): untagged.append("Description")
                
                ss_id = None
                if scope == "saved_search" and hasattr(self, 'saved_search_var'):
                    ss_id = self.search_map.get(self.saved_search_var.get())
                
                col_id = None
                if scope == "collection" and hasattr(self, 'collection_var'):
                    col_id = self.col_map.get(self.collection_var.get())
                
                max_to_fetch = 100 if scope == "all" else None
                
                # Try efficient counting first
                count = self.controller.session.daminion_client.get_filtered_item_count(
                    scope=scope,
                    saved_search_id=ss_id,
                    collection_id=col_id,
                    untagged_fields=untagged,
                    status_filter=status
                )
                
                suffix = ""
                if count == -1:
                    # Fallback to fetching items with a cap to Estimate
                    limit_fallback = 100
                    items = self.controller.session.daminion_client.get_items_filtered(
                        scope=scope,
                        saved_search_id=ss_id,
                        collection_id=col_id,
                        untagged_fields=untagged,
                        status_filter=status,
                        max_items=limit_fallback
                    )
                    count = len(items)
                    if count >= limit_fallback:
                        suffix = "+"
                
                self.after(0, lambda: self.lbl_total_count.configure(text=f"Records: {count}{suffix}"))
            except Exception as e:
                self.logger.error(f"Count failed: {e}")
                self.after(0, lambda: self.lbl_total_count.configure(text="Count Error"))
        
        threading.Thread(target=_bg_count, daemon=True).start()

    def next_step(self):
        # Save state
        ds = self.controller.session.datasource
        mode = self.source_var.get()
        ds.type = mode
        
        if mode == "local":
            path = self.path_entry.get()
            if not path:
                messagebox.showwarning("Warning", "Please select a folder first.")
                return
            ds.local_path = path
            ds.local_recursive = self.chk_recursive.get()
        else:
            if not self.controller.session.daminion_client or not self.controller.session.daminion_client.authenticated:
                 messagebox.showwarning("Warning", "Please connect to Daminion first.")
                 return
                 
            # Save Daminion Filters
            tab = self.tabview.get()
            tab_map = {"All Items": "all", "Saved Searches": "saved_search", "Shared Collections": "collection"}
            ds.daminion_scope = tab_map[tab]
            
            ds.status_filter = self.status_var.get()
            ds.daminion_untagged_keywords = self.chk_untagged_kws.get()
            ds.daminion_untagged_categories = self.chk_untagged_cats.get()
            ds.daminion_untagged_description = self.chk_untagged_desc.get()
            
            # Map names back to IDs
            if ds.daminion_scope == "saved_search":
                 ds.daminion_saved_search = self.search_map.get(self.saved_search_var.get())
            elif ds.daminion_scope == "collection":
                 ds.daminion_catalog_id = self.col_map.get(self.collection_var.get())

        # Proceed
        self.controller.show_step("Step2Tagging")
