"""
Daminion API Test Suite

Comprehensive tests for the new DaminionAPI client (v2.0).
Run with: python -m pytest tests/ -v
Or: python tests/test_daminion_api.py
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.daminion_api import (
    DaminionAPI,
    DaminionAPIError,
    DaminionAuthenticationError,
    DaminionNotFoundError,
    DaminionRateLimitError,
    DaminionNetworkError,
    DaminionPermissionError,
    TagInfo,
    TagValue,
    SharedCollection
)


# ============================================================================
# TEST CONFIGURATION
# ============================================================================
# Update these values to match your Daminion server for integration testing

TEST_DAMINION_URL = os.environ.get('DAMINION_URL', 'http://damserver.local/daminion')
TEST_DAMINION_USERNAME = os.environ.get('DAMINION_USERNAME', 'admin')
TEST_DAMINION_PASSWORD = os.environ.get('DAMINION_PASSWORD', 'admin')

# Note: Unit tests use mocks and don't connect to real server.
# For integration tests, set environment variables or edit defaults above.
# ============================================================================


class TestDaminionAPIInitialization(unittest.TestCase):
    """Test DaminionAPI initialization and configuration"""
    
    def test_init_basic(self):
        """Test basic initialization"""
        # Uses test values - for real server, use TEST_DAMINION_* variables
        api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        
        self.assertEqual(api.base_url, "https://test.daminion.net")
        self.assertEqual(api.username, "test_user")
        self.assertEqual(api.password, "test_pass")
        self.assertFalse(api.is_authenticated())
    
    def test_init_with_options(self):
        """Test initialization with optional parameters"""
        api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass",
            catalog_id=1,
            rate_limit=0.5,
            timeout=60
        )
        
        self.assertEqual(api.catalog_id, 1)
        self.assertEqual(api.rate_limit, 0.5)
        self.assertEqual(api.timeout, 60)
    
    def test_base_url_normalization(self):
        """Test that trailing slashes are removed from base URL"""
        api = DaminionAPI(
            base_url="https://test.daminion.net/",
            username="test_user",
            password="test_pass"
        )
        
        self.assertEqual(api.base_url, "https://test.daminion.net")
    
    def test_sub_apis_initialized(self):
        """Test that all sub-APIs are initialized"""
        api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        
        self.assertIsNotNone(api.media_items)
        self.assertIsNotNone(api.tags)
        self.assertIsNotNone(api.collections)
        self.assertIsNotNone(api.item_data)
        self.assertIsNotNone(api.settings)
        self.assertIsNotNone(api.thumbnails)
        self.assertIsNotNone(api.downloads)
        self.assertIsNotNone(api.imports)
        self.assertIsNotNone(api.user_manager)


class TestDaminionAPIAuthentication(unittest.TestCase):
    """Test authentication functionality"""
    
    @patch('src.core.daminion_api.urllib.request.urlopen')
    def test_authenticate_success(self, mock_urlopen):
        """Test successful authentication"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "success": True,
            "data": {"sessionId": "test123"}
        }).encode('utf-8')
        mock_response.getheader.return_value = "sessionId=test123; path=/"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        
        result = api.authenticate()
        
        self.assertTrue(result)
        self.assertTrue(api.is_authenticated())
    
    @patch('src.core.daminion_api.urllib.request.urlopen')
    def test_authenticate_failure(self, mock_urlopen):
        """Test authentication failure"""
        # Mock 401 error
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://test.daminion.net/api/UserManager/Login",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None
        )
        
        api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="wrong_user",
            password="wrong_pass"
        )
        
        with self.assertRaises(DaminionAuthenticationError):
            api.authenticate()
    
    def test_context_manager(self):
        """Test context manager auto-authentication"""
        with patch('src.core.daminion_api.DaminionAPI.authenticate') as mock_auth:
            mock_auth.return_value = True
            
            with DaminionAPI(
                base_url="https://test.daminion.net",
                username="test_user",
                password="test_pass"
            ) as api:
                self.assertIsNotNone(api)
                mock_auth.assert_called_once()


