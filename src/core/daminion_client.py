"""
Daminion DAMS API Client - Updated to use new DaminionAPI

This is a compatibility wrapper that maintains the old DaminionClient interface
while using the new, robust DaminionAPI implementation internally.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path

# Import the new API implementation
from .daminion_api import (
    DaminionAPI,
    DaminionAPIError,
    DaminionAuthenticationError,
    DaminionNetworkError,
    DaminionRateLimitError,
    DaminionNotFoundError,
    TagInfo,
    TagValue
)


logger = logging.getLogger(__name__)


class DaminionClient:
    """
    Compatibility wrapper for DaminionAPI.
    
    Maintains the old DaminionClient interface while using the new
    DaminionAPI implementation internally for better reliability.
    """
    
    def __init__(self, base_url: str, username: str, password: str, rate_limit: float = 0.1):
        """
        Initialize Daminion client.
        
        Args:
            base_url: Base URL of Daminion server
            username: Daminion username
            password: Daminion password
            rate_limit: Minimum seconds between API calls
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.rate_limit = rate_limit
        
        # Create new API instance
        self._api = DaminionAPI(
            base_url=base_url,
            username=username,
            password=password,
            rate_limit=rate_limit
        )
        
        # Cache for tag mappings
        self._tag_name_to_id: Dict[str, int] = {}
        self._tag_id_to_name: Dict[int, str] = {}
        self._tag_schema: Optional[List[TagInfo]] = None
        
        logger.info(f"DaminionClient initialized for {base_url}")
    
    @property
    def authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self._api.is_authenticated()
    
    def __enter__(self):
        """Enter context manager."""
        self._api.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        try:
            self._api.logout()
        except Exception as e:
            logger.debug(f"Error during logout: {e}")
        return False
    
    def authenticate(self) -> bool:
        """
        Authenticate with Daminion server.
        
        Returns:
            True if successful
        """
        try:
            self._api.authenticate()
            
            # Load and cache tag schema
            self._load_tag_schema()
            
            logger.info(f"Successfully authenticated to {self.base_url}")
            return True
            
        except DaminionAuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return False
    
    def _load_tag_schema(self):
        """Load and cache tag schema for name/ID mapping."""
        try:
            self._tag_schema = self._api.tags.get_all_tags()
            
            # Build lookup dictionaries
            for tag in self._tag_schema:
                self._tag_name_to_id[tag.name.lower()] = tag.id
                self._tag_id_to_name[tag.id] = tag.name
            
            logger.info(f"Loaded tag schema: {len(self._tag_schema)} tags")
            
        except Exception as e:
            logger.error(f"Failed to load tag schema: {e}")
            self._tag_schema = []
    
    def _get_tag_id(self, tag_name: str) -> Optional[int]:
        """Get tag ID from tag name."""
        return self._tag_name_to_id.get(tag_name.lower())
    
    def get_shared_collections(self, index: int = 0, page_size: int = 100) -> List[Dict]:
        """
        Retrieve list of shared collections.
        
        Args:
            index: Starting index
            page_size: Number of collections to retrieve
            
        Returns:
            List of shared collection dictionaries
        """
        try:
            collections = self._api.collections.get_all(index=index, page_size=page_size)
            
            # Convert to old format
            result = []
            for coll in collections:
                result.append({
                    'id': coll.id,
                    'name': coll.name,
                    'code': coll.code,
                    'itemCount': coll.item_count,
                    'created': coll.created,
                    'modified': coll.modified
                })
            
            logger.info(f"Retrieved {len(result)} shared collections")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get shared collections: {e}")
            return []
    
    def get_saved_searches(self) -> List[Dict]:
        """
        Retrieve list of saved searches.
        
        Note: Saved Searches are not available via Web API.
        Returns empty list with warning.
        """
        logger.warning("Saved Searches not available via Web API - use Shared Collections instead")
        return []
    
    def get_shared_collection_items(self, collection_id: int, index: int = 0, page_size: int = 200) -> List[Dict]:
        """
        Retrieve items from a shared collection.
        
        Args:
            collection_id: Collection ID
            index: Starting index
            page_size: Number of items to retrieve
            
        Returns:
            List of media items
        """
        try:
            items = self._api.collections.get_items(
                collection_id=collection_id,
                index=index,
                page_size=page_size
            )
            
            logger.info(f"Retrieved {len(items)} items from collection {collection_id}")
            return items
            
        except Exception as e:
            logger.error(f"Failed to get collection items: {e}")
            return []
    
    def get_filtered_item_count(
        self,
        scope: str = "all",
        status_filter: str = "all",
        untagged_tags: Optional[List[str]] = None,
        search_term: Optional[str] = None,
        collection_id: Optional[int] = None
    ) -> int:
        """
        Get count of items matching filters.
        
        Args:
            scope: Search scope ('all', 'search', 'collection')
            status_filter: Status filter ('all', 'unassigned', 'flagged', etc.)
            untagged_tags: List of tag names that must be empty
            search_term: Keyword search term
            collection_id: Collection ID for collection scope
            
        Returns:
            Number of matching items
        """
        try:
            if scope == "collection" and collection_id:
                # Get collection items count
                items = self._api.collections.get_items(collection_id, page_size=1)
                # Need to get full count - use MediaItems count with collection filter
                # For now, approximate from collection info
                collections = self._api.collections.get_all()
                for coll in collections:
                    if coll.id == collection_id:
                        return coll.item_count
                return 0
            
            elif scope == "search" and search_term:
                # Search by keyword
                keywords_tag_id = self._get_tag_id("keywords")
                if not keywords_tag_id:
                    logger.warning("Keywords tag not found")
                    return 0
                
                # Find keyword value
                keyword_values = self._api.tags.find_tag_values(
                    tag_id=keywords_tag_id,
                    filter_text=search_term
                )
                
                if not keyword_values:
                    logger.info(f"No keyword found matching '{search_term}'")
                    return 0
                
                # Use the first matching keyword
                keyword_value = keyword_values[0]
                
                # Search with this keyword
                query_line = f"{keywords_tag_id},{keyword_value.id}"
                operators = f"{keywords_tag_id},any"
                
                count = self._api.media_items.get_count(
                    query_line=query_line,
                    operators=operators
                )
                
                logger.info(f"Keyword search '{search_term}' found {count} items")
                return count
            
            else:
                # Get total count
                count = self._api.media_items.get_count()
                logger.info(f"Total catalog count: {count}")
                return count
                
        except Exception as e:
            logger.error(f"Failed to get filtered count: {e}", exc_info=True)
            return 0
    
    def get_items_filtered(
        self,
        scope: str = "all",
        status_filter: str = "all",
        untagged_tags: Optional[List[str]] = None,
        search_term: Optional[str] = None,
        collection_id: Optional[int] = None,
        max_items: int = 0,
        progress_callback: Optional[Callable] = None,
        stop_event: Optional[Any] = None
    ) -> List[Dict]:
        """
        Retrieve items matching filters.
        
        Args:
            scope: Search scope
            status_filter: Status filter
            untagged_tags: Tags that must be empty
            search_term: Keyword search term
            collection_id: Collection ID
            max_items: Maximum items to return (0 = unlimited)
            progress_callback: Progress callback function
            stop_event: Stop event for cancellation
            
        Returns:
            List of matching media items
        """
        try:
            items = []
            
            if scope == "collection" and collection_id:
                # Get collection items
                items = self._api.collections.get_items(
                    collection_id=collection_id,
                    page_size=max_items if max_items > 0 else 500
                )
                logger.info(f"Retrieved {len(items)} items from collection")
                
            elif scope == "search" and search_term:
                # Search by keyword
                keywords_tag_id = self._get_tag_id("keywords")
                if not keywords_tag_id:
                    logger.warning("Keywords tag not found")
                    return []
                
                # Find keyword value
                keyword_values = self._api.tags.find_tag_values(
                    tag_id=keywords_tag_id,
                    filter_text=search_term
                )
                
                if not keyword_values:
                    logger.info(f"No keyword found matching '{search_term}'")
                    return []
                
                # Use the first matching keyword
                keyword_value = keyword_values[0]
                
                # Search with this keyword
                query_line = f"{keywords_tag_id},{keyword_value.id}"
                operators = f"{keywords_tag_id},any"
                
                items = self._api.media_items.search(
                    query_line=query_line,
                    operators=operators,
                    page_size=max_items if max_items > 0 else 500
                )
                
                logger.info(f"Keyword search '{search_term}' returned {len(items)} items")
                
            else:
                # Get all items (with limit)
                items = self._api.media_items.search(
                    query="*",
                    page_size=max_items if max_items > 0 else 500
                )
                logger.info(f"Retrieved {len(items)} items (all)")
            
            # Apply status filter if needed
            if status_filter == "unassigned":
                filtered_items = []
                for item in items:
                    # Check if item needs filtering
                   # Get full metadata if needed
                    try:
                        metadata = self._api.item_data.get(item['id'], get_all=False)
                        # TODO: Implement proper status checking based on metadata
                        # For now, include all items
                        filtered_items.append(item)
                    except:
                        filtered_items.append(item)
                
                logger.info(f"Status filter '{status_filter}': {len(filtered_items)}/{len(items)} items passed")
                items = filtered_items
            
            # Apply untagged filter if needed
            if untagged_tags:
                filtered_items = []
                for item in items:
                    # TODO: Implement proper untagged filtering
                    # For now, include all items
                    filtered_items.append(item)
                
                logger.info(f"Untagged filter: {len(filtered_items)}/{len(items)} items passed")
                items = filtered_items
            
            return items
            
        except Exception as e:
            logger.error(f"Failed to get filtered items: {e}", exc_info=True)
            return []
    
    def get_thumbnail(self, item_id: int, width: int = 200, height: int = 200) -> Optional[bytes]:
        """
        Get thumbnail for an item.
        
        Args:
            item_id: Item ID
            width: Thumbnail width
            height: Thumbnail height
            
        Returns:
            Thumbnail image data or None
        """
        try:
            return self._api.thumbnails.get(item_id, width, height)
        except Exception as e:
            logger.error(f"Failed to get thumbnail for item {item_id}: {e}")
            return None
    
    def get_file_path(self, item_id: int) -> Optional[str]:
        """
        Get file path for an item.
        
        Args:
            item_id: Item ID
            
        Returns:
            File path or None
        """
        try:
            return self._api.media_items.get_absolute_path(item_id)
        except Exception as e:
            logger.error(f"Failed to get file path for item {item_id}: {e}")
            return None
    
    def logout(self):
        """Logout and cleanup."""
        try:
            self._api.logout()
            logger.info("Logged out successfully")
        except Exception as e:
            logger.debug(f"Error during logout: {e}")


# Export the same exceptions as before for compatibility
__all__ = [
    'DaminionClient',
    'DaminionAPIError',
    'DaminionAuthenticationError',
    'DaminionNetworkError',
    'DaminionRateLimitError'
]
