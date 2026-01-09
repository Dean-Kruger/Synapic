import json
import logging
from pathlib import Path
from dataclasses import asdict

from src.core.session import Session, DatasourceConfig, EngineConfig

CONFIG_PATH = Path.home() / ".synapic_v2_config.json"

def save_config(session: Session):
    try:
        data = {
            "datasource": asdict(session.datasource),
            "engine": asdict(session.engine)
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
        logging.info(f"Config saved to {CONFIG_PATH}")
    except Exception as e:
        logging.error(f"Failed to save config: {e}")

def load_config(session: Session):
    if not CONFIG_PATH.exists():
        return

    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            
        if "datasource" in data:
            ds_data = data["datasource"]
            # Safely update fields
            for k, v in ds_data.items():
                if hasattr(session.datasource, k):
                    setattr(session.datasource, k, v)

        if "engine" in data:
            eng_data = data["engine"]
            for k, v in eng_data.items():
                if hasattr(session.engine, k):
                    setattr(session.engine, k, v)
                    
        logging.info("Config loaded successfully.")
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