class TestMediaItemsAPI(unittest.TestCase):
    """Test MediaItemsAPI functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        self.api._authenticated = True
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_search_simple(self, mock_request):
        """Test simple text search"""
        mock_request.return_value = [
            {"id": 1, "filename": "test1.jpg"},
            {"id": 2, "filename": "test2.jpg"}
        ]
        
        items = self.api.media_items.search(query="test")
        
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["filename"], "test1.jpg")
        mock_request.assert_called_once()
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_search_structured(self, mock_request):
        """Test structured query search"""
        mock_request.return_value = [{"id": 1, "filename": "test.jpg"}]
        
        items = self.api.media_items.search(
            query_line="13,4949",
            operators="13,any"
        )
        
        self.assertEqual(len(items), 1)
        # Verify parameters were passed
        call_args = mock_request.call_args
        self.assertIn("queryLine", call_args[1]["params"])
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_get_by_ids(self, mock_request):
        """Test getting items by IDs"""
        mock_request.return_value = [
            {"id": 123, "filename": "test1.jpg"},
            {"id": 456, "filename": "test2.jpg"}
        ]
        
        items = self.api.media_items.get_by_ids([123, 456])
        
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], 123)
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_get_count(self, mock_request):
        """Test getting item count"""
        mock_request.return_value = 4134
        
        count = self.api.media_items.get_count()
        
        self.assertEqual(count, 4134)
        self.assertIsInstance(count, int)


class TestTagsAPI(unittest.TestCase):
    """Test TagsAPI functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        self.api._authenticated = True
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_get_all_tags(self, mock_request):
        """Test getting tag schema"""
        mock_request.return_value = [
            {"id": 13, "guid": "abc-123", "name": "Keywords", "type": "indexed"},
            {"id": 14, "guid": "def-456", "name": "Categories", "type": "indexed"}
        ]
        
        tags = self.api.tags.get_all_tags()
        
        self.assertEqual(len(tags), 2)
        self.assertIsInstance(tags[0], TagInfo)
        self.assertEqual(tags[0].name, "Keywords")
        self.assertEqual(tags[0].id, 13)
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_get_tag_values(self, mock_request):
        """Test getting tag values"""
        mock_request.return_value = [
            {"id": 4949, "text": "city", "count": 123},
            {"id": 4950, "text": "urban", "count": 456}
        ]
        
        values = self.api.tags.get_tag_values(tag_id=13)
        
        self.assertEqual(len(values), 2)
        self.assertIsInstance(values[0], TagValue)
        self.assertEqual(values[0].text, "city")
        self.assertEqual(values[0].count, 123)
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_find_tag_values(self, mock_request):
        """Test searching for tag values"""
        mock_request.return_value = [{"id": 4949, "text": "city", "count": 123}]
        
        values = self.api.tags.find_tag_values(tag_id=13, filter_text="city")
        
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].text, "city")


class TestCollectionsAPI(unittest.TestCase):
    """Test CollectionsAPI functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        self.api._authenticated = True
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_get_all_collections(self, mock_request):
        """Test getting all collections"""
        mock_request.return_value = [
            {
                "id": 1,
                "name": "Test Collection",
                "code": "ABC123",
                "itemCount": 50,
                "created": "2026-01-01",
                "modified": "2026-01-18"
            }
        ]
        
        collections = self.api.collections.get_all()
        
        self.assertEqual(len(collections), 1)
        self.assertIsInstance(collections[0], SharedCollection)
        self.assertEqual(collections[0].name, "Test Collection")
        self.assertEqual(collections[0].item_count, 50)
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_get_collection_items(self, mock_request):
        """Test getting items in a collection"""
        mock_request.return_value = [
            {"id": 1, "filename": "test1.jpg"},
            {"id": 2, "filename": "test2.jpg"}
        ]
        
        items = self.api.collections.get_items(collection_id=1)
        
        self.assertEqual(len(items), 2)
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_create_collection(self, mock_request):
        """Test creating a collection"""
        mock_request.return_value = {"id": 42}
        
        new_id = self.api.collections.create(
            name="New Collection",
            description="Test description"
        )
        
        self.assertEqual(new_id, 42)


class TestItemDataAPI(unittest.TestCase):
    """Test ItemDataAPI functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        self.api._authenticated = True
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_get_metadata(self, mock_request):
        """Test getting item metadata"""
        mock_request.return_value = {
            "id": 123,
            "properties": [
                {
                    "groupName": "General",
                    "properties": [
                        {"propertyName": "Keywords", "propertyValue": "test, city"}
                    ]
                }
            ]
        }
        
        metadata = self.api.item_data.get(item_id=123)
        
        self.assertEqual(metadata["id"], 123)
        self.assertIn("properties", metadata)
    
    @patch('src.core.daminion_api.DaminionAPI._make_request')
    def test_batch_update(self, mock_request):
        """Test batch updating tags"""
        mock_request.return_value = {"success": True}
        
        self.api.item_data.batch_update(
            item_ids=[123, 456],
            operations=[{"guid": "test-guid", "id": 4949, "remove": False}]
        )
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[1]["method"], "POST")


class TestErrorHandling(unittest.TestCase):
    """Test error handling and exceptions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        self.api._authenticated = True
    
    @patch('src.core.daminion_api.urllib.request.urlopen')
    def test_404_error(self, mock_urlopen):
        """Test 404 Not Found error"""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://test.daminion.net/api/test",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        
        with self.assertRaises(DaminionNotFoundError):
            self.api._make_request("/api/test")
    
    @patch('src.core.daminion_api.urllib.request.urlopen')
    def test_403_error(self, mock_urlopen):
        """Test 403 Forbidden error"""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://test.daminion.net/api/test",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None
        )
        
        with self.assertRaises(DaminionPermissionError):
            self.api._make_request("/api/test")
    
    @patch('src.core.daminion_api.urllib.request.urlopen')
    def test_429_error(self, mock_urlopen):
        """Test 429 Rate Limit error"""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://test.daminion.net/api/test",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None
        )
        
        with self.assertRaises(DaminionRateLimitError):
            self.api._make_request("/api/test")
    
    @patch('src.core.daminion_api.urllib.request.urlopen')
    def test_network_error(self, mock_urlopen):
        """Test network error"""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")
        
        with self.assertRaises(DaminionNetworkError):
            self.api._make_request("/api/test")
    
    def test_not_authenticated_error(self):
        """Test error when not authenticated"""
        api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass"
        )
        # Don't authenticate
        
        with self.assertRaises(DaminionAuthenticationError):
            api._make_request("/api/test")


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting functionality"""
    
    def test_rate_limit_enforcement(self):
        """Test that rate limiting delays requests"""
        import time
        
        api = DaminionAPI(
            base_url="https://test.daminion.net",
            username="test_user",
            password="test_pass",
            rate_limit=0.1  # 100ms between requests
        )
        
        start = time.time()
        api._enforce_rate_limit()
        api._enforce_rate_limit()
        elapsed = time.time() - start
        
        # Should take at least 100ms
        self.assertGreaterEqual(elapsed, 0.09)  # Allow small margin


