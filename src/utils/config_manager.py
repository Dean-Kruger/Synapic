"""
Configuration Manager
=====================

This module handles the persistence of application configuration to disk.
It uses a JSON file in the user's home directory to store datasource and 
engine settings across sessions. Sensitive data is automatically masked 
during logging.
"""

import json
import logging
from pathlib import Path
from dataclasses import asdict

from src.core.session import Session, DatasourceConfig, EngineConfig
from src.utils.logger import log_config

CONFIG_PATH = Path.home() / ".synapic_v2_config.json"

def save_config(session: Session):
    """
    Save session configuration to disk with logging.
    
    Converts the datasource and engine configuration to dictionaries
    and writes them to a JSON file in the user's home directory.
    Uses the logger to record the action, masking sensitive fields.
    
    Args:
        session: The Session object containing the configuration to save.
    """
    logger = logging.getLogger(__name__)
    
    try:
        data = {
            "datasource": asdict(session.datasource),
            "engine": asdict(session.engine)
        }
        
        # Log the configuration being saved (with sensitive data masked)
        log_config("Saving Configuration", data, logger)
        
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Configuration saved successfully to {CONFIG_PATH}")
        
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}", exc_info=True)

def load_config(session: Session):
    """Load session configuration from disk with logging."""
    logger = logging.getLogger(__name__)
    
    if not CONFIG_PATH.exists():
        logger.info(f"No existing configuration file found at {CONFIG_PATH}")
        return

    try:
        logger.info(f"Loading configuration from {CONFIG_PATH}")
        
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        
        # Log the loaded configuration (with sensitive data masked)
        log_config("Loaded Configuration", data, logger)
            
        if "datasource" in data:
            ds_data = data["datasource"]
            # Safely update fields
            for k, v in ds_data.items():
                if hasattr(session.datasource, k):
                    setattr(session.datasource, k, v)
            logger.debug(f"Datasource configuration updated: type={session.datasource.type}")

        if "engine" in data:
            eng_data = data["engine"]
            for k, v in eng_data.items():
                if hasattr(session.engine, k):
                    if k == "api_key" and isinstance(v, str):
                        v = v.strip()
                    setattr(session.engine, k, v)
            logger.debug(f"Engine configuration updated: provider={session.engine.provider}, task={session.engine.task}")
                    
        logger.info("Configuration loaded and applied successfully")
        
    except json.JSONDecodeError as e:
        logger.error(f"Configuration file is corrupted: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)

