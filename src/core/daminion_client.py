
"""
Daminion DAMS API Client for retrieving and updating media items.
"""

import logging
import urllib.request
import urllib.parse
import urllib.error
import json
import atexit
import weakref
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
import tempfile

class DaminionAPIError(Exception):
    """Custom exception for Daminion API errors."""
    pass

class DaminionAuthenticationError(DaminionAPIError):
    """Raised when authentication fails."""
    pass

class DaminionNetworkError(DaminionAPIError):
    """Raised when network operations fail."""
    pass

class DaminionRateLimitError(DaminionAPIError):
    """Raised when rate limit is exceeded."""
    pass

class DaminionClient:
    """Client for interacting with Daminion Server Web API.

    Supports context manager protocol for automatic cleanup:
        with DaminionClient(url, user, pass) as client:
            items = client.get_media_items()
    """

    _instances = weakref.WeakSet()

    def __init__(self, base_url: str, username: str, password: str, rate_limit: float = 0.1):
        """
        Initialize Daminion client.

        Args:
            base_url: Base URL of Daminion server (e.g., https://interiors.daminion.net)
            username: Daminion username
            password: Daminion password
            rate_limit: Minimum seconds between API calls (default: 0.1)
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.cookies = {}
        self.authenticated = False
        self.temp_dir = Path(tempfile.gettempdir()) / "daminion_cache"
        self.temp_dir.mkdir(exist_ok=True)
        self.rate_limit = rate_limit
        self._last_request_time = 0.0
        self._search_endpoint_unavailable = False
        self._structured_query_unavailable = False
        self._tag_map = {}  # Cache for Tag Name -> GUID mapping
        self._tag_id_map = {} # Cache for Tag Name -> Integer ID mapping (for indexedTagValues)

        DaminionClient._instances.add(self)
        atexit.register(self.cleanup_temp_files)

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and cleanup resources."""
        self.cleanup_temp_files()
        return False

    def authenticate(self) -> bool:
        """
        Authenticate with Daminion server and store session cookies.

        Returns:
            True if authentication successful, False otherwise

        Raises:
            DaminionAPIError: If authentication fails
        """
        logging.info(f"[DAMINION] Starting authentication to {self.base_url}...")
        try:
            params = urllib.parse.urlencode({
                "userName": self.username,
                "password": self.password
            })
            login_url = f"{self.base_url}/api/UserManager/Login?{params}"
            logging.debug(f"[DAMINION] Login URL: {self.base_url}/api/UserManager/Login")

            request = urllib.request.Request(login_url, method='POST')
            logging.debug(f"[DAMINION] Sending POST request to login endpoint...")

            logging.debug(f"[DAMINION] Opening connection with 30s timeout...")
            with urllib.request.urlopen(request, timeout=30) as response:
                logging.info(f"[DAMINION] Received response with status: {response.status}")
                if response.status != 200:
                    raise DaminionAPIError(f"Login failed with status {response.status}")

                # Extract session cookies
                logging.debug(f"[DAMINION] Extracting session cookies from response headers...")
                for header, value in response.headers.items():
                    if header.lower() == 'set-cookie':
                        cookie_parts = value.split(';')[0].split('=', 1)
                        if len(cookie_parts) == 2:
                            self.cookies[cookie_parts[0]] = cookie_parts[1]
                            logging.debug(f"[DAMINION] Stored cookie: {cookie_parts[0]}")

                if not self.cookies:
                    raise DaminionAPIError("No session cookies received from server")

                self.authenticated = True
                logging.info(f"[DAMINION] [OK] Successfully authenticated to {self.base_url} as {self.username}")
                logging.info(f"[DAMINION] Session has {len(self.cookies)} cookie(s)")
                
                # Fetch tag schema to populate GUID map
                self.get_tag_schema()
                
                return True

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            logging.error(f"[DAMINION] [ERROR] Authentication failed: {error_msg}")
            raise DaminionAuthenticationError(f"Authentication failed: {error_msg}")
        except urllib.error.URLError as e:
            logging.error(f"[DAMINION] [ERROR] Network error during authentication: {e}")
            raise DaminionNetworkError(f"Network error: {e}")
        except Exception as e:
            logging.exception(f"[DAMINION] [ERROR] Unexpected authentication error")
            raise DaminionAuthenticationError(f"Authentication error: {e}")

    def _get_cookie_header(self) -> str:
        """Generate cookie header string from stored cookies."""
        return "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        if self.rate_limit > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit:
                sleep_time = self.rate_limit - elapsed
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _make_request(self, endpoint: str, method: str = 'GET',
                     data: Optional[Dict] = None, timeout: int = 30) -> Dict:
        """
        Make authenticated API request with rate limiting.

        Args:
            endpoint: API endpoint (e.g., '/api/MediaItems/Get')
            method: HTTP method (GET, POST, etc.)
            data: Optional request body data
            timeout: Request timeout in seconds

        Returns:
            Response data as dictionary

        Raises:
            DaminionAuthenticationError: If not authenticated
            DaminionNetworkError: If network error occurs
            DaminionAPIError: If request fails
        """
        if not self.authenticated:
            raise DaminionAuthenticationError("Not authenticated. Call authenticate() first.")

        self._rate_limit()

        url = f"{self.base_url}{endpoint}"
        logging.debug(f"[DAMINION] API Request: {method} {endpoint}")

        try:
            request_data = None
            if data and method == 'POST':
                request_data = json.dumps(data).encode('utf-8')
                logging.debug(f"[DAMINION] Request body size: {len(request_data)} bytes")

            request = urllib.request.Request(url, data=request_data, method=method)
            request.add_header('Cookie', self._get_cookie_header())
            request.add_header('Content-Type', 'application/json')
            logging.debug(f"[DAMINION] Opening request with {timeout}s timeout...")

            with urllib.request.urlopen(request, timeout=timeout) as response:
                logging.debug(f"[DAMINION] Response status: {response.status}")
                body = response.read().decode('utf-8')
                logging.debug(f"[DAMINION] Response body size: {len(body)} bytes")
                result = json.loads(body)
                logging.debug(f"[DAMINION] [OK] API request successful")
                return result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            error_msg = f"HTTP {e.code}: {e.reason} - {error_body}"
            logging.error(f"[DAMINION] [ERROR] API request failed: {error_msg}")
            logging.error(f"[DAMINION] Failed endpoint: {method} {endpoint}")
            if e.code == 429:
                raise DaminionRateLimitError(f"Rate limit exceeded: {error_msg}")
            elif e.code in (401, 403):
                raise DaminionAuthenticationError(f"Authentication error: {error_msg}")
            raise DaminionAPIError(error_msg)
        except urllib.error.URLError as e:
            logging.error(f"[DAMINION] [ERROR] Network error: {e}")
            logging.error(f"[DAMINION] Failed endpoint: {method} {endpoint}")
            raise DaminionNetworkError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"[DAMINION] [ERROR] Invalid JSON response: {e}")
            raise DaminionAPIError(f"Invalid JSON response: {e}")
        except (DaminionAPIError, DaminionAuthenticationError, DaminionNetworkError, DaminionRateLimitError):
            raise
        except Exception as e:
            logging.exception(f"[DAMINION] [ERROR] Unexpected API request error: {url}")
            raise DaminionAPIError(f"Request error: {e}")

    def get_total_count(self) -> int:
        """
        Get total number of items in catalog.

        Returns:
            Total number of media items
        """
        logging.info(f"[DAMINION] Fetching total item count...")
        endpoint = "/api/MediaItems/GetCount"
        response = self._make_request(endpoint)
        total = response.get('data', 0)
        logging.info(f"[DAMINION] [OK] Total items in catalog: {total}")
        return total

    def get_media_items_by_ids(self, item_ids: List[int]) -> List[Dict]:
        """
        Retrieve specific media items by their IDs.

        Args:
            item_ids: List of item IDs to retrieve

        Returns:
            List of media items
        """
        if not item_ids:
            return []

        ids_str = ",".join(str(id) for id in item_ids)
        endpoint = f"/api/MediaItems/GetByIds?ids={ids_str}"
        response = self._make_request(endpoint)

        items = response.get('mediaItems', [])
        logging.info(f"Retrieved {len(items)} items from {len(item_ids)} IDs")
        return items

    def get_media_items(self, start_id: int = 1, batch_size: int = 100) -> Tuple[List[Dict], int]:
        """
        Retrieve media items from Daminion by ID range.

        Args:
            start_id: Starting ID (1-based)
            batch_size: Number of IDs to request

        Returns:
            Tuple of (list of media items, total count in catalog)

        Note:
            Daminion uses sequential IDs but not all IDs may exist.
            This method requests a range and returns only existing items.
        """
        total_count = self.get_total_count()
        item_ids = list(range(start_id, start_id + batch_size))
        items = self.get_media_items_by_ids(item_ids)

        logging.info(f"Retrieved {len(items)} items (catalog total: {total_count})")
        return items, total_count

    def get_all_items_paginated(self, batch_size: int = 100, max_items: Optional[int] = None, 
                              progress_callback: Optional[Callable[[int, int], None]] = None,
                              stop_event: Optional[Any] = None) -> List[Dict]:
        """
        Retrieve all media items with pagination.

        Args:
            batch_size: Number of items to fetch per batch
            max_items: Maximum number of items to retrieve (None = all)
            progress_callback: Optional function(current_count, total_count)
            stop_event: Optional event object with is_set() method to check for cancellation

        Returns:
            List of all media items
        """
        logging.info(f"[DAMINION] ========== STARTING PAGINATED FETCH ==========")
        logging.info(f"[DAMINION] Batch size: {batch_size}, Max items: {max_items or 'all'}")

        total_count = self.get_total_count()
        all_items = []
        current_id = 1
        batch_num = 0

        if max_items:
            total_count = min(total_count, max_items)

        logging.info(f"[DAMINION] Target: {total_count} items from Daminion")
        logging.info(f"[DAMINION] Estimated batches: {(total_count // batch_size) + 1}")

        # Initial progress update
        if progress_callback:
            progress_callback(0, total_count)

        while len(all_items) < total_count and current_id < total_count + batch_size:
            if stop_event and stop_event.is_set():
                logging.info("[DAMINION] Fetch cancelled by user.")
                break

            batch_num += 1
            logging.info(f"[DAMINION] --- Batch {batch_num} ---")
            logging.info(f"[DAMINION] Requesting IDs {current_id} to {min(current_id + batch_size - 1, total_count + batch_size - 1)}")

            item_ids = list(range(current_id, min(current_id + batch_size, total_count + batch_size)))
            logging.debug(f"[DAMINION] Fetching {len(item_ids)} item IDs...")

            batch_items = self.get_media_items_by_ids(item_ids)
            logging.info(f"[DAMINION] [OK] Received {len(batch_items)} items in batch {batch_num}")

            if batch_items:
                all_items.extend(batch_items)
                if progress_callback:
                    progress_callback(len(all_items), total_count)
            else:
                logging.debug("[DAMINION] Empty batch returned, skipping...")

            current_id += batch_size # Simply increment by batch size
            
            # Rate limiting / polite pause
            time.sleep(0.1) 
            
            if max_items and len(all_items) >= max_items:
                all_items = all_items[:max_items]
                logging.info(f"[DAMINION] Reached max_items limit, stopping")
                break

            if not batch_items:
                logging.warning(f"[DAMINION] Empty batch received, stopping pagination")
                break

        logging.info(f"[DAMINION] ========== FETCH COMPLETE ==========")
        logging.info(f"[DAMINION] [OK] Retrieved total of {len(all_items)} items in {batch_num} batches")
        return all_items

    def get_shared_collections(self, index: int = 0, page_size: int = 100) -> List[Dict]:
        """Retrieve list of shared collections available on the server.

        Returns a list of collection metadata dictionaries. Uses the
        /api/SharedCollection/GetCollections endpoint.
        """
        endpoint = f"/api/SharedCollection/GetCollections?index={index}&pageSize={page_size}"
        try:
            logging.info(f"[DEBUG] Fetching shared collections from {endpoint}")
            response = self._make_request(endpoint)
            # response shape may vary; handle both dict and list responses
            logging.info(f"[DEBUG] Raw response type: {type(response)}")
            logging.debug(f"[DEBUG] Raw response: {response}")

            if isinstance(response, list):
                # response is already a list
                logging.info(f"[DEBUG] Response is list with {len(response)} items")
                return response
            elif isinstance(response, dict):
                # response is a dict, try common keys
                collections = response.get('collections') or response.get('items') or response.get('data')
                logging.info(f"[DEBUG] Extracted 'collections': {type(collections)} (Keys found: {[k for k in response.keys()]})")
                
                if isinstance(collections, dict):
                    # sometimes API wraps in data/results
                    return list(collections.values())
                return collections if isinstance(collections, list) else []
            else:
                # unexpected response type
                logging.warning(f"[DEBUG] Unexpected response type: {type(response)}")
                return []
        except Exception as e:
            logging.exception("Failed to fetch shared collections")
            return []

    def get_shared_collection_items(self, collection_id: str | int, index: int = 0, page_size: int = 200) -> List[Dict]:
        """Retrieve items for a shared collection.

        Calls /api/SharedCollection/GetItems and expects a collection identifier value
        to be passed as a parameter. The exact server-side parameters may vary by
        Daminion version; we attempt common query names.
        """
        # try a couple of common parameter formats to support different server versions
        tried = [
            f"/api/SharedCollection/GetItems?id={collection_id}&index={index}&pageSize={page_size}",
            f"/api/SharedCollection/GetItems?collectionId={collection_id}&index={index}&pageSize={page_size}",
            f"/api/SharedCollection/PublicItems/{collection_id}/{index}/{page_size}/0/true"
        ]

        for endpoint in tried:
            try:
                response = self._make_request(endpoint)
                items = response.get('mediaItems') or response.get('items') or response.get('data') or response.get('collections') or response
                if isinstance(items, dict):
                     # Handle dictionary response {id: item, ...}
                    return list(items.values())
                if isinstance(items, list):
                    return items
            except Exception:
                continue

        logging.warning(f"Could not retrieve items for shared collection {collection_id}")
        return []

    def get_items_by_query(self, query: str, operators: str, index: int = 0, page_size: int = 500) -> Optional[List[Dict]]:
        """
        Search for items using a structured query string, common in some Daminion API versions.

        Args:
            query: The query string (e.g., '42,2,3' for Flag=Flagged or Rejected).
            operators: The operators for the query (e.g., '42,any').
            index: The starting index for pagination.
            page_size: The number of items to return per page.

        Returns:
            A list of media items, or None if the endpoint is not supported.
        """
        if self._structured_query_unavailable:
            logging.warning("[DAMINION] Structured query endpoint is unavailable.")
            return None

        logging.info(f"[DAMINION] Searching items with structured query: '{query}'")
        endpoint = f"/api/MediaItems/GetByQuery?query={query}&operators={operators}&start={index}&length={page_size}"

        try:
            response = self._make_request(endpoint, method='GET')
            items = response.get('mediaItems', [])
            logging.info(f"[DAMINION] [OK] Structured query returned {len(items)} items")
            return items
        except DaminionAPIError as e:
            if "404" in str(e):
                logging.warning("[DAMINION] Structured query endpoint '/api/MediaItems/GetByQuery' not found (404).")
                self._structured_query_unavailable = True
                return None
            raise


    def search_items(self, query: str, index: int = 0, page_size: int = 200) -> Optional[List[Dict]]:
        """
        Search for items on the server using a query string.
        Falls back to client-side filtering if the search endpoint is not available.

        Args:
            query: The search query (e.g., 'status:untagged', 'flag:rejected').
            index: The starting index for pagination.
            page_size: The number of items to return per page.

        Returns:
            A list of media items matching the search query, or None if fallback is needed.
        """
        if self._search_endpoint_unavailable:
            logging.warning("[DAMINION] Search endpoint is unavailable, cannot perform server-side search.")
            return None

        logging.info(f"[DAMINION] Searching items with query: '{query}'")
        endpoint = "/api/MediaItems/Search"
        data = {
            "search": query,
            "start": index,
            "length": page_size
        }
        try:
            response = self._make_request(endpoint, method='POST', data=data)
            items = response.get('mediaItems', [])
            logging.info(f"[DAMINION] [OK] Server-side search returned {len(items)} items")
            return items
        except DaminionAPIError as e:
            if "404" in str(e):
                logging.warning("[DAMINION] Search endpoint not found (404). Falling back to client-side filtering.")
                self._search_endpoint_unavailable = True
                return None
            raise


    def get_flagged_items(self, batch_size=50, max_items=200) -> List[Dict]:
        """
        Retrieve media items flagged as 'Flagged'.
        Returns:
            List of media item dicts
        """
        # Strategy: Find "Flag" tag ID and "Flagged" value ID dynamically
        flag_tag_name = "Flag"
        flag_value_name = "Flagged" # Could also be "Rejected" if user prefers
        
        # Ensure schema logic ran (populates _tag_id_map)
        if not self._tag_id_map:
             self.get_tag_schema()

        flag_tag_id = self._tag_id_map.get(flag_tag_name) or self._tag_id_map.get(flag_tag_name.lower())
        
        if flag_tag_id:
             logging.info(f"[DAMINION] Found 'Flag' tag ID: {flag_tag_id}. Fetching values...")
             try:
                 # Use verified endpoint: api/indexedTagValues/getIndexedTagValues
                 endpoint_vals = f"/api/indexedTagValues/getIndexedTagValues?indexedTagId={flag_tag_id}&pageIndex=0&pageSize=100"
                 vals = self._make_request(endpoint_vals)
                 
                 items_list = []
                 if isinstance(vals, dict):
                     items_list = vals.get('values') or vals.get('items') or []
                     
                 flagged_value_id = None
                 for v in items_list:
                     v_name = v.get('value') or v.get('name') or v.get('title')
                     if v_name and v_name.lower() == flag_value_name.lower():
                         flagged_value_id = v.get('id') or v.get('valueId')
                         break
                 
                 if flagged_value_id:
                      logging.info(f"[DAMINION] Found 'Flagged' value ID: {flagged_value_id}. Querying items...")
                      # Query: {TagID},{ValueID} using get_items_by_query
                      # Operators: {TagID},any
                      query_str = f"{flag_tag_id},{flagged_value_id}"
                      op_str = f"{flag_tag_id},any"
                      
                      items = self.get_items_by_query(query_str, op_str, page_size=max_items or 500)
                      if items is not None:
                           return items
                      
             except Exception as e:
                 logging.warning(f"[DAMINION] Failed to fetch Flag values: {e}")

        # Fallback: Text searches
        logging.info("[DAMINION] Trying text search 'Flag:Flagged'...")
        items = self.search_items(query="Flag:Flagged", page_size=max_items or 500)
        if items: 
            return items

        logging.warning("[DAMINION] Falling back to 'status:flagged' text search.")
        items = self.search_items(query="status:flagged", page_size=max_items or 500)
        if items:
             return items
             
        logging.warning("[DAMINION] Could not find flagged items via search. Aborting to avoid full catalog scan.")
        return []

    def get_tag_schema(self) -> Dict[str, str]:
        """
        Fetch the default layout to map Tag Names (e.g., 'Keywords') to their internal GUIDs.
        
        Returns:
            Dictionary mapping Tag Name -> GUID
        """
        logging.info("[DAMINION] Fetching tag schema (Layout) to map Tag Names to GUIDs...")
        endpoint = "/api/ItemData/GetDefaultLayout"
        try:
            response = self._make_request(endpoint)
            # Response format: { "properties": [ { "properties": [ { "propertyName": "Keywords", "propertyGuid": "..." } ... ] } ... ] }
            
            # Recursively find properties
            def extract_properties(obj):
                if isinstance(obj, dict):
                    p_name = obj.get('propertyName') or obj.get('name') or obj.get('tagName')
                    p_guid = obj.get('propertyGuid') or obj.get('guid') or obj.get('id')
                    
                    # Store if we have both (and check if p_name is string to avoid crashes)
                    if p_name and p_guid and isinstance(p_name, str):
                        # Normalize to title case or lower case? Daminion seems case-sensitive mostly but let's store as is
                        # We might want to store 'lower' -> guid for case-insensitive lookup
                        self._tag_map[p_name] = str(p_guid)
                        # Also store lowercase version for robust lookup
                        self._tag_map[p_name.lower()] = str(p_guid)
                        
                        # DEBUG: Check if we have an integer ID in the fields
                        if p_name == "Collections" or p_name == "Flag":
                             logging.info(f"[DAMINION] DEBUG Schema Object for '{p_name}': {obj.keys()}")
                             if 'id' in obj:
                                 logging.info(f"[DAMINION] DEBUG ID for '{p_name}': {obj['id']} (Type: {type(obj['id'])})")
                             # Try to populate int ID from here if possible?
                             # Usually GetDefaultLayout returns 'id' as 'PropertyID' (int)?
                             # Or 'propertyID'?
                             
                             potential_id = obj.get('id') or obj.get('propertyID') or obj.get('PropertyID')
                             if potential_id and isinstance(potential_id, int):
                                 self._tag_id_map[p_name] = potential_id
                                 self._tag_id_map[p_name.lower()] = potential_id
                                 logging.info(f"[DAMINION] Found Integer ID {potential_id} for '{p_name}' in Layout.")

                    # Recurse into children
                    for key, value in obj.items():
                        if isinstance(value, list):
                            for item in value:
                                extract_properties(item)
                        elif isinstance(value, dict):
                            extract_properties(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_properties(item)

            extract_properties(response)
            
            extract_properties(response)
            
            logging.info(f"[DAMINION] [OK] Mapped {len(self._tag_map) // 2} tags to GUIDs.")
            logging.info(f"[DAMINION] Available Tags: {list(self._tag_map.keys())}")
            
            # Additional step: Fetch Integer IDs for endpoints like IndexedTagValues
            try:
                # Based on C# SDK, GetTags endpoint is api/settings/getTags
                endpoint_tags = "/api/settings/getTags"
                response_tags = self._make_request(endpoint_tags)
                
                tags_list = []
                if isinstance(response_tags, list):
                    tags_list = response_tags
                elif isinstance(response_tags, dict):
                    tags_list = response_tags.get('tags') or response_tags.get('data') or []
                
                count_ids = 0
                for tag in tags_list:
                    if isinstance(tag, dict):
                         t_name = tag.get('name') or tag.get('tagName') or tag.get('Title')
                         t_id = tag.get('id') # Integer ID
                         if t_name and t_id is not None:
                             self._tag_id_map[t_name] = t_id
                             self._tag_id_map[t_name.lower()] = t_id
                             count_ids += 1
                
                logging.info(f"[DAMINION] Mapped {count_ids} tags to Integer IDs from /api/settings/getTags.")
            except Exception as e:
                logging.warning(f"[DAMINION] Failed to fetch tag integer IDs via /api/settings/getTags: {e}")

            return self._tag_map
            
        except Exception as e:
            logging.warning(f"[DAMINION] Failed to fetch tag schema: {e}. Tag updates using names might fail.")
            return {}

    def get_tag_values(self, tag_name: str) -> List[Dict]:
        """
        Retrieve values for a specific tag (e.g. 'Collection', 'Place').
        Tries multiple endpoints to ensure compatibility with different Daminion versions.
        """
        if not self._tag_map:
            self.get_tag_schema()
            
        guid = self._tag_map.get(tag_name) or self._tag_map.get(tag_name.lower()) or self._tag_map.get(tag_name.title()) 
        # Fallback for "Collection" / "Collections" pluralization
        if not guid and tag_name == "Collection":
             guid = self._tag_map.get("Collections")
        
        if not guid:
            logging.warning(f"Tag '{tag_name}' not found in schema.")
            return []

        # Try to look up Integer ID first (preferred for IndexedTagValues)
        int_id = self._tag_id_map.get(tag_name) or self._tag_id_map.get(tag_name.lower()) or self._tag_id_map.get(tag_name.title()) 
        if int_id is None and tag_name == "Collection":
             int_id = self._tag_id_map.get("Collections")

        if int_id is None:
            # Maybe we haven't fetched schema? (Already called above)
            logging.debug(f"Tag '{tag_name}' has no integer ID mapped. IndexedTagValues might fail.")

        # Candidate endpoints:
        # 1. api/indexedTagValues/getIndexedTagValues (Verified from C# SDK) - EXPECTS INTEGER ID
        # 2. api/Tag/GetStructure (Tree) - Usually takes GUID or ID? C# SDK uses GetTagValuesAsync with long.
        # 3. api/IndexedTagValues (Flat list)
        
        candidates = []
        if int_id is not None:
             candidates.append(f"/api/indexedTagValues/getIndexedTagValues?indexedTagId={int_id}&pageIndex=0&pageSize=1000")
             candidates.append(f"/api/IndexedTagValues?indexedTagId={int_id}&pageIndex=0&pageSize=1000")
        
        # Fallbacks using GUID if ID failed or not found (some endpoints might support GUID)
        if guid:
             # Some API versions might support GUID on GetStructure or GetNodes
             candidates.append(f"/api/Tag/GetStructure?tagId={guid}")
             candidates.append(f"/api/Tag/GetNodes?tagId={guid}")
             # If GUID is passed to indexedTagId it likely fails, but we can keep as last resort? No, generates 404.
             # candidates.append(f"/api/indexedTagValues/getIndexedTagValues?indexedTagId={guid}...") # Safe to skip

        for endpoint in candidates:
            try:
                logging.debug(f"[DAMINION] Trying endpoint: {endpoint}")
                response = self._make_request(endpoint)
                
                items = []
                if isinstance(response, list):
                    items = response
                elif isinstance(response, dict):
                     # Handle wrappers: data, values, items, nodes
                     items = response.get('data') or response.get('values') or response.get('items') or response.get('nodes')
                     # Special case: check if dict IS a node with 'subTags' or 'nodes'
                     if not items and ('subTags' in response or 'nodes' in response):
                          items = response.get('subTags') or response.get('nodes')
                          
                     if isinstance(items, dict):
                         items = list(items.values())
                
                if isinstance(items, list):
                    logging.info(f"[DAMINION] Retrieved {len(items)} values for tag '{tag_name}' via {endpoint.split('?')[0]}")
                    return items
            except Exception as e:
                logging.debug(f"[DAMINION] Endpoint {endpoint} failed: {e}")
                continue

        logging.warning(f"Failed to fetch values for tag {tag_name} using any known endpoint.")
        return []

    def get_items_by_tag(self, tag_name: str, value_id: str | int, value_name: str = None) -> List[Dict]:
        """
        Get items that have a specific tag value.
        """
        # Try structured query: TagGUID,ValueID
        guid = self._tag_map.get(tag_name) or self._tag_map.get(tag_name.lower()) or self._tag_map.get(tag_name.title())
        if not guid and tag_name == "Collection":
             guid = self._tag_map.get("Collections")
             
        if guid:
             # Structured: query="{TagGUID},{ValueID}"
             # If GetByQuery is supported (it might not be on older servers, returning 404)
             q = f"{guid},{value_id}"
             ops = f"{guid},any"
             items = self.get_items_by_query(q, ops)
             if items is not None:
                 return items
        
        # Fallback to search if name provided
        if value_name:
             # If tag is "Collection", query should be "Place:London" (if Place)
             # "Collections:MyCollection"
             # normalize tag name for search
             search_tag = "Collections" if tag_name == "Collection" else tag_name
             return self.search_items(f"{search_tag}:{value_name}")
             
        return []

    def get_untagged_items(self) -> Tuple[List[Dict], int]:
        """
        Retrieve media items that don't have all required metadata.

        Returns:
            Tuple of (list of media items, total count)

        Note:
            This endpoint returns items missing required metadata.
            May return empty if all items are properly tagged.
        """
        # Try structured query first (assuming 'status:untagged' corresponds to a specific property)
        # This is a guess; the exact property ID for "Status" might differ.
        # Let's try with the text search first as it's more standard.

        # Try efficient text-based server-side search first
        items = self.search_items(query="status:untagged", page_size=500)
        if items is not None:
            total = len(items)
            logging.info(f"Retrieved {len(items)} untagged items via server-side search.")
            return items, total

        # Fallback to legacy endpoint
        logging.warning("[DAMINION] Falling back to legacy '/api/MediaItems/MyItems' for untagged items.")
        endpoint = "/api/MediaItems/MyItems"
        response = self._make_request(endpoint)
        items = response.get('mediaItems', [])
        total = response.get('totalCount', 0)
        logging.info(f"Retrieved {len(items)} untagged items from legacy endpoint.")
        return items, total

    def download_thumbnail(self, item_id: str, width: int = 300,
                          height: int = 300) -> Optional[Path]:
        """
        Download thumbnail for a media item.

        Args:
            item_id: Media item ID
            width: Thumbnail width in pixels
            height: Thumbnail height in pixels

        Returns:
            Path to downloaded thumbnail file, or None if failed
        """
        if not self.authenticated:
            raise DaminionAPIError("Not authenticated")

        url = f"{self.base_url}/api/thumbnail/{item_id}/{width}/{height}"
        logging.debug(f"[DAMINION] Downloading thumbnail for item {item_id}...")

        try:
            request = urllib.request.Request(url)
            request.add_header('Cookie', self._get_cookie_header())

            logging.debug(f"[DAMINION] Opening thumbnail request with 30s timeout...")
            with urllib.request.urlopen(request, timeout=30) as response:
                # Save to temp file
                temp_file = self.temp_dir / f"{item_id}.jpg"
                data = response.read()
                logging.debug(f"[DAMINION] Downloaded {len(data)} bytes")

                with open(temp_file, 'wb') as f:
                    f.write(data)

                logging.debug(f"[DAMINION] [OK] Saved thumbnail to {temp_file}")
                return temp_file

        except Exception as e:
            logging.error(f"[DAMINION] [ERROR] Failed to download thumbnail for {item_id}: {e}")
            return None

    def batch_update_tags(self, item_ids: List[str], tags: Dict[str, List[str]], batch_size: int = 50) -> bool:
        """
        Update tags for multiple media items with automatic batching.

        Args:
            item_ids: List of media item IDs
            tags: Dictionary mapping tag field names to lists of values
                  Example: {"Keywords": ["sunset", "beach"], "Category": ["Scenery"]}
            batch_size: Number of items to update per batch (default: 50)

        Returns:
            True if all updates successful, False otherwise

        Note:
            Processes items in batches to avoid overwhelming the API.
            Payload format matches POST api/ItemData/BatchChange documentation.
        """
        if not item_ids:
            return True

        endpoint = "/api/ItemData/BatchChange"
        all_successful = True

        # Process in batches
        for i in range(0, len(item_ids), batch_size):
            batch = item_ids[i:i + batch_size]
            logging.debug(f"[DAMINION] Batch updating items {i+1} to {i+len(batch)}")

            # Transform tags dict into list of DataChangeItem objects
            data_items = []
            for tag_name, tag_values in tags.items():
                if isinstance(tag_values, list):
                    for val in tag_values:
                        data_items.append({
                            "guid": tag_name,   # Assuming 'guid' accepts the Tag Name
                            "value": str(val),
                            "remove": False
                        })
                else:
                     # Single value case
                     data_items.append({
                        "guid": tag_name,
                        "value": str(tag_values),
                        "remove": False
                    })
            

            
            # Construct payload
            # POST api/ItemData/BatchChange
            # { "ids": [...], "delete": false, "data": [...] }
            
            # Translate Tag Names to GUIDs
            final_data_items = []
            for item in data_items:
                raw_key = item['guid']
                # Try to find GUID
                guid = self._tag_map.get(raw_key) or self._tag_map.get(raw_key.lower())
                
                # Special handling for 'Category' which is not a standard Daminion tag
                if not guid and raw_key == 'Category':
                    # Try common synonyms
                    guid = self._tag_map.get('Categories') or self._tag_map.get('Subject') or self._tag_map.get('Classification')
                    if not guid:
                        # Fallback to Keywords so we at least save the data
                        guid = self._tag_map.get('Keywords')
                        if guid:
                            logging.warning(f"[DAMINION] 'Category' tag not found. Remapped to 'Keywords'.")

                if guid:
                    logging.debug(f"[DAMINION] Mapped tag '{raw_key}' -> {guid}")
                    item['guid'] = guid
                    final_data_items.append(item)
                else:
                    logging.warning(f"[DAMINION] Warning: Could not find GUID for tag '{raw_key}'. Sending as-is (might fail).")
                    final_data_items.append(item)

            payload = {
                "ids": [int(x) if str(x).isdigit() else x for x in batch], 
                "delete": False,
                "data": final_data_items
            }

            try:
                response = self._make_request(endpoint, method='POST', data=payload)
                success = response.get('success', False)
                
                # Some API versions return just { "success": true } or { "data": true }
                if success is True or response.get('data') is True:
                     logging.debug(f"[DAMINION] Successfully updated tags for batch of {len(batch)} items")
                else:
                    error = response.get('error') or 'Unknown error'
                    # Check for errorCode if present
                    if 'errorCode' in response:
                        error += f" (Code: {response['errorCode']})"
                    
                    logging.error(f"[DAMINION] Tag update failed for batch: {error}")
                    all_successful = False

            except (DaminionAPIError, DaminionNetworkError) as e:
                logging.error(f"[DAMINION] Batch update failed: {e}")
                all_successful = False

        if all_successful:
            logging.info(f"[DAMINION] Successfully updated tags for all {len(item_ids)} items")

        return all_successful

    def update_item_metadata(self, item_id: str, category: Optional[str] = None,
                           keywords: Optional[List[str]] = None,
                           description: Optional[str] = None) -> bool:
        """
        Update metadata for a single item.

        Args:
            item_id: Media item ID
            category: Category/classification for the item
            keywords: List of keywords to add
            description: Description/caption for the item

        Returns:
            True if successful, False otherwise
        """
        logging.debug(f"[DAMINION] Updating metadata for item {item_id}")
        logging.debug(f"[DAMINION] Category: {category}, Keywords: {keywords}, Desc: {bool(description)}")

        tags = {}

        if category:
            tags['Category'] = [category]

        if keywords:
            tags['Keywords'] = keywords

        if description:
            tags['Description'] = [description]

        if not tags:
            logging.warning(f"[DAMINION] No metadata to update for item {item_id}")
            return False

        result = self.batch_update_tags([item_id], tags)
        if result:
            logging.debug(f"[DAMINION] [OK] Metadata updated for item {item_id}")
        else:
            logging.warning(f"[DAMINION] [ERROR] Failed to update metadata for item {item_id}")
        return result

    def cleanup_temp_files(self):
        """Remove all cached thumbnail files."""
        try:
            if self.temp_dir.exists():
                for file in self.temp_dir.glob("*.jpg"):
                    try:
                        file.unlink()
                    except OSError as e:
                        logging.warning(f"Failed to delete {file}: {e}")
                logging.debug("Cleaned up temporary thumbnail files")
        except Exception as e:
            logging.error(f"Failed to cleanup temp files: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.cleanup_temp_files()
        except Exception:
            pass

    @classmethod
    def cleanup_all(cls):
        """Clean up all active client instances."""
        for client in list(cls._instances):
            try:
                client.cleanup_temp_files()
            except Exception:
                pass

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection and return server statistics.

        Returns:
            Dictionary with connection status and server info
        """
        try:
            if not self.authenticated:
                self.authenticate()

            total = self.get_total_count()
            test_items = self.get_media_items_by_ids([1, 2, 3, 4, 5])

            return {
                'connected': True,
                'server': self.base_url,
                'username': self.username,
                'total_items': total,
                'sample_items': len(test_items),
                'api_responding': True
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
