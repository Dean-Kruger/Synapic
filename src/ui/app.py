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


WINDOWS_APP_ID = "Synapic.ImageTagger.v2.0"


def _candidate_icon_paths():
    module_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    executable_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else module_root
    meipass_dir = getattr(sys, "_MEIPASS", None)

    candidates = [
        os.path.join(executable_dir, "Icon.ico"),
        os.path.join(executable_dir, "release", "Icon.ico"),
        os.path.join(executable_dir, "dist", "Icon.ico"),
        os.path.join(executable_dir, "dist", "release", "Icon.ico"),
    ]

    if meipass_dir:
        candidates.extend(
            [
                os.path.join(meipass_dir, "Icon.ico"),
                os.path.join(meipass_dir, "release", "Icon.ico"),
            ]
        )

    candidates.extend(
        [
            os.path.join(module_root, "dist", "Icon.ico"),
            os.path.join(module_root, "dist", "release", "Icon.ico"),
            os.path.join(module_root, "release", "Icon.ico"),
        ]
    )

    seen = set()
    for path in candidates:
        normalized = os.path.normpath(path)
        if normalized not in seen:
            seen.add(normalized)
            yield normalized


def _resolve_icon_path():
    for icon_path in _candidate_icon_paths():
        if os.path.exists(icon_path):
            return icon_path
    return None


def _set_windows_app_id(logger: logging.Logger):
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
        logger.debug("Windows AppUserModelID set successfully")
    except Exception as e:
        logger.warning(f"Failed to set Windows AppUserModelID: {e}")

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
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing main application window")
        _set_windows_app_id(self.logger)

        super().__init__()

        self.title("Hugging Juice Face v2")
        self.geometry("1280x840")
        self.minsize(1100, 760)
        
        # Set theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.logger.debug("UI theme configured: Dark mode with blue color theme")

        icon_path = _resolve_icon_path()
        if icon_path:
            try:
                self.iconbitmap(default=icon_path)
                self.logger.info(f"Loaded application icon from {icon_path}")
            except Exception as e:
                self.logger.warning(f"Failed to set application icon: {e}")
        else:
            self.logger.warning("Application icon was not found in any expected location")


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

