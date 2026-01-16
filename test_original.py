import sys
import os
import logging

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.core.daminion_client import DaminionClient

logging.basicConfig(level=logging.DEBUG)

def test_original():
    url = "http://researchserver.juicefilm.local/daminion"
    user = "admin"
    pwd = "admin"
    
    print(f"Testing original DaminionClient with {url}...")
    try:
        client = DaminionClient(url, user, pwd)
        if client.authenticate():
            print("Original client SUCCESS!")
            count = client.get_total_count()
            print(f"Count: {count}")
            
            print("Testing shared collections...")
            collections = client.get_shared_collections()
            print(f"Found {len(collections)} shared collections.")
        else:
            print("Original client FAILED.")
    except Exception as e:
        print(f"Original client ERROR: {e}")

if __name__ == "__main__":
    test_original()
