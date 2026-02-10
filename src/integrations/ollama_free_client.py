"""
OllamaFreeAPI Client
====================

Lightweight wrapper around the ollamafreeapi Python package.
This provides free, zero-configuration access to 50+ open-source LLMs
(LLaMA, Mistral, DeepSeek, Qwen, etc.) via distributed Ollama servers
with automatic load-balancing across global nodes.

The client wraps the OllamaFreeAPI class and adapts it to match
Synapic's inference provider interface, supporting:
- Model listing and family browsing
- Text chat with automatic server selection
- Image analysis via multimodal prompts (text-only models will
  receive a text description prompt instead)

Note: This is a FREE tier service with rate limits (~100 req/hr).
No API key is required.

Reference: https://github.com/mfoud444/ollamafreeapi
"""

import base64
import logging
import os
from typing import List, Dict, Any, Optional

# Known patterns for vision/multimodal-capable models on Ollama
# These models can potentially accept image inputs
VISION_MODEL_PATTERNS = [
    'vision',       # e.g., llava, llama3.2-vision
    'llava',        # LLaVA models
    'bakllava',     # BakLLaVA
    'moondream',    # Moondream vision model
    'minicpm-v',    # MiniCPM-V
]


def is_vision_model(model_name: str) -> bool:
    """Check if a model name indicates vision/multimodal capability.

    Args:
        model_name: The model identifier to check

    Returns:
        True if the model likely supports vision/image inputs
    """
    if not model_name:
        return False
    model_lower = model_name.lower()
    return any(pattern in model_lower for pattern in VISION_MODEL_PATTERNS)


