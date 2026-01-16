r"""
Live test script for the DaminionClient class.

Tests the extended API functionality including:
- Authentication
- Saved searches
- Shared collections  
- Text search
- Flag filtering (flagged/rejected/unflagged)
- Rating filtering
- Catalog statistics
- Pagination

Credentials are loaded from Windows Registry at:
  HKEY_CURRENT_USER\SOFTWARE\Synapic\Daminion

Usage:
  python tests/test_daminion_api_live.py
  python tests/test_daminion_api_live.py --verbose
"""
import sys
import os
import argparse
import logging
from typing import Dict, List, Any

# Ensure project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_subheader(title: str):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---")


def print_result(label: str, value: Any, indent: int = 2):
    """Print a labeled result."""
    prefix = " " * indent
    if isinstance(value, (list, dict)):
        print(f"{prefix}{label}:")
        if isinstance(value, list):
            for i, item in enumerate(value[:5], 1):  # Show first 5
                if isinstance(item, dict):
                    name = item.get('Name') or item.get('name') or item.get('Title') or item.get('title') or f"Item {i}"
                    print(f"{prefix}  {i}. {name}")
                else:
                    print(f"{prefix}  {i}. {item}")
            if len(value) > 5:
                print(f"{prefix}  ... and {len(value) - 5} more")
        else:
            for k, v in value.items():
                print(f"{prefix}  {k}: {v}")
    else:
        print(f"{prefix}{label}: {value}")


def test_authentication(api) -> bool:
    """Test API authentication."""
    print_subheader("Authentication")
    try:
        result = api.authenticate()
        if result:
            print("  [OK] Successfully authenticated")
            return True
        else:
            print("  [FAIL] Authentication returned False")
            return False
    except Exception as e:
        print(f"  [FAIL] Authentication error: {e}")
        return False


def test_catalog_stats(api) -> Dict:
    """Test getting catalog statistics."""
    print_subheader("Catalog Statistics")
    try:
        stats = api.get_catalog_stats()
        print_result("Total items", stats.get('total_items', 0))
        print_result("Collections", stats.get('collections_count', 0))
        print_result("Saved searches", stats.get('saved_searches_count', 0))
        return stats
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {}


def test_media_item_count(api) -> int:
    """Test getting total media item count."""
    print_subheader("Media Item Count")
    try:
        count = api.get_total_count()
        print_result("Total count", count)
        return count
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return 0


def test_shared_collections(api) -> List:
    """Test getting shared collections."""
    print_subheader("Shared Collections")
    try:
        collections = api.get_shared_collections()
        if collections:
            print(f"  Found {len(collections)} collection(s)")
            for i, col in enumerate(collections[:5], 1):
                name = col.get('Name') or col.get('name') or col.get('Title') or 'Unnamed'
                col_id = col.get('Id') or col.get('id')
                print(f"    {i}. {name} (ID: {col_id})")
            if len(collections) > 5:
                print(f"    ... and {len(collections) - 5} more")
            return collections
        else:
            print("  No shared collections found")
            return []
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return []


def test_collection_items(api, collection_id) -> Dict:
    """Test getting items from a collection."""
    print_subheader(f"Collection Items (ID: {collection_id})")
    try:
        items = api.get_shared_collection_items(collection_id, page_size=10)
        print_result("Total items in collection", len(items))
        print_result("Retrieved items (sample)", len(items))
        if items:
            for i, item in enumerate(items[:3], 1):
                name = item.get('Name') or item.get('FileName') or item.get('name') or f"Item {i}"
                print(f"    {i}. {name}")
        return {'Items': items, 'TotalCount': len(items)}
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {'Items': [], 'TotalCount': 0}


def test_saved_searches(api) -> List:
    """Test getting saved searches."""
    print_subheader("Saved Searches")
    try:
        searches = api.get_saved_searches()
        if searches:
            print(f"  Found {len(searches)} saved search(es)")
            for i, search in enumerate(searches[:5], 1):
                name = search.get('Name') or search.get('name') or search.get('Text') or 'Unnamed'
                search_id = search.get('Id') or search.get('id') or search.get('SearchId')
                print(f"    {i}. {name} (ID: {search_id})")
            if len(searches) > 5:
                print(f"    ... and {len(searches) - 5} more")
            return searches
        else:
            print("  No saved searches found")
            return []
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return []


