"""
Step 1: Datasource Selection UI
===============================

This module provides the interface for selecting the image source for the 
tagging process. It supports two primary modes:
1. Local Filesystem: Scanning directories with recursive support.
2. Daminion DAM: Connecting to a Daminion Server to process items within a 
   specific scope (Catalog, Collections, or Saved Searches).

The UI handles credentials storage, background connection validation, and 
real-time item counting based on applied filters.

Key Components:
---------------
- Source Selection: Radio buttons to toggle between Local and Daminion modes.
- Local Config: Path browser and recursive scanning options.
- Daminion Config: Server URL, credentials, and connection management.
- Scope Selector: Tabbed interface for Daminion-specific data scopes.
- Filtering: Status-based (Flagged, Rejected) and Metadata-based (Untagged) filters.

Author: Synapic Project
"""

import customtkinter as ctk
import logging
from tkinter import messagebox

class Step1Datasource(ctk.CTkFrame):
    """
    UI component for the first step of the tagging wizard.
    
    This frame allows users to:
    - Choose between 'Local Folder' and 'Daminion Server' as the data source.
    - Select a local directory and toggle recursive scanning.
    - Connect to and browse a Daminion catalog, including views for:
        - Catalog (filtered by keywords, status, etc.)
        - Shared Collections
        - Saved Searches
    - View item counts and status updates from the DAM.
    
    Attributes:
        controller: The main App instance managing the wizard flow.
        session: Global application state and configuration.
        logger: Logger instance for debugging and error reporting.
    """
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
        self.lbl_total_count.grid(row=1, column=0, sticky="e", padx=60)

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

        # Debounce timer for search
        self._debounce_timer = None
        self._current_total_count = 0

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
        """
        Initialize the Daminion Server configuration and filtering UI.
        
        This method builds the connection configuration area (URL/Credentials)
        and the placeholder for the scope filtering tabs.
        """
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
        """
        Switch between Local Folder and Daminion Server views.
        
        Updates the session datasource type and refreshes the displayed 
        configuration frame.
        """
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
        """
        Validate and initialize the Daminion Server connection.
        
        Displays immediate UI feedback and spawns a background thread to 
        perform the actual authentication to avoid UI freezing.
        """
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
        
        if not self.winfo_exists(): return
        
        def _bg_connect():
            success = self.controller.session.connect_daminion()
            if self.winfo_exists():
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
        
        self.show_simplified_daminion_filters()

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
        
        self.show_daminion_scope_selector()

    def show_daminion_scope_selector(self):
        """Shows scope selection (Tabs) and detailed filters for Daminion."""
        self.clear_container(self.filters_container)
        ds = self.controller.session.datasource

        ctk.CTkLabel(self.filters_container, text="Select Target Scope:", font=("Roboto", 18, "bold")).pack(anchor="w", padx=20, pady=(10, 0))
        
        self.tabs = ctk.CTkTabview(self.filters_container, height=150, command=self.update_count)
        self.tabs.pack(fill="x", padx=20, pady=(0, 10))
        
        self.tabs.add("Global Scan")
        self.tabs.add("Saved Searches")
        self.tabs.add("Shared Collections")
        self.tabs.add("Keyword Search")
        
        # Set default tab from session
        scope_map = {"all": "Global Scan", "saved_search": "Saved Searches", "collection": "Shared Collections", "search": "Keyword Search"}
        self.tabs.set(scope_map.get(ds.daminion_scope, "Global Scan"))

        # --- Tab 1: Global Scan (Status Filters) ---
        global_tab = self.tabs.tab("Global Scan")
        
        status_frame = ctk.CTkFrame(global_tab, fg_color="transparent")
        status_frame.pack(fill="x", padx=10, pady=10)

        self.status_var = ctk.StringVar(value=ds.status_filter or "all")
        
        options = [
            ("All Items", "all"),
            ("Flagged Only", "approved"),
            ("Rejected Only", "rejected"),
            ("Unflagged Only", "unassigned")
        ]
        
        for text, val in options:
            ctk.CTkRadioButton(status_frame, text=text, variable=self.status_var, value=val, 
                               command=self.update_count).pack(side="left", padx=(0, 20))

        # --- Tab 2: Saved Searches ---
        ss_tab = self.tabs.tab("Saved Searches")
        
        self.ss_var = ctk.StringVar(value="Select a saved search...")
        self.ss_dropdown = ctk.CTkOptionMenu(ss_tab, variable=self.ss_var, values=["Loading..."], command=self.update_count, width=400)
        self.ss_dropdown.pack(pady=20, padx=20)
        
        # --- Tab 3: Shared Collections ---
        col_tab = self.tabs.tab("Shared Collections")
        
        self.col_var = ctk.StringVar(value="Select a collection...")
        self.col_dropdown = ctk.CTkOptionMenu(col_tab, variable=self.col_var, values=["Loading..."], command=self.update_count, width=400)
        self.col_dropdown.pack(pady=20, padx=20)

        # --- Tab 4: Keyword Search ---
        search_tab = self.tabs.tab("Keyword Search")
        search_instr = ctk.CTkLabel(search_tab, text="Enter search term (searches across all fields):", font=("Roboto", 12))
        search_instr.pack(anchor="w", padx=20, pady=(10, 0))
        
        self.search_entry = ctk.CTkEntry(search_tab, placeholder_text="e.g. CTICC", width=400)
        if ds.daminion_search_term:
             self.search_entry.insert(0, ds.daminion_search_term)
        self.search_entry.pack(pady=10, padx=20)
        self.search_entry.bind("<KeyRelease>", self.update_count)

        # Metadata Condition (Untagged)
        self.metadata_frame = ctk.CTkFrame(self.filters_container)
        self.metadata_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.metadata_frame, text="Identify Untagged Items (Optional):", font=("Roboto", 16, "bold")).pack(anchor="w", padx=20, pady=(10, 5))

        untagged_frame = ctk.CTkFrame(self.metadata_frame, fg_color="transparent")
        untagged_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.chk_untagged_kws = ctk.CTkCheckBox(untagged_frame, text="Keywords", command=self.update_count)
        if ds.daminion_untagged_keywords: self.chk_untagged_kws.select()
        self.chk_untagged_kws.pack(side="left", padx=(0, 20))

        self.chk_untagged_cats = ctk.CTkCheckBox(untagged_frame, text="Category", command=self.update_count)
        if ds.daminion_untagged_categories: self.chk_untagged_cats.select()
        self.chk_untagged_cats.pack(side="left", padx=20)

        self.chk_untagged_desc = ctk.CTkCheckBox(untagged_frame, text="Description", command=self.update_count)
        if ds.daminion_untagged_description: self.chk_untagged_desc.select()
        self.chk_untagged_desc.pack(side="left", padx=20)

        # Limit Control (Slider - hidden by default)
        self.limit_toggle_frame = ctk.CTkFrame(self.filters_container, fg_color="#1a1a1a")
        # Managed in update_count
        
        limit_container = ctk.CTkFrame(self.limit_toggle_frame, fg_color="transparent")
        limit_container.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(limit_container, text="Process Limit:", font=("Roboto", 14, "bold"), text_color="#ffcc00").pack(side="left", padx=(0, 20))
        
        # Slider from 1% (0.01) to 100% (1.0)
        self.limit_slider = ctk.CTkSlider(limit_container, from_=0.01, to=1.0, number_of_steps=99, command=self.on_slider_change)
        self.limit_slider.set(1.0) # Default to all
        self.limit_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        self.lbl_limit_value = ctk.CTkLabel(limit_container, text="All", font=("Roboto", 14, "bold"), width=150)
        self.lbl_limit_value.pack(side="right", padx=10)

        # Background Fetching for dropdowns
        self._load_daminion_data()
        
        # Initial count
        self.after(500, self.update_count)

    def _load_daminion_data(self):
        """Fetch Saved Searches and Collections in background."""
        import threading
        def _bg_load():
            client = self.controller.session.daminion_client
            if not client: return
            
            # 1. Saved Searches
            searches = client.get_saved_searches()
            self._ss_map = {s.get('name'): s.get('id') for s in searches if s.get('name')}
            ss_names = sorted(list(self._ss_map.keys())) if self._ss_map else []
            
            # 2. Shared Collections
            cols = client.get_shared_collections()
            # Shared collection objects might have 'name' or 'title' or 'code'
            self._col_map = {}
            for c in cols:
                name = c.get('name') or c.get('title') or c.get('accessCode')
                cid = c.get('id') or c.get('accessCode')
                if name: self._col_map[name] = cid
            col_names = sorted(list(self._col_map.keys())) if self._col_map else []
            
            def _update_ui():
                if not self.winfo_exists(): return
                
                if hasattr(self, 'ss_dropdown'):
                    self.ss_dropdown.configure(values=ss_names if ss_names else ["No Saved Searches found"])
                    if ss_names: 
                        # Try to restore previous selection
                        prev = self.controller.session.datasource.daminion_saved_search
                        if prev in self._ss_map: self.ss_var.set(prev)
                        else: self.ss_var.set(ss_names[0])
                
                if hasattr(self, 'col_dropdown'):
                    self.col_dropdown.configure(values=col_names if col_names else ["No Collections found"])
                    if col_names:
                        prev = self.controller.session.datasource.daminion_catalog_id
                        if prev in self._col_map: self.col_var.set(prev)
                        else: self.col_var.set(col_names[0])
            
            self.after(0, _update_ui)

        threading.Thread(target=_bg_load, daemon=True).start()

    def clear_container(self, container):
        for widget in container.winfo_children():
            widget.destroy()

    def select_all_untagged(self):
        self.chk_untagged_kws.select()
        self.chk_untagged_cats.select()
        self.chk_untagged_desc.select()
        self.update_count()

    def update_count(self, *args):
        """
        Trigger a background recount of target items based on current filters.
        
        Implements a debouncing mechanism (500ms for typing, 100ms for clicks)
        to prevent excessive API requests during rapid UI interaction.
        """
        if not self.controller.session.daminion_client or not self.controller.session.daminion_client.authenticated:
            self.lbl_total_count.configure(text="")
            return

        # Cancel existing timer if any
        if self._debounce_timer:
            self.after_cancel(self._debounce_timer)
        
        # Determine if we should debounce (only for keyword search typing)
        is_typing = False
        if hasattr(self, 'tabs') and self.tabs.get() == "Keyword Search":
            is_typing = True
        
        delay = 500 if is_typing else 100
        if self.winfo_exists():
            self._debounce_timer = self.after(delay, self._update_count_actual)

    def on_slider_change(self, value):
        if value >= 1.0:
            self.lbl_limit_value.configure(text="All")
        else:
            pct = int(value * 100)
            count = int(self._current_total_count * value)
            if count == 0 and self._current_total_count > 0:
                count = 1
            self.lbl_limit_value.configure(text=f"{pct}% ({count:,} records)")

    def _update_count_actual(self):
        self.lbl_total_count.configure(text="Counting...")
        
        import threading
        def _bg_count():
            try:
                # 1. Determine Scope from Tabs
                tab = self.tabs.get()
                scope = "all"
                ss_id = None
                col_id = None
                search_term = None
                
                if tab == "Saved Searches":
                    scope = "saved_search"
                    ss_name = self.ss_var.get()
                    ss_id = getattr(self, '_ss_map', {}).get(ss_name)
                    if not ss_id: 
                         self.after(0, lambda: self.lbl_total_count.configure(text="Select Search"))
                         return
                elif tab == "Shared Collections":
                    scope = "collection"
                    col_name = self.col_var.get()
                    col_id = getattr(self, '_col_map', {}).get(col_name)
                    if not col_id:
                         self.after(0, lambda: self.lbl_total_count.configure(text="Select Collection"))
                         return
                elif tab == "Keyword Search":
                    scope = "search"
                    search_term = self.search_entry.get()
                    if not search_term:
                         self.after(0, lambda: self.lbl_total_count.configure(text="Enter Search Term"))
                         return

                status = self.status_var.get()
                
                untagged = []
                if hasattr(self, 'chk_untagged_kws') and self.chk_untagged_kws.get(): 
                    untagged.append("Keywords")
                if hasattr(self, 'chk_untagged_cats') and self.chk_untagged_cats.get(): 
                    untagged.append("Category")
                if hasattr(self, 'chk_untagged_desc') and self.chk_untagged_desc.get(): 
                    untagged.append("Description")
                
                logging.debug(f"[UI] Triggering filtered count: scope={scope}, term='{search_term if scope == 'search' else ''}', status={status}, untagged={untagged}")
                
                # Efficient count
                count = self.controller.session.daminion_client.get_filtered_item_count(
                    scope=scope,
                    saved_search_id=ss_id,
                    collection_id=col_id,
                    search_term=search_term if scope == "search" else None,
                    untagged_fields=untagged,
                    status_filter=status
                )
                
                logging.debug(f"[UI] Filtered count result: {count}")
                
                suffix = ""
                final_count = count
                if count == -1:
                    # Fallback to fetching items with a cap to Estimate
                    limit_fallback = 1000 # Increased for better estimation
                    items = self.controller.session.daminion_client.get_items_filtered(
                        scope=scope,
                        saved_search_id=ss_id,
                        collection_id=col_id,
                        search_term=search_term if scope == "search" else None,
                        untagged_fields=untagged,
                        status_filter=status,
                        max_items=limit_fallback,
                        force_refresh=True
                    )
                    final_count = len(items)
                    if final_count >= limit_fallback:
                        suffix = "+"
                
                # Update UI and Toggle Visibility
                def _update_ui():
                    if not self.winfo_exists(): return
                    
                    self.lbl_total_count.configure(text=f"Records: {final_count}{suffix}")
                    self._current_total_count = final_count
                    
                    # Update slider display
                    self.on_slider_change(self.limit_slider.get())
                    
                    # Show toggle if records > 500 (or unknown)
                    if final_count > 500 or suffix == "+":
                         if hasattr(self, 'metadata_frame'):
                             # Reposition before metadata frame if possible
                             self.limit_toggle_frame.pack(fill="x", padx=20, pady=10, before=self.metadata_frame)
                         else:
                             self.limit_toggle_frame.pack(fill="x", padx=20, pady=10)
                    else:
                         self.limit_toggle_frame.pack_forget()

                self.after(0, _update_ui)
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
            
            # Save Scope
            tab = self.tabs.get()
            if tab == "Global Scan":
                ds.daminion_scope = "all"
            elif tab == "Saved Searches":
                ds.daminion_scope = "saved_search"
                ds.daminion_saved_search = self.ss_var.get()
                ds.daminion_saved_search_id = getattr(self, '_ss_map', {}).get(ds.daminion_saved_search)
            elif tab == "Shared Collections":
                ds.daminion_scope = "collection"
                ds.daminion_catalog_id = self.col_var.get() # This is the display name
                ds.daminion_collection_id = getattr(self, '_col_map', {}).get(ds.daminion_catalog_id)
            else: # Keyword Search
                ds.daminion_scope = "search"
                ds.daminion_search_term = self.search_entry.get()
            
            ds.status_filter = self.status_var.get()
            ds.daminion_untagged_keywords = self.chk_untagged_kws.get()
            ds.daminion_untagged_categories = self.chk_untagged_cats.get()
            ds.daminion_untagged_description = self.chk_untagged_desc.get()
            
            # Apply limit from slider if visible
            if self.limit_toggle_frame.winfo_manager(): # Check if packed/grid
                 val = self.limit_slider.get()
                 if val >= 1.0:
                     ds.max_items = 0 # 0 means unlimited
                 else:
                     ds.max_items = int(self._current_total_count * val)
                     if ds.max_items == 0 and self._current_total_count > 0:
                         ds.max_items = 1
            else:
                 ds.max_items = 0
        
        self.controller.show_step("Step2Tagging")
