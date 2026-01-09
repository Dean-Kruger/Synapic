from dataclasses import dataclass, field
from typing import Optional, List
import logging
from .daminion_client import DaminionClient

@dataclass
class DatasourceConfig:
    type: str = "local" # 'local' or 'daminion'
    local_path: str = ""
    daminion_url: str = ""
    daminion_user: str = ""
    daminion_pass: str = ""
    daminion_catalog_id: str = ""
    daminion_scope: str = "all" # 'all', 'selection', 'collection'

@dataclass
class EngineConfig:
    provider: str = "huggingface" # 'local', 'huggingface', 'openrouter'
    model_id: str = ""
    api_key: str = ""
    system_prompt: str = "" # For OpenRouter/LLMs
    task: str = "image-to-text" # Default task

class Session:
    def __init__(self):
        self.datasource = DatasourceConfig()
        self.engine = EngineConfig()
        
        self.daminion_client: Optional[DaminionClient] = None
        self.is_processing = False
        
        # Runtime stats
        self.total_items = 0
        self.processed_items = 0
        self.failed_items = 0
        self.results: List[dict] = []
        
    def connect_daminion(self) -> bool:
        if self.datasource.type != "daminion":
            return False
            
        try:
            self.daminion_client = DaminionClient(
                base_url=self.datasource.daminion_url,
                username=self.datasource.daminion_user,
                password=self.datasource.daminion_pass
            )
            # Authenticate
            return self.daminion_client.authenticate()
        except Exception as e:
            logging.error(f"Failed to connect to Daminion: {e}")
            return False

    def validate_engine(self) -> bool:
        # TODO: Implement verification logic using utils
        return True

    def reset_stats(self):
        self.total_items = 0
        self.processed_items = 0
        self.failed_items = 0
        self.results = []
