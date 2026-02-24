"""
Google AI Studio Client
========================

REST client for the Google Gemini API (generativelanguage.googleapis.com).
Provides model listing and multimodal (image + text) inference using the
generateContent endpoint.

Free tier is available with rate limits — obtain an API key at:
https://aistudio.google.com/app/apikey

Authentication is via the ``x-goog-api-key`` HTTP header.

Author: Synapic Project
"""

import base64
import logging
import mimetypes
from typing import List, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GoogleAIClient:
    """Client for Google AI Studio (Gemini API).

    Mirrors the interface of ``NvidiaClient`` so it can be plugged into the
    processing pipeline as a drop-in provider.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = (api_key or "").strip()
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })
        if self.api_key:
            self.session.headers["x-goog-api-key"] = self.api_key

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True when an API key has been configured."""
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Model listing
    # ------------------------------------------------------------------

    def list_models(self, limit: int = 50) -> List[Dict]:
        """Fetch models that support ``generateContent``.

        Returns a list of dicts with keys ``id``, ``provider``, and
        ``capability`` — compatible with the UI display helpers.
        """
        url = f"{BASE_URL}/models"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            resp.close()
        except Exception as exc:
            logger.error("Google AI model listing failed: %s", exc)
            return []

        results: List[Dict] = []
        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            model_name: str = m.get("name", "")
            # The API returns names like "models/gemini-2.5-flash"
            display_id = model_name.replace("models/", "") if model_name.startswith("models/") else model_name
            results.append({
                "id": display_id,
                "provider": "Google",
                "capability": "Vision" if "vision" in display_id.lower() else "Multi-modal",
            })
            if len(results) >= limit:
                break

        logger.info("Google AI: found %d models", len(results))
        return results

    # ------------------------------------------------------------------
    # Multimodal inference
    # ------------------------------------------------------------------

    def chat_with_image(
        self,
        model_name: str,
        prompt: str,
        image_path: str,
    ) -> str:
        """Send a text+image prompt to Gemini and return the generated text.

        Args:
            model_name: Model identifier (e.g. ``gemini-2.5-flash``).
            prompt: Text instruction.
            image_path: Absolute path to the image file.

        Returns:
            The model's text response.

        Raises:
            RuntimeError: On any API / network error.
        """
        # Determine MIME type
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"

        # Read and base64-encode the image
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_b64,
                            }
                        },
                        {"text": prompt},
                    ]
                }
            ]
        }
        # Free the standalone base64 copy now that it's embedded in the payload
        del image_b64

        url = f"{BASE_URL}/models/{model_name}:generateContent"
        try:
            resp = self.session.post(url, json=payload, timeout=60)
            # Free the large payload dict immediately after the request is sent
            del payload

            resp.raise_for_status()
            data = resp.json()
            resp.close()
        except requests.exceptions.HTTPError as exc:
            # Try to extract a helpful error message from the response body
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except Exception:
                pass
            raise RuntimeError(
                f"Google AI API error ({exc.response.status_code}): {detail or exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Google AI API request failed: {exc}") from exc

        # Extract generated text from candidates
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Google AI returned no candidates")
            text = candidates[0]["content"]["parts"][0]["text"]
            return text
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected Google AI response structure: {exc}") from exc

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """Quick connectivity check — tries to list models."""
        try:
            models = self.list_models(limit=1)
            return len(models) > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Release the underlying HTTP session and connection pool."""
        try:
            self.session.close()
        except Exception:
            pass
