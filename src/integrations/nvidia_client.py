"""
Nvidia NIM Client
=================

Wrapper around Nvidia's Inference Microservices (NIM) API.
Supports multimodal chat completions for image analysis.
"""

import logging
import base64
import os
import requests
from typing import Optional, List, Dict, Any

class NvidiaClient:
    """
    Client wrapper for Nvidia NIM API.
    
    Attributes:
        api_key (str): Nvidia API key for authentication.
        base_url (str): Base URL for Nvidia NIM API.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://integrate.api.nvidia.com/v1"):
        """Initialize the Nvidia client.
        
        Args:
            api_key: Nvidia API key. If None, looks for NVIDIA_API_KEY env var.
            base_url: Base URL for the API.
        """
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")
        self.base_url = base_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def is_available(self) -> bool:
        """Check if the API key is configured."""
        return bool(self.api_key)

    def list_models(self) -> List[Dict[str, Any]]:
        """List available models from Nvidia NIM.
        
        Note: Currently filters for vision-capable models if possible, 
        or returns the standard list.
        """
        models = []
        if not self.api_key:
            return models
            
        try:
            url = f"{self.base_url}/models"
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            raw_models = data.get('data', [])
            for m in raw_models:
                m_id = m.get('id')
                if not m_id:
                    continue
                
                # Basic heuristics for vision models if needed
                # For now, include all as the user might want to try specific ones
                models.append({
                    'id': m_id,
                    'provider': 'Nvidia',
                    'capability': 'Vision' if 'vision' in m_id.lower() or 'phi-3-vision' in m_id.lower() or 'mistral' in m_id.lower() else 'LLM'
                })
        except Exception as e:
            self.logger.error(f"Failed to list Nvidia models: {e}")
            
        return models

    def chat_with_image(self, model_name: str, prompt: str, image_path: str) -> str:
        """Send a prompt with an image to an Nvidia NIM model.
        
        Args:
            model_name: The model identifier.
            prompt: The text prompt.
            image_path: Path to the local image file.
            
        Returns:
            str: The model's response text.
        """
        if not self.api_key:
            raise RuntimeError("Nvidia API key not configured")
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image path not found: {image_path}")

        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()

            # Determine file extension/type for the data URI
            ext = os.path.splitext(image_path)[1].lower().replace('.', '')
            if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                ext = 'png' # Fallback
            
            mime_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"

            # Nvidia NIM specific prompt format as per user's snippet:
            # content: f"Describe this image <img src=\"data:image/png;base64,{image_b64}\" />"
            
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": f"{prompt} <img src=\"data:{mime_type};base64,{image_b64}\" />"
                    }
                ],
                "max_tokens": 2048,
                "temperature": 0.15,
                "top_p": 1.00,
                "stream": False
            }

            url = f"{self.base_url}/chat/completions"
            resp = self.session.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            
            data = resp.json()
            choices = data.get('choices', [])
            if choices:
                return choices[0].get('message', {}).get('content', '')
            
            raise RuntimeError("No response from Nvidia NIM (empty choices)")

        except (RuntimeError, FileNotFoundError):
            raise  # Re-raise our own exceptions as-is
        except Exception as e:
            self.logger.error(f"Error calling Nvidia NIM: {e}")
            raise RuntimeError(f"Error calling Nvidia NIM: {str(e)}") from e

    def test_connection(self) -> bool:
        """Simple test to verify API key and connectivity."""
        if not self.api_key:
            return False
        try:
            # Just try to list models with a small limit if supported, 
            # or just see if the endpoint responds.
            url = f"{self.base_url}/models"
            resp = self.session.get(url, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<NvidiaClient base_url={self.base_url} has_api_key={bool(self.api_key)}>"
