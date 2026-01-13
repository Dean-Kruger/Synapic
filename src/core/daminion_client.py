
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
        """
        if not self.authenticated and "Login" not in endpoint:
            # Auto-authenticate if needed? No, simpler to raise
            pass

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
            # Mimic browser headers to avoid 500s or 403s on strict servers
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            request.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')
            request.add_header('X-Requested-With', 'XMLHttpRequest')
            
            logging.debug(f"[DAMINION] Opening request with {timeout}s timeout...")

            with urllib.request.urlopen(request, timeout=timeout) as response:
                logging.debug(f"[DAMINION] Response status: {response.status}")
                body = response.read().decode('utf-8')
                logging.debug(f"[DAMINION] Response body size: {len(body)} bytes")
                
                if not body:
                    return {}
                    
                result = json.loads(body)
                return result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            # Clean up error body for logging
            error_body = error_body[:500].replace('\n', ' ') if error_body else ''
            
            error_msg = f"HTTP {e.code}: {e.reason} - {error_body}"
            logging.error(f"[DAMINION] [ERROR] API request failed: {error_msg}")
            
            if e.code == 429:
                raise DaminionRateLimitError(f"Rate limit exceeded: {error_msg}")
            elif e.code in (401, 403):
                raise DaminionAuthenticationError(f"Authentication error: {error_msg}")
            raise DaminionAPIError(error_msg)
            
        except urllib.error.URLError as e:
            logging.error(f"[DAMINION] [ERROR] Network error: {e}")
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
        # try multiple endpoint formats based on Daminion API documentation
        # code is preferred for PublicItems
        # 1. Try with ID first (as passed)
        # 2. If ID fails, fetch collection details to get the "accessCode" and try that.
        
        # Candidate endpoints
        tried_endpoints = [
            f"/api/SharedCollection/GetItems?id={collection_id}&index={index}&pageSize={page_size}", 
            f"/api/SharedCollection/GetItems?collectionId={collection_id}&index={index}&pageSize={page_size}",
             # PublicItems requires 'code' (accessCode), not internal ID often.
            f"/api/SharedCollection/PublicItems?code={collection_id}&index={index}&size={page_size}&sortag=0&asc=true",
            f"/api/SharedCollection/PublicItems/{collection_id}/{index}/{page_size}/0/true",
        ]

        # Helper to try a list of endpoints
        def try_fetch(endpoints):
            for endpoint in endpoints:
                try:
                    response = self._make_request(endpoint)
                    if not response: continue
                    if isinstance(response, list): return response
                    if isinstance(response, dict):
                         # Look for common wrapper names
                         for k in ['mediaItems', 'items', 'data', 'collections']:
                             if k in response:
                                 val = response[k]
                                 if isinstance(val, list): return val
                                 if isinstance(val, dict) and val: # check for {id:item} map
                                      vlist = list(val.values())
                                      if vlist and isinstance(vlist[0], dict): return vlist
                except Exception:
                    pass
            return None

        # Attempt 1: Use passed ID directly
        items = try_fetch(tried_endpoints)
        if items is not None: return items

        # Attempt 2: If passed arg was integer-like ID, fetch Details to get 'accessCode'
        # The 'PublicItems' endpoint typically needs the alphanumeric accessCode (e.g. 'pjrzp5ny')
        try:
            details_ep = f"/api/SharedCollection/GetDetails/{collection_id}"
            details = self._make_request(details_ep)
            if isinstance(details, dict):
                 access_code = details.get('accessCode')
                 if access_code and access_code != str(collection_id):
                     logging.info(f"[DAMINION] Retrying shared collection fetch with accessCode: {access_code}")
                     code_endpoints = [
                        f"/api/SharedCollection/PublicItems?code={access_code}&index={index}&size={page_size}&sortag=0&asc=true",
                        f"/api/SharedCollection/PublicItems/{access_code}/{index}/{page_size}/0/true"
                     ]
                     items = try_fetch(code_endpoints)
                     if items is not None: return items
        except Exception as e:
            logging.debug(f"[DAMINION] Failed to fetch collection details for ID {collection_id}: {e}")

        # If we reach here, we failed
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
            # Handle different response shapes
            items = []
            if isinstance(response, list):
                items = response
            elif isinstance(response, dict):
                items = response.get('mediaItems') or response.get('items') or response.get('data') or []
            
            logging.info(f"[DAMINION] [OK] Structured query returned {len(items)} items")
            return items
        except DaminionAPIError as e:
            if "404" in str(e):
                logging.warning("[DAMINION] Structured query endpoint '/api/MediaItems/GetByQuery' not found (404).")
                self._structured_query_unavailable = True
                return None
            raise

    def get_saved_searches(self) -> List[Dict]:
        """Retrieve list of saved searches via the tag tree or specialized endpoint."""
        logging.info("[DAMINION] Fetching saved searches...")
        
        # 1. Try specialized endpoint (works on some versions)
        try:
            endpoint = "/api/MediaItems/GetSavedSearches"
            response = self._make_request(endpoint)
            # Response handling...
            if isinstance(response, list):
                return response
            if isinstance(response, dict):
                 searches = response.get('values') or response.get('items') or response.get('data')
                 if searches: return searches
        except Exception:
             pass
             
        # 2. Try fetching as Tag Values for ID 39 (Saved Searches)
        # Proven to be ID 39 via probe.
        # User hint: ?query=39,117 suggests 39 is the tag, 117 is the value (Saved Search Item).
        # We need the LIST of values (117, etc).
        
        # Try GetStructure/GetNodes for ID 39 which usually returns the tree
        candidates = [
            "/api/Tag/GetStructure?tagId=39",
            "/api/Tag/GetNodes?tagId=39", 
            "/api/ItemData/GetTagValues?tagId=39",
            # Try GUID just in case
            "/api/Tag/GetStructure?tagId=09bba98e-7112-42fe-9ed1-3624a881d160",
             # Try plural
            "/api/SavedSearches/Get"
        ]
        
        for endpoint in candidates:
             try:
                 logging.debug(f"[DAMINION] Trying saved search endpoint: {endpoint}")
                 response = self._make_request(endpoint)
                 
                 items = []
                 if isinstance(response, list):
                     items = response
                 elif isinstance(response, dict):
                     items = response.get('items') or response.get('nodes') or response.get('values') or []
                     
                 if items:
                     logging.info(f"[DAMINION] Found {len(items)} saved searches via {endpoint}")
                     # Ensure items have 'name' or 'title' mapping
                     for item in items:
                          if 'title' in item and 'name' not in item:
                               item['name'] = item['title']
                          if 'id' in item and 'value' not in item:
                               item['value'] = item['name'] # for dropdown
                     return items
             except Exception as e:
                 logging.debug(f"[DAMINION] Endpoint {endpoint} failed: {e}")

        # 3. Fallback: If we assume 500s on correct endpoints are due to server issues, 
        # we return empty but user can manually input if we enabled it.
        logging.warning("[DAMINION] Failed to retrieve Saved Searches. The server might require specific version endpoints.")
        return []

    def get_items_filtered(self, 
                          scope: str = "all",
                          saved_search_id: Optional[Union[str, int]] = None,
                          collection_id: Optional[Union[str, int]] = None,
                          untagged_fields: List[str] = None,
                          status_filter: str = "all",
                          max_items: Optional[int] = None,
                          progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict]:
        """
        Retrieve media items based on advanced filters.
        """
        logging.info(f"[DAMINION] Fetching items with scope={scope}, status={status_filter}")
        
        filtered_items = []
        
        # 1. Specialized fast-path for "Any Untagged" global search
        if scope == "all" and status_filter == "all" and untagged_fields:
             # Try server-side status:untagged which is very common definition of 'untagged'
             logging.info("[DAMINION] Using fast-path 'status:untagged' search.")
             fast_items = self.search_items(query="status:untagged", page_size=max_items if (max_items and max_items > 0) else 500)
             if fast_items:
                 # Still apply field-specific filters to be sure
                 for item in fast_items:
                     if self._passes_filters(item, status_filter, untagged_fields):
                         filtered_items.append(item)
                         if max_items and len(filtered_items) >= max_items:
                             return filtered_items
        
        # 2. Standard paths
        items_to_process = []
        if scope == "saved_search":
             if saved_search_id:
                  logging.info(f"[DAMINION] Using specialized query for Saved Search: query=39,{saved_search_id}")
                  endpoint = f"/api/MediaItems/Get?query=39,{saved_search_id}&page=0&pageSize={max_items or 1000}"
                  response = self._make_request(endpoint)
                  if isinstance(response, dict):
                       items_to_process = response.get('items') or response.get('data') or []
                  elif isinstance(response, list):
                       items_to_process = response
             else:
                  logging.warning("[DAMINION] Scope is 'saved_search' but no ID provided.")
        elif scope == "collection":
             if collection_id:
                 items_to_process = self.get_shared_collection_items(collection_id)
             else:
                 logging.warning("[DAMINION] Scope is 'collection' but no ID provided.")
        else:
             # Global scan: Fetch in larger batches and filter until we reach max_items
             batch_size = 200
             current_id = 1
             total_catalog = self.get_total_count()
             
             logging.info(f"[DAMINION] Starting global scan with filters. Target match: {max_items or 'all'}")
             
             while (not max_items or len(filtered_items) < max_items) and current_id <= total_catalog:
                 item_ids = list(range(current_id, current_id + batch_size))
                 batch = self.get_media_items_by_ids(item_ids)
                 if not batch:
                     if current_id > total_catalog + 1000: break # Safety break
                     current_id += batch_size
                     continue
                 
                 for item in batch:
                     if self._passes_filters(item, status_filter, untagged_fields):
                         filtered_items.append(item)
                         if max_items and len(filtered_items) >= max_items:
                             break
                 
                 if progress_callback:
                      # Approximate progress based on ID range
                      progress_callback(len(filtered_items), max_items or total_catalog)
                      
                 current_id += batch_size
             
             return filtered_items

        # Apply filtering for non-global paths
        for item in items_to_process:
            if self._passes_filters(item, status_filter, untagged_fields):
                filtered_items.append(item)
                if max_items and len(filtered_items) >= max_items:
                    break
        
        return filtered_items

    def _passes_filters(self, item: Dict, status_filter: str, untagged_fields: List[str]) -> bool:
        """Helper to check if an item passes status and untagged metadata filters."""
        if not isinstance(item, dict): return False
        
        # Status check
        # Daminion 7+ uses 'Status' string or integer 2. 
        # Check for presence in various forms
        status_val = item.get('Status') or item.get('status') or item.get('2')
        status_str = str(status_val or "").lower()
        
        if status_filter == "approved" and status_str != "approved": return False
        if status_filter == "rejected" and status_str != "rejected": return False
        if status_filter == "unassigned":
            # Unassigned usually means no status set or not approved/rejected
            if status_str in ["approved", "rejected", "flagged"]: return False
        
        # Untagged check
        if untagged_fields:
            is_any_field_empty = False
            item_lower = {k.lower(): v for k, v in item.items()}
            
            for field in untagged_fields:
                val = item_lower.get(field.lower())
                # Empty means None, "", empty list, or null string
                if val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and not val):
                    is_any_field_empty = True
                    break
            
            if not is_any_field_empty: return False
            
        return True


    def search_items(self, query: str, index: int = 0, page_size: int = 200) -> Optional[List[Dict]]:
        """
        Search for items on the server using a query string.
        Uses GET /api/MediaItems/Get (POST /Search is deprecated/unavailable).

        Args:
            query: The search query (e.g., 'status:untagged', 'flag:rejected').
            index: The starting index.
            page_size: The number of items to return.

        Returns:
            A list of media items matching the search query.
        """
        if self._search_endpoint_unavailable:
            logging.warning("[DAMINION] Search endpoint is unavailable, cannot perform server-side search.")
            return None

        logging.info(f"[DAMINION] Searching items with query: '{query}'")
        # Use GET /api/MediaItems/Get which returns totalCount and mediaItems
        endpoint = f"/api/MediaItems/Get?search={urllib.parse.quote(query)}&start={index}&length={page_size}"
        
        try:
            response = self._make_request(endpoint, method='GET')
            items = []
            if isinstance(response, dict):
                items = response.get('mediaItems') or response.get('items') or response.get('data') or []
            elif isinstance(response, list):
                items = response

            logging.info(f"[DAMINION] [OK] Server-side search returned {len(items)} items")
            return items
        except DaminionAPIError as e:
            if "404" in str(e):
                logging.warning("[DAMINION] Search endpoint '/api/MediaItems/Get' not found (404).")
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
                        
                        # DEBUG: Map integer IDs for all properties if present
                        potential_id = obj.get('id') or obj.get('propertyID') or obj.get('PropertyID')
                        if potential_id and isinstance(potential_id, int):
                            self._tag_id_map[p_name] = potential_id
                            self._tag_id_map[p_name.lower()] = potential_id
                            logging.debug(f"[DAMINION] Found Integer ID {potential_id} for '{p_name}' in Layout.")

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
                
                # Force map Saved Searches ID 39 if not found, based on probe
                if 'saved searches' not in self._tag_id_map:
                     self._tag_id_map['saved searches'] = 39
                     logging.info(f"[DAMINION] 'Saved Searches' manually mapped to ID 39.")
                     
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
        
        if not guid and tag_name != "Saved Searches":
            logging.warning(f"Tag '{tag_name}' not found in schema.")
            return []

        # Try to look up Integer ID first (preferred for IndexedTagValues)
        int_id = self._tag_id_map.get(tag_name) or self._tag_id_map.get(tag_name.lower()) or self._tag_id_map.get(tag_name.title()) 
        if int_id is None:
            if tag_name == "Collection":
                int_id = self._tag_id_map.get("Collections")
            elif tag_name == "Saved Searches":
                int_id = 40 # Standard Daminion TagID for Saved Searches

        if int_id is None:
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
        
        # Specialized fallback for Saved Searches (Tag ID 40)
        # Methodology: API works with IDs so we use standard ID 40 for Saved Searches
        if tag_name == "Saved Searches" and value_id:
             # Use the mapped ID (39) if available, otherwise default to 39 (based on user hint)
             tag_int_id = self._tag_id_map.get("Saved Searches") or self._tag_id_map.get("saved searches") or 39
             logging.info(f"[DAMINION] Querying Saved Search {value_id} using ID {tag_int_id}...")
             q = f"{tag_int_id},{value_id}"
             ops = f"{tag_int_id},any"
             items = self.get_items_by_query(q, ops)
             if items:
                 return items

        # Fallback to search if name provided
        if value_name:
             # If tag is "Collection", query should be "Place:London" (if Place)
             # "Collections:MyCollection"
             # normalize tag name for search
             search_tag = "Collections" if tag_name == "Collection" else tag_name
             return self.search_items(f"{search_tag}:{value_name}")
             
        return []

    def get_filtered_item_count(self, scope: str = "all",
                               saved_search_id: Optional[Union[str, int]] = None,
                               collection_id: Optional[Union[str, int]] = None,
                               untagged_fields: List[str] = None,
                               status_filter: str = "all") -> int:
        """
        Efficiently count items matching filters without downloading them.
        """
        # 1. Simple Case: All items, no sub-filters
        if scope == "all" and status_filter == "all" and not untagged_fields:
            return self.get_total_count()

        # 2. Combined Query Construction
        query_parts = []
        
        # Status
        if status_filter == "approved": query_parts.append("status:approved")
        elif status_filter == "rejected": query_parts.append("status:rejected")
        elif status_filter == "unassigned": query_parts.append("status:unassigned")
        
        # Untagged (approximate with status:untagged if any field selected)
        if untagged_fields:
            query_parts.append("status:untagged")
            
        if scope == "all" and query_parts:
            # Combine multiple parts into a space-separated search query
            combined_query = " ".join(query_parts)
            return self._count_query(combined_query)
        
        # 3. Fallback: If we can't count efficiently, return -1 or estimation?
        return -1

    def _count_query(self, query: str) -> int:
        """Helper to count via Search endpoint."""
        try:
            endpoint = f"/api/MediaItems/Get?search={urllib.parse.quote(query)}&start=0&length=1"
            response = self._make_request(endpoint, method='GET')
            if isinstance(response, dict):
                return response.get('totalCount', 0)
        except Exception:
            pass
        return 0

    def get_untagged_items(self) -> Tuple[List[Dict], int]:
        """
        Retrieve media items that don't have all required metadata.

        Returns:
            Tuple of (list of media items, total count)
        """
        # Try efficient text-based server-side search first
        query = "status:untagged"
        items = self.search_items(query=query, page_size=500)
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

    def get_items_filtered(self, 
                          scope: str = "all",
                          saved_search_id: Optional[Union[str, int]] = None,
                          collection_id: Optional[Union[str, int]] = None,
                          untagged_fields: List[str] = None,
                          status_filter: str = "all",
                          max_items: Optional[int] = None,
                          progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict]:
        """
        Retrieve media items based on advanced filters.
        
        Args:
            scope: 'all', 'saved_search', 'collection'
            saved_search_id: ID of the saved search to use if scope is 'saved_search'
            collection_id: ID of collection if scope is 'collection'
            untagged_fields: List of fields like ['Keywords', 'Description'] that must be empty
            status_filter: 'all', 'approved' (flagged), 'rejected', 'unassigned' (unflagged)
        """
        logging.info(f"[DAMINION] Fetching items with scope={scope}, status={status_filter}, untagged={untagged_fields}")
        
        # 1. Start with base set of items based on scope
        items = []
        if scope == "saved_search":
             if saved_search_id:
                 items = self.get_items_by_tag("Saved Searches", saved_search_id)
             else:
                 logging.warning("[DAMINION] Scope is 'saved_search' but no ID provided. Returning empty.")
                 items = []
        elif scope == "collection":
             if collection_id:
                 items = self.get_shared_collection_items(collection_id)
             else:
                 logging.warning("[DAMINION] Scope is 'collection' but no ID provided. Returning empty.")
                 items = []
        else:
             # Default: fetch all items paginated (with max_items limit)
             items = self.get_all_items_paginated(max_items=max_items, progress_callback=progress_callback)

        # 2. Client-side filtering for Approval Status and Untagged fields
        filtered_items = []
        for item in items:
            if not isinstance(item, dict):
                logging.debug(f"Skipping non-dictionary item in filter loop: {type(item)}")
                continue

            # Check Status (Flagging)
            # Daminion Property: 2 (Status) or 'Status' field
            status = item.get('Status') or item.get('status')
            
            if status_filter == "approved" and str(status).lower() != "approved":
                continue
            if status_filter == "rejected" and str(status).lower() != "rejected":
                continue
            if status_filter == "unassigned" and status is not None and str(status).strip() != "":
                continue

            # Check Untagged fields
            if untagged_fields:
                is_any_field_empty = False
                # Daminion JSON keys can be 'Keywords' or 'keywords'
                # Create a lowercase map for robust lookup
                item_lower = {k.lower(): v for k, v in item.items()}
                
                for field in untagged_fields:
                    val = item_lower.get(field.lower())
                    if not val or not str(val).strip() or val == []:
                        is_any_field_empty = True
                        break
                
                if not is_any_field_empty:
                    # All selected untagged fields have data, so skip this item
                    continue
                
            filtered_items.append(item)
            
            if max_items and len(filtered_items) >= max_items:
                break
                
        logging.info(f"[DAMINION] Filtering complete. Returning {len(filtered_items)} items.")
        return filtered_items

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
