"""
Daminion Server Web API Client

A comprehensive, production-ready client for the Daminion Server Web API.
Based on official API documentation: https://marketing.daminion.net/APIHelp

This module provides a clean, intuitive interface to all major Daminion API endpoints
with proper error handling, type hints, and session management.

Author: Synapic Project
Version: 2.0.0
Last Updated: 2026-01-18
"""

import logging
import urllib.request
import urllib.parse
import urllib.error
import json
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# EXCEPTIONS
# ============================================================================

class DaminionAPIError(Exception):
    """Base exception for all Daminion API errors."""
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


class DaminionNotFoundError(DaminionAPIError):
    """Raised when a resource is not found (404)."""
    pass


class DaminionPermissionError(DaminionAPIError):
    """Raised when user lacks permissions for an operation."""
    pass


# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class SortOrder(Enum):
    """Sort order enumeration."""
    ASCENDING = "asc"
    DESCENDING = "desc"


class FilterOperator(Enum):
    """Filter operators for tag queries."""
    ANY = "any"  # Match any of the values
    ALL = "all"  # Match all values
    NONE = "none"  # Match none of the values


@dataclass
class TagInfo:
    """Information about a Daminion tag."""
    id: int
    guid: str
    name: str
    type: str
    indexed: bool = False


@dataclass
class TagValue:
    """A value for an indexed tag."""
    id: int
    text: str
    count: int = 0
    parent_id: Optional[int] = None


@dataclass
class MediaItem:
    """Represents a media item in Daminion."""
    id: int
    guid: str
    filename: str
    path: str
    properties: Dict[str, Any]


@dataclass
class SharedCollection:
    """Represents a shared collection."""
    id: int
    name: str
    code: str
    item_count: int
    created: str
    modified: str


# ============================================================================
# MAIN API CLIENT
# ============================================================================

