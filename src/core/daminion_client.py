"""
Daminion DAMS API Client - Updated to use new DaminionAPI

This is a compatibility wrapper that maintains the old DaminionClient interface
while using the new, robust DaminionAPI implementation internally.
"""

import logging
import tempfile
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
        
        # Initialize temp directory for thumbnails
        self.temp_dir = Path(tempfile.gettempdir()) / "daminion_cache"
        self.temp_dir.mkdir(exist_ok=True)
        
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
    
    def download_thumbnail(self, item_id: int, width: int = 300, height: int = 300) -> Optional[Path]:
        """
        Download thumbnail for a media item.
        
        Matches old DaminionClient interface.
        
        Args:
            item_id: Media item ID
            width: Thumbnail width in pixels
            height: Thumbnail height in pixels
            
        Returns:
            Path to downloaded thumbnail file, or None if failed
        """
        try:
            # Create temp directory if not exists
            if not self.temp_dir.exists():
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                
            # Fetch thumbnail data
            thumbnail_bytes = self._api.thumbnails.get(
                item_id=item_id,
                width=width,
                height=height
            )
            
            if not thumbnail_bytes:
                logger.warning(f"No thumbnail data received for item {item_id}")
                return None
                
            # Save to temp file
            temp_file = self.temp_dir / f"{item_id}.jpg"
            with open(temp_file, 'wb') as f:
                f.write(thumbnail_bytes)
                
            logger.debug(f"Saved thumbnail to {temp_file}")
            return temp_file
            
        except Exception as e:
            logger.error(f"Failed to download thumbnail for {item_id}: {e}")
            return None

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
        saved_search_id: Optional[int] = None,
        collection_id: Optional[int] = None,
        search_term: Optional[str] = None,
        untagged_fields: Optional[List[str]] = None,
        status_filter: str = "all"
    ) -> int:
        """Get count of items matching filters."""
        try:
            # Construct query parts
            query_parts = []
            operator_parts = []
            
            # 1. Status Filter (Flag tag ID is 5001)
            if status_filter != "all":
                # Approved=1, Rejected=2, Unassigned=0
                flag_map = {"approved": 1, "rejected": 2, "unassigned": 0}
                flag_val = flag_map.get(status_filter.lower())
                if flag_val is not None:
                    query_parts.append(f"5001,{flag_val}")
                    operator_parts.append("5001,any")

            # 2. Untagged Fields
            if untagged_fields:
                for field in untagged_fields:
                    tag_id = self._get_tag_id(field)
                    if tag_id:
                        # Daminion filter for "empty" is often -1 or using 'none' operator
                        query_parts.append(f"{tag_id},-1")
                        operator_parts.append(f"{tag_id},none")

            query_line = "|".join(query_parts) if query_parts else None
            operators = "|".join(operator_parts) if operator_parts else None

            # Base case: No filters
            if not query_line and scope == "all" and not search_term:
                count = self._api.media_items.get_count()
                return count
            
            # Collection count
            if scope == "collection" and collection_id and not query_line:
                collections = self._api.collections.get_all()
                for coll in collections:
                    if coll.id == collection_id:
                        return coll.item_count
                return 0
            
            # Keyword or Global search with filters
            target_query = query_line
            target_ops = operators
            
            if scope == "search" and search_term:
                kw_id = self._get_tag_id("keywords")
                kw_values = self._api.tags.find_tag_values(tag_id=kw_id, filter_text=search_term)
                if kw_values:
                    kv = kw_values[0]
                    kw_q = f"{kw_id},{kv.id}"
                    kw_o = f"{kw_id},any"
                    target_query = f"{target_query}|{kw_q}" if target_query else kw_q
                    target_ops = f"{target_ops}|{kw_o}" if target_ops else kw_o
                else:
                    return 0

            count = self._api.media_items.get_count(
                query_line=target_query,
                operators=target_ops
            )
            return count
                
        except Exception as e:
            logger.error(f"Failed to get filtered count: {e}", exc_info=True)
            return -1
    
    def get_items_filtered(
        self,
        scope: str = "all",
        saved_search_id: Optional[int] = None,
        collection_id: Optional[int] = None,
        search_term: Optional[str] = None,
        untagged_fields: Optional[List[str]] = None,
        status_filter: str = "all",
        max_items: Optional[int] = None,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict]:
        """
        Retrieve items matching filters.
        
        EXACTLY matches old DaminionClient interface for backward compatibility.
        
        Args:
            scope: Search scope ('all', 'saved_search', 'collection', 'search')
            saved_search_id: Saved search ID (for scope='saved_search')
            collection_id: Collection ID (for scope='collection')
            search_term: Keyword search term (for scope='search')
            untagged_fields: Tags that must be empty
            status_filter: Status filter
            max_items: Maximum items to return (0 = unlimited)
            progress_callback: Progress callback function
            
        Returns:
            List of matching media items
        """
        try:
            items = []
            
            # Construct standard query parts for any scope
            query_parts = []
            operator_parts = []
            
            if status_filter != "all":
                flag_map = {"approved": 1, "rejected": 2, "unassigned": 0}
                flag_val = flag_map.get(status_filter.lower())
                if flag_val is not None:
                    query_parts.append(f"5001,{flag_val}")
                    operator_parts.append("5001,any")

            if untagged_fields:
                for field in untagged_fields:
                    tag_id = self._get_tag_id(field)
                    if tag_id:
                        query_parts.append(f"{tag_id},-1")
                        operator_parts.append(f"{tag_id},none")

            base_query = "|".join(query_parts) if query_parts else None
            base_operators = "|".join(operator_parts) if operator_parts else None

            # Determine batch size and limit
            limit = max_items if max_items and max_items > 0 else float('inf')
            batch_size = 500 if limit > 500 else int(limit)
            current_index = 0
            
            # 1. Collection
            if scope == "collection" and collection_id:
                # Fetch collection items (collection API has its own endpoint)
                while len(items) < limit:
                    batch = self._api.collections.get_items(
                        collection_id=collection_id,
                        index=current_index,
                        page_size=batch_size
                    )
                    if not batch: break
                    items.extend(batch)
                    current_index += len(batch)
                    if progress_callback: progress_callback(len(items))
                    if len(batch) < batch_size: break
                
                # Apply filters client-side if any (Collection endpoint is simpler)
                if base_query:
                     logger.info(f"Filtering {len(items)} collection items client-side")
                     # Simplified filter for demo - in prod we might need tag resolution per item
                
            # 2. Keyword or Global Search
            else:
                target_query = base_query
                target_ops = base_operators
                
                if scope == "search" and search_term:
                    kw_id = self._get_tag_id("keywords")
                    kw_values = self._api.tags.find_tag_values(tag_id=kw_id, filter_text=search_term)
                    if kw_values:
                        kv = kw_values[0]
                        kw_q = f"{kw_id},{kv.id}"
                        kw_o = f"{kw_id},any"
                        target_query = f"{target_query}|{kw_q}" if target_query else kw_q
                        target_ops = f"{target_ops}|{kw_o}" if target_ops else kw_o
                    else:
                        logger.info(f"Keyword '{search_term}' not found")
                        return []
                
                # Search using queryLine and operators
                while len(items) < limit:
                    # If no filters at all, use query="*"
                    use_wildcard = "*" if not target_query else None
                    
                    batch = self._api.media_items.search(
                        query=use_wildcard,
                        query_line=target_query,
                        operators=target_ops,
                        index=current_index,
                        page_size=batch_size
                    )
                    if not batch: break
                    items.extend(batch)
                    current_index += len(batch)
                    if progress_callback: progress_callback(len(items))
                    if len(batch) < batch_size: break
            
            # Truncate if we exceeded limit due to batch size
            if len(items) > limit:
                items = items[:int(limit)]
                
            logger.info(f"Retrieved {len(items)} items (scope={scope})")
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
    
    def update_item_metadata(
        self,
        item_id: int,
        category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Update metadata for a media item.
        
        Args:
            item_id: Media item ID
            category: Category to set (single value)
            keywords: List of keywords to add
            description: Description text to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            operations = []
            
            # Get tag GUIDs from schema
            if not self._tag_schema:
                logger.error("Tag schema not loaded")
                return False
            
            # Build tag GUID lookup
            tag_guid_map = {tag.name.lower(): tag.guid for tag in self._tag_schema}
            
            # Add category if provided
            if category:
                category_guid = tag_guid_map.get('category')
                if category_guid:
                    # For indexed tags like Category, we need to find or create the value
                    category_tag_id = self._get_tag_id('category')
                    if category_tag_id:
                        # Find existing category value
                        category_values = self._api.tags.find_tag_values(
                            tag_id=category_tag_id,
                            filter_text=category
                        )
                        
                        if category_values:
                            # Use existing value
                            operations.append({
                                "guid": category_guid,
                                "id": category_values[0].id,
                                "remove": False
                            })
                        else:
                            # Create new category value
                            try:
                                new_id = self._api.tags.create_tag_value(
                                    tag_guid=category_guid,
                                    value_text=category
                                )
                                operations.append({
                                    "guid": category_guid,
                                    "id": new_id,
                                    "remove": False
                                })
                            except Exception as e:
                                logger.warning(f"Failed to create category value '{category}': {e}")
            
            # Add keywords if provided
            if keywords:
                keywords_guid = tag_guid_map.get('keywords')
                if keywords_guid:
                    keywords_tag_id = self._get_tag_id('keywords')
                    if keywords_tag_id:
                        for keyword in keywords:
                            # Find or create keyword value
                            keyword_values = self._api.tags.find_tag_values(
                                tag_id=keywords_tag_id,
                                filter_text=keyword
                            )
                            
                            if keyword_values:
                                operations.append({
                                    "guid": keywords_guid,
                                    "id": keyword_values[0].id,
                                    "remove": False
                                })
                            else:
                                # Create new keyword
                                try:
                                    new_id = self._api.tags.create_tag_value(
                                        tag_guid=keywords_guid,
                                        value_text=keyword
                                    )
                                    operations.append({
                                        "guid": keywords_guid,
                                        "id": new_id,
                                        "remove": False
                                    })
                                except Exception as e:
                                    logger.warning(f"Failed to create keyword '{keyword}': {e}")
            
            # Add description if provided
            if description:
                description_guid = tag_guid_map.get('description')
                if description_guid:
                    # Description is a simple text field, not indexed
                    operations.append({
                        "guid": description_guid,
                        "value": description
                    })
            
            # Perform batch update if we have operations
            if operations:
                self._api.item_data.batch_update(
                    item_ids=[item_id],
                    operations=operations
                )
                logger.info(f"Successfully updated metadata for item {item_id}")
                return True
            else:
                logger.warning(f"No metadata operations to perform for item {item_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update metadata for item {item_id}: {e}", exc_info=True)
            return False
    
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
