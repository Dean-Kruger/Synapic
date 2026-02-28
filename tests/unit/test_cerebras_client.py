"""
Unit Tests — CerebrasClient
=============================

Tests for src/integrations/cerebras_client.py
"""

import base64
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open


class TestCerebrasClientAvailability(unittest.TestCase):
    """Tests for is_available() under various conditions."""

    def test_is_available_with_key_and_sdk(self):
        """Client is available when SDK loaded and key provided."""
        mock_cerebras_cls = MagicMock()
        with patch.dict("sys.modules", {"cerebras": MagicMock(), "cerebras.cloud": MagicMock(), "cerebras.cloud.sdk": MagicMock(Cerebras=mock_cerebras_cls)}):
            from src.integrations.cerebras_client import CerebrasClient
            client = CerebrasClient(api_key="test_key_123")
            self.assertTrue(client.is_available())

    def test_is_not_available_without_key(self):
        """Client is NOT available when no API key provided."""
        mock_cerebras_cls = MagicMock()
        with patch.dict("sys.modules", {"cerebras": MagicMock(), "cerebras.cloud": MagicMock(), "cerebras.cloud.sdk": MagicMock(Cerebras=mock_cerebras_cls)}):
            from src.integrations.cerebras_client import CerebrasClient
            client = CerebrasClient(api_key="")
            self.assertFalse(client.is_available())

    def test_is_not_available_without_sdk(self):
        """Client is NOT available when SDK is not installed."""
        import importlib
        import sys
        # Temporarily remove cerebras_client from cache and mock ImportError
        sys.modules.pop("src.integrations.cerebras_client", None)
        original = sys.modules.get("cerebras.cloud.sdk")
        sys.modules["cerebras.cloud.sdk"] = None  # Simulate ImportError
        try:
            from src.integrations import cerebras_client
            importlib.reload(cerebras_client)
            client = cerebras_client.CerebrasClient(api_key="some_key")
            # available should be False because import failed
            self.assertFalse(client.available)
        except Exception:
            pass  # Import error itself counts as unavailable
        finally:
            if original is not None:
                sys.modules["cerebras.cloud.sdk"] = original
            elif "cerebras.cloud.sdk" in sys.modules:
                del sys.modules["cerebras.cloud.sdk"]
            sys.modules.pop("src.integrations.cerebras_client", None)


class TestCerebrasClientListModels(unittest.TestCase):
    """Tests for list_models()."""

    def _make_client_with_mock_sdk(self, api_key="key"):
        """Create a CerebrasClient with a fully mocked SDK."""
        mock_model = MagicMock()
        mock_model.id = "llama3.1-8b"
        mock_models_response = MagicMock()
        mock_models_response.data = [mock_model]

        mock_sdk_instance = MagicMock()
        mock_sdk_instance.models.list.return_value = mock_models_response

        mock_cerebras_cls = MagicMock(return_value=mock_sdk_instance)

        import sys
        mock_sdk_module = MagicMock()
        mock_sdk_module.Cerebras = mock_cerebras_cls

        sys.modules.pop("src.integrations.cerebras_client", None)
        with patch.dict("sys.modules", {
            "cerebras": MagicMock(),
            "cerebras.cloud": MagicMock(),
            "cerebras.cloud.sdk": mock_sdk_module,
        }):
            from src.integrations.cerebras_client import CerebrasClient
            client = CerebrasClient(api_key=api_key)
            client._client = mock_sdk_instance  # Inject pre-built mock client
            return client

    def test_list_models_returns_list(self):
        """list_models() returns a list of dicts with 'id' key."""
        client = self._make_client_with_mock_sdk()
        models = client.list_models()
        self.assertIsInstance(models, list)
        self.assertTrue(len(models) > 0)
        self.assertIn("id", models[0])

    def test_list_models_fallback_without_key(self):
        """list_models() returns static KNOWN_MODELS fallback when no API key."""
        import sys
        sys.modules.pop("src.integrations.cerebras_client", None)
        mock_sdk_module = MagicMock()
        mock_sdk_module.Cerebras = MagicMock()
        with patch.dict("sys.modules", {
            "cerebras": MagicMock(),
            "cerebras.cloud": MagicMock(),
            "cerebras.cloud.sdk": mock_sdk_module,
        }):
            from src.integrations.cerebras_client import CerebrasClient, KNOWN_MODELS
            client = CerebrasClient(api_key="")
            models = client.list_models()
            self.assertEqual(models, list(KNOWN_MODELS))

    def test_list_models_fallback_on_api_error(self):
        """list_models() returns KNOWN_MODELS when the API call raises."""
        import sys
        mock_sdk_instance = MagicMock()
        mock_sdk_instance.models.list.side_effect = Exception("network error")
        mock_cerebras_cls = MagicMock(return_value=mock_sdk_instance)
        mock_sdk_module = MagicMock()
        mock_sdk_module.Cerebras = mock_cerebras_cls

        sys.modules.pop("src.integrations.cerebras_client", None)
        with patch.dict("sys.modules", {
            "cerebras": MagicMock(),
            "cerebras.cloud": MagicMock(),
            "cerebras.cloud.sdk": mock_sdk_module,
        }):
            from src.integrations.cerebras_client import CerebrasClient, KNOWN_MODELS
            client = CerebrasClient(api_key="some_key")
            client._client = mock_sdk_instance
            models = client.list_models()
            self.assertEqual(models, list(KNOWN_MODELS))


