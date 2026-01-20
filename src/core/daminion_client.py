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
            
            # Build lookup dictionaries from standard tags
            for tag in self._tag_schema:
                self._tag_name_to_id[tag.name.lower()] = tag.id
                self._tag_id_to_name[tag.id] = tag.name
            
            # Also fetch from layout to find system tags (Flag, Status, etc)
            try:
                layout = self._api.item_data.get_default_layout()
                self._extract_tags_from_layout(layout)
            except Exception as e:
                logger.debug(f"Failed to load tags from layout: {e}")
            
            logger.info(f"Loaded tag schema: {len(self._tag_name_to_id)} unique tags mapped")
            
        except Exception as e:
            logger.error(f"Failed to load tag schema: {e}")
            self._tag_schema = []

    def _extract_tags_from_layout(self, obj):
        """Recursively extract property IDs from layout structure."""
        if isinstance(obj, dict):
            p_name = obj.get('propertyName') or obj.get('name')
            p_id = obj.get('id') or obj.get('propertyId')
            
            if p_name and p_id and isinstance(p_id, int):
                self._tag_name_to_id[p_name.lower()] = p_id
                self._tag_id_to_name[p_id] = p_name
            
            for val in obj.values():
                if isinstance(val, (dict, list)):
                    self._extract_tags_from_layout(val)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_tags_from_layout(item)
    
    def get_thumbnail(self, item_id: int, width: int = 200, height: int = 200) -> Optional[bytes]:
        """Get raw thumbnail bytes."""
        try:
            return self._api.thumbnails.get(item_id, width, height)
        except Exception as e:
            logger.error(f"Failed to get thumbnail for item {item_id}: {e}")
            return None

    def get_file_path(self, item_id: int) -> Optional[str]:
        """Get the absolute path to the original file."""
        try:
            return self._api.media_items.get_absolute_path(item_id)
        except Exception as e:
            logger.error(f"Failed to get file path for item {item_id}: {e}")
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
        
        Note: Saved Searches are often not available via a dedicated Web API endpoint.
        We fallback to fetching values from the 'Saved Searches' tag.
        """
        try:
            tag_id = self._get_tag_id("saved searches")
            if not tag_id:
                logger.warning("Tag 'Saved Searches' not found in schema. Cannot retrieve saved searches.")
                return []
            
            tag_values = self._api.tags.get_tag_values(tag_id=tag_id)
            result = []
            for val in tag_values:
                result.append({
                    'id': val.id,
                    'name': val.text,
                    'count': val.count
                })
            
            logger.info(f"Retrieved {len(result)} saved searches via tag values")
            return result
        except Exception as e:
            logger.error(f"Failed to get saved searches: {e}")
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
        status_filter: str = "all",
        force_refresh: bool = False
    ) -> int:
        """Get count of items matching filters."""
        logger.info(f"DAMINION COUNT REQUEST | scope: {scope} | search: {search_term} | status: {status_filter} | untagged: {untagged_fields} | force: {force_refresh}")
        try:
            # 1. Build structured query components
            q_parts = []
            f_parts = []
            
            # Status Filter (Flag Tag usually ID 41)
            sf = (status_filter or "all").lower()
            flag_tag_id = self._get_tag_id("flag") or 41
            if sf == "approved": 
                q_parts.append(f"{flag_tag_id},2") # Flagged
                f_parts.append(f"{flag_tag_id},any")
            elif sf == "rejected": 
                q_parts.append(f"{flag_tag_id},3") # Rejected
                f_parts.append(f"{flag_tag_id},any")
            elif sf == "unassigned": 
                q_parts.append(f"{flag_tag_id},1") # Unflagged
                f_parts.append(f"{flag_tag_id},any")
            
            # Untagged Logic (Text-based search is often better for ':none' on some versions)
            search_parts = []
            if untagged_fields:
                # If plural 'categories' wasn't used, normalize it
                normalized_untagged = []
                for f in untagged_fields:
                    if f.lower() == "category": normalized_untagged.append("Categories")
                    else: normalized_untagged.append(f)
                
                # Some servers support specific 'Tag:none'
                for f in normalized_untagged:
                    search_parts.append(f"{f}:none")

            # Keyword Search term
            if scope == "search" and search_term:
                search_parts.append(f'"{search_term}"')

            combined_search = " ".join(search_parts) if search_parts else None
            
            # 2. Scope-specific structured query components
            if scope == "saved_search" and saved_search_id:
                tag_id = self._get_tag_id("saved searches") or 39
                q_parts.append(f"{tag_id},{saved_search_id}")
                f_parts.append(f"{tag_id},any")
            elif scope == "collection" and collection_id:
                tag_id = self._get_tag_id("shared collections") or self._get_tag_id("collections") or 46
                q_parts.append(f"{tag_id},{collection_id}")
                f_parts.append(f"{tag_id},any")

            q_line = ";".join(q_parts) if q_parts else None
            ops = ";".join(f_parts) if f_parts else None

            # Execute Count with search string and structured query
            count = self._api.media_items.get_count(
                query=combined_search, 
                query_line=q_line,
                operators=ops,
                force=force_refresh
            )
            logger.debug(f"Initial get_count(query='{combined_search}', q_line='{q_line}') returned {count}")
            
            # If we got a count that looks like total catalog size but we HAD filters/scope,
            # try fallback search to verify totalCount
            if (combined_search or q_line) and count > 0:
                 total_catalog = self._api.media_items.get_count()
                 if count >= total_catalog:
                      logger.warning(f"Count {count} likely incorrect (matches total). Trying fallback search...")
                      _, count = self._api.media_items.search(
                          query=combined_search, 
                          query_line=q_line,
                          operators=ops,
                          page_size=1, 
                          include_total=True
                      )
                      logger.info(f"Fallback search returned totalCount={count}")
            
            # Fallback for structured searches if search string failed (returned 0)
            if count <= 0:
                 # Try structured query for keyword if text search failed
                 if scope == "search" and search_term:
                      kw_id = self._get_tag_id("keywords")
                      kw_vals = self._api.tags.find_tag_values(tag_id=kw_id, filter_text=search_term)
                      if kw_vals:
                           count = self._api.media_items.get_count(
                               query_line=f"{kw_id},{kw_vals[0].id}",
                               operators=f"{kw_id},any"
                           )

            logger.info(f"DAMINION COUNT RESULT | count: {count} | scope: {scope} | query: '{combined_search}'")
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
        """Retrieve items matching filters with pagination."""
        try:
            items = []
            limit = max_items if max_items and max_items > 0 else float('inf')
            batch_size = 500 if limit > 500 else int(limit)
            current_index = 0
            
            # 1. Build text-based search components
            search_parts = []
            sf = (status_filter or "all").lower()
            if sf == "approved": search_parts.append("flag:flagged")
            elif sf == "rejected": search_parts.append("flag:rejected")
            elif sf == "unassigned": search_parts.append("flag:unflagged")
            
            if untagged_fields:
                for f in untagged_fields:
                    f_name = "Categories" if f.lower() == "category" else f
                    search_parts.append(f"{f_name}:none")

            combined_search = " ".join(search_parts) if search_parts else None
            
            # Scope: Keyword Search
            if scope == "search" and search_term:
                final_search = f'"{search_term}"'
                if combined_search:
                    final_search += f" {combined_search}"
                
                while len(items) < limit:
                    batch = self._api.media_items.search(query=final_search, index=current_index, page_size=batch_size)
                    if not batch: break
                    items.extend(batch)
                    current_index += len(batch)
                    if progress_callback: progress_callback(len(items))
                    if len(batch) < batch_size: break
            
            # Scope: Global Scan
            elif scope == "all":
                while len(items) < limit:
                    query = combined_search or "*"
                    batch = self._api.media_items.search(query=query, index=current_index, page_size=batch_size)
                    if not batch: break
                    items.extend(batch)
                    current_index += len(batch)
                    if progress_callback: progress_callback(len(items))
                    if len(batch) < batch_size: break
            
            # Scope: Shared Collection
            elif scope == "collection" and collection_id:
                while len(items) < limit:
                    batch = self._api.collections.get_items(collection_id=collection_id, index=current_index, page_size=batch_size)
                    if not batch: break
                    items.extend(batch)
                    current_index += len(batch)
                    if len(batch) < batch_size: break
                
                # Apply filters client-side for collections
                if sf != "all" or untagged_fields:
                    original_items = items
                    items = [it for it in original_items if self._passes_filters(it, status_filter, untagged_fields)]
                    if progress_callback: progress_callback(len(items))
            
            # Scope: Saved Search
            elif scope == "saved_search" and saved_search_id:
                # Saved searches often need structured query
                tag_id = self._get_tag_id("saved searches") or 39
                while len(items) < limit:
                    batch = self._api.media_items.search(
                        query_line=f"{tag_id},{saved_search_id}",
                        operators=f"{tag_id},any",
                        index=current_index,
                        page_size=batch_size
                    )
                    if not batch: break
                    items.extend(batch)
                    current_index += len(batch)
                    if len(batch) < batch_size: break
                
                # Apply filters client-side
                if sf != "all" or untagged_fields:
                    original_items = items
                    items = [it for it in original_items if self._passes_filters(it, status_filter, untagged_fields)]
                    if progress_callback: progress_callback(len(items))

            return items[:int(limit)] if limit != float('inf') else items
                
        except Exception as e:
            logger.error(f"Failed to retrieve filtered items: {e}")
            return []

    def _passes_filters(self, item: Dict, status_filter: str, untagged_fields: Optional[List[str]]) -> bool:
        """Check if an item passes status and untagged filters (client-side)."""
        # Note: Search results often have limited properties.
        # This is a best-effort check. If data is missing, we prefer to ACCEPT the item
        # so the user can see it, rather than hiding it incorrectly.
        
        # 1. Status Filter
        sf = (status_filter or "all").lower()
        if sf != "all":
            # Attempt to find flag status in various fields
            flag_val = item.get('flag') or item.get('Flag')
            if flag_val is not None:
                # Map Daminion Flag values: 1=Approved, 2=Rejected, 0=Unassigned
                # Or sometimes strings "Flagged", "Unflagged"
                fv = str(flag_val).lower()
                if sf == "approved" and fv not in ("1", "approved", "flagged"): return False
                if sf == "rejected" and fv not in ("2", "rejected"): return False
                if sf == "unassigned" and fv not in ("0", "unassigned", "unflagged"): return False
        
        # 2. Untagged Check
        if untagged_fields:
            for field in untagged_fields:
                f_norm = field.lower()
                # Check for empty values in typical result keys
                val = item.get(field) or item.get(field.capitalize()) or item.get(f_norm)
                if val:
                    # Not untagged - if any required untagged field has data, it fails the "must be untagged" check
                    # (Assuming the logic is "Item must have NO keywords" if untagged_keywords is checked)
                    # Wait, if user checked multiple, usually it's "OR" or "AND"?
                    # UI says "Identify Untagged Items", usually means "Show me items where these are empty".
                    pass # Keep going
                else:
                    # Found an empty field, this might be what we want
                    continue
            
            # Brute force check for Keywords specifically
            if "keywords" in [f.lower() for f in untagged_fields]:
                 kws = item.get('Keywords') or item.get('keywords') or []
                 if kws: return False # Has keywords, so not untagged
        
        return True

    def get_items_by_ids(self, item_ids: List[int]) -> List[Dict]:
        """Fetch full details for specific items."""
        try:
            return self._api.media_items.get_by_ids(item_ids)
        except Exception as e:
            logger.error(f"Failed to get items by IDs: {e}")
            return []

    def get_media_items_by_ids(self, item_ids: List[int]) -> List[Dict]:
        """Compatibility wrapper for get_items_by_ids."""
        return self.get_items_by_ids(item_ids)

    def download_thumbnail(self, item_id: int, width: int = 300, height: int = 300) -> Optional[Path]:
        """Download thumbnail to a temporary file."""
        try:
            # Fetch thumbnail data
            thumbnail_bytes = self.get_thumbnail(item_id, width, height)
            if not thumbnail_bytes:
                return None
                
            # Save to temp file
            temp_file = self.temp_dir / f"{item_id}.jpg"
            with open(temp_file, 'wb') as f:
                f.write(thumbnail_bytes)
            return temp_file
        except Exception as e:
            logger.error(f"Failed to download thumbnail: {e}")
            return None

    def update_item_tags(self, item_id: int, tags: Dict[str, List[str]]) -> bool:
        """
        Update tags for a single item.
        
        Args:
            item_id: Media item ID
            tags: Dict of tag names and values
            
        Returns:
            True if successful
        """
        try:
            # Prepare operations
            ops = []
            for tag_name, values in tags.items():
                tag_id = self._get_tag_id(tag_name)
                tag_info = next((t for t in self._tag_schema if t.id == tag_id), None) if self._tag_schema else None
                guid = tag_info.guid if tag_info else tag_name
                
                for val in values:
                    # Try to find value ID for indexed tags
                    val_id = None
                    if tag_id:
                        # This should Ideally be cached
                        found_vals = self._api.tags.find_tag_values(tag_id=tag_id, filter_text=val)
                        if found_vals:
                            val_id = found_vals[0].id
                    
                    ops.append({
                        "guid": guid,
                        "value": val,
                        "id": val_id,
                        "remove": False
                    })
            
            self._api.item_data.batch_update(item_ids=[item_id], operations=ops)
            return True
        except Exception as e:
            logger.error(f"Failed to update tags for item {item_id}: {e}")
            return False
    
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
                category_guid = tag_guid_map.get('category') or tag_guid_map.get('categories')
                if category_guid:
                    category_tag_id = self._get_tag_id('category') or self._get_tag_id('categories')
                    if category_tag_id:
                        # Find existing category value
                        category_values = self._api.tags.find_tag_values(
                            tag_id=category_tag_id,
                            filter_text=category
                        )
                        
                        if category_values:
                            operations.append({
                                "guid": category_guid,
                                "id": category_values[0].id,
                                "remove": False
                            })
                        else:
                            # Try to create or just pass value
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
                                # Fallback to value
                                operations.append({
                                    "guid": category_guid,
                                    "value": category,
                                    "remove": False
                                })
            
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
                                    # Fallback to value
                                    operations.append({
                                        "guid": keywords_guid,
                                        "value": keyword,
                                        "remove": False
                                    })
            
            # Add description if provided
            if description:
                description_guid = tag_guid_map.get('description') or tag_guid_map.get('caption')
                if description_guid:
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
