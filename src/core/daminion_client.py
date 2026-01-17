
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
        self._tag_id_map = {} # Cache for Tag Name -> Integer ID mapping
        
        # Hardcoded IDs observed in many Daminion versions
        # Updated via probe: Saved Searches=40, Shared Collections=46
        self.SAVED_SEARCH_TAG_ID = 40 
        self.SHARED_COLLECTIONS_TAG_ID = 46 

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
                
                # Additional step: Fetch Integer IDs for endpoints like IndexedTagValues
                try:
                    # Based on C# SDK, GetTags endpoint is api/settings/getTags
                    endpoint_tags = "/api/settings/getTags"
                    response_tags = self._make_request(endpoint_tags)
                    
                    tags_list = []
                    if isinstance(response_tags, list):
                        tags_list = response_tags
                    elif isinstance(response_tags, dict):
                        tags_list = response_tags.get('tags') or response_tags.get('data') or response_tags.get('items') or []
                    
                    count_ids = 0
                    for tag in tags_list:
                        if isinstance(tag, dict):
                             t_name = tag.get('name') or tag.get('tagName') or tag.get('Title')
                             t_id = tag.get('id') # Integer ID
                             if t_name and t_id is not None:
                                 self._tag_id_map[t_name] = t_id
                                 self._tag_id_map[t_name.lower()] = t_id
                                 
                                 # Update internal constants if found
                                 if t_name == "Keywords": 
                                      self.KEYWORDS_TAG_ID = t_id
                                      logging.info(f"[DAMINION] Tag Tree: Keywords = {t_id}")
                                 count_ids += 1
                    
                    # Explicitly check/set critical IDs if found
                    if 'Saved Searches' in self._tag_id_map:
                        self.SAVED_SEARCH_TAG_ID = self._tag_id_map['Saved Searches']
                    if 'saved searches' in self._tag_id_map:
                         self.SAVED_SEARCH_TAG_ID = self._tag_id_map['saved searches']
                         
                    if 'Shared Collections' in self._tag_id_map:
                        self.SHARED_COLLECTIONS_TAG_ID = self._tag_id_map['Shared Collections']
                    if 'shared collections' in self._tag_id_map:
                         self.SHARED_COLLECTIONS_TAG_ID = self._tag_id_map['shared collections']

                    logging.info(f"[DAMINION] Mapped {len(self._tag_id_map)} tags to Integer IDs from /api/settings/getTags.")
                except Exception as e:
                    logging.warning(f"[DAMINION] Failed to fetch integer tag IDs: {e}")
                
                return True

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            logging.error(f"[DAMINION] [ERROR] Authentication failed: {error_msg}")
            raise DaminionAuthenticationError(f"Authentication failed: {error_msg}")
        except urllib.error.URLError as e:
            logging.error(f"[DAMINION] [ERROR] Network error during authentication: {e}")
            raise DaminionNetworkError(f"Connection failed: {e}")
        except Exception as e:
            logging.error(f"[DAMINION] [ERROR] Unexpected authentication error: {e}")
            raise DaminionAPIError(f"Authentication failed: {e}")

    def _get_cookie_header(self) -> str:
        """Generate cookie header string from stored cookies."""
        return "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def _make_request(self, endpoint: str, method: str = 'GET',
                    data: Optional[Dict] = None, timeout: int = 30) -> Any:
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
        if not self.authenticated and "/UserManager/Login" not in endpoint:
             # Auto-reauthenticate if needed? For now just warn or error.
             # Ideally we should try to authenticate.
             if self.username and self.password:
                 self.authenticate()

        self._rate_limit()

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Mimic browser headers to avoid 500s or 403s on strict servers
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }

        if self.cookies:
            headers["Cookie"] = self._get_cookie_header()

        body = None
        if data:
            body = json.dumps(data).encode('utf-8')

        req = urllib.request.Request(url, method=method, headers=headers, data=body)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 204:  # No Content
                    return None
                    
                response_data = response.read().decode('utf-8')
                
                # Check for redirects or login pages (session expired)
                if "<!DOCTYPE html>" in response_data or "<html" in response_data:
                     # If we got HTML, it likely means we were redirected to login page
                     # or error page.
                     if "/UserManager/Login" not in endpoint:
                         logging.warning("[DAMINION] Received HTML response (likely login page). Converting to error.")
                         raise DaminionAuthenticationError("Session expired or invalid.")

                try:
                    return json.loads(response_data)
                except json.JSONDecodeError:
                    return response_data  # Return raw text if not JSON
        except urllib.error.HTTPError as e:
            if e.code == 401 or e.code == 403:
                raise DaminionAuthenticationError(f"Authentication failed: {e}")
            elif e.code == 429:
                raise DaminionRateLimitError(f"Rate limit exceeded: {e}")
            else:
                # Try to read error message
                error_body = e.read().decode('utf-8') if e.fp else ''
                logging.error(f"[DAMINION] [ERROR] API request failed: HTTP {e.code}: {e.reason} - {error_body}")
                raise DaminionAPIError(f"API request failed: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            raise DaminionNetworkError(f"Network error: {e}")

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
        """Retrieve list of shared collections available on the server."""
        logging.info("[DAMINION] Fetching shared collections...")
        
        # Proven to be ID 46 via probe (previously thought 45).
        results = self.get_tag_values("Shared Collections")
        if not results:
             results = self.get_tag_values("shared collections")

        # Also try "Collections" (ID 41) just in case
        if not results:
             logging.info("[DAMINION] No Shared Collections found, trying 'Collections'...")
             results = self.get_tag_values("Collections")

        if results:
             transformed = []
             for item in results:
                  transformed.append({
                       "id": item.get('id') or item.get('valueId'),
                       "name": item.get('name') or item.get('title') or item.get('stringValue') or item.get('value'),
                       "count": item.get('count', 0)
                  })
             return transformed

        # Legacy endpoint fallback? (The probe showed 404 for this, but maybe keep as last resort)
        # endpoint = f"/api/SharedCollection/GetCollections?index={index}&pageSize={page_size}"
        # ... skipped as it failed in probe ...
        
        return []

    def get_shared_collection_items(self, collection_id: str | int, index: int = 0, page_size: int = 200) -> List[Dict]:
        """Retrieve items for a shared collection."""
        # Update this to use queryLine logic with SHARED_COLLECTIONS_TAG_ID
        
        # 1. Try standard query approach first as it's most robust
        # "collection_id" here is likely the Value ID of the tag.
        
        logging.info(f"[DAMINION] Fetching items for Shared Collection ID {collection_id}")
        
        # We need to constructing a query.
        # TagID for Shared Collections is self.SHARED_COLLECTIONS_TAG_ID (e.g. 46)
        # ValueID is collection_id
        
        query = f"{self.SHARED_COLLECTIONS_TAG_ID},{collection_id}"
        operators = f"{self.SHARED_COLLECTIONS_TAG_ID},any" # Or 'all'? Collections usually imply membership, so 'any' in the collection.
        
        items = self.get_items_by_query(query, operators, index=index, page_size=page_size)
        if items:
             return items
             
        # Fallback to the old endpoint approach if the query fails
        # (Rest of original code...)
        
        # Candidate endpoints
        tried_endpoints = [
            f"/api/SharedCollection/GetItems?id={collection_id}&index={index}&pageSize={page_size}", 
            f"/api/SharedCollection/GetItems?collectionId={collection_id}&index={index}&pageSize={page_size}",
             # PublicItems requires 'code' (accessCode), not internal ID often.
            f"/api/SharedCollection/PublicItems?code={collection_id}&index={index}&size={page_size}&sortag=0&asc=true",
        ]

        # Helper to try a list of endpoints
        def try_fetch(endpoints):
            for endpoint in endpoints:
                try:
                    response = self._make_request(endpoint)
                    if not response: continue
                    
                    if isinstance(response, list): return response
                    if isinstance(response, dict):
                         # Look for common wrapper names, handle case-insensitivity
                         for k in ['mediaItems', 'MediaItems', 'items', 'Items', 'data', 'collections', 'Collections']:
                             if k in response:
                                 val = response[k]
                                 if isinstance(val, list) and val: # prioritize non-empty lists
                                      return val
                except Exception:
                    pass
            return None

        items = try_fetch(tried_endpoints)
        if items: return items
        
        return []

    def get_items_by_query(self, query: str, operators: str, index: int = 0, page_size: int = 500) -> List[Dict]:
        """
        Search for items using a structured query string.
        Supports cumulative filters using semicolon separation.
        """
        if self._structured_query_unavailable:
            return []

        # Properly encode parameters to handle spaces and special chars
        # Daminion API uses 'index' and 'size' for pagination in MediaItems/Get
        params = urllib.parse.urlencode({
            "queryLine": query,
            "f": operators,
            "index": index,
            "size": page_size,
            # Fallbacks for legacy/other versions
            "query": query,
            "operators": operators,
            "start": index,
            "length": page_size
        })
        endpoint = f"/api/MediaItems/Get?{params}"
        
        logging.info(f"[DAMINION] Querying: {endpoint}")

        try:
            response = self._make_request(endpoint, method='GET')
            
            items = []
            if isinstance(response, dict):
                # Check for various list keys, handle case variations
                items = (response.get('mediaItems') or 
                         response.get('MediaItems') or 
                         response.get('items') or 
                         response.get('Items') or
                         response.get('data') or [])
                
                total_count = response.get('totalCount', 0)
                if total_count > 0 and not items:
                    logging.warning(f"[DAMINION] Get returned totalCount={total_count} but 0 results in list. Keys found: {list(response.keys())}")
            elif isinstance(response, list):
                items = response
            
            return items if items else []
            
        except DaminionAPIError as e:
            if "404" in str(e):
                logging.warning(f"[DAMINION] Endpoint /api/MediaItems/Get not supported? {e}")
                self._structured_query_unavailable = True
                return []
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
            f"/api/TagValue/GetValues?tagId={self.SAVED_SEARCH_TAG_ID}",
            f"/api/Tag/GetStructure?tagId={self.SAVED_SEARCH_TAG_ID}",
            f"/api/Tag/GetNodes?tagId={self.SAVED_SEARCH_TAG_ID}", 
            f"/api/ItemData/GetTagValues?tagId={self.SAVED_SEARCH_TAG_ID}",
            f"/api/SavedSearches/Get",
            f"/api/MediaItems/GetSavedSearches"
        ]
        
        # Fallback to get_tag_values which is more comprehensive
        results = self.get_tag_values("Saved Searches")
        if results:
             # Transform to standard format if needed
             transformed = []
             for item in results:
                  transformed.append({
                       "id": item.get('id') or item.get('valueId'),
                       "name": item.get('name') or item.get('title') or item.get('stringValue')
                  })
             return transformed

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
                     return items
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
                          search_term: Optional[str] = None,
                          untagged_fields: List[str] = None,
                          status_filter: str = "all",
                          max_items: Optional[int] = None,
                          progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict]:
        """
        Retrieve media items based on advanced filters.
        """
        logging.info(f"[DAMINION] Fetching items with scope={scope}, status={status_filter}")
        
        filtered_items = []
        
        # Prepare search query for server-side pre-filtering
        query_parts = []
        if status_filter == "approved": query_parts.append("status:approved")
        elif status_filter == "rejected": query_parts.append("status:rejected")
        elif status_filter == "unassigned": query_parts.append("status:unassigned")
        if untagged_fields: query_parts.append("status:untagged")
        
        combined_query = " ".join(query_parts)
        
        # 1. Specialized fast-path for Global Scan (scope="all")
        if scope == "all":
             batch_size = 500
             current_start = 0
             
             logging.info(f"[DAMINION] Starting global scan with filters. Query: '{combined_query}', Target: {max_items if (max_items and max_items > 0) else 'all'}")
             
             # Attempt server-side search first
             server_search_worked = False
             try:
                 # Try several variations of status search
                 search_variants = [combined_query]
                 if "status:approved" in combined_query: search_variants.append("flag:flagged")
                 if "status:unassigned" in combined_query: search_variants.append("flag:unflagged")
                 
                 for variant in search_variants:
                     if not variant: continue
                     start_check = self.search_items(query=variant, index=0, page_size=1)
                     if start_check and len(start_check) > 0:
                         combined_query = variant
                         server_search_worked = True
                         break
             except Exception:
                 pass
             
             if server_search_worked:
                 logging.info(f"[DAMINION] Server-side search functional for query '{combined_query}'. Using it.")
                 while (not max_items or max_items <= 0 or len(filtered_items) < max_items):
                     batch = self.search_items(query=combined_query, index=current_start, page_size=batch_size)
                     if not batch: break
                     
                     for item in batch:
                         if self._passes_filters(item, status_filter, untagged_fields):
                             filtered_items.append(item)
                             if max_items and max_items > 0 and len(filtered_items) >= max_items:
                                 break
                     
                     if progress_callback:
                          progress_callback(len(filtered_items), max_items or -1)
                          
                     if len(batch) < batch_size: break
                     current_start += batch_size
             else:
                 # Fallback to Client-side Scan
                 total_count = self.get_total_count()
                 if total_count > 50000 and not max_items:
                      logging.error(f"[DAMINION] Catalog is too large ({total_count}) for full scan without 'max_items'. Aborting to prevent hang.")
                      return []

                 logging.warning(f"[DAMINION] Server-side search failed. Using Optimized Client-side Scan (Backwards).")
                 filtered_items = self.scan_catalog(
                     lambda item: self._passes_filters(item, status_filter, untagged_fields),
                     max_items=max_items,
                     progress_callback=progress_callback
                 )
             
             return filtered_items

        # 2. Non-global paths (Saved Search, Collection)
        items_to_process = []
        if scope == "saved_search":
             if saved_search_id:
                  logging.info(f"[DAMINION] Fetching Saved Search ID: {saved_search_id}")
                  # Try structured query first
                  items_to_process = self.get_items_by_query(f"{self.SAVED_SEARCH_TAG_ID},{saved_search_id}", f"{self.SAVED_SEARCH_TAG_ID},any", page_size=max_items or 1000)
                  if items_to_process is None:
                       # Fallback
                       eps = [
                            f"/api/MediaItems/Get?query={self.SAVED_SEARCH_TAG_ID}:{saved_search_id}&start=0&length={max_items or 1000}",
                            f"/api/MediaItems/Get?query={self.SAVED_SEARCH_TAG_ID},{saved_search_id}&start=0&length={max_items or 1000}"
                       ]
                       for ep in eps:
                            try:
                                resp = self._make_request(ep)
                                items = []
                                if isinstance(resp, dict):
                                     items = resp.get('mediaItems') or resp.get('items') or resp.get('data') or []
                                elif isinstance(resp, list):
                                     items = resp
                                if items:
                                     items_to_process = items
                                     break
                                if isinstance(resp, dict) and resp.get('totalCount', 0) > 0 and items == []:
                                     # Signal that items exist but list is empty (indicates scan fallback might be needed)
                                     items_to_process = []
                                     break
                            except Exception:
                                continue
             else:
                  logging.warning("[DAMINION] Scope is 'saved_search' but no ID provided.")
        elif scope == "collection":
             if collection_id:
                  items_to_process = self.get_shared_collection_items(collection_id)
             else:
                  logging.warning("[DAMINION] Scope is 'collection' but no ID provided.")
        elif scope == "search":
             if search_term:
                  logging.info(f"[DAMINION] Fetching Keyword Search: {search_term}")
                  # Use the proper keyword search method that looks up value IDs
                  items, count = self.search_by_keyword(search_term, page_size=max_items or 1000)
                  if items:
                       items_to_process = items
                       logging.info(f"[DAMINION] Keyword search returned {len(items)} items")
                  else:
                       # Fallback to text search
                       logging.info(f"[DAMINION] Keyword not found as exact tag, trying text search")
                       current_start = 0
                       batch_size = 500
                       while (not max_items or max_items <= 0 or len(items_to_process) < max_items):
                            batch = self.search_items(queryBody=search_term, index=current_start, page_size=batch_size)
                            if not batch: break
                            items_to_process.extend(batch)
                            if len(batch) < batch_size: break
                            current_start += batch_size
                            if max_items and max_items > 0 and len(items_to_process) >= max_items:
                                 items_to_process = items_to_process[:max_items]
                                 break
             else:
                  logging.warning("[DAMINION] Scope is 'search' but no search term provided.")

        # If we got NO items but the count indicated items exist, use a brute-force scan if small
        if not items_to_process and scope != "all" and (scope == "collection" or scope == "saved_search"):
             # Check if we have a way to get the count
             count = 0
             if scope == "collection" and collection_id:
                  # Use the totalCount from a probe if we had it? No, simpler to just check catalog size.
                  pass
             
             total_catalog = self.get_total_count()
             if total_catalog > 0 and total_catalog <= 1000:
                  logging.info(f"[DAMINION] Retreival returned 0 items but catalog is small ({total_catalog}). Using brute-force scan for {scope}...")
                  # Fetch all items and filter them in memory
                  all_items = self.get_media_items_by_ids(list(range(1, total_catalog + 100)))
                  # The caller will filter them using _passes_filters below.
                  items_to_process = all_items

        # Apply final pass filtering
        # When doing keyword search, exclude 'Keywords' from untagged filter since results will have keywords
        effective_untagged_fields = untagged_fields
        if scope == "search" and search_term and untagged_fields:
            effective_untagged_fields = [f for f in untagged_fields if f.lower() != 'keywords']
            if len(effective_untagged_fields) < len(untagged_fields):
                logging.debug(f"[DAMINION] Excluded 'Keywords' from untagged filter for keyword search")
        
        if items_to_process:
             processed_count = 0
             dropped_count = 0
             for item in items_to_process:
                # Add ID normalization
                if 'id' not in item and 'uniqueId' in item:
                     item['id'] = item['uniqueId']
                     
                if self._passes_filters(item, status_filter, effective_untagged_fields):
                    filtered_items.append(item)
                    processed_count += 1
                    if max_items and max_items > 0 and len(filtered_items) >= max_items:
                        break
                else:
                    dropped_count += 1
             
             logging.info(f"[DAMINION] Filter summary: {processed_count} passed, {dropped_count} dropped by status '{status_filter}' and untagged check.")
        
        return filtered_items

    def scan_catalog(self, filter_func: Callable[[Dict], bool], max_items: Optional[int] = None, progress_callback = None) -> List[Dict]:
        """
        Scan catalog by iterating IDs backwards (newest first).
        Includes safety logic to skip empty ID gaps in large catalogs.
        """
        filtered_items = []
        total_estimate = self.get_total_count()
        if not total_estimate:
             # Try a probe search to find latest ID
             probe = self.search_items(query="*", index=0, page_size=1)
             if probe:
                  total_estimate = probe[0].get('id', 4000)
             else:
                  total_estimate = 4000

        batch_size = 100
        # Start scanning from the estimated total ID upwards slightly (to catch newest)
        current_max_id = total_estimate + 100
        current_id = current_max_id
        
        empty_batches_count = 0
        max_empty_batches = 10 # Stop if we hit 1000 sequential empty IDs at the start or in a gap

        logging.info(f"[DAMINION] Starting backwards scan from ID {current_id}...")
        
        while current_id > 0:
            if max_items and len(filtered_items) >= max_items:
                break
                
            # 1. Check existence of a batch of IDs
            start_id = max(1, current_id - batch_size)
            ids_to_check = list(range(start_id, current_id + 1))
            
            # Fetch summary items (fast)
            summaries = self.get_media_items_by_ids(ids_to_check)
            
            if summaries:
                empty_batches_count = 0
                # Process items (usually newest first in Daminion's response, but we ensure order)
                sorted_summaries = sorted(summaries, key=lambda x: x.get('id', 0), reverse=True)
                
                for summary in sorted_summaries:
                    item_id = summary.get('id')
                    try:
                        # Full details fetch (slow, but only for existing items)
                        detail = self.get_item_details(item_id)
                        if detail:
                            detail['id'] = item_id 
                            if filter_func(detail):
                                filtered_items.append(detail)
                                if max_items and len(filtered_items) >= max_items:
                                    break
                    except Exception:
                         pass
            else:
                empty_batches_count += 1
                if empty_batches_count > max_empty_batches:
                    logging.info(f"[DAMINION] Hit {empty_batches_count} consecutive empty batches. Stopping scan.")
                    break
            
            if progress_callback:
                 progress_callback(len(filtered_items), max_items or -1)
            
            current_id -= batch_size
            
        logging.info(f"[DAMINION] Backwards scan complete. Found {len(filtered_items)} items.")
        return filtered_items

    def get_item_details(self, item_id: int) -> Optional[Dict]:
        """Fetch full item details including tags from ItemData endpoint."""
        endpoint = f"/api/ItemData/Get?id={item_id}"
        try:
            resp = self._make_request(endpoint)
            # Flatten properties for easier filtering
            item_data = resp.copy()
            props = item_data.get('properties', [])
            item_data['tags'] = {}
            if isinstance(props, list):
                for section in props:
                    for p in section.get('properties', []):
                        # Store by Name and maybe by ID if available?
                        p_name = p.get('propertyName')
                        p_val = p.get('propertyValue')
                        # Also check values list for structured tags
                        raw_values = p.get('values') 
                        
                        item_data[p_name] = p_val
                        item_data['tags'][p_name] = p_val
                        # If raw_values exists, it might contain tag IDs etc
                        # For Flag, raw_values is [] if unflagged
                        if p_name == "Flag":
                             # If raw_values is not empty, it's flagged
                             item_data['Flagged'] = bool(raw_values)
                             
            # Map common fields for UI compatibility
            if 'title' in item_data and 'name' not in item_data:
                item_data['name'] = item_data['title']
            if 'id' in item_data:
                item_data['value'] = item_data.get('name') or str(item_data['id'])
                
            return item_data
        except Exception:
            return None

    def _passes_filters(self, item: Dict, status_filter: str, untagged_fields: List[str]) -> bool:
        """Helper to check if an item passes status and untagged metadata filters."""
        if not isinstance(item, dict): return False
        
        # Status/Flag Logic
        # From ItemData: 'Flag' property. 'values' list is non-empty if flagged?
        # User screenshot: Unflagged items have no flag info or specific tag?
        # In test output: ID 1 and 4 had Flag Raw Value = [] (Empty list). 
        # We assume Empty List = Unflagged.
        
        is_flagged = item.get('Flagged', False) # Set by get_item_details
        
        # Fallback to old checks if 'Flagged' key missing (e.g. from search results)
        if 'Flagged' not in item:
             status_val = item.get('Status') or item.get('status')
             status_id = item.get('2') 
             flag_val = item.get('Flag') or item.get('flag')
             status_str = str(status_val or "").lower()
             flag_str = str(flag_val or "").lower()
             is_flagged = "flagged" in status_str or "flagged" in flag_str or status_id in [1, 2] or flag_val == 2

        # Status Filter Logic
        if status_filter == "approved":
             # In this user's context, "Approved" likely means "Flagged" based on UI?
             # User UI shows: Unflagged, Flagged, Rejected.
             # "Approved" usually maps to Flagged for selection.
             if not is_flagged: return False
        elif status_filter == "rejected":
             # Need to detect Rejected status. Usually ID 3.
             # In ItemData properties, if Flag is Rejected, how does it look?
             # Assuming Flag is 3?
             pass # Logic for rejected - if we can't detect, we might miss it.
        elif status_filter == "unassigned": # Unflagged
             if is_flagged: return False
        
        # Untagged check
        if untagged_fields:
            is_any_field_empty = False
            item_lower = {k.lower(): v for k, v in item.items()} # Flattened keys
            
            for field in untagged_fields:
                val = item_lower.get(field.lower())
                # Empty means None, "", empty list, or null string
                # If field missing from ItemData/Get, it's untagged
                if val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and not val):
                    is_any_field_empty = True
                    break
            
            if not is_any_field_empty: return False
            
        return True


    def search_items(self, query: str, index: int = 0, page_size: int = 200) -> Optional[List[Dict]]:
        """
        Search for items using a simple query string.
        """
        if self._search_endpoint_unavailable:
            logging.warning("[DAMINION] Search endpoint is unavailable, cannot perform server-side search.")
            return None

        logging.info(f"[DAMINION] Searching items with query: '{query}'")
        # Use GET /api/MediaItems/Get which returns totalCount and mediaItems
        params = urllib.parse.urlencode({
            "search": query,
            "start": index,
            "length": page_size
        })
        endpoint = f"/api/MediaItems/Get?{params}"
        
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
            logging.debug(f"[DAMINION] Available Tags: {list(self._tag_map.keys())}")
            
            # Force map Saved Searches ID 39 if not found, based on common Daminion structure
            if 'saved searches' not in self._tag_id_map:
                 self._tag_id_map['saved searches'] = 39
                 logging.debug(f"[DAMINION] 'Saved Searches' manually mapped to default ID 39.")
                     
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
        # 1. api/IndexedTagValues/GetIndexedTagValues (Verified from C# SDK) - EXPECTS INTEGER ID
        # 2. api/Tag/GetStructure (Tree) - Usually takes GUID or ID? C# SDK uses GetTagValuesAsync with long.
        # 3. api/IndexedTagValues (Flat list)
        
        candidates = []
        if int_id is not None:
             # Case sensitive on some servers: IndexedTagValues vs indexedTagValues
             candidates.append(f"/api/IndexedTagValues/GetIndexedTagValues?indexedTagId={int_id}&pageIndex=0&pageSize=1000")
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
                               search_term: Optional[str] = None,
                               untagged_fields: List[str] = None,
                               status_filter: str = "all") -> int:
        """
        """
        logging.info(f"[DAMINION] get_filtered_item_count: scope={scope}, status={status_filter}, untagged={untagged_fields}, search={search_term}")
        
        # 1. Simple Case: All items, no sub-filters
        if scope == "all" and status_filter == "all" and not untagged_fields:
            total = self.get_total_count()
            logging.info(f"[DAMINION] Base case: All items. Count: {total}")
            return total

        # 2. Scope-based counting
        if scope == "saved_search" and saved_search_id:
             # Most Saved Searches return totalCount in the MediaItems/Get response
             try:
                 endpoint = f"/api/MediaItems/Get?query={self.SAVED_SEARCH_TAG_ID}:{saved_search_id}&start=0&length=1"
                 resp = self._make_request(endpoint)
                 if isinstance(resp, dict): return resp.get('totalCount', 0)
             except: pass

        if scope == "collection" and collection_id:
             # Use GetDetails endpoint which should have itemCount
             try:
                  details_ep = f"/api/SharedCollection/GetDetails/{collection_id}"
                  details = self._make_request(details_ep)
                  if isinstance(details, dict):
                       # Try various count field names, avoid HTTP status values (200, 201, etc)
                       for key in ['itemCount', 'count', 'totalItems', 'recordsTotal', 'totalCount']:
                           count_val = details.get(key)
                           if count_val is not None and isinstance(count_val, int):
                               # Skip if it looks like an HTTP status code
                               if 200 <= count_val <= 299 and count_val != details.get('itemCount'):
                                   continue
                               return count_val
             except Exception:
                  pass
             # Fallback: fetch actual items and count
             items = self.get_shared_collection_items(collection_id, page_size=500)
             return len(items) if items else 0


        if scope == "search" and search_term:
             # Use the proper keyword search method that looks up value IDs
             count = self.get_keyword_search_count(search_term)
             if count > 0:
                  logging.info(f"[DAMINION] get_keyword_search_count for '{search_term}' is {count}")
                  return count
             # Fallback to direct tag text query count
             logging.info(f"[DAMINION] keyword search count failed for '{search_term}', trying direct tag text fallback...")
             keywords_tag_id = self._tag_id_map.get('Keywords') or self._tag_id_map.get('keywords') or 13
             count = self.search_count(f"{keywords_tag_id},{search_term}")
             return count


        # 3. All Items with Filters: Try search variants
        if scope == "all":
            query_parts = []
            if status_filter == "approved": query_parts.append("status:approved")
            elif status_filter == "rejected": query_parts.append("status:rejected")
            elif status_filter == "unassigned": query_parts.append("status:unassigned")
            
            # Untagged (approximate with status:untagged)
            if untagged_fields:
                query_parts.append("status:untagged")
                
            if query_parts:
                combined_query = " ".join(query_parts)
                count = self._count_query(combined_query)
                if count > 0: return count
                
                # Try variants if 0 (0 might mean "no results" OR "query not understood")
                # If total_count is 1M, 0 is suspicious for status:unassigned.
                if "status:approved" in combined_query:
                     count = self._count_query("flag:flagged")
                     if count > 0: return count
                if "status:unassigned" in combined_query:
                     count = self._count_query("flag:unflagged")
                     if count > 0: return count
        
        # 4. Final Fallback: If we can't count efficiently, return -1 to signal UI
        return -1

    def _count_query(self, query: str) -> int:
        """Helper to count via Search endpoint."""
        try:
            # Use /api/MediaItems/Get with search param to get totalCount
            params = urllib.parse.urlencode({
                "search": query,
                "start": 0,
                "length": 1
            })
            endpoint = f"/api/MediaItems/Get?{params}"
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
                    # Try common synonyms for Classification/Category
                    guid = (self._tag_map.get('Categories') or 
                            self._tag_map.get('Subject') or 
                            self._tag_map.get('Classification') or
                            self._tag_map.get('Project'))
                    if not guid:
                        # Fallback to Keywords so we at least save the data, but log as warning
                        guid = self._tag_map.get('Keywords')
                        if guid:
                            logging.warning(f"[DAMINION] 'Category' tag not found. Remapped to 'Keywords' for persistence.")

                # Special handling for 'Description' synonyms
                if not guid and (raw_key == 'Description' or raw_key == 'Caption'):
                    # Try common Daminion names for the description/caption field
                    guid = (self._tag_map.get('Description') or 
                            self._tag_map.get('Caption') or 
                            self._tag_map.get('Headline') or 
                            self._tag_map.get('Annotation') or
                            self._tag_map.get('Notes'))

                if guid:
                    logging.debug(f"[DAMINION] Mapped tag '{raw_key}' -> {guid}")
                    item['guid'] = guid
                else:
                    logging.warning(f"[DAMINION] Warning: Could not find GUID for tag '{raw_key}'. Sending as-is (might fail if server is strict).")
                    final_data_items.append(item)
                    continue # Skip the direct append below as we handled it here

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

            logging.info(f"[DAMINION] Successfully updated tags for all {len(item_ids)} items")

        return all_successful

    def get_items_by_saved_search(self, search_name_or_id: Union[str, int], page: int = 1, page_size: int = 50) -> Dict:
        """
        Retrieve items belonging to a specific Saved Search.

        Args:
            search_name_or_id: The Name or ID of the saved search. 
                               Note: Using Name might require the saved search to be retrievable via get_saved_searches,
                               which is currently limited. Integers are treated as Value IDs for Tag 40.
            page: Page number (1-based).
            page_size: Number of items per page.

        Returns:
            Dict containing 'items' list and 'total_count'.
        """
        # If it's a string, we might want to try to resolve it to an ID if possible, 
        # but since listing fails, we might just pass it as a value and hope the query engine handles it.
        # Ideally, we pass the ID.
        
        # We use the Tag ID 40 for Saved Searches.
        query = {
             "Saved Searches": [search_name_or_id]
        }
        return self.get_items_by_query(query, page=page, page_size=page_size)

    def get_items_by_shared_collection(self, collection_name_or_id: Union[str, int], page: int = 1, page_size: int = 50) -> Dict:
        """
        Retrieve items belonging to a specific Shared Collection.

        Args:
            collection_name_or_id: The Name or ID of the shared collection.
            page: Page number (1-based).
            page_size: Number of items per page.

        Returns:
             Dict containing 'items' list and 'total_count'.
        """
        # We use Tag ID 46 for Shared Collections.
        query = {
             "Shared Collections": [collection_name_or_id]
        }
        return self.get_items_by_query(query, page=page, page_size=page_size)

    def get_items_by_query(self, query: Dict[str, Union[str, int, List[Union[str, int]]]], 
                          operators: Dict[str, str] = None,
                          page: int = 1, 
                          page_size: int = 50) -> Dict:
        """
        Search for media items using a specialized query dictionary.
        
        Args:
            query: Dictionary where key is Tag Name (e.g. 'Keywords', 'Saved Searches') 
                   and value is the value(s) to search for.
            operators: Optional dict mapping Tag Name to operator ('AND', 'OR', 'IS'). Defaults to OR.
            page: Page number (1-based).
            page_size: Number of items per page.
            
        Returns:
            Dict with 'items' (List[Dict]) and 'total_count' (int).
        """
        if not self.authenticated:
             self.authenticate()

        # Construct parameters for filtering
        query_lines = []
        f_params = []

        # Ensure tag map is loaded
        if not self._tag_map:
            self.get_tag_schema()

        for tag_name, values in query.items():
            # Resolve tag_name to GUID
            guid = self._tag_map.get(tag_name) or self._tag_map.get(tag_name.lower())
            if not guid:
                logging.warning(f"[DAMINION] Could not find GUID for tag '{tag_name}'. Skipping.")
                continue

            # Ensure values is a list
            if not isinstance(values, list):
                values = [values]

            # Build queryLine part
            query_parts = []
            for val in values:
                if isinstance(val, int): # Handle raw IDs
                    query_parts.append(f"{guid},{val}")
                else: # Handle string values
                    query_parts.append(f"{guid},'{val}'") # Wrap string values in single quotes

            query_lines.append(" OR ".join(query_parts)) # Default to OR for multiple values of the same tag

            # Build f_param part (operators)
            op = operators.get(tag_name, 'any') if operators else 'any' # Default to 'any' (OR)
            f_params.append(f"{guid},{op}")

        final_query_line = " AND ".join(query_lines) # Combine different tags with AND
        final_f_param = ";".join(f_params)

        if not final_query_line:
            return {'Items': [], 'TotalCount': 0}

        start = (page - 1) * page_size
            
        params = {
            'queryLine': final_query_line,
            'f': final_f_param,
            'index': start,
            'size': page_size,
            # Legacy fallbacks
            'search': final_query_line,
            'start': start,
            'length': page_size
        }
        
        response = self._make_request(f"/api/MediaItems/Get?{urllib.parse.urlencode(params)}")
        return self._normalize_items_response(response)

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

    # ==================== MERGED FROM DaminionAPI ====================
    # Flag filtering, rating filter, favorites, AI processing, catalog stats
    
    def _normalize_items_response(self, response: Any) -> Dict:
        """
        Normalize various API response formats into a consistent structure.
        
        Returns:
            Dict with 'Items' (list) and 'TotalCount' (int)
        """
        if response is None:
            return {'Items': [], 'TotalCount': 0}
        
        if isinstance(response, list):
            return {'Items': response, 'TotalCount': len(response)}
        
        if isinstance(response, dict):
            # Daminion uses 'mediaItems' for item lists (primary)
            items = (response.get('mediaItems') or response.get('Items') or 
                    response.get('items') or response.get('Data') or 
                    response.get('data') or [])
            
            # Daminion uses 'recordsTotal' or 'data' for total count
            total = (response.get('recordsTotal') or response.get('TotalCount') or 
                    response.get('totalCount') or response.get('Total') or 
                    response.get('total') or response.get('Count') or 
                    response.get('count') or len(items))
            
            return {'Items': items, 'TotalCount': total}
        
        return {'Items': [], 'TotalCount': 0}

    # --- Flag Filtering ---
    # Based on network interception: Flag Tag ID = 42
    # Unflagged = 1, Flagged = 2, Rejected = 3
    FLAGS_TAG_ID = 42
    FLAG_VALUE_UNFLAGGED = 1
    FLAG_VALUE_FLAGGED = 2
    FLAG_VALUE_REJECTED = 3

    def get_flagged_items_filtered(self, page_index: int = 0, page_size: int = 100) -> Dict:
        """
        Retrieve items marked as 'Flagged'.
        """
        # Note: FLAGS_TAG_ID is numeric ID 42, but get_items_by_query expects tag names
        # We'll use direct API call instead since this uses numeric IDs
        query_str = f"{self.FLAGS_TAG_ID},{self.FLAG_VALUE_FLAGGED}"
        operators = f"{self.FLAGS_TAG_ID},any"
        # Use search_items which accepts string queries
        result = self.search_items(query_str, operators, page_index=page_index, page_size=page_size)
        items = self._normalize_items_response(result).get('Items', [])
        count = self.search_count(query_str, operators=operators)
        return {'Items': items, 'TotalCount': count}

    def get_rejected_items_filtered(self, page_index: int = 0, page_size: int = 100) -> Dict:
        """
        Retrieve items marked as 'Rejected'.
        """
        query_str = f"{self.FLAGS_TAG_ID},{self.FLAG_VALUE_REJECTED}"
        operators = f"{self.FLAGS_TAG_ID},any"
        # Use search_items which accepts string queries
        result = self.search_items(query_str, operators, page_index=page_index, page_size=page_size)
        items = self._normalize_items_response(result).get('Items', [])
        count = self.search_count(query_str, operators=operators)
        return {'Items': items, 'TotalCount': count}

    def get_unflagged_items_filtered(self, page_index: int = 0, page_size: int = 100) -> Dict:
        """
        Retrieve items without any flag.
        """
        query_str = f"{self.FLAGS_TAG_ID},{self.FLAG_VALUE_UNFLAGGED}"
        operators = f"{self.FLAGS_TAG_ID},any"
        # Use search_items which accepts string queries
        result = self.search_items(query_str, operators, page_index=page_index, page_size=page_size)
        items = self._normalize_items_response(result).get('Items', [])
        count = self.search_count(query_str, operators=operators)
        return {'Items': items, 'TotalCount': count}

    # --- Rating Filter ---

    def get_items_by_rating(self, min_rating: int = 1, max_rating: int = 5, 
                           page_index: int = 0, page_size: int = 100) -> Dict:
        """
        Retrieve items within a rating range (1-5 stars).
        
        Returns:
            Dict with 'Items' list and 'TotalCount' integer
        """
        if min_rating == max_rating:
            query = f'Rating:={min_rating}'
        else:
            query = f'Rating:>={min_rating} AND Rating:<={max_rating}'
        
        params = urllib.parse.urlencode({
            'search': query,
            'start': page_index * page_size,
            'length': page_size
        })
        response = self._make_request(f"/api/MediaItems/Get?{params}")
        return self._normalize_items_response(response)

    # --- Text Search with Normalized Response ---

    def search_items(self, queryBody: str, operators: Optional[str] = None, index: int = 0, 
                     page_index: Optional[int] = None, page_size: int = 100) -> Dict:
        """
        Search for items using the discovered queryLine and size parameters.
        Supports cumulative filters if queryBody and operators contain semicolons.
        """
        if not self.authenticated:
            self.authenticate()

        start = index
        if page_index is not None:
            start = page_index * page_size
            
        # Determine tag ID mapping if not already set
        kw_tag_id = getattr(self, 'KEYWORDS_TAG_ID', None)
        if kw_tag_id is None:
            self.get_tag_schema()
            kw_tag_id = getattr(self, 'KEYWORDS_TAG_ID', 13)
        
        f_param = operators or f"{kw_tag_id},all"

        params = {
            'queryLine': queryBody,
            'f': f_param,
            'index': start,
            'size': page_size,
            # Legacy fallbacks
            'search': queryBody,
            'start': start,
            'length': page_size
        }
        
        return self._make_request(f"/api/MediaItems/Get?{urllib.parse.urlencode(params)}")

    def text_search(self, query: str, page_index: int = 0, page_size: int = 100) -> Dict:
        """Full-text search (alias for search_items)."""
        return self._normalize_items_response(self.search_items(query, page_index=page_index, page_size=page_size))


    # --- Favorites (Tray) Operations ---

    def get_favorites(self) -> List[Dict]:
        """GET api/MediaItems/Tray - Get items in favorites/tray."""
        try:
            response = self._make_request("/api/MediaItems/Tray")
            return self._normalize_items_response(response).get('Items', [])
        except DaminionAPIError:
            return []

    def add_to_favorites(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/AppendToTray - Add items to favorites."""
        try:
            self._make_request("/api/MediaItems/AppendToTray", method='POST', data=item_ids)
            return True
        except DaminionAPIError:
            return False

    def clear_favorites(self) -> bool:
        """POST api/MediaItems/ClearTray/0 - Clear all favorites."""
        try:
            self._make_request("/api/MediaItems/ClearTray/0", method='POST')
            return True
        except DaminionAPIError:
            return False

    # --- AI Processing ---

    def process_ai_labels(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/ProcessAILabels - Trigger AI labeling for items."""
        try:
            self._make_request("/api/MediaItems/ProcessAILabels", method='POST', data=item_ids)
            return True
        except DaminionAPIError:
            return False

    def process_ai_labels_query(self, query: str) -> bool:
        """POST api/MediaItems/ProcessAILabelsQuery - AI labeling by query."""
        try:
            self._make_request("/api/MediaItems/ProcessAILabelsQuery", method='POST', data=query)
            return True
        except DaminionAPIError:
            return False

    # --- Item Approval/Deletion ---

    def approve_items(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/ApproveItems - Approve pending items."""
        try:
            self._make_request("/api/MediaItems/ApproveItems", method='POST', data=item_ids)
            return True
        except DaminionAPIError:
            return False

    def delete_items(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/Remove - Delete items from catalog."""
        try:
            self._make_request("/api/MediaItems/Remove", method='POST', data=item_ids)
            return True
        except DaminionAPIError:
            return False

    # --- Settings ---

    def get_watermark_data(self, guid: str) -> Dict:
        """GET api/Settings/GetWatermarkData - Get watermark configuration."""
        try:
            return self._make_request(f"/api/Settings/GetWatermarkData?guid={guid}")
        except DaminionAPIError:
            return {}

    def get_security_mode(self) -> str:
        """GET api/Settings/GetSecurityMode - Get security mode setting."""
        try:
            response = self._make_request("/api/Settings/GetSecurityMode")
            return str(response) if response else ""
        except DaminionAPIError:
            return ""

    # --- User Management ---

    def get_users(self) -> List[Dict]:
        """GET api/UserManager/GetUsers - Get list of users."""
        try:
            response = self._make_request("/api/UserManager/GetUsers")
            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                return response.get('users', response.get('items', []))
            return []
        except DaminionAPIError:
            return []

    def get_roles(self) -> List[Dict]:
        """GET api/UserManager/GetRoles - Get list of roles."""
        try:
            response = self._make_request("/api/UserManager/GetRoles")
            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                return response.get('roles', response.get('items', []))
            return []
        except DaminionAPIError:
            return []

    # --- Catalog Statistics ---

    def get_catalog_stats(self) -> Dict[str, Any]:
        """
        Get overall catalog statistics.
        
        Returns:
            Dict with total_items, collections_count, saved_searches_count
        """
        stats = {
            'total_items': 0,
            'collections_count': 0,
            'saved_searches_count': 0
        }
        
        try:
            stats['total_items'] = self.get_total_count()
        except DaminionAPIError:
            pass
        
        try:
            collections = self.get_shared_collections()
            if collections:
                stats['collections_count'] = len(collections)
        except DaminionAPIError:
            pass
        
        try:
            searches = self.get_saved_searches()
            if searches:
                stats['saved_searches_count'] = len(searches)
        except DaminionAPIError:
            pass
        
        return stats

    # --- Thumbnail URL ---

    def get_thumbnail_url(self, item_id: int, width: int = 200, height: int = 200) -> str:
        """Returns the URL for a thumbnail."""
        return f"{self.base_url}/api/Thumbnail/Get/{item_id}?width={width}&height={height}"

    # --- Pagination Helper ---

    def paginate_results(self, fetch_func: Callable, page_size: int = 100, 
                        max_items: Optional[int] = None) -> List[Dict]:
        """
        Helper to paginate through all results using a fetch function.
        
        Args:
            fetch_func: Function that takes (page_index, page_size) and returns {'Items': [], 'TotalCount': int}
            page_size: Items per page
            max_items: Maximum items to retrieve (None = all)
            
        Returns:
            List of all items
        """
        all_items = []
        page_index = 0
        
        while True:
            result = fetch_func(page_index, page_size)
            items = result.get('Items', [])
            total = result.get('TotalCount', 0)
            
            if not items:
                break
            
            all_items.extend(items)
            
            if len(all_items) >= total:
                break
            if max_items and len(all_items) >= max_items:
                all_items = all_items[:max_items]
                break
            
            page_index += 1
        
        return all_items

    def get_all_flagged_items(self, max_items: Optional[int] = None) -> List[Dict]:
        """Retrieve all flagged items with automatic pagination."""
        return self.paginate_results(
            lambda pi, ps: self.get_flagged_items_filtered(page_index=pi, page_size=ps),
            max_items=max_items
        )

    def get_all_search_results(self, query: str, max_items: Optional[int] = None) -> List[Dict]:
        """Retrieve all items matching a search query with automatic pagination."""
        return self.paginate_results(
            lambda pi, ps: self.text_search(query, page_index=pi, page_size=ps),
            max_items=max_items
        )

    # ==================== KEYWORD SEARCH BY TAG VALUE ====================
    
    def search_by_keyword(self, keyword: str, page_size: int = 500) -> Tuple[List[Dict], int]:
        """
        Search for items by keyword using proper IndexedTagValues query.
        
        This uses the correct Daminion API pattern:
        1. Find the Keywords tag ID from schema
        2. Query IndexedTagValues to find the value ID for the keyword
        3. Use query={TagID},{ValueID}&operators={TagID},any format
        
        Args:
            keyword: The keyword value to search for (e.g., "abaya")
            page_size: Max items to return
            
        Returns:
            Tuple of (items list, total count)
        """
        # Ensure tag schema is loaded
        if not self._tag_id_map:
            self.get_tag_schema()
        
        # Get Keywords tag ID (typically 5000 or similar)
        keywords_tag_id = self._tag_id_map.get('Keywords') or self._tag_id_map.get('keywords')
        
        if not keywords_tag_id:
            logging.warning("[DAMINION] Keywords tag ID not found in schema")
            # Try common default
            keywords_tag_id = 5000
        
        logging.info(f"[DAMINION] Searching for keyword '{keyword}' using tag ID {keywords_tag_id}")
        
        # Try multiple endpoint formats for compatibility with different Daminion versions
        # Note: parentValueId=-2 means "search everywhere" (all hierarchy levels)
        endpoint_formats = [
            # Format 1: Query params at root with parentValueId (required parameter)
            f"/api/IndexedTagValues?indexedTagId={keywords_tag_id}&parentValueId=-2&filter={urllib.parse.quote(keyword)}&pageIndex=0&pageSize=100",
            # Format 2: FindValues endpoint
            f"/api/IndexedTagValues/FindValues?indexedTagId={keywords_tag_id}&parentValueId=-2&filter={urllib.parse.quote(keyword)}&pageIndex=0&pageSize=100",
            # Format 3: GetIndexedTagValues path (newer servers)
            f"/api/IndexedTagValues/GetIndexedTagValues?indexedTagId={keywords_tag_id}&parentValueId=-2&filter={urllib.parse.quote(keyword)}&pageIndex=0&pageSize=100",
        ]
        
        values_response = None
        for endpoint in endpoint_formats:
            try:
                values_response = self._make_request(endpoint)
                if values_response:
                    logging.info(f"[DAMINION] IndexedTagValues endpoint working: {endpoint.split('?')[0]}")
                    break
            except DaminionAPIError as e:
                if "404" in str(e):
                    continue
                raise
        
        if not values_response:
            logging.warning(f"[DAMINION] No IndexedTagValues endpoint available for keyword lookup")
            return [], 0
        
        keyword_value_id = None
        total_items_for_keyword = 0
        
        if isinstance(values_response, dict):
            values_list = values_response.get('values') or values_response.get('items') or values_response.get('data') or []
            logging.info(f"[DAMINION] IndexedTagValues returned {len(values_list)} items. Looking for '{keyword}'")
            for v in values_list:
                v_name = v.get('text') or v.get('value') or v.get('name') or v.get('title') or ''
                logging.debug(f"[DAMINION] Checking tag value: '{v_name}'")
                if v_name.lower() == keyword.lower():
                    keyword_value_id = v.get('id') or v.get('valueId')
                    total_items_for_keyword = v.get('count', 0)
                    logging.info(f"[DAMINION] Found keyword '{keyword}' with value ID: {keyword_value_id}, count: {total_items_for_keyword}")
                    break
        elif isinstance(values_response, list):
            logging.info(f"[DAMINION] IndexedTagValues returned {len(values_response)} items. Looking for '{keyword}'")
            for v in values_response:
                v_name = v.get('text') or v.get('value') or v.get('name') or v.get('title') or ''
                logging.debug(f"[DAMINION] Checking tag value: '{v_name}'")
                if v_name.lower() == keyword.lower():
                    keyword_value_id = v.get('id') or v.get('valueId')
                    total_items_for_keyword = v.get('count', 0)
                    break
        
        # If we found an ID, use it for exact match
        if keyword_value_id:
            # Build proper query dictionary for get_items_by_query
            query = {"Keywords": keyword_value_id}
            operators = {"Keywords": "any"}
            logging.info(f"[DAMINION] Keyword search with ID: Keywords={keyword_value_id}")
            result = self.get_items_by_query(query, operators, page_size=page_size)
            items = result.get('Items', [])
            
            # If the index count is 0 or missing, use search_count to get the true result count
            actual_count = total_items_for_keyword
            if actual_count <= 0:
                actual_count = self.search_count(query)
            
            # If search_count also fails, fall back to results length
            if actual_count <= 0:
                actual_count = len(items)
                
            logging.info(f"[DAMINION] Keyword ID results: {len(items)} items, count {actual_count}")
            return items, actual_count
            
        # Fallback: try text-based keyword search through query dictionary
        logging.info(f"[DAMINION] Keyword ID not found, trying direct tag text query for '{keyword}'")
        query = {"Keywords": keyword}
        operators = {"Keywords": "any"}
        result = self.get_items_by_query(query, operators, page_size=page_size)
        items = result.get('Items', [])
        
        # For text query, we need to get total count specifically
        # Need to use the numeric tag ID for search_count
        count_query = f"{keywords_tag_id}:'{keyword}'"
        count = self.search_count(count_query)
        logging.info(f"[DAMINION] Keyword text fallback: {len(items)} items, search_count {count}")
        return items, count

    def get_keyword_search_count(self, keyword: str) -> int:
        """
        Get count of items matching a keyword without fetching all items.
        
        Args:
            keyword: The keyword to search for
            
        Returns:
            Count of matching items
        """
        if not self._tag_id_map:
            self.get_tag_schema()
        
        keywords_tag_id = self._tag_id_map.get('Keywords') or self._tag_id_map.get('keywords') or 5000
        
        # Try multiple endpoint formats (with parentValueId=-2 for searching all levels)
        endpoint_formats = [
            f"/api/IndexedTagValues?indexedTagId={keywords_tag_id}&parentValueId=-2&filter={urllib.parse.quote(keyword)}&pageIndex=0&pageSize=100",
            f"/api/IndexedTagValues/FindValues?indexedTagId={keywords_tag_id}&parentValueId=-2&filter={urllib.parse.quote(keyword)}&pageIndex=0&pageSize=100",
            f"/api/IndexedTagValues/GetIndexedTagValues?indexedTagId={keywords_tag_id}&parentValueId=-2&filter={urllib.parse.quote(keyword)}&pageIndex=0&pageSize=100",
        ]
        
        for endpoint in endpoint_formats:
            try:
                values_response = self._make_request(endpoint)
                if not values_response:
                    continue
                    
                values_list = []
                if isinstance(values_response, dict):
                    values_list = values_response.get('values') or values_response.get('items') or values_response.get('data') or []
                elif isinstance(values_response, list):
                    values_list = values_response
                
                for v in values_list:
                    v_name = v.get('text') or v.get('value') or v.get('name') or v.get('title') or ''
                    if v_name.lower() == keyword.lower():
                        count = v.get('count', 0)
                        if count > 0:
                            return count
                        # If no count in response, we need to query
                        keyword_value_id = v.get('id') or v.get('valueId')
                        if keyword_value_id:
                            # Use GetCount with query format
                            query = f"{keywords_tag_id},{keyword_value_id}"
                            return self.search_count(query)
                # If we get here, we reached the end of the list without exact text match
                # Try direct tag text query count as fallback
                logging.info(f"[DAMINION] Keyword ID not found for count, trying direct tag text query: search=Keywords:{keyword}")
                return self.search_count(f"Keywords:{keyword}")
            except DaminionAPIError as e:
                if "404" in str(e):
                    continue
                return 0
        
        # Last fallback
        return self.search_count(f"Keywords:{keyword}")


    def get_all_keywords(self, page_size: int = 1000) -> List[Dict]:
        """
        Get all available keywords in the catalog.
        
        Returns:
            List of keyword dicts with 'value', 'id', and 'count' keys
        """
        if not self._tag_id_map:
            self.get_tag_schema()
        
        keywords_tag_id = self._tag_id_map.get('Keywords') or self._tag_id_map.get('keywords') or 5000
        
        try:
            endpoint = f"/api/IndexedTagValues/GetIndexedTagValues?indexedTagId={keywords_tag_id}&pageIndex=0&pageSize={page_size}"
            values_response = self._make_request(endpoint)
            
            if isinstance(values_response, dict):
                return values_response.get('values') or values_response.get('items') or []
            elif isinstance(values_response, list):
                return values_response
            return []
        except DaminionAPIError:
            return []

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

    def search_count(self, query: str, operators: Optional[str] = None) -> int:
        """
        Get count of items matching a query.
        Uses both 'queryLine' and 'search' parameters for cross-version compatibility.
        """
        if not self.authenticated:
            self.authenticate()

        kw_tag_id = getattr(self, 'KEYWORDS_TAG_ID', None)
        if kw_tag_id is None:
            self.get_tag_schema()
            kw_tag_id = getattr(self, 'KEYWORDS_TAG_ID', 13)
            
        f_param = operators or f"{kw_tag_id},all"
        
        # 1. Try MediaItems/GetCount (Discovered format)
        try:
            params = {
                "queryLine": query,
                "f": f_param,
                "force": "false"
            }
            logging.info(f"[DAMINION] search_count trying GetCount (new format): {params}")
            endpoint = f"/api/MediaItems/GetCount?{urllib.parse.urlencode(params)}"
            resp = self._make_request(endpoint)
            
            if isinstance(resp, int):
                return resp
            if isinstance(resp, dict):
                count = resp.get('data') or resp.get('totalCount') or resp.get('count')
                if isinstance(count, int):
                    return count
        except Exception as e:
            logging.debug(f"[DAMINION] GetCount (new format) failed: {e}")

        # 2. Try MediaItems/GetCount (Legacy search format)
        try:
            params = {"search": query}
            endpoint = f"/api/MediaItems/GetCount?{urllib.parse.urlencode(params)}"
            resp = self._make_request(endpoint)
            
            if isinstance(resp, int):
                return resp
            if isinstance(resp, dict):
                count = resp.get('data') or resp.get('totalCount') or resp.get('count')
                if isinstance(count, int):
                    return count
        except Exception:
            pass

        # 3. Try MediaItems/Get with size=1 (Final fallback)
        try:
            params = {
                "queryLine": query,
                "f": f_param,
                "index": 0,
                "size": 1
            }
            endpoint = f"/api/MediaItems/Get?{urllib.parse.urlencode(params)}"
            resp = self._make_request(endpoint)
            if isinstance(resp, dict):
                return resp.get('totalCount') or resp.get('recordsTotal') or 0
        except Exception:
            pass
            
        return 0

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
