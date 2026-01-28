"""
Step 3: Processing Execution
============================

This module defines the UI for monitoring the batch tagging process.
It provides real-time updates on progress, status, and execution logs.
"""

import customtkinter as ctk

class Step3Process(ctk.CTkFrame):
    """
    UI component for the third step of the tagging wizard.
    
    This frame allows users to:
    - Start and abort the batch tagging process.
    - Monitor progress via a progress bar and item counter.
    - View a detailed execution log in real-time.
    - Navigate to the final results step upon completion.
    
    Attributes:
        controller: The main App instance managing the wizard flow.
        manager: The ProcessingManager instance handling the background tasks.
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(3, weight=1) # Log expands

        # Title
        title = ctk.CTkLabel(self.container, text="Step 3: Processing", font=("Roboto", 24, "bold"))
        title.grid(row=0, column=0, pady=(20, 30))

        # Controls
        controls_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        controls_frame.grid(row=1, column=0, pady=10)
        
        self.btn_start = ctk.CTkButton(controls_frame, text="Start Processing", fg_color="green", width=200, height=50, font=("Roboto", 16, "bold"), command=self.start_process)
        self.btn_start.pack(side="left", padx=20)
        
        self.btn_stop = ctk.CTkButton(controls_frame, text="ABORT", fg_color="red", width=150, height=50, font=("Roboto", 16, "bold"), state="disabled", command=self.stop_process)
        self.btn_stop.pack(side="left", padx=20)

        # Progress Area
        progress_frame = ctk.CTkFrame(self.container)
        progress_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        
        self.lbl_status = ctk.CTkLabel(progress_frame, text="Ready to start.", font=("Roboto", 16))
        self.lbl_status.pack(pady=(10, 5))
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=20)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(5, 10))
        
        self.lbl_counter = ctk.CTkLabel(progress_frame, text="0 / 0 Images")
        self.lbl_counter.pack(pady=(0, 10))

        # Console Log
        ctk.CTkLabel(self.container, text="Execution Log:", anchor="w").grid(row=3, column=0, sticky="w", padx=20, pady=(10,0))
        
        self.console = ctk.CTkTextbox(self.container, font=("Consolas", 12))
        self.console.grid(row=4, column=0, sticky="nsew", padx=20, pady=(5, 20))
        self.console.insert("0.0", "--- Log initialized ---\n")
        self.console.configure(state="disabled")

        # Navigation Buttons
        nav_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        nav_frame.grid(row=5, column=0, pady=20, sticky="ew")
        
        ctk.CTkButton(nav_frame, text="Previous", command=lambda: self.controller.show_step("Step2Tagging"), width=150, fg_color="gray").pack(side="left", padx=20)
        ctk.CTkButton(nav_frame, text="View Results", command=lambda: self.controller.show_step("Step4Results"), width=200, height=40).pack(side="right", padx=20)

    def start_process(self):
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="Initializing...")
        
        # Start Worker
        from src.core.processing import ProcessingManager
        
        self.manager = ProcessingManager(
            session=self.controller.session,
            log_callback=self.safe_log,
            progress_callback=self.safe_update_progress
        )
        self.manager.start()

    def stop_process(self):
        if hasattr(self, 'manager'):
            self.manager.abort()
        
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="Stopping...")

    def shutdown(self):
        """Clean up resources on application exit."""
        if hasattr(self, 'manager') and self.manager:
            self.manager.shutdown()

    def safe_log(self, message):
        self.after(0, lambda: self.log(message))

    def safe_update_progress(self, pct, current, total):
        def _update():
            self.progress_bar.set(pct)
            self.lbl_counter.configure(text=f"{current} / {total} Images")
            if pct >= 1.0:
                 self.lbl_status.configure(text="Completed.")
                 self.btn_start.configure(state="normal")
                 self.btn_stop.configure(state="disabled")
        self.after(0, _update)

    def log(self, message):
        self.console.configure(state="normal")
        self.console.insert("end", f"> {message}\n")
        self.console.see("end")
        self.console.configure(state="disabled")
