"""
Daminion API Test Suite

Run this script to test the new Daminion API implementation.
Update the credentials at the bottom before running.
"""

import sys
import logging
from typing import Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Import the new API
try:
    from daminion_api import (
        DaminionAPI,
        DaminionAuthenticationError,
        DaminionAPIError
    )
except ImportError:
    logging.error("Could not import daminion_api module")
    logging.error("Make sure you're running from src/core directory")
    sys.exit(1)


class DaminionAPITester:
    """Test suite for Daminion API"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.passed = 0
        self.failed = 0
    
    def run_test(self, name: str, test_func) -> bool:
        """Run a single test and track results"""
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print('='*60)
        
        try:
            test_func()
            print(f"✅ PASSED: {name}")
            self.passed += 1
            return True
        except Exception as e:
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
            self.failed += 1
            return False
    
    def test_authentication(self):
        """Test 1: Authentication"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            assert api.is_authenticated(), "Not authenticated"
            print("✓ Successfully authenticated")
    
    def test_get_version(self):
        """Test 2: Get Server Version"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            version = api.settings.get_version()
            assert version, "No version returned"
            print(f"✓ Daminion version: {version}")
    
    def test_get_catalog_info(self):
        """Test 3: Get Catalog Information"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            guid = api.settings.get_catalog_guid()
            assert guid, "No catalog GUID returned"
            print(f"✓ Catalog GUID: {guid}")
            
            user = api.settings.get_logged_user()
            print(f"✓ Logged in as: {user.get('username', 'Unknown')}")
    
    def test_get_tags_schema(self):
        """Test 4: Get Tag Schema"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            tags = api.tags.get_all_tags()
            assert tags, "No tags returned"
            assert len(tags) > 0, "Tag list is empty"
            
            print(f"✓ Found {len(tags)} tags:")
            for tag in tags[:5]:  # Show first 5
                print(f"   - {tag.name} (ID: {tag.id}, Type: {tag.type})")
            
            if len(tags) > 5:
                print(f"   ... and {len(tags) - 5} more")
    
    def test_search_basic(self):
        """Test 5: Basic Search"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            # Simple search with wildcard
            items = api.media_items.search(query="*", page_size=10)
            
            print(f"✓ Found {len(items)} items (max 10)")
            
            if items:
                print(f"   First item: {items[0].get('filename', 'Unknown')}")
    
    def test_get_item_count(self):
        """Test 6: Get Item Count"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            count = api.media_items.get_count()
            assert isinstance(count, int), "Count is not an integer"
            print(f"✓ Catalog has {count:,} total items")
    
    def test_get_collections(self):
        """Test 7: Get Shared Collections"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            collections = api.collections.get_all()
            
            print(f"✓ Found {len(collections)} shared collections")
            
            if collections:
                for coll in collections[:3]:  # Show first 3
                    print(f"   - {coll.name}: {coll.item_count} items")
    
    def test_get_tag_values(self):
        """Test 8: Get Tag Values"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            # Get tag schema first
            tags = api.tags.get_all_tags()
            
            # Find Keywords tag
            keywords_tag = next((t for t in tags if t.name == "Keywords"), None)
            
            if keywords_tag:
                values = api.tags.get_tag_values(
                    tag_id=keywords_tag.id,
                    page_size=10
                )
                
                print(f"✓ Found {len(values)} keyword values:")
                for val in values[:5]:
                    print(f"   - {val.text} ({val.count} items)")
            else:
                print("⚠ Keywords tag not found in catalog")
    
    def test_get_metadata(self):
        """Test 9: Get Item Metadata"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            # Get an item first
            items = api.media_items.search(query="*", page_size=1)
            
            if not items:
                print("⚠ No items found to test metadata")
                return
            
            item_id = items[0]['id']
            metadata = api.item_data.get(item_id, get_all=True)
            
            assert metadata, "No metadata returned"
            print(f"✓ Retrieved metadata for item {item_id}")
            
            # Show some properties
            props_count = sum(
                len(group.get('properties', []))
                for group in metadata.get('properties', [])
            )
            print(f"   Found {props_count} properties")
    
    def test_thumbnails(self):
        """Test 10: Get Thumbnails"""
        with DaminionAPI(self.base_url, self.username, self.password) as api:
            # Get an item first
            items = api.media_items.search(query="*", page_size=1)
            
            if not items:
                print("⚠ No items found to test thumbnails")
                return
            
            item_id = items[0]['id']
            thumbnail = api.thumbnails.get(item_id, width=100, height=100)
            
            assert thumbnail, "No thumbnail data returned"
            assert isinstance(thumbnail, bytes), "Thumbnail is not binary data"
            
            print(f"✓ Retrieved thumbnail for item {item_id}")
            print(f"   Size: {len(thumbnail):,} bytes")
    
    def test_error_handling(self):
        """Test 11: Error Handling"""
        # Test invalid credentials
        try:
            with DaminionAPI(
                self.base_url,
                "invalid_user",
                "invalid_password"
            ) as api:
                api.media_items.search(query="test")
            
            # Should not reach here
            raise AssertionError("Expected authentication error but succeeded")
            
        except DaminionAuthenticationError as e:
            print(f"✓ Correctly caught authentication error: {e}")
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("DAMINION API TEST SUITE")
        print("="*60)
        print(f"Server: {self.base_url}")
        print(f"User: {self.username}")
        print("="*60)
        
        # Run each test
        self.run_test("Authentication", self.test_authentication)
        self.run_test("Get Server Version", self.test_get_version)
        self.run_test("Get Catalog Info", self.test_get_catalog_info)
        self.run_test("Get Tag Schema", self.test_get_tags_schema)
        self.run_test("Basic Search", self.test_search_basic)
        self.run_test("Get Item Count", self.test_get_item_count)
        self.run_test("Get Collections", self.test_get_collections)
        self.run_test("Get Tag Values", self.test_get_tag_values)
        self.run_test("Get Item Metadata", self.test_get_metadata)
        self.run_test("Get Thumbnails", self.test_thumbnails)
        self.run_test("Error Handling", self.test_error_handling)
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Total: {self.passed + self.failed}")
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print(f"\n⚠️  {self.failed} test(s) failed")
        
        print("="*60)
        
        return self.failed == 0


def main():
    """Main entry point"""
    print("\n⚠️  UPDATE CREDENTIALS BEFORE RUNNING!")
    print("     Edit this file and set your server URL, username, and password.\n")
    
    # ========================================================================
    # UPDATE THESE WITH YOUR DAMINION SERVER CREDENTIALS
    # ========================================================================
    BASE_URL = "https://your-server.daminion.net"
    USERNAME = "your_username"
    PASSWORD = "your_password"
    # ========================================================================
    
    # Check if credentials were updated
    if "your-server" in BASE_URL or "your_username" in USERNAME:
        print("❌ ERROR: Please update the credentials in this file first!")
        print("   Look for the BASE_URL, USERNAME, and PASSWORD variables.")
        return False
    
    # Run tests
    tester = DaminionAPITester(BASE_URL, USERNAME, PASSWORD)
    success = tester.run_all_tests()
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
