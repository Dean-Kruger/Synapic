"""
Step Groq: Groq Explorer UI
===========================

UI for querying data via Groq API. This is an optional exploration tool to fetch
data from Groq-backed datasets.
"""
import json
import threading
import customtkinter as ctk
from src.integrations.groq_client import GroqClient

class StepGroq(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self.container, text="Groq Explorer", font=("Roboto", 22, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 10), columnspan=2)

        # Dataset
        ctk.CTkLabel(self.container, text="Dataset:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.dataset_var = ctk.StringVar(value="")
        self.dataset_entry = ctk.CTkEntry(self.container, textvariable=self.dataset_var, width=360)
        self.dataset_entry.grid(row=1, column=1, sticky="w", pady=5)

        # Groq Query
        ctk.CTkLabel(self.container, text="Groq Query:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.query_var = ctk.StringVar(value="")
        self.query_entry = ctk.CTkEntry(self.container, textvariable=self.query_var, width=480)
        self.query_entry.grid(row=2, column=1, sticky="w", pady=5)

        # Run
        self.run_btn = ctk.CTkButton(self.container, text="Run Query", command=self.run_query, width=160)
        self.run_btn.grid(row=3, column=0, columnspan=2, pady=12)

        # Groq Settings
        self.settings_btn = ctk.CTkButton(self.container, text="Groq Settings", command=self.open_settings, width=160)
        self.settings_btn.grid(row=3, column=0, columnspan=2, pady=2, sticky="s")

        # Results
        self.results_frame = ctk.CTkScrollableFrame(self.container, label_text="Groq Results")
        self.results_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=5)
        self.results_label = ctk.CTkLabel(self.results_frame, text="No results yet", justify="left", anchor="w")
        self.results_label.pack(fill="both", expand=True)

    def run_query(self):
        dataset = self.dataset_var.get().strip()
        groq_query = self.query_var.get().strip()
        if not dataset or not groq_query:
            self.results_label.configure(text="Please provide dataset and query.")
            return

        client = GroqClient(
            base_url=self.controller.session.engine.groq_base_url or None,
            api_key=self.controller.session.engine.groq_api_key or None
        )

        def worker():
            try:
                results = client.query(dataset, groq_query, limit=100)
                self.after(0, lambda: self.show_results(results))
            except Exception as e:
                self.after(0, lambda: self.results_label.configure(text=f"Error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def show_results(self, results):
        try:
            text = json.dumps(results, indent=2)
        except Exception:
            text = str(results)
        self.results_label.configure(text=text)

    def open_settings(self):
        """Open Groq configuration settings dialog."""
        try:
            from src.ui.steps.step_groq_settings import GroqSettingsDialog
            GroqSettingsDialog(self, self.controller.session).wait_window()
        except Exception as e:
            # If the settings dialog can't be opened, show a simple message
            self.results_label.configure(text=f"Settings unavailable: {e}")
