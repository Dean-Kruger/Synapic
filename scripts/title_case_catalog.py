#!/usr/bin/env python3
"""
Title Case Catalog Utility
==========================

This script retrieves all Keywords and Categories from the Daminion catalog and
converts them to proper Title Case formatting.

Key Insight: Instead of updating each item individually, this script updates
the TAG VALUES themselves. When a keyword value like "blue sky" is renamed to
"Blue Sky", all items using that keyword are automatically updated.

Usage:
    python scripts/title_case_catalog.py [--dry-run] [--verbose]

Options:
    --dry-run     Preview changes without applying them
    --verbose     Enable verbose logging

Example:
    python scripts/title_case_catalog.py --dry-run
    python scripts/title_case_catalog.py
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.daminion_api import DaminionAPI
from src.core.image_processing import to_title_case

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config() -> Dict:
    """Load Synapic configuration from user's home directory."""
    config_path = Path.home() / ".synapic_v2_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        return json.load(f)


def find_tag_by_name(tags, name: str):
    """Find a tag by name from the tag schema."""
    name_lower = name.lower()
    for tag in tags:
        if tag.name.lower() == name_lower:
            return tag
    return None


def process_tag_values(
    api: DaminionAPI,
    tag_name: str,
    dry_run: bool = True
) -> Dict:
    """
    Process all values for a tag and convert to Title Case.
    
    Args:
        api: Authenticated Daminion API client
        tag_name: Name of the tag to process (e.g., "Keywords", "Categories")
        dry_run: If True, only preview changes without applying
        
    Returns:
        Statistics dictionary
    """
    stats = {
        "tag_name": tag_name,
        "total_values": 0,
        "values_changed": 0,
        "errors": 0,
        "changes": []  # List of (old_value, new_value) tuples
    }
    
    # Get tag schema
    tags = api.tags.get_all_tags()
    tag = find_tag_by_name(tags, tag_name)
    
    if not tag:
        logger.warning(f"Tag '{tag_name}' not found in schema")
        return stats
    
    logger.info(f"Processing {tag_name} (Tag ID: {tag.id}, GUID: {tag.guid})")
    
    # Get all values for this tag
    # parent_value_id=-2 means get all levels (for hierarchical tags)
    all_values = []
    page_index = 0
    page_size = 500
    
    while True:
        values = api.tags.get_tag_values(
            tag_id=tag.id,
            parent_value_id=-2,
            page_index=page_index,
            page_size=page_size
        )
        
        if not values:
            break
        
        all_values.extend(values)
        page_index += 1
        
        if len(values) < page_size:
            break
    
    stats["total_values"] = len(all_values)
    logger.info(f"  Found {len(all_values)} {tag_name} values")
    
    # Process each value
    for value in all_values:
        original_text = value.text
        title_text = to_title_case(original_text)
        
        if original_text != title_text:
            stats["values_changed"] += 1
            stats["changes"].append({
                "original": original_text,
                "new": title_text,
                "value_id": value.id,
                "count": value.count
            })
            
            if dry_run:
                logger.debug(f"    [DRY-RUN] Would change: '{original_text}' -> '{title_text}' ({value.count} items)")
            else:
                try:
                    api.tags.update_tag_value(
                        tag_id=tag.id,
                        value_id=value.id,
                        new_text=title_text
                    )
                    logger.debug(f"    Updated: '{original_text}' -> '{title_text}'")
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"    Failed to update '{original_text}': {e}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Convert Daminion catalog Keywords and Categories to Title Case"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("Please run the main Synapic application first to configure Daminion connection.")
        sys.exit(1)
    
    ds = config.get("datasource", {})
    if ds.get("type") != "daminion":
        logger.error("This script only works with Daminion datasource.")
        logger.error(f"Current datasource type: {ds.get('type')}")
        sys.exit(1)
    
    daminion_url = ds.get("daminion_url")
    daminion_user = ds.get("daminion_user")
    daminion_pass = ds.get("daminion_pass")
    
    if not all([daminion_url, daminion_user, daminion_pass]):
        logger.error("Daminion connection details missing from configuration.")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("DAMINION CATALOG TITLE CASE CONVERTER")
    logger.info("=" * 60)
    logger.info(f"Server: {daminion_url}")
    logger.info(f"User: {daminion_user}")
    logger.info(f"Mode: {'DRY-RUN (no changes will be made)' if args.dry_run else 'LIVE (changes will be applied)'}")
    logger.info("=" * 60)
    
    if not args.dry_run:
        response = input("\n⚠️  WARNING: This will modify your Daminion catalog. Continue? [y/N] ")
        if response.lower() != 'y':
            logger.info("Aborted by user.")
            sys.exit(0)
    
    # Connect to Daminion
    try:
        with DaminionAPI(
            base_url=daminion_url,
            username=daminion_user,
            password=daminion_pass
        ) as api:
            logger.info("✓ Connected to Daminion server")
            
            # Process Keywords and Categories
            all_stats = []
            
            for tag_name in ["Keywords", "Categories"]:
                logger.info(f"\n--- Processing {tag_name} ---")
                stats = process_tag_values(api, tag_name, dry_run=args.dry_run)
                all_stats.append(stats)
            
            # Print results
            logger.info("")
            logger.info("=" * 60)
            logger.info("RESULTS")
            logger.info("=" * 60)
            
            total_values = 0
            total_changed = 0
            total_errors = 0
            
            for stats in all_stats:
                logger.info(f"\n{stats['tag_name']}:")
                logger.info(f"  Total values:    {stats['total_values']}")
                logger.info(f"  Values changed:  {stats['values_changed']}")
                logger.info(f"  Errors:          {stats['errors']}")
                
                total_values += stats['total_values']
                total_changed += stats['values_changed']
                total_errors += stats['errors']
                
                # Show sample changes
                if stats['changes']:
                    logger.info(f"\n  Sample changes (showing first 10):")
                    for change in stats['changes'][:10]:
                        logger.info(f"    '{change['original']}' -> '{change['new']}' ({change['count']} items)")
            
            logger.info("")
            logger.info("-" * 60)
            logger.info(f"TOTAL: {total_changed} values would be changed out of {total_values}")
            if total_errors > 0:
                logger.info(f"ERRORS: {total_errors}")
            
            if args.dry_run and total_changed > 0:
                logger.info("")
                logger.info("To apply these changes, run without --dry-run flag:")
                logger.info(f"  python scripts/title_case_catalog.py")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
