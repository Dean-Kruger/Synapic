import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

def get_record_metadata(client, item_id: int) -> Dict[str, Any]:
    """
    Fetch metadata (categories, keywords, description) for a Daminion media item.
    Uses ItemData/GetAll for complete property retrieval.
    """
    try:
        # Use ItemData/GetAll which returns full properties in nested structure
        # instead of MediaItems/GetByIds which often has missing 'values'
        data = client._api.item_data.get(item_id, get_all=True)
        if not data:
            logger.error(f"No item data returned for item {item_id}")
            return {}
            
        # Extract all properties from nested layouts
        all_props = {}
        if 'properties' in data:
            for layout in data['properties']:
                if 'properties' in layout:
                    for prop in layout['properties']:
                        prop_name = prop.get('propertyName')
                        if prop_name:
                            all_props[prop_name] = prop

        # Diagnostic logging
        logger.debug(f"Retrieved item {item_id} property names: {list(all_props.keys())}")
        
        # Helper to extract values from a property
        def parse_prop_values(prop):
            if not prop: return []
            # 'values' list in property object contains tag value objects with 'text' field
            values = prop.get('values')
            if values and isinstance(values, list):
                return [v.get('text', '') for v in values if v.get('text')]
            # Fallback to propertyValue for simple text fields
            val = prop.get('propertyValue')
            return [str(val)] if val is not None and val != "" else []

        metadata = {
            "categories": parse_prop_values(all_props.get('Categories')),
            "keywords": parse_prop_values(all_props.get('Keywords')),
            "description": str(all_props.get('Description', {}).get('propertyValue') or "")
        }
        
        logger.debug(f"Metadata for item {item_id}: {metadata}")
        return metadata

    except Exception as e:
        logger.error(f"Error fetching metadata for item {item_id}: {e}")
        return {}

def verify_metadata_update(
    client, 
    item_id: int, 
    expected_cat: Optional[str] = None, 
    expected_kws: Optional[List[str]] = None, 
    expected_desc: Optional[str] = None
) -> bool:
    """
    Verify that an item's metadata matches expected values.
    
    Args:
        client: DaminionClient instance
        item_id: Media item ID
        expected_cat: Expected category string
        expected_kws: Expected list of keywords
        expected_desc: Expected description string
        
    Returns:
        True if all specified expected values match, False otherwise
    """
    actual = get_record_metadata(client, item_id)
    if not actual:
        return False
        
    success = True
    
    # Verify Description
    if expected_desc is not None:
        if actual["description"] != expected_desc:
            logger.warning(f"Verification FAILED for item {item_id} [Description]: Expected '{expected_desc}', got '{actual['description']}'")
            success = False
        else:
            logger.info(f"Verification PASSED for item {item_id} [Description]")
            
    # Verify Category
    if expected_cat:
        # Expected cat can be single string or list in actual
        actual_cats = actual["categories"]
        if isinstance(actual_cats, list):
            if expected_cat not in actual_cats:
                logger.warning(f"Verification FAILED for item {item_id} [Category]: Expected '{expected_cat}' to be in {actual_cats}")
                success = False
            else:
                logger.info(f"Verification PASSED for item {item_id} [Category]")
        else:
            actual_cats_lower = [c.lower().strip() for c in actual_cats]
            if expected_cat.lower().strip() not in actual_cats_lower:
                logger.warning(f"Verification FAILED for item {item_id} [Category]: Expected '{expected_cat}', got '{actual_cats}'")
                success = False
            else:
                logger.info(f"Verification PASSED for item {item_id} [Category]")
                
    # Verify Keywords
    if expected_kws:
        actual_kws = actual["keywords"]
        actual_kws_lower = [kw.lower().strip() for kw in actual_kws]
        missing = [kw for kw in expected_kws if kw.lower().strip() not in actual_kws_lower]
        if missing:
            logger.warning(f"Verification FAILED for item {item_id} [Keywords]: Missing {missing}. Actual: {actual_kws}")
            success = False
        else:
            logger.info(f"Verification PASSED for item {item_id} [Keywords]")
            
    return success

if __name__ == "__main__":
    # Example usage / manual test
    import os
    import sys
    # Add src to path if running directly
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from core.daminion_client import DaminionClient
    
    # This part would require real credentials to run
    print("This script is intended to be used as a module for verification.")
