
import logging
import sys
import os

# Add src to sys.path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from src.core.daminion_client import DaminionClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_global_search():
    url = "http://researchserver.juicefilm.local/daminion"
    user = "admin"
    password = "admin"
    
    client = DaminionClient(url, user, password)
    
    try:
        logging.info("Authenticating...")
        if client.authenticate():
            logging.info("Authentication successful!")
            
            # The test query from the user: "CTICC"
            search_query = "5000,cticc"
            search_operators = "5000,all"
            
            logging.info(f"Testing global search with query='{search_query}' and operators='{search_operators}'")
            
            # We'll try calling get_items_by_query
            items = client.get_items_by_query(search_query, search_operators, page_size=10)
            
            if items is not None:
                logging.info(f"Search returned {len(items)} items.")
                for item in items[:5]:
                    logging.info(f"Item: ID={item.get('id') or item.get('uniqueId')}, Name={item.get('name') or item.get('title')}")
            else:
                logging.warning("Search returned None (endpoint might be missing).")
                
            # Let's also try Tag 5000 specifically with just search_items if possible
            # But search_items usually uses a different syntax.
            
            # The user provided: http://researchserver.juicefilm.local/daminion/?query=5000,cticc&operators=5000,all
            # In some Daminion versions, MediaItems/Get also accepts query and operators.
            
            logging.info("Testing MediaItems/Get with global search parameters...")
            endpoint = f"/api/MediaItems/Get?query={search_query}&operators={search_operators}&start=0&length=10"
            response = client._make_request(endpoint)
            
            items_get = response.get('mediaItems') or response.get('items') or response.get('data') or []
            logging.info(f"MediaItems/Get returned {len(items_get)} items.")
            for item in items_get[:5]:
                 logging.info(f"Item: ID={item.get('id') or item.get('uniqueId')}, Name={item.get('name') or item.get('title')}")

        else:
            logging.error("Authentication failed.")
    except Exception as e:
        logging.exception(f"An error occurred: {e}")

if __name__ == "__main__":
    test_global_search()
