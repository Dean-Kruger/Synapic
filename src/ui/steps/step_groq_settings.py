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
        ctk.CTkButton(btn_frame, text="Save", command=self.save, width=100).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.close, width=100).pack(side="left", padx=8)

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

    def close(self):
        self.grab_release()
        self.destroy()
