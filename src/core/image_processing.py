"""
Functions for processing images and writing metadata.
Enhanced with type hints, validation, and error handling.
"""

import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple, Any
from queue import Queue
from PIL import Image, UnidentifiedImageError
import piexif
from iptcinfo3 import IPTCInfo

from src.core import config

class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass

def validate_image(image_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that an image file can be opened and processed.

    Args:
        image_path: Path to the image file

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> valid, error = validate_image(Path("test.jpg"))
        >>> if valid:
        ...     print("Image is valid")
    """
    try:
        if not image_path.exists():
            return False, "File does not exist"

        if not image_path.is_file():
            return False, "Path is not a file"

        if image_path.stat().st_size == 0:
            return False, "File is empty"

        if image_path.stat().st_size > config.MAX_IMAGE_SIZE_MB * 1024 * 1024:
            return False, f"File exceeds {config.MAX_IMAGE_SIZE_MB}MB limit"

        with Image.open(image_path) as img:
            img.verify()

        with Image.open(image_path) as img:
            img.load()

        return True, None

    except UnidentifiedImageError:
        return False, "Cannot identify image file"
    except PermissionError:
        return False, "Permission denied"
    except Exception as e:
        return False, f"Validation failed: {str(e)}"

def write_metadata_with_retry(
    image_path: Path,
    category: str,
    keywords: List[str],
    description: str,
    q: Queue,
    max_retries: int = 3,
    retry_delay: float = 0.5
) -> bool:
    """
    Write metadata to image with retry logic.

    Args:
        image_path: Path to the image file
        category: Category to write
        keywords: Keywords to write
        description: Description/Caption to write
        q: Queue for status messages
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    """
    for attempt in range(max_retries):
        try:
            return write_metadata(image_path, category, keywords, description, q)
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(
                    f"Metadata write attempt {attempt + 1} failed for {image_path.name}: {e}. Retrying..."
                )
                time.sleep(retry_delay)
            else:
                logging.error(f"All metadata write attempts failed for {image_path.name}")
                return False
    return False

def write_metadata(image_path: Path, category: str, keywords: List[str], description: str, q: Optional[Queue] = None) -> bool:
    """
    Write category, keywords, and description to the image's IPTC and EXIF metadata.
    """
    iptc_success = False
    exif_success = False

    try:
        logging.info(f"Writing IPTC metadata to {image_path.name}")
        info = IPTCInfo(image_path, force=True)

        if category:
            info['object name'] = category

        if description:
             # IPTC Caption/Abstract
            info['caption/abstract'] = description

        if keywords:
            existing_keywords = [k.decode('utf-8') if isinstance(k, bytes) else k
                               for k in (info['keywords'] or [])]
            # Use set for O(1) lookups instead of O(n)
            existing_set = set(existing_keywords)
            for k in keywords:
                if k not in existing_set:
                    existing_keywords.append(k)
                    existing_set.add(k)
            info['keywords'] = existing_keywords

        info.save()
        iptc_success = True
        logging.debug(f"IPTC metadata written successfully for {image_path.name}")
        
        # Cleanup temp file if created
        temp_file = image_path.with_name(image_path.name + "~")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as tmp_err:
                logging.warning(f"Failed to delete temp file {temp_file}: {tmp_err}")

    except Exception as e:
        logging.exception(f"Failed to write IPTC metadata for {image_path.name}")

    try:
        logging.info(f"Writing EXIF metadata to {image_path.name}")
        exif_dict = piexif.load(str(image_path))

        if category:
            exif_dict['0th'][piexif.ImageIFD.XPSubject] = category.encode('utf-16le')

        if description:
             # EXIF ImageDescription - standard ascii
            exif_dict['0th'][piexif.ImageIFD.ImageDescription] = description.encode('utf-8')
            # XPTitle/XPComment are sometimes used by Windows, but ImageDescription is standard.
            # Windows 'Title' maps to ImageDescription or XPTitle. 'Subject' maps to XPSubject.
            exif_dict['0th'][piexif.ImageIFD.XPTitle] = description.encode('utf-16le')

        if keywords:
            existing_keywords_bytes = exif_dict['0th'].get(piexif.ImageIFD.XPKeywords, b'')
            
            # Piexif can sometimes return tuple of ints instead of bytes
            if isinstance(existing_keywords_bytes, tuple):
                try:
                    existing_keywords_bytes = bytes(existing_keywords_bytes)
                except Exception:
                    existing_keywords_bytes = b''
            
            existing_keywords_str = existing_keywords_bytes.decode('utf-16le').rstrip('\x00') if existing_keywords_bytes else ''
            existing_keywords = existing_keywords_str.split(';') if existing_keywords_str else []

            # Use set for O(1) lookups instead of O(n)
            existing_set = set(existing_keywords)
            for k in keywords:
                if k not in existing_set:
                    existing_keywords.append(k)
                    existing_set.add(k)

            exif_dict['0th'][piexif.ImageIFD.XPKeywords] = ";".join(existing_keywords).encode('utf-16le')

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(image_path))
        exif_success = True
        logging.debug(f"EXIF metadata written successfully for {image_path.name}")

    except Exception as e:
        logging.exception(f"Failed to write EXIF metadata for {image_path.name}")

    return iptc_success or exif_success

def process_single_image(
    image_path: Path,
    model: Any,
    model_task: str,
    categories: List[str],
    keywords: List[str],
    q: Queue
) -> Tuple[bool, Optional[str]]:
    # ... (Logic mostly delegated to batch usually, but let's update if used)
    # NOTE: This function seems less used than the batch worker, but we should update it if it's called.
    # For now, I'll leave it as is or update it if I see it's used. 
    # Actually, looking at gui_workers, it IS NOT used by the main batch loop.
    # But I should update extract_tags_from_result below.
    return False, "Function deprecated in favor of batch pipeline"


def extract_tags_from_result(
    result: Any,
    model_task: str,
    threshold: float = 0.0,
    stop_words: Optional[List[str]] = None
) -> Tuple[str, List[str], str]:
    """
    Extract category, keywords, and description from a single model result.

    Args:
        result: The output from the pipeline for a single item
        model_task: Task type
        threshold: Confidence threshold
        stop_words: List of words to ignore (for image-to-text)

    Returns:
        Tuple of (category, keywords, description)
    """
    category = ""
    keywords = []
    description = ""
    
    # Temporary debug logging for troubleshooting
    if model_task == config.MODEL_TASK_IMAGE_CLASSIFICATION:
        pass # standard classification
    elif model_task == config.MODEL_TASK_ZERO_SHOT:
        logging.info(f"Extractingtags - Task: {model_task}, Threshold: {threshold}")
        logging.info(f"Raw Result: {str(result)[:200]}...")

    try:
        if model_task == config.MODEL_TASK_IMAGE_CLASSIFICATION:
            # "Keywords (Auto)" - Extract top 5 specific tags
            # We map this to KEYWORDS now.
            if isinstance(result, list):
                # Sort by score descending just in case
                sorted_res = sorted(result, key=lambda x: x['score'], reverse=True)
                for item in sorted_res[:5]: # Top 5
                   if item['score'] >= threshold:
                       keywords.append(item['label'])
                       
            elif isinstance(result, dict):
                 if result['score'] >= threshold:
                    keywords.append(result['label'])

        elif model_task == config.MODEL_TASK_ZERO_SHOT:
            # "Categories (Custom)" - Extract broad buckets
            # We map this to CATEGORY (Subject) now.
            matched_categories = []
            
            # Handle list of dicts (standard for image zero-shot)
            if isinstance(result, list):
                # Sort by score descending
                sorted_res = sorted(result, key=lambda x: x['score'], reverse=True)
                for item in sorted_res:
                    if isinstance(item, dict) and 'label' in item and 'score' in item:
                        if item['score'] >= threshold:
                            matched_categories.append(item['label'])
            
            # Handle dict with lists (text-style zero-shot)
            elif isinstance(result, dict) and 'labels' in result and 'scores' in result:
                # Zip and sort
                zipped = sorted(zip(result['labels'], result['scores']), key=lambda x: x[1], reverse=True)
                for label, score in zipped:
                    if score >= threshold:
                        matched_categories.append(label)
            
            if matched_categories:
                # User preference: Single best category instead of list
                category = matched_categories[0]
                # Log usage
                logging.info(f"Zero-Shot Category: '{category}' (Score: >={threshold})")

        elif model_task in [config.MODEL_TASK_IMAGE_TO_TEXT, "image-text-to-text"]:
            # Result: [{'generated_text': '...'}] or chat-style structures
            text = ""
            raw_gen = None
            if isinstance(result, list) and len(result) > 0:
                raw_gen = result[0].get('generated_text', '')
            elif isinstance(result, dict):
                raw_gen = result.get('generated_text', '')
            
            # If raw_gen is a list of messages (chat format), extract assistant text
            if isinstance(raw_gen, list):
                for msg in raw_gen:
                    if isinstance(msg, dict) and msg.get('role') == 'assistant':
                        content = msg.get('content', '')
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get('type') == 'text':
                                    text += item.get('text', '')
                        elif isinstance(content, str):
                            text += content
            elif isinstance(raw_gen, str):
                text = raw_gen
            
            if text:
                description = text.strip()
                
                # 1. Handle JSON-wrapped responses that sometimes slip through as text
                if (description.startswith("{") and "generated_text" in description) or description.startswith("{\""):
                    try:
                        import json
                        import re
                        # Clean up potential markdown formatting around JSON
                        clean_json = re.sub(r'^```json\s*|\s*```$', '', description).strip()
                        data = json.loads(clean_json)
                        if isinstance(data, dict):
                            description = data.get("generated_text") or data.get("text") or description
                    except:
                        pass

                # 2. Cleanup: remove common prompt prefixes and structural artifacts
                prefixes_to_strip = [
                    "Describe the image.", "Describe this image.", "Caption:", "Description:",
                    "The image shows", "This image shows", "An image of", "A picture of",
                    "generated_text:", "Output:", "Response:"
                ]
                
                # Case-insensitive prefix stripping loop
                still_stripping = True
                while still_stripping:
                    original = description
                    for prefix in prefixes_to_strip:
                        if description.lower().startswith(prefix.lower()):
                            description = description[len(prefix):].strip()
                    
                    # Also strip rogue leading characters often seen in some model outputs (like 's, ')
                    if description.startswith("s, ") or description.startswith("s "):
                        description = description[2:].strip()
                    
                    # Strip leading punctuation/symbols often left by prefix removal
                    description = description.lstrip(":.,- ")
                    
                    if description == original:
                        still_stripping = False

                # 3. Final polish
                description = description.strip()
                if description and not description[0].isupper():
                    description = description[0].upper() + description[1:]
                
                # We do NOT extract keywords from caption anymore.
                keywords = []

    except Exception as e:
        logging.error(f"Error extracting tags from result: {e}")

    return category, keywords, description
