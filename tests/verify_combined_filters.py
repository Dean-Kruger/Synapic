import os
import sys
import logging
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.daminion_client import DaminionClient
from src.utils.registry_config import load_daminion_credentials

logging.basicConfig(level=logging.INFO, format='%(message)s')

def test_cumulative_filters():
    creds = load_daminion_credentials()
    if not creds:
        print("Failed to load credentials")
        return

    client = DaminionClient(creds['url'], creds['username'], creds['password'])
    
    # Keyword "alp" ID from browser discovery was 4346
    # Keywords Tag ID is 13 (usually)
    kw_tag = 13
    kw_val = 4346
    
    # Flag Tag ID is 42
    flag_tag = 42
    flag_val = 2 # Flagged
    
    print("\n--- 1. Keyword ONLY Search ('alp') ---")
    query1 = f"{kw_tag},{kw_val}"
    ops1 = f"{kw_tag},all"
    count1 = client.search_count(query1, operators=ops1)
    items1 = client.get_items_by_query(query1, ops1, page_size=5)
    print(f"Count: {count1}")
    print(f"Retrieved: {len(items1)} items")

    print("\n--- 2. Flag ONLY Search (Flagged) ---")
    query2 = f"{flag_tag},{flag_val}"
    ops2 = f"{flag_tag},any"
    count2 = client.search_count(query2, operators=ops2)
    items2 = client.get_items_by_query(query2, ops2, page_size=5)
    print(f"Count: {count2}")
    print(f"Retrieved: {len(items2)} items")

    print("\n--- 3. Combined Search ('alp' + Flagged) ---")
    query3 = f"{kw_tag},{kw_val};{flag_tag},{flag_val}"
    ops3 = f"{kw_tag},all;{flag_tag},any"
    count3 = client.search_count(query3, operators=ops3)
    items3 = client.get_items_by_query(query3, ops3, page_size=5)
    print(f"Count: {count3}")
    print(f"Retrieved: {len(items3)} items")
    
    # Sanity check: Combined count should be <= individual counts
    if count3 > count1 or count3 > count2:
         print("WARNING: Combined count is higher than individual counts. Parameter joining might be wrong.")
    else:
         print("SUCCESS: Combined count logic seems correct.")

if __name__ == "__main__":
    test_cumulative_filters()
