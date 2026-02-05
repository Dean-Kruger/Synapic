"""
Groq Settings Dialog
=====================

Modal dialog to configure Groq integration (base URL and API key).
Saves values back to the application's EngineConfig and persists via config_manager.
"""
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from src.utils.config_manager import save_config
from src.integrations.groq_client import GroqClient

class GroqSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, session, title: str = "Groq Settings"):
        super().__init__(parent)
        self.parent = parent
        self.session = session
        self.title(title)
        self.geometry("520x180")
        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        frame.grid_columnconfigure(1, weight=1)

        # Base URL
        ctk.CTkLabel(frame, text="Groq Base URL:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.base_url_var = ctk.StringVar(value=getattr(session.engine, 'groq_base_url', ''))
        self.base_url_entry = ctk.CTkEntry(frame, textvariable=self.base_url_var, width=380)
        self.base_url_entry.grid(row=0, column=1, sticky="w", pady=5)

        # API Key
        ctk.CTkLabel(frame, text="Groq API Key:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.api_key_var = ctk.StringVar(value=getattr(session.engine, 'groq_api_key', ''))
        self.api_key_entry = ctk.CTkEntry(frame, textvariable=self.api_key_var, show='*', width=380)
        self.api_key_entry.grid(row=1, column=1, sticky="w", pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=1, column=0, pady=8)
        ctk.CTkButton(btn_frame, text="Test Connection", command=self.test_connection, width=140).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Load Groq Models", command=self.load_models, width=180).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Save", command=self.save, width=120).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.close, width=100).pack(side="left", padx=8)

        self.status_label = ctk.CTkLabel(self, text="Not tested", text_color="gray")
        self.status_label.grid(row=2, column=0, sticky="w", padx=12, pady=6)
        self.models_frame = None

        self.protocol("WM_DELETE_WINDOW", self.close)

    def save(self):
        # Persist to session engine config
        self.session.engine.groq_base_url = self.base_url_var.get().strip()
        self.session.engine.groq_api_key = self.api_key_var.get().strip()
        try:
            save_config(self.session)
        except Exception:
            pass
        self.close()

    def test_connection(self):
        base = self.base_url_var.get().strip()
        key = self.api_key_var.get().strip()
        client = GroqClient(base_url=base or None, api_key=key or None)
        self.status_label.configure(text="Testing Groq connection...", text_color="gray")

        def worker():
            ok = False
            try:
                ok = client.test_connection()
            except Exception as e:
                ok = False
                self.after(0, lambda: self.status_label.configure(text=f"Error: {e}", text_color="red"))
            self.after(0, lambda: self.status_label.configure(text=("Connection OK" if ok else "Connection failed"), text_color=("green" if ok else "red")))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def load_models(self):
        base = self.base_url_var.get().strip()
        key = self.api_key_var.get().strip()
        client = GroqClient(base_url=base or None, api_key=key or None)
        def worker():
            try:
                models = client.list_models(limit=40)
                self.after(0, lambda: self.display_models(models))
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(text=f"Error loading models: {e}", text_color="red"))
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def display_models(self, models):
        # Create or refresh models frame below current controls
        if self.models_frame:
            self.models_frame.destroy()
        self.models_frame = ctk.CTkScrollableFrame(self, label_text="Available Groq Models")
        self.models_frame.grid(row=3, column=0, padx=12, pady=6, sticky="ew")

        self.selected_model_id = getattr(self, 'selected_model_id', "")
        for m in models or []:
            mid = m.get('id') or m.get('model_id') or ""
            cost = m.get('token_cost') or m.get('token_cost_per_inference') or m.get('cost')
            cap = m.get('capability') or m.get('task') or 'Groq'
            cost_text = f"{cost} tokens" if cost is not None else "Cost: Unknown"
            display = f"{mid:<40} | {cap:^12} | {cost_text:>20}"
            btn = ctk.CTkButton(self.models_frame, text=display, anchor="w", width=0,
                                command=lambda m_id=mid: self.select_model(m_id))
            btn.pack(fill="x", pady=2)
        if models:
            self.status_label.configure(text=f"Loaded {len(models)} Groq models", text_color="green")
        else:
            self.status_label.configure(text="No Groq models found", text_color="gray")

    def select_model(self, model_id):
        self.selected_model_id = model_id
        self.session.engine.model_id = model_id
        # Update a small status/tiny display if desired
        self.status_label.configure(text=f"Selected: {model_id}", text_color="green")
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
        except Exception:
            pass

    def close(self):
        self.grab_release()
        self.destroy()
