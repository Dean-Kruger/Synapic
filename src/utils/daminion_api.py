import logging
import requests
import time
from typing import Dict, List, Optional, Any, Union, Callable
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class DaminionAPIError(Exception):
    """Base exception for Daminion API errors."""
    pass

class DaminionAuthenticationError(DaminionAPIError):
    """Raised when authentication fails."""
    pass

class DaminionAPI:
    """
    A robust Python utility class for interacting with the Daminion Server Web API.
    Ref: https://marketing.daminion.net/apihelp
    """

    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        })
        self.authenticated = False

    def authenticate(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Authenticate with the Daminion server.
        """
        user = username or self.username
        pwd = password or self.password

        if not user or not pwd:
            raise DaminionAuthenticationError("Username and password are required for authentication.")

        # Daminion often uses a specific login endpoint or basic auth depending on version.
        # Based on documentation chunks, UserManager/Login is common.
        login_url = f"{self.base_url}/api/UserManager/Login"
        params = {'userName': user, 'password': pwd}
        
        try:
            response = self.session.post(login_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                self.authenticated = True
                logger.info("Successfully authenticated with Daminion.")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            raise DaminionAuthenticationError(f"Failed to connect for authentication: {e}")

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Internal helper to make requests."""
        if not self.authenticated and "UserManager/Login" not in endpoint:
            # Auto-authenticate if credentials are provided
            if self.username and self.password:
                self.authenticate()
            else:
                raise DaminionAuthenticationError("Client is not authenticated.")

        # Match DaminionClient's URL construction: base_url + / + endpoint (stripped of leading /)
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', self.timeout)
        logger.debug(f"Making {method} request to: {url}")
        
        try:
            # Add some common headers like the original client
            headers = kwargs.get('headers', {})
            headers.update({
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            })
            kwargs['headers'] = headers

            response = self.session.request(method, url, **kwargs)
            if response.status_code != 200 and response.status_code != 204:
                logger.error(f"Request failed with {response.status_code}: {response.text} at {url}")
            response.raise_for_status()
            
            if response.status_code == 204 or not response.content:
                return None
            
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise DaminionAPIError(f"API Request failed: {e}")
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise DaminionAPIError(f"An unexpected error occurred: {e}")

    # --- MediaItems Endpoints ---

    def get_media_item(self, item_id: int) -> Dict:
        """GET api/MediaItems?id={id}"""
        return self._request("GET", f"api/MediaItems?id={item_id}")

    def get_media_items_by_ids(self, ids: List[int]) -> List[Dict]:
        """GET api/MediaItems/GetByIds?ids={ids}"""
        ids_str = ",".join(map(str, ids))
        return self._request("GET", f"api/MediaItems/GetByIds?ids={ids_str}")

    def search_media_items(self, query: Optional[str] = None, page_index: int = 0, page_size: int = 100) -> Dict:
        """GET api/MediaItems/Get"""
        params = {
            'query': query,
            'index': page_index,
            'size': page_size
        }
        return self._request("GET", "api/MediaItems/Get", params=params)

    def get_media_item_count(self, query: Optional[str] = None) -> int:
        """GET api/MediaItems/GetCount"""
        params = {'query': query} if query else {}
        return self._request("GET", "api/MediaItems/GetCount", params=params)

    def approve_items(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/ApproveItems"""
        return self._request("POST", "api/MediaItems/ApproveItems", json=item_ids)

    def delete_items(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/Remove"""
        return self._request("POST", "api/MediaItems/Remove", json=item_ids)

    # --- IndexedTagValues Endpoints ---

    def get_tag_values(self, tag_id: int, parent_id: int = 0, filter_text: str = "", page_index: int = 0, page_size: int = 100) -> List[Dict]:
        """GET api/IndexedTagValues/GetIndexedTagValues"""
        params = {
            'indexedTagId': tag_id,
            'parentValueId': parent_id,
            'filter': filter_text,
            'pageIndex': page_index,
            'pageSize': page_size
        }
        return self._request("GET", "api/IndexedTagValues/GetIndexedTagValues", params=params)

    def create_custom_tag(self, name: str, data_type: int) -> Dict:
        """POST api/IndexedTagValues/CreateCustomTag"""
        payload = {'Name': name, 'DataType': data_type}
        return self._request("POST", "api/IndexedTagValues/CreateCustomTag", json=payload)

    # --- UserManager Endpoints ---

    def get_users(self) -> List[Dict]:
        """GET api/UserManager/GetUsers"""
        return self._request("GET", "api/UserManager/GetUsers")

    def get_roles(self) -> List[Dict]:
        """GET api/UserManager/GetRoles"""
        return self._request("GET", "api/UserManager/GetRoles")

    # --- Thumbnail & Preview Endpoints ---

    def get_thumbnail_url(self, item_id: int, width: int = 200, height: int = 200) -> str:
        """Returns the URL for a thumbnail."""
        return f"{self.base_url}/api/Thumbnail/Get/{item_id}?width={width}&height={height}"

    def download_thumbnail(self, item_id: int, width: int = 200, height: int = 200) -> bytes:
        """Downloads thumbnail content."""
        url = self.get_thumbnail_url(item_id, width, height)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    # --- SharedCollection Endpoints ---

    def get_shared_collections(self) -> List[Dict]:
        """GET api/SharedCollection/GetCollections"""
        return self._request("GET", "api/SharedCollection/GetCollections")

    # --- ItemData (Metadata) Endpoints ---

    def get_item_data(self, item_id: int) -> Dict:
        """GET api/ItemData/Get/{id}"""
        return self._request("GET", f"api/ItemData/Get/{item_id}")

    def update_item_metadata(self, item_id: int, metadata: Dict) -> bool:
        """POST api/ItemData/Change"""
        payload = {'Id': item_id, 'Properties': metadata}
        return self._request("POST", "api/ItemData/Change", json=payload)

    def batch_change_metadata(self, item_ids: List[int], properties: Dict) -> bool:
        """POST api/ItemData/BatchChange"""
        payload = {
            'Ids': item_ids,
            'Properties': properties
        }
        return self._request("POST", "api/ItemData/BatchChange", json=payload)

    # --- Settings Endpoints ---

    def get_watermark_data(self, guid: str) -> Dict:
        """GET api/Settings/GetWatermarkData?guid={guid}"""
        return self._request("GET", f"api/Settings/GetWatermarkData?guid={guid}")

    def get_security_mode(self) -> str:
        """GET api/Settings/GetSecurityMode"""
        return self._request("GET", "api/Settings/GetSecurityMode")

    # --- Favorites (Tray) Endpoints ---

    def get_favorites(self) -> List[Dict]:
        """GET api/MediaItems/Tray"""
        return self._request("GET", "api/MediaItems/Tray")

    def add_to_favorites(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/AppendToTray"""
        return self._request("POST", "api/MediaItems/AppendToTray", json=item_ids)

    def clear_favorites(self) -> bool:
        """POST api/MediaItems/ClearTray/0 (0 usually clears all)"""
        return self._request("POST", "api/MediaItems/ClearTray/0")

    # --- AI Processing Endpoints ---

    def process_ai_labels(self, item_ids: List[int]) -> bool:
        """POST api/MediaItems/ProcessAILabels"""
        return self._request("POST", "api/MediaItems/ProcessAILabels", json=item_ids)

    def process_ai_labels_query(self, query: str) -> bool:
        """POST api/MediaItems/ProcessAILabelsQuery"""
        return self._request("POST", "api/MediaItems/ProcessAILabelsQuery", json=query)
