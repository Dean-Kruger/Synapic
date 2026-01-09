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
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing new session")
        
        self.datasource = DatasourceConfig()
        self.engine = EngineConfig()
        
        self.daminion_client: Optional[DaminionClient] = None
        self.is_processing = False
        
        # Runtime stats
        self.total_items = 0
        self.processed_items = 0
        self.failed_items = 0
        self.results: List[dict] = []
        
        self.logger.debug(f"Session initialized - Datasource: {self.datasource.type}, Engine: {self.engine.provider}")
        
    def connect_daminion(self) -> bool:
        """Connect to Daminion server with logging."""
        if self.datasource.type != "daminion":
            self.logger.warning("Attempted to connect to Daminion but datasource type is not 'daminion'")
            return False
            
        try:
            self.logger.info(f"Connecting to Daminion server at {self.datasource.daminion_url}")
            self.logger.debug(f"Daminion user: {self.datasource.daminion_user}")
            
            self.daminion_client = DaminionClient(
                base_url=self.datasource.daminion_url,
                username=self.datasource.daminion_user,
                password=self.datasource.daminion_pass
            )
            
            # Authenticate
            success = self.daminion_client.authenticate()
            
            if success:
                self.logger.info("Successfully authenticated with Daminion server")
            else:
                self.logger.error("Daminion authentication failed")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Daminion: {e}", exc_info=True)
            return False

    def validate_engine(self) -> bool:
        """Validate engine configuration."""
        self.logger.info(f"Validating engine configuration - Provider: {self.engine.provider}, Model: {self.engine.model_id}")
        # TODO: Implement verification logic using utils
        self.logger.debug("Engine validation not yet implemented, returning True")
        return True

    def reset_stats(self):
        """Reset processing statistics."""
        self.logger.info("Resetting session statistics")
        self.logger.debug(f"Previous stats - Total: {self.total_items}, Processed: {self.processed_items}, Failed: {self.failed_items}")
        
        self.total_items = 0
        self.processed_items = 0
        self.failed_items = 0
        self.results = []
        
        self.logger.info("Session statistics reset complete")
