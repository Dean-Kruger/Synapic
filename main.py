import sys
import os
import logging

# Ensure src is in the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Initialize logging before any other imports
from src.utils.logger import setup_logging
log_file = setup_logging()

from src.ui.app import App

def main():
    """Main application entry point."""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Initializing Synapic application")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {current_dir}")
        
        app = App()
        logger.info("Application window created successfully")
        app.mainloop()
        
    except Exception as e:
        logger.critical(f"Fatal error in main application: {e}", exc_info=True)
        raise
    finally:
        logger.info("Application shutdown")
        from src.utils.logger import shutdown_logging
        shutdown_logging()

if __name__ == "__main__":
    main()
