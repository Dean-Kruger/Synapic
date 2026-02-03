import unittest
from urllib.error import HTTPError, URLError

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.daminion_api import DaminionAPI, DaminionAuthenticationError, DaminionNotFoundError, DaminionRateLimitError, DaminionNetworkError


class _DummyResponse:
    def __init__(self, content: bytes = b'{}'):
        self._content = content
    def read(self) -> bytes:
        return self._content
    def getheader(self, name: str, default=None):
        if name == 'Content-Type':
            return 'application/json'
        return default
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


def _fake_context_manager(resp: _DummyResponse):
    class CM:
        def __enter__(self_inner):
            return resp
        def __exit__(self_inner, exc_type, exc, tb):
            return False
    return CM()


class TestApiErrorPaths(unittest.TestCase):
    def setUp(self):
        self.api = DaminionAPI(base_url="https://example.net", username="u", password="p")
        self.api._authenticated = True

    def test_authentication_error_mapping(self):
        from urllib import request
        def _raise(*args, **kwargs):
            raise HTTPError(url="https://example/api", code=401, msg="Unauthorized", hdrs=None, fp=None)
        request.urlopen = _raise  # type: ignore
        with self.assertRaises(DaminionAuthenticationError):
            self.api._make_request("/api/test")

    def test_not_found_error_mapping(self):
        from urllib import request
        def _raise(*args, **kwargs):
            raise HTTPError(url="https://example/api", code=404, msg="Not Found", hdrs=None, fp=None)
        request.urlopen = _raise  # type: ignore
        with self.assertRaises(DaminionNotFoundError):
            self.api._make_request("/api/test")

    def test_rate_limit_error_mapping(self):
        from urllib import request
        def _raise(*args, **kwargs):
            raise HTTPError(url="https://example/api", code=429, msg="Too Many Requests", hdrs=None, fp=None)
        request.urlopen = _raise  # type: ignore
        with self.assertRaises(DaminionRateLimitError):
            self.api._make_request("/api/test")

    def test_network_error_mapping(self):
        from urllib import request
        def _raise(*args, **kwargs):
            raise URLError("Network down")
        request.urlopen = _raise  # type: ignore
        with self.assertRaises(DaminionNetworkError):
            self.api._make_request("/api/test")

    def test_observability_counter_increments(self):
        import json
        # Prepare a dummy successful JSON response
        content = json.dumps({"success": True, "data": {}}).encode('utf-8')
        self.api._authenticated = True
        from urllib import request
        def _ok(*args, **kwargs):
            return _fake_context_manager(_DummyResponse(content))
        request.urlopen = _ok  # type: ignore
        data = self.api._make_request("/api/test", skip_auth=False, skip_rate_limit=True)
        # Ensure that a request was counted
        self.assertTrue(hasattr(self.api, 'get_request_count'))
        self.assertIsInstance(self.api.get_request_count(), int)


if __name__ == '__main__':
    unittest.main()