class TestDataClasses(unittest.TestCase):
    """Test data classes"""
    
    def test_tag_info(self):
        """Test TagInfo data class"""
        tag = TagInfo(
            id=13,
            guid="abc-123",
            name="Keywords",
            type="indexed",
            indexed=True
        )
        
        self.assertEqual(tag.id, 13)
        self.assertEqual(tag.name, "Keywords")
        self.assertTrue(tag.indexed)
    
    def test_tag_value(self):
        """Test TagValue data class"""
        value = TagValue(
            id=4949,
            text="city",
            count=123,
            parent_id=None
        )
        
        self.assertEqual(value.id, 4949)
        self.assertEqual(value.text, "city")
        self.assertEqual(value.count, 123)
    
    def test_shared_collection(self):
        """Test SharedCollection data class"""
        coll = SharedCollection(
            id=1,
            name="Test Collection",
            code="ABC123",
            item_count=50,
            created="2026-01-01",
            modified="2026-01-18"
        )
        
        self.assertEqual(coll.id, 1)
        self.assertEqual(coll.name, "Test Collection")
        self.assertEqual(coll.item_count, 50)


# ============================================================================
# INTEGRATION TESTS (Optional - requires real Daminion server)
# ============================================================================
# These tests connect to a real server using TEST_DAMINION_* variables
# Set RUN_INTEGRATION_TESTS=1 environment variable to enable
# ============================================================================

RUN_INTEGRATION_TESTS = os.environ.get('RUN_INTEGRATION_TESTS', '0') == '1'


@unittest.skipUnless(RUN_INTEGRATION_TESTS, "Integration tests disabled (set RUN_INTEGRATION_TESTS=1 to enable)")
class TestDaminionAPIIntegration(unittest.TestCase):
    """Integration tests with real Daminion server"""
    
    def setUp(self):
        """Set up connection to real server"""
        self.api = DaminionAPI(
            base_url=TEST_DAMINION_URL,
            username=TEST_DAMINION_USERNAME,
            password=TEST_DAMINION_PASSWORD
        )
    
    def test_real_authentication(self):
        """Test authentication with real server"""
        result = self.api.authenticate()
        self.assertTrue(result)
        self.assertTrue(self.api.is_authenticated())
    
    def test_real_get_version(self):
        """Test getting server version"""
        with self.api:
            version = self.api.settings.get_version()
            self.assertIsNotNone(version)
            self.assertIsInstance(version, str)
            print(f"Server version: {version}")
    
    def test_real_get_tags(self):
        """Test getting tag schema from real server"""
        with self.api:
            tags = self.api.tags.get_all_tags()
            self.assertIsNotNone(tags)
            self.assertGreater(len(tags), 0)
            print(f"Found {len(tags)} tags")
    
    def test_real_search(self):
        """Test searching on real server"""
        with self.api:
            # Simple wildcard search
            items = self.api.media_items.search(query="*", page_size=5)
            self.assertIsNotNone(items)
            print(f"Found {len(items)} items (max 5)")
    
    def test_real_get_collections(self):
        """Test getting collections from real server"""
        with self.api:
            collections = self.api.collections.get_all()
            self.assertIsNotNone(collections)
            print(f"Found {len(collections)} collections")


def run_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("DAMINION API TEST SUITE")
    print("="*70)
    print(f"Configuration:")
    print(f"  URL: {TEST_DAMINION_URL}")
    print(f"  Username: {TEST_DAMINION_USERNAME}")
    print(f"  Password: {'*' * len(TEST_DAMINION_PASSWORD)}")
    print(f"  Integration Tests: {'ENABLED' if RUN_INTEGRATION_TESTS else 'DISABLED'}")
    print("="*70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all unit test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDaminionAPIInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestDaminionAPIAuthentication))
    suite.addTests(loader.loadTestsFromTestCase(TestMediaItemsAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestTagsAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestCollectionsAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestItemDataAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestRateLimiting))
    suite.addTests(loader.loadTestsFromTestCase(TestDataClasses))
    
    # Add integration tests if enabled
    if RUN_INTEGRATION_TESTS:
        print("\n⚠️  Integration tests ENABLED - will connect to real server")
        suite.addTests(loader.loadTestsFromTestCase(TestDaminionAPIIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