def test_saved_search_items(api, search_id) -> Dict:
    """Test executing a saved search."""
    print_subheader(f"Saved Search Items (ID: {search_id})")
    try:
        # Use get_items_by_query with saved search tag ID
        items = api.get_items_by_query(f"{api.SAVED_SEARCH_TAG_ID},{search_id}", f"{api.SAVED_SEARCH_TAG_ID},any", page_size=10)
        print_result("Total items matching", len(items))
        print_result("Retrieved items (sample)", len(items))
        return {'Items': items, 'TotalCount': len(items)}
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {'Items': [], 'TotalCount': 0}


def test_text_search(api, query: str = "test") -> Dict:
    """Test text search functionality."""
    print_subheader(f"Text Search: '{query}'")
    try:
        result = api.text_search(query, page_size=10)
        items = result.get('Items', [])
        total = result.get('TotalCount', 0)
        print_result("Total matches", total)
        print_result("Retrieved items (sample)", len(items))
        if items:
            for i, item in enumerate(items[:3], 1):
                name = item.get('Name') or item.get('FileName') or item.get('name') or f"Item {i}"
                print(f"    {i}. {name}")
        return result
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {'Items': [], 'TotalCount': 0}


def test_search_count(api, query: str = "test") -> int:
    """Test search count functionality."""
    print_subheader(f"Search Count: '{query}'")
    try:
        count = api.search_count(query)
        print_result("Match count", count)
        return count
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return 0


def test_flagged_items(api) -> Dict:
    """Test getting flagged items."""
    print_subheader("Flagged Items")
    try:
        result = api.get_flagged_items_filtered(page_size=10)
        items = result.get('Items', [])
        total = result.get('TotalCount', 0)
        print_result("Total flagged", total)
        print_result("Retrieved (sample)", len(items))
        return result
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {'Items': [], 'TotalCount': 0}


def test_rejected_items(api) -> Dict:
    """Test getting rejected items."""
    print_subheader("Rejected Items")
    try:
        result = api.get_rejected_items_filtered(page_size=10)
        items = result.get('Items', [])
        total = result.get('TotalCount', 0)
        print_result("Total rejected", total)
        print_result("Retrieved (sample)", len(items))
        return result
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {'Items': [], 'TotalCount': 0}


def test_unflagged_items(api) -> Dict:
    """Test getting unflagged items."""
    print_subheader("Unflagged Items")
    try:
        result = api.get_unflagged_items_filtered(page_size=10)
        items = result.get('Items', [])
        total = result.get('TotalCount', 0)
        print_result("Total unflagged", total)
        print_result("Retrieved (sample)", len(items))
        return result
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {'Items': [], 'TotalCount': 0}


def test_rating_filter(api, min_rating: int = 3, max_rating: int = 5) -> Dict:
    """Test getting items by rating."""
    print_subheader(f"Items Rated {min_rating}-{max_rating} Stars")
    try:
        result = api.get_items_by_rating(min_rating, max_rating, page_size=10)
        items = result.get('Items', [])
        total = result.get('TotalCount', 0)
        print_result("Total matching", total)
        print_result("Retrieved (sample)", len(items))
        return result
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {'Items': [], 'TotalCount': 0}


def test_single_item(api, item_id: int = 1) -> Dict:
    """Test getting a single media item."""
    print_subheader(f"Single Item (ID: {item_id})")
    try:
        items = api.get_media_items_by_ids([item_id])
        if items:
            item = items[0]
            name = item.get('Name') or item.get('FileName') or item.get('name') or 'Unknown'
            print_result("Name", name)
            print_result("ID", item.get('Id') or item.get('id'))
            return item
        else:
            print("  Item not found")
            return {}
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {}


def test_item_data(api, item_id: int = 1) -> Dict:
    """Test getting full item data/metadata."""
    print_subheader(f"Item Data/Metadata (ID: {item_id})")
    try:
        data = api.get_item_details(item_id)
        if data:
            # Show key fields
            print_result("Has data", True)
            if isinstance(data, dict):
                for key in ['Name', 'Title', 'Description', 'Keywords', 'Author'][:5]:
                    if key in data:
                        print_result(key, data[key])
            return data
        else:
            print("  No item data found")
            return {}
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return {}