class OllamaFreeClient:
    """
    Client wrapper for the OllamaFreeAPI package.

    Provides a consistent interface for Synapic's processing pipeline,
    matching the patterns used by GroqPackageClient and other integrations.

    Features:
    - Zero-configuration: No API key required
    - Auto load-balanced across global Ollama servers
    - Access to 50+ open-source models (LLaMA 3, Mistral, DeepSeek, Qwen, etc.)
    - Graceful degradation if the package is not installed

    Attributes:
        available (bool): Whether the ollamafreeapi package is installed and usable
    """

    def __init__(self):
        """Initialize the OllamaFreeAPI client.

        Attempts to import and instantiate the OllamaFreeAPI class.
        If the package is not installed, the client degrades gracefully
        with available=False.
        """
        self._client = None
        self._api_class = None
        self.available = False
        self.logger = logging.getLogger(__name__)

        try:
            from ollamafreeapi import OllamaFreeAPI
            self._api_class = OllamaFreeAPI
            self._client = OllamaFreeAPI()
            self.available = True
            self.logger.debug("OllamaFreeClient initialized: available=True")
        except ImportError as e:
            self.logger.warning(f"OllamaFreeClient: ollamafreeapi package not installed: {e}")
        except Exception as e:
            self.logger.error(f"OllamaFreeClient: unexpected error during init: {e}")

    def is_available(self) -> bool:
        """Check if the client is ready to use.

        Returns:
            True if the ollamafreeapi package is installed and initialized
        """
        return self.available

    def list_families(self) -> List[str]:
        """List all available model families.

        Returns:
            List of family names (e.g., 'llama3', 'mistral', 'deepseek')
        """
        if not self.available or not self._client:
            return []

        try:
            return self._client.list_families()
        except Exception as e:
            self.logger.debug(f"Failed to list families: {e}")
            return []

    def list_models(self, family: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List available models, optionally filtered by family.

        Args:
            family: Filter by model family (e.g., 'llama3', 'mistral')
            limit: Maximum number of models to return

        Returns:
            List of model dictionaries with 'id', 'family', 'capability', etc.
        """
        models: List[Dict[str, Any]] = []
        if not self.available or not self._client:
            return models

        try:
            # Get raw model names from the API
            model_names = self._client.list_models(family=family)

            for name in model_names[:limit]:
                model_dict = {
                    'id': name,
                    'family': family or self._get_family_for_model(name),
                    'capability': 'Vision' if is_vision_model(name) else 'LLM',
                    'provider': 'OllamaFreeAPI',
                    'cost': 'Free',
                }

                # Try to get additional model info
                try:
                    info = self._client.get_model_info(name)
                    if isinstance(info, dict):
                        model_dict['size'] = info.get('size', '')
                        model_dict['quantization'] = info.get('quantization_level', '')
                except (ValueError, Exception):
                    pass

                models.append(model_dict)

        except Exception as e:
            self.logger.debug(f"Failed to list models: {e}")

        return models

    def _get_family_for_model(self, model_name: str) -> str:
        """Determine the family for a given model name.

        Args:
            model_name: The model name to categorize

        Returns:
            The family name, or 'unknown' if not determinable
        """
        if not self._client:
            return 'unknown'

        try:
            families = self._client.list_families()
            for family in families:
                family_models = self._client.list_models(family=family)
                if model_name in family_models:
                    return family
        except Exception:
            pass

        return 'unknown'

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific model.

        Args:
            model_name: Name of the model to query

        Returns:
            Dictionary with model metadata

        Raises:
            ValueError: If the model is not found
        """
        if not self.available or not self._client:
            raise ValueError("OllamaFreeAPI client not available")

        return self._client.get_model_info(model_name)

    def get_model_servers(self, model_name: str) -> List[Dict[str, Any]]:
        """Get the list of servers hosting a specific model.

        Useful for checking availability and geographic distribution.

        Args:
            model_name: Name of the model

        Returns:
            List of server dictionaries with url, location, performance info
        """
        if not self.available or not self._client:
            return []

        try:
            return self._client.get_model_servers(model_name)
        except Exception as e:
            self.logger.debug(f"Failed to get servers for {model_name}: {e}")
            return []

    def chat(self, model_name: str, prompt: str, **kwargs) -> str:
        """Send a text prompt to a model and get a response.

        Automatically selects a server and handles failover.

        Args:
            model_name: Name of the model to use
            prompt: The input prompt text
            **kwargs: Additional parameters (temperature, top_p, etc.)

        Returns:
            The generated response text

        Raises:
            RuntimeError: If no working server is found or client unavailable
        """
        if not self.available or not self._client:
            raise RuntimeError("OllamaFreeAPI client not available. Install with: pip install ollamafreeapi")

        return self._client.chat(prompt=prompt, model=model_name, **kwargs)

    def chat_with_image(self, model_name: str, prompt: str,
                        image_path: Optional[str] = None,
                        base64_image: Optional[str] = None) -> str:
        """Send a prompt with an image for analysis.

        For text-only models, the image context is described in the prompt.
        For vision-capable models, the image is sent alongside the prompt
        via the Ollama multimodal API.

        Args:
            model_name: Name of the model to use
            prompt: The analysis prompt
            image_path: Path to the image file (optional if base64_image provided)
            base64_image: Base64-encoded image data (optional if image_path provided)

        Returns:
            The generated analysis text

        Raises:
            RuntimeError: If the client is unavailable or all servers fail
        """
        if not self.available or not self._client:
            return "OllamaFreeAPI client not available. Install with: pip install ollamafreeapi"

        # Prepare base64 image data
        b64 = base64_image
        if image_path and not b64:
            try:
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
            except Exception as e:
                return f"Error reading image: {e}"

        if not b64:
            return "No image provided"

        # For vision models, try to use Ollama's multimodal API via direct client
        if is_vision_model(model_name):
            return self._chat_with_image_vision(model_name, prompt, b64)

        # For text-only models, append image context to the prompt
        # (the model won't see the actual image, but we use a descriptive prompt)
        enhanced_prompt = (
            f"{prompt}\n\n"
            "Note: An image has been provided for analysis. "
            "Please provide your best analysis based on the prompt above."
        )

        try:
            return self._client.chat(prompt=enhanced_prompt, model=model_name)
        except Exception as e:
            return f"Error calling OllamaFreeAPI: {e}"

    def _chat_with_image_vision(self, model_name: str, prompt: str, b64_image: str) -> str:
        """Internal method for vision model inference with image data.

        Uses the Ollama Client directly with multimodal messages to send
        the actual image data to vision-capable models.

        Args:
            model_name: Name of the vision model
            prompt: The analysis prompt
            b64_image: Base64-encoded image data

        Returns:
            The generated analysis text
        """
        try:
            # Get server info for this model
            servers = self._client.get_model_servers(model_name)
            if not servers:
                return f"No servers available for model '{model_name}'"

            import random
            random.shuffle(servers)

            last_error = None
            for server in servers:
                try:
                    from ollama import Client
                    client = Client(host=server['url'])

                    # Use Ollama's generate API with images parameter
                    response = client.generate(
                        model=model_name,
                        prompt=prompt,
                        images=[b64_image],
                        options={
                            "temperature": 0.7,
                            "num_predict": 512
                        }
                    )
                    return response.get('response', str(response))
                except Exception as e:
                    last_error = e
                    continue

            return f"All servers failed for vision model '{model_name}'. Last error: {last_error}"

        except Exception as e:
            return f"Error with vision inference: {e}"

    def test_connection(self) -> bool:
        """Test if the OllamaFreeAPI service is reachable.

        Attempts to list model families as a lightweight health check.

        Returns:
            True if the service responds, False otherwise
        """
        if not self.available:
            return False

        try:
            families = self.list_families()
            return len(families) > 0
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<OllamaFreeClient available={self.available}>"
