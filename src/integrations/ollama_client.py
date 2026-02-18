"""
Ollama Client
=============

Wrapper around the official 'ollama' Python library.
Supports connecting to local or remote Ollama servers.
"""

import logging
from typing import Optional, List, Dict, Any
import base64
import os

# Known vision models
VISION_MODEL_PATTERNS = [
    'llava', 'llama3.2-vision', 'bakllava', 'moondream', 'minicpm-v', 'qwen2-vl', 'yi-vl'
]

def is_vision_model(model_name: str) -> bool:
    """Check if a model name indicates vision/multimodal capability."""
    if not model_name:
        return False
    return any(pattern in model_name.lower() for pattern in VISION_MODEL_PATTERNS)

class OllamaClient:
    """
    Client wrapper for the official Ollama Python library.
    
    Attributes:
        host (str): URL of the Ollama server (e.g., "http://localhost:11434")
    """
    
    def __init__(self, host: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize the Ollama client.
        
        Args:
            host: Optional host URL. If None/empty, defaults to localhost:11434 (library default).
            api_key: Optional API key for authentication (e.g. for cloud providers).
        """
        self.host = host
        self.client = None
        self.available = False
        self.logger = logging.getLogger(__name__)

        try:
            from ollama import Client
            
            # Configure headers if API key provided
            # Official docs: headers={'Authorization': 'Bearer ' + api_key}
            # Configure headers if API key provided
            # Official docs: headers={'Authorization': 'Bearer ' + api_key}
            headers = {}
            if api_key:
                clean_key = api_key.strip()
                if clean_key.startswith("ssh-"):
                    self.logger.warning("Configured API key starts with 'ssh-', which indicates an SSH key. " 
                                      "Ollama Cloud requires an HTTP API key (token), not an SSH key.")
                headers["Authorization"] = f"Bearer {clean_key}"
            
            # Initialize Client
            # If host is provided, use it. Otherwise let Client use defaults (env vars or localhost)
            # Pass headers if configured (important for cloud auth)
            if host:
                # Remove trailing slash if present to avoid double slash issues
                host = host.rstrip('/')
                self.client = Client(host=host, headers=headers if headers else None)
            else:
                self.client = Client(headers=headers if headers else None)
                
            self.available = True
            
            # log sensitive info masked
            masked_headers = {k: (v[:10] + '...' if k == 'Authorization' else v) for k, v in headers.items()}
            self.logger.debug(f"OllamaClient initialized with host: {host or 'default'}, headers: {masked_headers}")
        except ImportError:
            self.logger.warning("ollama package not installed. Install with: pip install ollama")
        except Exception as e:
            self.logger.error(f"Error initializing Ollama client: {e}")

    def is_available(self) -> bool:
        """Check if the client library is installed and initialized."""
        return self.available

    def list_models(self) -> List[Dict[str, Any]]:
        """List available models from the Ollama server."""
        models = []
        if not self.available or not self.client:
            return models
            
        try:
            response = self.client.list()
            
            # Handle different response formats (pydantic object vs dict)
            raw_models = []
            if hasattr(response, 'models'):
                raw_models = response.models
            elif isinstance(response, dict) and 'models' in response:
                raw_models = response['models']
            
            for m in raw_models:
                # Handle object attribute access vs dict access
                if isinstance(m, dict):
                    name = m.get('model') or m.get('name')
                    size = m.get('size', 0)
                    details = m.get('details', {})
                    family = details.get('family', 'unknown') if isinstance(details, dict) else 'unknown'
                else:
                    name = getattr(m, 'model', None) or getattr(m, 'name', None)
                    size = getattr(m, 'size', 0)
                    details = getattr(m, 'details', None)
                    family = getattr(details, 'family', 'unknown') if details else 'unknown'
                
                if not name:
                    continue
                
                # If family is still unknown, infer from name
                if family == 'unknown':
                    family = name.split(':')[0]

                models.append({
                    'id': name,
                    'family': family,
                    'capability': 'Vision' if is_vision_model(name) else 'LLM',
                    'provider': 'Ollama',
                    'size': self._format_size(size)
                })
                
        except Exception as e:
            self.logger.error(f"Failed to list Ollama models: {e}")
            
        return models

    def chat_with_image(self, model_name: str, prompt: str, image_path: str = None) -> str:
        """Send a prompt with an image to an Ollama model."""
        if not self.available or not self.client:
            return "Ollama client not available"
        
        # Message structure for Ollama Python library
        message = {'role': 'user', 'content': prompt}
        
        # Add image if provided
        if image_path:
            # Manually encode to base64 to ensure remote compatibility and avoid WAF issues with file paths
            if os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as img_f:
                        b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                        message['images'] = [b64_data]
                except Exception as e:
                    self.logger.error(f"Failed to encode image {image_path}: {e}")
            else:
                 self.logger.warning(f"Image path not found: {image_path}")

        messages = [message]

        try:
            # For cloud models or newer library versions, ensure stream is handled if needed
            # We are not using streaming here to keep it simple for now
            # Log masked messages to avoid flooding logs with base64 data
            log_msgs = []
            for m in messages:
                m_copy = m.copy()
                if 'images' in m_copy:
                    m_copy['images'] = [f"<base64_len_{len(img)}>" for img in m_copy['images']]
                log_msgs.append(m_copy)
            
            self.logger.debug(f"Sending chat request to {model_name} with messages: {log_msgs}")
            response = self.client.chat(model=model_name, messages=messages)
            
            # Extract content from response
            # Response is ChatResponse object or dict
            if hasattr(response, 'message'):
                content = response.message.content
            elif isinstance(response, dict):
                content = response.get('message', {}).get('content', '')
            else:
                content = str(response)
                
            return content
            
        except Exception as e:
            self.logger.error(f"Error calling Ollama chat: {e}")
            return f"Error calling Ollama: {e}"

    def test_connection(self) -> bool:
        """Test connectivity to the Ollama server."""
        if not self.available or not self.client:
            return False
        try:
            self.client.list()
            return True
        except Exception:
            return False

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable string (GB/MB)."""
        if not size_bytes: return ""
        try:
            size_bytes = int(size_bytes)
            if size_bytes >= 1e9:
                return f"{size_bytes / 1e9:.1f} GB"
            elif size_bytes >= 1e6:
                return f"{size_bytes / 1e6:.1f} MB"
            return f"{size_bytes} B"
        except (ValueError, TypeError):
            return str(size_bytes)

    def __repr__(self) -> str:
        return f"<OllamaClient host={self.host} available={self.available}>"