class DaminionAPI:
    """
    Comprehensive Daminion Server Web API Client.
    
    Provides access to all major Daminion API endpoints with a clean,
    intuitive interface. Handles authentication, rate limiting, and
    error management automatically.
    
    Usage:
        ```python
        # Context manager (recommended)
        with DaminionAPI(server_url, username, password) as api:
            items = api.media_items.search(query="city")
            collections = api.collections.get_all()
        
        # Manual resource management
        api = DaminionAPI(server_url, username, password)
        api.authenticate()
        try:
            items = api.media_items.search(query="city")
        finally:
            api.logout()
        ```
    
    Attributes:
        media_items: MediaItemsAPI - Media item operations
        tags: TagsAPI - Tag and tag value operations
        collections: CollectionsAPI - Shared collections operations
        item_data: ItemDataAPI - Item metadata operations
        settings: SettingsAPI - Server settings and configuration
        thumbnails: ThumbnailsAPI - Thumbnail and preview operations
        downloads: DownloadsAPI - File download and export operations
        imports: ImportsAPI - File import operations
        user_manager: UserManagerAPI - User and role management
    """
    
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        catalog_id: Optional[int] = None,
        rate_limit: float = 0.1,
        timeout: int = 30
    ):
        """
        Initialize the Daminion API client.
        
        Args:
            base_url: Base URL of Daminion server (e.g., "https://example.daminion.net")
            username: Daminion username
            password: Daminion password
            catalog_id: Optional catalog ID (if server has multiple catalogs)
            rate_limit: Minimum seconds between API calls (default: 0.1)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.catalog_id = catalog_id
        self.rate_limit = rate_limit
        self.timeout = timeout
        
        # Session management
        self._cookies: Dict[str, str] = {}
        self._authenticated = False
        self._last_request_time = 0.0
        
        # Initialize sub-APIs
        self.media_items = MediaItemsAPI(self)
        self.tags = TagsAPI(self)
        self.collections = CollectionsAPI(self)
        self.item_data = ItemDataAPI(self)
        self.settings = SettingsAPI(self)
        self.thumbnails = ThumbnailsAPI(self)
        self.downloads = DownloadsAPI(self)
        self.imports = ImportsAPI(self)
        self.user_manager = UserManagerAPI(self)
        
        logging.info(f"Initialized DaminionAPI for {self.base_url}")
    
    # ------------------------------------------------------------------------
    # CONTEXT MANAGER
    # ------------------------------------------------------------------------
    
    def __enter__(self):
        """Enter context manager and authenticate."""
        self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and cleanup."""
        try:
            self.logout()
        except Exception as e:
            logging.warning(f"Error during logout: {e}")
        return False
    
    # ------------------------------------------------------------------------
    # AUTHENTICATION
    # ------------------------------------------------------------------------
    
    def authenticate(self) -> bool:
        """
        Authenticate with Daminion server and establish session.
        
        Returns:
            True if authentication successful
            
        Raises:
            DaminionAuthenticationError: If authentication fails
        """
        try:
            # Build query parameters (Daminion expects these in URL, not body)
            params = {
                "userName": self.username,
                "password": self.password
            }
            
            if self.catalog_id:
                params["catalogId"] = self.catalog_id
            
            # Make POST request with params in URL
            response = self._make_request(
                "/api/UserManager/Login",
                method="POST",
                params=params,
                skip_auth=True
            )
            
            self._authenticated = True
            logging.info(f"Successfully authenticated as {self.username}")
            return True
            
        except Exception as e:
            raise DaminionAuthenticationError(f"Authentication failed: {e}")
    
    def logout(self):
        """Log out and end session."""
        if self._authenticated:
            try:
                self._make_request("/api/UserManager/Logout", method="GET")
                logging.info("Logged out successfully")
            except Exception as e:
                logging.warning(f"Logout error: {e}")
            finally:
                self._authenticated = False
                self._cookies.clear()
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._authenticated
    
    # ------------------------------------------------------------------------
    # REQUEST HANDLING
    # ------------------------------------------------------------------------
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between API calls."""
        if self.rate_limit > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()
    
    def _get_cookie_header(self) -> str:
        """Generate cookie header string from stored cookies."""
        if not self._cookies:
            return ""
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())
    
    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        skip_auth: bool = False,
        skip_rate_limit: bool = False
    ) -> Any:
        """
        Make an authenticated API request.
        
        Args:
            endpoint: API endpoint (e.g., "/api/MediaItems/Get")
            method: HTTP method (GET, POST, etc.)
            data: Optional request body data (for POST/PUT)
            params: Optional URL query parameters
            skip_auth: Skip auth check (for login endpoint)
            skip_rate_limit: Skip rate limiting
            
        Returns:
            Response data (parsed JSON or raw content)
            
        Raises:
            DaminionAPIError: For various API errors
        """
        if not skip_auth and not self._authenticated:
            raise DaminionAuthenticationError("Not authenticated. Call authenticate() first.")
        
        if not skip_rate_limit:
            self._enforce_rate_limit()
        
        # Build URL
        url = f"{self.base_url}{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
        
        # Build request
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self._cookies:
            headers["Cookie"] = self._get_cookie_header()
        
        request_body = None
        if data is not None:
            request_body = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=request_body,
            headers=headers,
            method=method
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                # Store cookies from response
                cookie_header = response.getheader('Set-Cookie')
                if cookie_header:
                    for cookie in cookie_header.split(','):
                        if '=' in cookie:
                            key, value = cookie.split('=', 1)
                            value = value.split(';')[0].strip()
                            self._cookies[key.strip()] = value
                
                # Parse response
                content_type = response.getheader('Content-Type', '')
                response_data = response.read()
                
                if 'application/json' in content_type:
                    result = json.loads(response_data.decode('utf-8'))
                    
                    # Check for API-level errors
                    if isinstance(result, dict):
                        if not result.get('success', True):
                            error_msg = result.get('error', 'Unknown error')
                            error_code = result.get('errorCode', 0)
                            raise DaminionAPIError(f"API Error {error_code}: {error_msg}")
                        
                        # Return data field if present
                        if 'data' in result:
                            return result['data']
                    
                    return result
                else:
                    # Return raw binary data (for images, files, etc.)
                    return response_data
                    
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            
            if e.code == 401:
                self._authenticated = False
                raise DaminionAuthenticationError(f"Authentication required: {error_msg}")
            elif e.code == 403:
                raise DaminionPermissionError(f"Permission denied: {error_msg}")
            elif e.code == 404:
                raise DaminionNotFoundError(f"Resource not found: {error_msg}")
            elif e.code == 429:
                raise DaminionRateLimitError(f"Rate limit exceeded: {error_msg}")
            else:
                raise DaminionAPIError(f"API request failed: {error_msg}")
                
        except urllib.error.URLError as e:
            raise DaminionNetworkError(f"Network error: {e.reason}")
        except json.JSONDecodeError as e:
            raise DaminionAPIError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise DaminionAPIError(f"Request failed: {e}")


# ============================================================================
# SUB-API CLASSES
# ============================================================================

class BaseAPI:
    """Base class for sub-API implementations."""
    
    def __init__(self, client: DaminionAPI):
        self.client = client
    
    def _request(self, *args, **kwargs):
        """Shortcut to client._make_request()"""
        return self.client._make_request(*args, **kwargs)


class MediaItemsAPI(BaseAPI):
    """
    Media Items API - Search, retrieve, and manage media items.
    
    Endpoints:
        - Search for media items
        - Get items by ID or query
        - Get item counts
        - Manage favorites
        - Approve items
        - Delete items
    """
    
    def search(
        self,
        query: Optional[str] = None,
        query_line: Optional[str] = None,
        operators: Optional[str] = None,
        index: int = 0,
        page_size: int = 500,
        sort_tag: Optional[int] = None,
        ascending: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for media items using text or structured query.
        
        Args:
            query: Text search query (simple search)
            query_line: Structured query (e.g., "13,4949" for Keywords tag=13, value=4949)
            operators: Operators for each tag (e.g., "13,any")
            index: Starting index for pagination (default: 0)
            page_size: Number of items per page (default: 500)
            sort_tag: Optional tag ID to sort by
            ascending: Sort order (default: True)
            
        Returns:
            List of media item dictionaries
            
        Example:
            # Simple text search
            items = api.media_items.search(query="city")
            
            # Structured query (Keywords tag ID 13, value 4949)
            items = api.media_items.search(
                query_line="13,4949",
                operators="13,any"
            )
        """
        params = {
            "index": index,
            "size": page_size
        }
        
        if query:
            params["search"] = query
        if query_line:
            params["queryLine"] = query_line
        if operators:
            params["f"] = operators
        if sort_tag:
            params["sortag"] = sort_tag
            params["asc"] = str(ascending).lower()
        
        response = self._request("/api/MediaItems/Get", params=params)
        
        # Handle different response formats
        if isinstance(response, dict):
            return response.get('mediaItems', response.get('items', response.get('data', [])))
        return response if isinstance(response, list) else []
    
    def get_by_ids(self, item_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get media items by their IDs.
        
        Args:
            item_ids: List of item IDs to retrieve
            
        Returns:
            List of media item dictionaries
        """
        ids_str = ','.join(str(id) for id in item_ids)
        return self._request("/api/MediaItems/GetByIds", params={"ids": ids_str})
    
    def get_count(
        self,
        query_line: Optional[str] = None,
        operators: Optional[str] = None,
        force: bool = False
    ) -> int:
        """
        Get count of items matching query without retrieving full data.
        
        Args:
            query_line: Structured query
            operators: Operators for query
            force: Force refresh of cached count
            
        Returns:
            Number of matching items
        """
        params = {"force": str(force).lower()}
        if query_line:
            params["queryLine"] = query_line
        if operators:
            params["f"] = operators
        
        result = self._request("/api/MediaItems/GetCount", params=params)
        return result if isinstance(result, int) else result.get('count', 0)
    
    def get_absolute_path(self, item_id: int) -> str:
        """
        Get the absolute file path for a media item.
        
        Args:
            item_id: Media item ID
            
        Returns:
            Absolute file path
        """
        return self._request(f"/api/MediaItems/GetAbsolutePath/{item_id}")
    
    def get_favorites(self) -> List[Dict[str, Any]]:
        """
        Get current user's favorite media items.
        
        Returns:
            List of favorite media items
        """
        return self._request("/api/MediaItems/Tray")
    
    def add_to_favorites(self, item_ids: List[int]):
        """
        Add items to favorites (tray).
        
        Args:
            item_ids: List of item IDs to add
        """
        self._request(
            "/api/MediaItems/AppendToTray",
            method="POST",
            data={"itemIds": item_ids}
        )
    
    def clear_favorites(self):
        """Clear all favorite items."""
        self._request(f"/api/MediaItems/ClearTray/0", method="POST")
    
    def approve_items(self, item_ids: List[int]):
        """
        Approve (flag) media items.
        
        Args:
            item_ids: List of item IDs to approve
        """
        self._request(
            "/api/MediaItems/ApproveItems",
            method="POST",
            data={"itemIds": item_ids}
        )
    
    def delete_items(self, item_ids: List[int]):
        """
        Delete media items from catalog.
        
        Args:
            item_ids: List of item IDs to delete
        """
        self._request(
            "/api/MediaItems/Remove",
            method="POST",
            data={"itemIds": item_ids}
        )


class TagsAPI(BaseAPI):
    """
    Tags API - Manage tags and tag values.
    
    Endpoints:
        - Get tag schema
        - Get/create/update/delete tag values
        - Search tag values
        - Manage custom tags
    """
    
    def get_all_tags(self) -> List[TagInfo]:
        """
        Get all tags in the catalog with their IDs and metadata.
        
        Returns:
            List of TagInfo objects
        """
        tags_data = self._request("/api/Settings/GetTags")
        
        result = []
        if isinstance(tags_data, list):
            for tag in tags_data:
                result.append(TagInfo(
                    id=tag.get('id', 0),
                    guid=tag.get('guid', ''),
                    name=tag.get('name', ''),
                    type=tag.get('type', ''),
                    indexed=tag.get('indexed', False)
                ))
        
        return result
    
    def get_tag_values(
        self,
        tag_id: int,
        parent_value_id: int = -2,
        filter_text: str = "",
        page_index: int = 0,
        page_size: int = 500
    ) -> List[TagValue]:
        """
        Get values for an indexed tag (e.g., Keywords, Categories).
        
        Args:
            tag_id: Integer tag ID
            parent_value_id: Parent value ID for hierarchical tags (-2 = all levels)
            filter_text: Optional text filter
            page_index: Page index for pagination
            page_size: Number of values per page
            
        Returns:
            List of TagValue objects
        """
        params = {
            "indexedTagId": tag_id,
            "parentValueId": parent_value_id,
            "filter": filter_text,
            "pageIndex": page_index,
            "pageSize": page_size
        }
        
        response = self._request("/api/IndexedTagValues/GetIndexedTagValues", params=params)
        
        # Parse response
        values_data = response
        if isinstance(response, dict):
            values_data = response.get('values', response.get('items', response.get('data', [])))
        
        result = []
        for value in values_data:
            result.append(TagValue(
                id=value.get('id', value.get('valueId', 0)),
                text=value.get('text', value.get('value', value.get('name', ''))),
                count=value.get('count', 0),
                parent_id=value.get('parentId')
            ))
        
        return result
    
    def find_tag_values(
        self,
        tag_id: int,
        filter_text: str
    ) -> List[TagValue]:
        """
        Search for specific tag values by text.
        
        Args:
            tag_id: Tag ID to search within
            filter_text: Search text
            
        Returns:
            List of matching TagValue objects
        """
        params = {
            "indexedTagId": tag_id,
            "filter": filter_text
        }
        
        response = self._request("/api/IndexedTagValues/FindValues", params=params)
        
        values_data = response if isinstance(response, list) else response.get('values', [])
        
        return [
            TagValue(
                id=v.get('id', 0),
                text=v.get('text', ''),
                count=v.get('count', 0)
            )
            for v in values_data
        ]
    
    def create_tag_value(
        self,
        tag_guid: str,
        value_text: str,
        parent_id: Optional[int] = None
    ) -> int:
        """
        Create a new value for an indexed tag.
        
        Args:
            tag_guid: GUID of the tag
            value_text: Text for the new value
            parent_id: Optional parent value ID (for hierarchical tags)
            
        Returns:
            ID of created value
        """
        data = {
            "tagGuid": tag_guid,
            "value": value_text
        }
        if parent_id is not None:
            data["parentId"] = parent_id
        
        return self._request(
            "/api/IndexedTagValues/CreateValueByGuid",
            method="POST",
            data=data
        )
    
    def update_tag_value(
        self,
        tag_id: int,
        value_id: int,
        new_text: str
    ):
        """
        Update an existing tag value.
        
        Args:
            tag_id: Tag ID
            value_id: Value ID to update
            new_text: New text for the value
        """
        self._request(
            "/api/IndexedTagValues/ChangeValue",
            method="POST",
            data={
                "tagId": tag_id,
                "valueId": value_id,
                "newValue": new_text
            }
        )
    
    def delete_tag_value(
        self,
        tag_guid: str,
        value_id: int
    ):
        """
        Delete a tag value.
        
        Args:
            tag_guid: Tag GUID
            value_id: Value ID to delete
        """
        self._request(
            "/api/IndexedTagValues/DeleteValueByGuid",
            method="POST",
            data={
                "tagGuid": tag_guid,
                "valueId": value_id
            }
        )


class CollectionsAPI(BaseAPI):
    """
    Shared Collections API - Manage shared collections.
    
    Endpoints:
        - Get/create/update/delete shared collections
        - Get items in collections
        - Manage collection access codes
    """
    
    def get_all(
        self,
        index: int = 0,
        page_size: int = 100
    ) -> List[SharedCollection]:
        """
        Get list of shared collections.
        
        Args:
            index: Starting index for pagination
            page_size: Number of collections per page
            
        Returns:
            List of SharedCollection objects
        """
        params = {
            "index": index,
            "pageSize": page_size
        }
        
        response = self._request("/api/SharedCollection/GetCollections", params=params)
        
        collections_data = response
        if isinstance(response, dict):
            collections_data = response.get('collections', response.get('items', response.get('data', [])))
        
        result = []
        for coll in collections_data:
            result.append(SharedCollection(
                id=coll.get('id', 0),
                name=coll.get('name', coll.get('title', '')),
                code=coll.get('code', ''),
                item_count=coll.get('itemCount', coll.get('count', 0)),
                created=coll.get('created', ''),
                modified=coll.get('modified', '')
            ))
        
        return result
    
    def get_details(self, collection_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a shared collection.
        
        Args:
            collection_id: Collection ID
            
        Returns:
            Collection details dictionary
        """
        return self._request(f"/api/SharedCollection/GetDetails/{collection_id}")
    
    def get_items(
        self,
        collection_id: int,
        index: int = 0,
        page_size: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get media items in a shared collection.
        
        Args:
            collection_id: Collection ID
            index: Starting index
            page_size: Items per page
            
        Returns:
            List of media items
        """
        params = {
            "id": collection_id,
            "index": index,
            "pageSize": page_size
        }
        
        response = self._request("/api/SharedCollection/GetItems", params=params)
        
        if isinstance(response, dict):
            return response.get('items', response.get('mediaItems', response.get('data', [])))
        return response if isinstance(response, list) else []
    
    def create(
        self,
        name: str,
        description: str = "",
        item_ids: Optional[List[int]] = None
    ) -> int:
        """
        Create a new shared collection.
        
        Args:
            name: Collection name
            description: Collection description
            item_ids: Optional list of item IDs to add
            
        Returns:
            ID of created collection
        """
        data = {
            "name": name,
            "description": description
        }
        
        if item_ids:
            data["itemIds"] = item_ids
        
        result = self._request(
            "/api/SharedCollection/Create",
            method="POST",
            data=data
        )
        
        return result.get('id', 0) if isinstance(result, dict) else result
    
    def update(
        self,
        collection_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        Update shared collection properties.
        
        Args:
            collection_id: Collection ID
            name: New name (optional)
            description: New description (optional)
        """
        data = {"id": collection_id}
        
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        
        self._request(
            "/api/SharedCollection/Change",
            method="POST",
            data=data
        )
    
    def delete(self, collection_ids: List[int]):
        """
        Delete shared collections.
        
        Args:
            collection_ids: List of collection IDs to delete
        """
        self._request(
            "/api/SharedCollection/Delete",
            method="POST",
            data={"ids": collection_ids}
        )


class ItemDataAPI(BaseAPI):
    """
    Item Data API - Manage media item metadata and tags.
    
    Endpoints:
        - Get item metadata
        - Batch update tags
        - Get/set property panel layouts
    """
    
    def get(self, item_id: int, get_all: bool = False) -> Dict[str, Any]:
        """
        Get metadata for a media item.
        
        Args:
            item_id: Media item ID
            get_all: If True, get all metadata; if False, get based on property panel settings
            
        Returns:
            Item metadata dictionary
        """
        endpoint = f"/api/ItemData/GetAll/{item_id}" if get_all else f"/api/ItemData/Get/{item_id}"
        return self._request(endpoint)
    
    def batch_update(
        self,
        item_ids: List[int],
        operations: List[Dict[str, Any]],
        exclude_ids: Optional[List[int]] = None
    ):
        """
        Batch update tags on multiple items.
        
        Args:
            item_ids: List of item IDs to update
            operations: List of tag operations, each containing:
                - guid: Tag GUID
                - value: New value
                - id: Tag value ID (for indexed tags)
                - remove: True to remove tag value
            exclude_ids: Optional list of IDs to exclude from update
            
        Example:
            # Add keyword "city" (value ID 4949) to items
            api.item_data.batch_update(
                item_ids=[123, 456],
                operations=[{"guid": "...", "id": 4949, "remove": False}]
            )
        """
        data = {
            "ids": item_ids,
            "data": operations,
            "delete": False
        }
        
        if exclude_ids:
            data["excludeIds"] = exclude_ids
        
        self._request(
            "/api/ItemData/BatchChange",
            method="POST",
            data=data
        )
    
    def get_default_layout(self) -> List[Dict[str, Any]]:
        """
        Get list of available tags for property panel.
        
        Returns:
            List of tag definitions with GUIDs and names
        """
        return self._request("/api/ItemData/GetDefaultLayout")


class SettingsAPI(BaseAPI):
    """
    Settings API - Server configuration and user settings.
    
    Endpoints:
        - Get server version
        - Get/set user permissions
        - Manage export presets
        - Get logged user info
    """
    
    def get_version(self) -> str:
        """
        Get Daminion server version.
        
        Returns:
            Version string
        """
        return self._request("/api/Settings/GetVersion")
    
    def get_logged_user(self) -> Dict[str, Any]:
        """
        Get information about the currently logged-in user.
        
        Returns:
            User information dictionary
        """
        return self._request("/api/Settings/GetLoggedUser")
    
    def get_rights(self) -> Dict[str, bool]:
        """
        Get permissions for the current user.
        
        Returns:
            Dictionary of permission flags
        """
        return self._request("/api/Settings/GetRights")
    
    def get_catalog_guid(self) -> str:
        """
        Get the GUID of the current catalog.
        
        Returns:
            Catalog GUID string
        """
        return self._request("/api/Settings/GetCatalogGuid")
    
    def get_export_presets(self) -> List[Dict[str, Any]]:
        """
        Get available export presets.
        
        Returns:
            List of export preset configurations
        """
        return self._request("/api/Settings/GetExportPresets")


class ThumbnailsAPI(BaseAPI):
    """
    Thumbnails & Previews API - Get thumbnails and preview images.
    
    Endpoints:
        - Get thumbnails
        - Get preview images
        - Update thumbnails
    """
    
    def get(
        self,
        item_id: int,
        width: int = 200,
        height: int = 200
    ) -> bytes:
        """
        Get thumbnail image for a media item.
        
        Args:
            item_id: Media item ID
            width: Thumbnail width in pixels
            height: Thumbnail height in pixels
            
        Returns:
            Binary image data (JPEG)
        """
        params = {
            "width": width,
            "height": height
        }
        
        return self._request(f"/api/Thumbnail/Get/{item_id}", params=params)
    
    def get_preview(
        self,
        item_id: int,
        width: int = 1000,
        height: int = 1000
    ) -> bytes:
        """
        Get preview image for a media item.
        
        Args:
            item_id: Media item ID
            width: Preview width in pixels
            height: Preview height in pixels
            
        Returns:
            Binary image data (JPEG)
        """
        params = {
            "width": width,
            "height": height
        }
        
        return self._request(f"/api/Preview/Get/{item_id}", params=params)


class DownloadsAPI(BaseAPI):
    """
    Downloads API - Download original files and exports.
    
    Endpoints:
        - Download original files
        - Export with presets
        - Batch downloads
    """
    
    def get_original(self, item_id: int) -> bytes:
        """
        Download the original file for a media item.
        
        Args:
            item_id: Media item ID
            
        Returns:
            Binary file data
        """
        return self._request(f"/api/Download/Get/{item_id}")
    
    def get_with_preset(
        self,
        item_id: int,
        preset_guid: str
    ) -> bytes:
        """
        Export a file using an export preset.
        
        Args:
            item_id: Media item ID
            preset_guid: Export preset GUID
            
        Returns:
            Binary file data
        """
        params = {"guid": preset_guid}
        return self._request(f"/api/Download/GetWithPreset/{item_id}", params=params)


class ImportsAPI(BaseAPI):
    """
    Imports API - Import files into the catalog.
    
    Endpoints:
        - Upload files
        - Import by URL
        - Get import status
    """
    
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported file formats for import.
        
        Returns:
            List of file extensions (e.g., [".jpg", ".png", ...])
        """
        return self._request("/api/Import/GetSupported")
    
    def import_by_urls(
        self,
        file_urls: List[str],
        tags: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Import files from direct URLs.
        
        Args:
            file_urls: List of URLs to import
            tags: Optional tags to apply to imported files
            
        Returns:
            Import session ID
        """
        data = {"urls": file_urls}
        
        if tags:
            data["tags"] = tags
        
        result = self._request(
            "/api/Import/ImportFiles",
            method="POST",
            data=data
        )
        
        return result.get('importId', '') if isinstance(result, dict) else str(result)


class UserManagerAPI(BaseAPI):
    """
    User Manager API - User and role management.
    
    Endpoints:
        - Get/create/update/delete users
        - Manage roles and permissions
    """
    
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get list of all users (admin only).
        
        Returns:
            List of user dictionaries
        """
        return self._request("/api/UserManager/GetUsers")
    
    def get_roles(self) -> List[Dict[str, Any]]:
        """
        Get list of user roles.
        
        Returns:
            List of role dictionaries
        """
        return self._request("/api/UserManager/GetRoles")
    
    def create_user(
        self,
        username: str,
        password: str,
        email: str,
        role_id: int
    ) -> int:
        """
        Create a new user (admin only).
        
        Args:
            username: Username
            password: Password
            email: Email address
            role_id: Role ID to assign
            
        Returns:
            New user ID
        """
        data = {
            "username": username,
            "password": password,
            "email": email,
            "roleId": role_id
        }
        
        result = self._request(
            "/api/UserManager/Create",
            method="POST",
            data=data
        )
        
        return result.get('id', 0) if isinstance(result, dict) else result
