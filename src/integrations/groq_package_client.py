"""
Groq Package Client
====================

Lightweight wrapper around the Groq Python SDK (groq package).
This provides a minimal, environment-friendly way to probe availability
and perform basic interactions without requiring a manually configured base URL.

Note: The exact Groq SDK API may vary by version. This wrapper is designed
to be forgiving and degrade gracefully if the API surface differs.
"""
import base64
import os

from typing import List, Dict, Any, Optional

# Known patterns for vision-capable models on Groq
# These models can accept image inputs in chat completions
VISION_MODEL_PATTERNS = [
    'vision',           # e.g., llama-3.2-90b-vision-preview
    'llava',            # LLaVA models
    'scout',            # meta-llama/llama-4-scout (vision capable)
    'maverick',         # meta-llama/llama-4-maverick (vision capable)
]

def is_vision_model(model_id: str) -> bool:
    """Check if a model ID indicates vision capability.
    
    Args:
        model_id: The model identifier to check
        
    Returns:
        True if the model likely supports vision/image inputs
    """
    if not model_id:
        return False
    model_lower = model_id.lower()
    return any(pattern in model_lower for pattern in VISION_MODEL_PATTERNS)


class GroqPackageClient:
    def __init__(self, api_key: Optional[str] = None):
        self._client = None
        self._groq_class = None
        self._cached_key = None  # Track which API key the cached client was created with
        self.available = False
        self.api_key = api_key
        import logging
        logger = logging.getLogger(__name__)
        try:
            # Groq provides a Groq class in the groq package (e.g. from groq import Groq)
            from groq import Groq  # type: ignore
            self._groq_class = Groq
            self._client = None  # will instantiate per-call using environment key
            self.available = True
            logger.debug(f"GroqPackageClient initialized: available=True, Groq class loaded")
        except ImportError as e:
            logger.warning(f"GroqPackageClient: groq package not installed: {e}")
            self._groq_class = None
            self._client = None
            self.available = False
        except Exception as e:
            logger.error(f"GroqPackageClient: unexpected error during init: {e}")
            self._groq_class = None
            self._client = None
            self.available = False

    def is_available(self) -> bool:
        return self.available

    def _ensure_client(self):
        if self._groq_class is None:
            import logging
            logging.getLogger(__name__).warning("Groq class is None - SDK not imported")
            return None
        try:
            import logging
            # Checks self.api_key first, then env var
            key = self.api_key or os.environ.get("GROQ_API_KEY")
            logging.getLogger(__name__).debug(f"GROQ_API_KEY resolution: {'Found' if key else 'Not found'}")
            
            # Reuse cached client if key hasn't changed
            if self._client is not None and key == self._cached_key:
                return self._client
            
            # Close previous client if it exists (free connection pools)
            if self._client is not None:
                try:
                    if hasattr(self._client, 'close'):
                        self._client.close()
                except Exception:
                    pass
                self._client = None
            
            if key:
                self._client = self._groq_class(api_key=key)
            else:
                # If no key found, this will likely fail unless implicit env var works
                self._client = self._groq_class()
            
            self._cached_key = key
            return self._client
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to create Groq client: {e}")
            return None

    def close(self):
        """Close the cached Groq SDK client and free connection pools."""
        if self._client is not None:
            try:
                if hasattr(self._client, 'close'):
                    self._client.close()
            except Exception:
                pass
            self._client = None
            self._cached_key = None

    def chat_with_image(self, model: str, prompt: str, image_path: str = None, base64_image: str = None) -> str:
        """Send a prompt with an image (base64) to Groq chat API and return the response text.

        The payload matches the Groq documentation example:
        user content contains a text prompt and an image_url with a data URL.
        
        Note: Only vision-capable models (e.g., llama-3.2-*-vision, llava, llama-4-scout/maverick)
        can process images. Text-only models will return an error.
        """
        # Check if the model supports vision
        if not is_vision_model(model):
            return (
                f"Error: Model '{model}' does not support vision/image input. "
                f"Please select a vision-capable model such as 'llama-3.2-90b-vision-preview', "
                f"'llama-3.2-11b-vision-preview', or 'meta-llama/llama-4-scout-17b-16e-instruct'."
            )
        
        # Prepare base64 image payload
        b64 = base64_image
        if image_path and not b64:
            try:
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
            except Exception as e:
                return f"Error reading image: {e}"
        if not b64:
            return "No image provided"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ]
        try:
            client = self._ensure_client()
            if client is None:
                return "Groq Python package not available"
            # Prefer the Groq API shipped via the groq package (newer models typically use chat completions)
            chat_completion = client.chat.completions.create(messages=messages, model=model)
            # Groq returns a list of choices; extract the content if present
            return getattr(chat_completion.choices[0].message, 'content', str(chat_completion))
        except Exception as e:
            return f"Error calling Groq chat: {e}"

    def list_models(self, dataset: Optional[str] = None, limit: int = 40) -> List[Dict[str, Any]]:
        """Fetch available models from Groq API.
        
        Uses the Groq SDK's models.list() endpoint to retrieve available models.
        Returns a list of model dictionaries with 'id' and other metadata.
        
        Args:
            dataset: Unused, kept for API compatibility
            limit: Maximum number of models to return
            
        Returns:
            List of model dictionaries with 'id', 'owned_by', 'context_window', etc.
        """
        models: List[Dict[str, Any]] = []
        if not self.available:
            return models
            
        client = self._ensure_client()
        if client is None:
            return models
            
        try:
            # Use the correct Groq SDK API: client.models.list()
            if hasattr(client, 'models') and hasattr(client.models, 'list'):
                response = client.models.list()
                # The response is a ModelList object with a 'data' attribute
                model_list = getattr(response, 'data', None)
                if model_list is None:
                    model_list = response  # Fallback if structure differs
                    
                for m in model_list:
                    # Convert model object to dictionary
                    model_id = getattr(m, 'id', '')
                    model_dict = {
                        'id': model_id,
                        'owned_by': getattr(m, 'owned_by', 'Groq'),
                        'context_window': getattr(m, 'context_window', None),
                        'capability': 'Vision' if is_vision_model(model_id) else 'LLM'
                    }
                    models.append(model_dict)
                    
                # Apply limit
                models = models[:limit]
        except Exception as e:
            # Log error but don't raise - gracefully return empty list
            import logging
            logging.getLogger(__name__).debug(f"Failed to list Groq models: {e}")
            
        return models

    def test_connection(self) -> bool:
        return self.available

    def chat_with_image_rotating(self, engine_config, model: str, prompt: str,
                                  image_path: str = None, base64_image: str = None) -> str:
        """Send a prompt with an image, automatically rotating API keys on errors.

        This method wraps chat_with_image and provides automatic key rotation:
        - On success, returns the response text as usual.
        - On rate-limit / quota / auth errors it rotates to the next key and retries.
        - It tries every available key at most once before giving up.

        Args:
            engine_config: The EngineConfig dataclass instance (provides key list + rotation).
            model: Groq model identifier.
            prompt: Text prompt to send.
            image_path: Optional path to the image file.
            base64_image: Optional base64-encoded image string.

        Returns:
            Response text from the first successful call, or the last error message.
        """
        import logging
        logger = logging.getLogger(__name__)

        keys = engine_config.get_groq_key_list()
        if not keys:
            return "Error: No Groq API keys configured."

        num_keys = len(keys)
        last_error = ""

        for attempt in range(num_keys):
            current_key = engine_config.groq_api_key  # property reads current index
            self.api_key = current_key  # update client key

            logger.info(f"Groq API attempt {attempt + 1}/{num_keys} using key ...{current_key[-4:] if len(current_key) >= 4 else '****'}")

            response = self.chat_with_image(
                model=model,
                prompt=prompt,
                image_path=image_path,
                base64_image=base64_image,
            )

            # Check if the response indicates an error that warrants key rotation
            if isinstance(response, str) and response.startswith("Error"):
                last_error = response
                # Check for rate-limit / quota / auth errors
                error_lower = response.lower()
                should_rotate = any(kw in error_lower for kw in [
                    "rate_limit", "rate limit", "quota", "429",
                    "too many requests", "limit exceeded",
                    "authentication", "invalid api key", "401", "403",
                    "insufficient_quota", "tokens per",
                ])
                if should_rotate and num_keys > 1:
                    old_key_suffix = current_key[-4:] if len(current_key) >= 4 else "****"
                    new_key = engine_config.rotate_groq_key()
                    new_key_suffix = new_key[-4:] if len(new_key) >= 4 else "****"
                    logger.warning(
                        f"Groq API error with key ...{old_key_suffix}, rotating to ...{new_key_suffix}: {response}"
                    )
                    continue
                else:
                    # Non-rotatable error or only one key — return immediately
                    return response
            else:
                # Success
                return response

        # All keys exhausted
        logger.error(f"All {num_keys} Groq API keys exhausted. Last error: {last_error}")
        return f"Error: All {num_keys} API keys exhausted (quota/rate-limit). Last error: {last_error}"

