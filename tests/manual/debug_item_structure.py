import sys
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.daminion_client import DaminionClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    # Use credentials from existing config if possible, or common defaults
    base_url = "http://researchserver.juicefilm.local/daminion"
    username = "admin"
    password = "admin" # Based on previous conversations
    
    client = DaminionClient(base_url, username, password)
    if not client.authenticate():
        print("Failed to authenticate")
        return

    # Use item ID from logs
    item_id = 883889
    
    print(f"\n--- Testing verify_metadata.get_record_metadata for item {item_id} ---")
    try:
        from tests.verify_metadata import get_record_metadata
        metadata = get_record_metadata(client, item_id)
        print(f"Metadata outcome: {metadata}")
        if metadata:
            print(f"Keywords found: {len(metadata.get('keywords', []))}")
            print(f"Categories found: {len(metadata.get('categories', []))}")
            print(f"Description length: {len(metadata.get('description', ''))}")
    except Exception as e:
        print(f"Error calling get_record_metadata: {e}")

if __name__ == "__main__":
    main()
