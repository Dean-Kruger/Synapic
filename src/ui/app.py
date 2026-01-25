"""
Main Application Window
=======================

This module defines the root CustomTkinter application window for Synapic.
It manages the overall UI structure, session state, and wizard-style workflow.

Architecture:
The application uses a multi-step wizard interface:
1. Step 1 (Datasource): Select images from folder or Daminion DAM
2. Step 2 (Tagging): Configure AI model and processing parameters
3. Step 3 (Process): Execute batch tagging with progress monitoring
4. Step 4 (Results): Review, export, and manage processed metadata

Key Responsibilities:
- Window initialization and theme configuration
- Session management (creating/loading/saving configuration)
- Step container lifecycle (creating and destroying wizard steps)
- Navigation between wizard steps
- Resource loading (icon) for both development and bundled environments

The App class coordinates between:
- Session (src.core.session): Stores datasource and engine configuration
- Step modules (src.ui.steps.*): Individual wizard pages
- Config manager (src.utils.config_manager): Persistence layer

Usage:
    >>> app = App()
    >>> app.mainloop()

Author: Synapic Project
"""

import customtkinter as ctk
import logging
import os
import sys

class App(ctk.CTk):
    """
    Main application window and wizard coordinator.
    
    Manages the CustomTkinter root window, session state, and navigation
    between wizard steps. Handles theme configuration, icon loading,
    and configuration persistence.
    
    Attributes:
        logger: Logger instance for this module
        session: Session object containing datasource and engine config
        current_step: Currently displayed wizard step container
        save_config_callback: Function to persist configuration to disk
    """
    
    def __init__(self):
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing main application window")

        self.title("Hugging Juice Face v2")
        self.geometry("1100x700")
        
        # Set theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.logger.debug("UI theme configured: Dark mode with blue color theme")

        # Set Icon
        # Handle path for PyInstaller bundle
        if getattr(sys, 'frozen', False):
            # Running in a bundle
            base_dir = sys._MEIPASS
        else:
            # Running in normal python environment
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
        icon_path = os.path.join(base_dir, "release", "Icon.ico")
        if os.path.exists(icon_path):
            try:
                # Use iconbitmap for .ico files on Windows
                self.iconbitmap(icon_path)
                self.logger.info(f"Loaded application icon from {icon_path}")
            except Exception as e:
                self.logger.warning(f"Failed to set application icon: {e}")


        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Initialize Session
        from src.core.session import Session
        from src.utils.config_manager import load_config, save_config
        
        self.logger.info("Creating new session")
        self.session = Session()
        
        self.logger.info("Loading saved configuration")
        load_config(self.session)
        
        # Save on exit
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.steps = {}
        
        from src.ui.steps import Step1Datasource, Step2Tagging, Step3Process, Step4Results

        self.logger.info("Creating UI steps")
        for F in (Step1Datasource, Step2Tagging, Step3Process, Step4Results):
            page_name = F.__name__
            self.logger.debug(f"Creating step: {page_name}")
            frame = F(parent=self.container, controller=self)
            self.steps[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.logger.info("Showing initial step: Step1Datasource")
        self.show_step("Step1Datasource")

    def show_step(self, page_name):
        self.logger.info(f"Navigating to step: {page_name}")
        frame = self.steps[page_name]
        frame.tkraise()
        # Trigger explicit refresh if supported (tkraise handles visibility but custom hooks might exist)
        if hasattr(frame, 'refresh_stats'):
             frame.refresh_stats()

    def on_close(self):
        self.logger.info("Application close requested - saving configuration")
        from src.utils.config_manager import save_config
        save_config(self.session)
        self.logger.info("Configuration saved, destroying window")
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()