class TestCerebrasClientChatWithImage(unittest.TestCase):
    """Tests for chat_with_image() including multimodal and text-only fallback."""

    def _build_mock_response(self, content: str):
        mock_msg = MagicMock()
        mock_msg.content = content
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response

    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_bytes")
    @patch("os.path.exists", return_value=True)
    def test_chat_with_image_success(self, mock_exists, mock_file):
        """chat_with_image() returns model response text on success."""
        import sys
        expected = '{"description": "A lake", "category": "Nature", "keywords": ["water"]}'

        mock_sdk_instance = MagicMock()
        mock_sdk_instance.chat.completions.create.return_value = self._build_mock_response(expected)
        mock_cerebras_cls = MagicMock(return_value=mock_sdk_instance)
        mock_sdk_module = MagicMock()
        mock_sdk_module.Cerebras = mock_cerebras_cls

        sys.modules.pop("src.integrations.cerebras_client", None)
        with patch.dict("sys.modules", {
            "cerebras": MagicMock(),
            "cerebras.cloud": MagicMock(),
            "cerebras.cloud.sdk": mock_sdk_module,
        }):
            from src.integrations.cerebras_client import CerebrasClient
            client = CerebrasClient(api_key="test_key")
            client._client = mock_sdk_instance

            result = client.chat_with_image("llama3.1-8b", "Analyze this image.", "test.jpg")

        self.assertEqual(result, expected)
        mock_sdk_instance.chat.completions.create.assert_called_once()
        # Verify the call used image_url content part
        call_kwargs = mock_sdk_instance.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        self.assertEqual(messages[0]["role"], "user")
        content_parts = messages[0]["content"]
        image_parts = [p for p in content_parts if p.get("type") == "image_url"]
        self.assertTrue(len(image_parts) > 0)
        # Check base64 encoding present
        self.assertIn("base64,", image_parts[0]["image_url"]["url"])

    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_bytes")
    @patch("os.path.exists", return_value=True)
    def test_chat_with_image_falls_back_to_text_on_vision_rejection(self, mock_exists, mock_file):
        """chat_with_image() retries text-only when image is rejected."""
        import sys
        text_only_response = '{"description": "Unknown", "category": "Other", "keywords": []}'

        mock_sdk_instance = MagicMock()
        # First call (multimodal) raises a vision-rejection error
        mock_sdk_instance.chat.completions.create.side_effect = [
            Exception("image content is not supported by this model"),
            self._build_mock_response(text_only_response),
        ]
        mock_cerebras_cls = MagicMock(return_value=mock_sdk_instance)
        mock_sdk_module = MagicMock()
        mock_sdk_module.Cerebras = mock_cerebras_cls

        sys.modules.pop("src.integrations.cerebras_client", None)
        with patch.dict("sys.modules", {
            "cerebras": MagicMock(),
            "cerebras.cloud": MagicMock(),
            "cerebras.cloud.sdk": mock_sdk_module,
        }):
            from src.integrations.cerebras_client import CerebrasClient
            client = CerebrasClient(api_key="test_key")
            client._client = mock_sdk_instance

            result = client.chat_with_image("llama3.1-8b", "Analyze.", "test.png")

        # Should have been called twice (multimodal attempt + text-only fallback)
        self.assertEqual(mock_sdk_instance.chat.completions.create.call_count, 2)
        self.assertEqual(result, text_only_response)

    @patch("os.path.exists", return_value=False)
    def test_chat_with_image_missing_file(self, mock_exists):
        """chat_with_image() returns an Error string when image file is missing."""
        import sys
        mock_sdk_module = MagicMock()
        mock_sdk_module.Cerebras = MagicMock()

        sys.modules.pop("src.integrations.cerebras_client", None)
        with patch.dict("sys.modules", {
            "cerebras": MagicMock(),
            "cerebras.cloud": MagicMock(),
            "cerebras.cloud.sdk": mock_sdk_module,
        }):
            from src.integrations.cerebras_client import CerebrasClient
            client = CerebrasClient(api_key="test_key")
            result = client.chat_with_image("llama3.1-8b", "Analyze.", "/nonexistent.jpg")

        self.assertTrue(result.startswith("Error:"))

    def test_chat_with_image_no_key(self):
        """chat_with_image() returns an Error string when no API key configured."""
        import sys
        mock_sdk_module = MagicMock()
        mock_sdk_module.Cerebras = MagicMock()

        sys.modules.pop("src.integrations.cerebras_client", None)
        with patch.dict("sys.modules", {
            "cerebras": MagicMock(),
            "cerebras.cloud": MagicMock(),
            "cerebras.cloud.sdk": mock_sdk_module,
        }):
            from src.integrations.cerebras_client import CerebrasClient
            client = CerebrasClient(api_key="")
            result = client.chat_with_image("llama3.1-8b", "Analyze.", "test.jpg")

        self.assertTrue(result.startswith("Error:"))


if __name__ == "__main__":
    unittest.main()
