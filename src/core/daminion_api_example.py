"""
Daminion API Usage Examples

This file demonstrates common usage patterns for the new DaminionAPI client.
Run this to test your Daminion connection and see the API in action.
"""

from daminion_api import DaminionAPI


def example_basic_search():
    """Example 1: Basic text search"""
    print("\n=== Example 1: Basic Search ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Simple text search
        items = api.media_items.search(query="city", page_size=10)
        print(f"Found {len(items)} items matching 'city'")
        
        for item in items[:5]:  # Show first 5
            print(f"  - {item.get('filename', 'Unknown')}")


def example_get_collections():
    """Example 2: List shared collections"""
    print("\n=== Example 2: Shared Collections ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Get all collections
        collections = api.collections.get_all()
        print(f"Found {len(collections)} shared collections:")
        
        for coll in collections:
            print(f"  {coll.name}: {coll.item_count} items (code: {coll.code})")


def example_tag_operations():
    """Example 3: Working with tags"""
    print("\n=== Example 3: Tag Operations ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Get tag schema
        print("Getting tag schema...")
        tags = api.tags.get_all_tags()
        
        print(f"Catalog has {len(tags)} tags:")
        for tag in tags[:10]:  # Show first 10
            print(f"  {tag.name} (ID: {tag.id})")
        
        # Find Keywords tag
        keywords_tag = next((t for t in tags if t.name == "Keywords"), None)
        
        if keywords_tag:
            print(f"\nGetting keyword values (tag ID: {keywords_tag.id})...")
            keyword_values = api.tags.get_tag_values(
                tag_id=keywords_tag.id,
                page_size=20
            )
            
            print(f"Found {len(keyword_values)} keyword values:")
            for kw in keyword_values[:10]:
                print(f"  {kw.text} ({kw.count} items)")


def example_structured_search():
    """Example 4: Structured search by tag value"""
    print("\n=== Example 4: Structured Search ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Get tag schema
        tags = api.tags.get_all_tags()
        keywords_tag = next((t for t in tags if t.name == "Keywords"), None)
        
        if not keywords_tag:
            print("Keywords tag not found!")
            return
        
        # Find a specific keyword
        keyword_values = api.tags.find_tag_values(
            tag_id=keywords_tag.id,
            filter_text="city"
        )
        
        if keyword_values:
            value_id = keyword_values[0].id
            print(f"Found keyword 'city' with ID: {value_id}")
            
            # Search for items with this keyword
            items = api.media_items.search(
                query_line=f"{keywords_tag.id},{value_id}",
                operators=f"{keywords_tag.id},any",
                page_size=10
            )
            
            print(f"Found {len(items)} items with keyword 'city':")
            for item in items[:5]:
                print(f"  - {item.get('filename', 'Unknown')}")


def example_batch_tagging():
    """Example 5: Batch tag items"""
    print("\n=== Example 5: Batch Tagging ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Search for items
        items = api.media_items.search(query="landscape", page_size=5)
        
        if not items:
            print("No items found to tag")
            return
        
        item_ids = [item['id'] for item in items]
        print(f"Found {len(item_ids)} items to tag")
        
        # Get tag schema
        tags = api.tags.get_all_tags()
        keywords_tag = next((t for t in tags if t.name == "Keywords"), None)
        
        if not keywords_tag:
            print("Keywords tag not found!")
            return
        
        # Find or get keyword value ID
        keyword_values = api.tags.find_tag_values(
            tag_id=keywords_tag.id,
            filter_text="nature"
        )
        
        if keyword_values:
            value_id = keyword_values[0].id
            
            print(f"Applying keyword 'nature' (ID: {value_id}) to {len(item_ids)} items...")
            
            # Batch update
            api.item_data.batch_update(
                item_ids=item_ids,
                operations=[{
                    "guid": keywords_tag.guid,
                    "id": value_id,
                    "remove": False
                }]
            )
            
            print("✓ Tags applied successfully!")


def example_get_metadata():
    """Example 6: Get item metadata"""
    print("\n=== Example 6: Item Metadata ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Get an item
        items = api.media_items.search(query="*", page_size=1)
        
        if not items:
            print("No items found")
            return
        
        item_id = items[0]['id']
        print(f"Getting metadata for item {item_id}...")
        
        # Get full metadata
        metadata = api.item_data.get(item_id, get_all=True)
        
        # Display metadata
        print(f"\nMetadata for {items[0].get('filename', 'Unknown')}:")
        
        for group in metadata.get('properties', []):
            print(f"\n{group['groupName']}:")
            for prop in group.get('properties', []):
                value = prop.get('propertyValue', '')
                if value:
                    print(f"  {prop['propertyName']}: {value}")


def example_server_info():
    """Example 7: Get server information"""
    print("\n=== Example 7: Server Information ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Get server version
        version = api.settings.get_version()
        print(f"Daminion version: {version}")
        
        # Get catalog GUID
        catalog_guid = api.settings.get_catalog_guid()
        print(f"Catalog GUID: {catalog_guid}")
        
        # Get current user
        user = api.settings.get_logged_user()
        print(f"Logged in as: {user.get('username', 'Unknown')}")
        
        # Get permissions
        rights = api.settings.get_rights()
        print("\nUser permissions:")
        for right, enabled in rights.items():
            if enabled:
                print(f"  ✓ {right}")


def example_download_file():
    """Example 8: Download a file"""
    print("\n=== Example 8: Download File ===")
    
    with DaminionAPI(
        base_url="https://your-server.daminion.net",
        username="your_username",
        password="your_password"
    ) as api:
        # Get an item
        items = api.media_items.search(query="*", page_size=1)
        
        if not items:
            print("No items found")
            return
        
        item_id = items[0]['id']
        filename = items[0].get('filename', f'download_{item_id}.jpg')
        
        print(f"Downloading {filename}...")
        
        # Download original file
        file_data = api.downloads.get_original(item_id)
        
        # Save to disk
        with open(filename, 'wb') as f:
            f.write(file_data)
        
        print(f"✓ Saved to {filename} ({len(file_data)} bytes)")


def example_error_handling():
    """Example 9: Error handling"""
    print("\n=== Example 9: Error Handling ===")
    
    from daminion_api import (
        DaminionAuthenticationError,
        DaminionNotFoundError,
        DaminionAPIError
    )
    
    try:
        with DaminionAPI(
            base_url="https://your-server.daminion.net",
            username="wrong_user",
            password="wrong_password"
        ) as api:
            items = api.media_items.search(query="test")
            
    except DaminionAuthenticationError as e:
        print(f"✓ Caught authentication error: {e}")
        
    except DaminionNotFoundError as e:
        print(f"Resource not found: {e}")
        
    except DaminionAPIError as e:
        print(f"API error: {e}")
        
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Daminion API Examples")
    print("=" * 60)
    
    # UPDATE THESE WITH YOUR SERVER DETAILS
    print("\n⚠️  Remember to update the server URL and credentials in this file!")
    print("    Then run the examples you want to test.\n")
    
    # Uncomment the examples you want to run:
    
    # example_basic_search()
    # example_get_collections()
    # example_tag_operations()
    # example_structured_search()
    # example_batch_tagging()
    # example_get_metadata()
    # example_server_info()
    # example_download_file()
    # example_error_handling()
    
    print("\n✓ Examples complete!")
