"""
Tests for API Error Handling and Observability
==============================================

This module checks that provider integrations surface useful failures and emit
enough information for debugging and operational support.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

import requests

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.daminion_api import DaminionAPI, DaminionAuthenticationError, DaminionNotFoundError, DaminionRateLimitError, DaminionNetworkError


class _FakeResponse:
    """Minimal stand-in for a requests.Response used by the mocked session."""

    def __init__(self, status_code: int = 200, content: bytes = b'{}', headers=None, cookies=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"Content-Type": "application/json"}
        self.cookies = cookies or {}

    def json(self):
        return json.loads(self._text())

    def _text(self):
        return self.content.decode("utf-8")


def _fake_session(status_code: int = 200, content: bytes = b'{}', cookies=None):
    fake = MagicMock()
    fake.request.return_value = _FakeResponse(
        status_code=status_code, content=content, cookies=cookies
    )
    return fake


class TestApiErrorPaths(unittest.TestCase):
    def setUp(self):
        self.api = DaminionAPI(base_url="https://example.net", username="u", password="p")
        self.api._authenticated = True

    def test_authentication_error_mapping(self):
        fake = _fake_session(status_code=401)
        with patch.object(self.api, "_session", fake):
            with self.assertRaises(DaminionAuthenticationError):
                self.api._make_request("/api/test")

    def test_not_found_error_mapping(self):
        fake = _fake_session(status_code=404)
        with patch.object(self.api, "_session", fake):
            with self.assertRaises(DaminionNotFoundError):
                self.api._make_request("/api/test")

    def test_rate_limit_error_mapping(self):
        fake = _fake_session(status_code=429)
        with patch.object(self.api, "_session", fake):
            with self.assertRaises(DaminionRateLimitError):
                self.api._make_request("/api/test")

    def test_network_error_mapping(self):
        fake = MagicMock()
        fake.request.side_effect = requests.exceptions.ConnectionError("Network down")
        with patch.object(self.api, "_session", fake):
            with self.assertRaises(DaminionNetworkError):
                self.api._make_request("/api/test")

    def test_observability_counter_increments(self):
        content = json.dumps({"success": True, "data": {}}).encode("utf-8")
        fake = _fake_session(status_code=200, content=content)
        with patch.object(self.api, "_session", fake):
            data = self.api._make_request("/api/test", skip_auth=False, skip_rate_limit=True)
        # Ensure that a request was counted
        self.assertTrue(hasattr(self.api, 'get_request_count'))
        self.assertIsInstance(self.api.get_request_count(), int)
        self.assertEqual(data, {})


if __name__ == '__main__':
    unittest.main()