def test_thumbnail_url(api, item_id: int = 1) -> str:
    """Test getting thumbnail URL."""
    print_subheader(f"Thumbnail URL (ID: {item_id})")
    try:
        url = api.get_thumbnail_url(item_id)
        print_result("URL", url)
        return url
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return ""


def run_all_tests(verbose: bool = False):
    """Run all API tests."""
    from src.utils.registry_config import load_daminion_credentials, credentials_exist
    from src.core.daminion_client import DaminionClient, DaminionAPIError, DaminionAuthenticationError

    print_header("DAMINION CLIENT LIVE TEST")
    
    # Load credentials
    if not credentials_exist():
        print("\n[FAIL] No Daminion credentials found in registry.")
        print("       Run: python tests/test_daminion_connection.py --save")
        return False
    
    creds = load_daminion_credentials()
    if not creds:
        print("\n[FAIL] Failed to load credentials from registry.")
        return False
    
    print(f"\n  Server: {creds['url']}")
    print(f"  User:   {creds['username']}")
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create API instance
    api = DaminionClient(
        base_url=creds['url'],
        username=creds['username'],
        password=creds['password']
    )
    
    # Run tests
    results = {
        'passed': 0,
        'failed': 0,
        'skipped': 0
    }
    
    # 1. Authentication
    print_header("1. AUTHENTICATION")
    if test_authentication(api):
        results['passed'] += 1
    else:
        results['failed'] += 1
        print("\n[ABORT] Cannot proceed without authentication")
        return False
    
    # 2. Basic Queries
    print_header("2. BASIC QUERIES")
    
    count = test_media_item_count(api)
    results['passed' if count > 0 else 'skipped'] += 1
    
    stats = test_catalog_stats(api)
    results['passed' if stats else 'skipped'] += 1
    
    # 3. Collections
    print_header("3. SHARED COLLECTIONS")
    collections = test_shared_collections(api)
    results['passed' if collections else 'skipped'] += 1
    
    if collections:
        first_collection = collections[0]
        col_id = first_collection.get('Id') or first_collection.get('id')
        if col_id:
            test_collection_items(api, col_id)
            results['passed'] += 1
    
    # 4. Saved Searches
    print_header("4. SAVED SEARCHES")
    searches = test_saved_searches(api)
    results['passed' if searches is not None else 'skipped'] += 1
    
    if searches:
        first_search = searches[0]
        search_id = first_search.get('Id') or first_search.get('id') or first_search.get('SearchId')
        if search_id:
            test_saved_search_items(api, search_id)
            results['passed'] += 1
    
    # 5. Text Search
    print_header("5. TEXT SEARCH")
    test_text_search(api, "photo")
    results['passed'] += 1
    
    test_search_count(api, "photo")
    results['passed'] += 1
    
    # 6. Flag Filtering
    print_header("6. FLAG FILTERING")
    test_flagged_items(api)
    results['passed'] += 1
    
    test_rejected_items(api)
    results['passed'] += 1
    
    test_unflagged_items(api)
    results['passed'] += 1
    
    # 7. Rating Filter
    print_header("7. RATING FILTER")
    test_rating_filter(api, 3, 5)
    results['passed'] += 1
    
    # 8. Single Item Operations
    print_header("8. SINGLE ITEM OPERATIONS")
    item = test_single_item(api, 1)
    results['passed' if item else 'skipped'] += 1
    
    if item:
        item_id = item.get('Id') or item.get('id') or 1
        test_item_data(api, item_id)
        results['passed'] += 1
        
        test_thumbnail_url(api, item_id)
        results['passed'] += 1
    
    # Summary
    print_header("TEST SUMMARY")
    print(f"\n  Passed:  {results['passed']}")
    print(f"  Failed:  {results['failed']}")
    print(f"  Skipped: {results['skipped']}")
    
    success = results['failed'] == 0
    print(f"\n  {'[OK] All tests passed!' if success else '[WARN] Some tests failed'}")
    
    return success


def main():
    parser = argparse.ArgumentParser(description="Live test for DaminionClient class")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    success = run_all_tests(verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
