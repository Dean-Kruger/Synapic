"""
Synapic Main Application Window
===============================

This module defines the root CustomTkinter application window for the Synapic
tagging application. It manages the overall UI structure, global session state,
and the wizard-style navigation between processing steps.

Architecture:
-------------
The application implements a "one-window" wizard interface where different
'Steps' are swapped in and out of a central container.
- Step 1 (Datasource): Image selection and DAM connection.
- Step 2 (Tagging): AI model selection and parameter tuning.
- Step 3 (Process): Real-time processing and logging.
- Step 4 (Results): Reviewing and managing outcomes.

Key Responsibilities:
---------------------
- Root window initialization and theme (Dark Mode) orchestration.
- Global Session lifecycle management (Creation -> Load -> Save).
- Navigation logic (tkraise) between wizard steps.
- Asset management (application icon) with PyInstaller compatibility.
- Graceful shutdown and configuration persistence.

Usage:
------
    >>> from src.ui.app import App
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
    
    This class is the central orchestrator for the Synapic UI. It maintains
    the persistent 'Session' state that is shared across all wizard steps.
    
    Attributes:
        session: The global Session object containing all user configuration.
        steps (dict): Dictionary mapping step names to their respective UI frames.
        container (ctk.CTkFrame): The main container where steps are displayed.
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
                
                # Windows-specific: Set AppUserModelID to ensure taskbar icon displays correctly
                # This prevents Windows from grouping the app with Python and shows our custom icon
                if sys.platform == 'win32':
                    try:
                        import ctypes
                        # Set a unique AppUserModelID for this application
                        myappid = 'Synapic.ImageTagger.v2.0'
                        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                        self.logger.debug("Windows AppUserModelID set successfully")
                    except Exception as e:
                        self.logger.warning(f"Failed to set Windows AppUserModelID: {e}")
                        
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
        
        from src.ui.steps import Step1Datasource, Step2Tagging, Step3Process, Step4Results, StepDedup

        self.logger.info("Creating UI steps")
        for F in (Step1Datasource, Step2Tagging, Step3Process, Step4Results, StepDedup):
            page_name = F.__name__
            self.logger.debug(f"Creating step: {page_name}")
            frame = F(parent=self.container, controller=self)
            self.steps[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.logger.info("Showing initial step: Step1Datasource")
        self.show_step("Step1Datasource")

    def show_step(self, page_name: str):
        """
        Navigate to a specific wizard step.
        
        This method brings the requested step frame to the top of the container
        stack and triggers any necessary data refreshes.
        
        Args:
            page_name: The class name of the step to show (e.g., "Step1Datasource").
        """
        self.logger.info(f"Navigating to step: {page_name}")
        frame = self.steps[page_name]
        frame.tkraise()
        # Trigger explicit refresh if supported
        if hasattr(frame, 'refresh_stats'):
             frame.refresh_stats()
        elif hasattr(frame, 'refresh'):
             frame.refresh()

    def on_close(self):
        """
        Handle application shutdown.
        
        Executes an orderly shutdown sequence that:
        1. Triggers shutdown hooks on all individual wizard steps.
        2. Persists the current session configuration to disk.
        3. Destroys the main window and terminates the event loop.
        """
        self.logger.info("Application close requested - starting shutdown sequence")
        
        # 1. Shutdown all steps (e.g., stop processing threads)
        for name, step in self.steps.items():
            if hasattr(step, 'shutdown'):
                self.logger.debug(f"Shutting down step: {name}")
                try:
                    step.shutdown()
                except Exception as e:
                    self.logger.error(f"Error shutting down step {name}: {e}")

        # 2. Save configuration
        try:
            from src.utils.config_manager import save_config
            save_config(self.session)
            self.logger.info("Configuration saved")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")

        # 3. Final cleanup and destruction
        self.logger.info("Destroying window and exiting")
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()

