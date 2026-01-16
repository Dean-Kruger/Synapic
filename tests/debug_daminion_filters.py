
import os
import sys
import logging
import urllib.parse
from pathlib import Path

# Add project root to PYTHONPATH
project_root = Path(r"c:\Users\Dean\Source code\Synapic")
sys.path.append(str(project_root))

from src.core.daminion_client import DaminionClient
from src.utils.registry_config import load_daminion_credentials

logging.basicConfig(level=logging.INFO, format='%(message)s')

def test_filters():
    creds = load_daminion_credentials()
    if not creds:
        print("Could not load Daminion credentials from registry.")
        return

    client = DaminionClient(creds['url'], creds['username'], creds['password'])
    if not client.authenticate():
        print("Failed to authenticate.")
        return

    print(f"\n--- Daminion Filter Debug ---")
    print(f"Server: {creds['url']}")
    
    # 1. Check Tag Schema for Saved Searches and Shared Collections
    tags = client._tag_id_map
    print(f"\n[TAGS] Detected Tag IDs:")
    for name in ['Keywords', 'Flag', 'Rating', 'Saved Searches', 'Shared Collections', 'Collections']:
        print(f"  {name}: {tags.get(name) or tags.get(name.lower())}")

    # 2. Test GetCount with various Flag queries
    flag_queries = [
        "Flag:=1", "Flag:=-1", "Flag:=0",
        "flag:flagged", "flag:rejected", "flag:unflagged",
        "Pick:=1", "Pick:=-1", "Pick:=0"
    ]
    
    tag_id = tags.get('Flag') or 0 # Need to check if Flag has an ID
    
    print(f"\n--- Testing Flag Counts ---")
    for q in flag_queries:
        # Try discovered queryLine syntax
        params = {"queryLine": q, "force": "false"}
        endpoint = f"/api/MediaItems/GetCount?{urllib.parse.urlencode(params)}"
        try:
            resp = client._make_request(endpoint)
            print(f"Query '{q}' (queryLine) -> {resp}")
        except Exception as e:
            print(f"Query '{q}' (queryLine) -> ERROR: {e}")

        # Try search syntax
        params = {"search": q}
        endpoint = f"/api/MediaItems/GetCount?{urllib.parse.urlencode(params)}"
        try:
            resp = client._make_request(endpoint)
            print(f"Query '{q}' (search)    -> {resp}")
        except Exception as e:
            print(f"Query '{q}' (search)    -> ERROR: {e}")

    # 3. Test Saved Searches
    print(f"\n--- Testing Saved Searches ---")
    # First, list some saved searches to get IDs
    try:
        ss_id = client.SAVED_SEARCH_TAG_ID
        endpoint = f"/api/IndexedTagValues/{ss_id}"
        resp = client._make_request(endpoint)
        if isinstance(resp, list) and resp:
            print(f"Found {len(resp)} Saved Searches. testing first 3:")
            for ss in resp[:3]:
                ss_name = ss.get('value')
                ss_val_id = ss.get('id')
                print(f"  SS: '{ss_name}' (ID: {ss_val_id})")
                
                # Test count for this saved search
                # Try discovery syntax: queryLine=39,ID
                params = {"queryLine": f"{ss_id},{ss_val_id}", "f": f"{ss_id},all"}
                ep_count = f"/api/MediaItems/GetCount?{urllib.parse.urlencode(params)}"
                count_resp = client._make_request(ep_count)
                print(f"    Count (queryLine={ss_id},{ss_val_id}) -> {count_resp}")
                
    except Exception as e:
        print(f"Error testing Saved Searches: {e}")

    # 4. Test Shared Collections
    print(f"\n--- Testing Shared Collections ---")
    try:
        sc_id = client.SHARED_COLLECTIONS_TAG_ID
        endpoint = f"/api/SharedCollection/Get"
        resp = client._make_request(endpoint)
        if isinstance(resp, list) and resp:
            print(f"Found {len(resp)} Shared Collections. testing first 3:")
            for sc in resp[:3]:
                sc_name = sc.get('name') or sc.get('Title')
                sc_val_id = sc.get('id')
                print(f"  SC: '{sc_name}' (ID: {sc_val_id})")
                
                # Test item retrieval
                ep_items = f"/api/MediaItems/Get?queryLine={sc_id},{sc_val_id}&f={sc_id},all&index=0&size=10"
                items_resp = client._normalize_items_response(client._make_request(ep_items))
                print(f"    Items Count (Get via queryLine) -> {items_resp.get('TotalCount')} (Items: {len(items_resp.get('Items', []))})")
                
                # Test GetDetails if available
                try:
                    ep_details = f"/api/SharedCollection/GetDetails/{sc_val_id}"
                    details = client._make_request(ep_details)
                    print(f"    GetDetails keys: {list(details.keys()) if isinstance(details, dict) else 'Not a dict'}")
                    if isinstance(details, dict):
                        print(f"    GetDetails itemCount: {details.get('itemCount')}")
                except:
                    pass
    except Exception as e:
        print(f"Error testing Shared Collections: {e}")

if __name__ == "__main__":
    test_filters()
