"""
Synapic - AI-Powered Image Tagging Application
===============================================

Main entry point for the Synapic application. This application uses AI models
(local, Hugging Face, or OpenRouter) to automatically generate metadata tags
for images, including categories, keywords, and descriptions.

The application can work with:
- Local image folders
- Daminion Digital Asset Management (DAM) system

Author: Dean
License: Proprietary
"""

import sys
import os
import logging

# ============================================================================
# WINDOWS COMPATIBILITY - HUGGING FACE CACHE SYMLINKS
# ============================================================================
# On Windows, Hugging Face Hub tries to use symlinks for caching which requires
# Developer Mode or Administrator privileges. Setting this env var disables
# symlink warnings and tells HF Hub to copy files instead.
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# ============================================================================
# PATH SETUP
# ============================================================================
# Ensure the 'src' directory is in Python's module search path.
# This allows us to import modules using 'from src.core import ...' syntax
# regardless of where the script is executed from.
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# ============================================================================
# LOGGING INITIALIZATION
# ============================================================================
# Initialize the logging system BEFORE importing any other application modules.
# This ensures all subsequent imports and operations are properly logged.
# The logger writes to both console and a rotating file in the 'logs' directory.
from src.utils.logger import setup_logging
log_file = setup_logging()

# Import the main application UI after logging is configured
from src.ui.app import App

def main():
    """
    Main application entry point.
    
    This function:
    1. Initializes the logger for this module
    2. Creates the main application window (CustomTkinter-based GUI)
    3. Starts the GUI event loop
    4. Handles any fatal errors with comprehensive logging
    5. Ensures proper cleanup on shutdown
    
    The application follows a wizard-style workflow:
    - Step 1: Select data source (local folder or Daminion)
    - Step 2: Configure tagging engine (model selection, device, threshold)
    - Step 3: Process images with AI model
    - Step 4: View and export results
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Log application startup information
        logger.info("Initializing Synapic application")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {current_dir}")
        
        # Create and display the main application window
        # The App class (from src.ui.app) handles all UI initialization
        app = App()
        logger.info("Application window created successfully")
        
        # Start the GUI event loop (blocks until window is closed)
        app.mainloop()
        
    except Exception as e:
        # Log any fatal errors with full stack trace
        logger.critical(f"Fatal error in main application: {e}", exc_info=True)
        raise  # Re-raise to ensure the application exits with error code
    finally:
        # Always perform cleanup, even if an error occurred
        logger.info("Application shutdown")
        from src.utils.logger import shutdown_logging
        shutdown_logging()
        
        # Explicitly exit to ensure all threads/processes are terminated
        # This is especially important for Windows where pythonw can sometimes hang
        sys.exit(0)

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    main()
