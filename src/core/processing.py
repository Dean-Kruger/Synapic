import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional
from PIL import Image

from .session import Session
from . import huggingface_utils
from . import openrouter_utils
from . import image_processing
from . import config

class ProcessingManager:
    def __init__(self, session: Session, log_callback: Callable[[str], None], progress_callback: Callable[[float, int, int], None]):
        self.session = session
        self.log = log_callback
        self.progress = progress_callback
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_job, daemon=True)
        self.thread.start()

    def abort(self):
        self.stop_event.set()
        self.log("Stopping job... please wait.")

    def _run_job(self):
        try:
            self.log("Job started.")
            self.session.reset_stats()

            # 1. Fetch Items
            items = self._fetch_items()
            if not items:
                self.log("No items found to process.")
                return

            self.session.total_items = len(items)
            self.log(f"Found {len(items)} items to process.")
            self.progress(0, 0, len(items))

            # 2. Initialize Engine (if Local)
            if self.session.engine.provider == "local":
                self._init_local_model()

            # 3. Process Loop
            for i, item in enumerate(items):
                if self.stop_event.is_set():
                    self.log("Job aborted by user.")
                    break

                self._process_single_item(item)
                
                # Update progress
                self.session.processed_items += 1
                pct = (i + 1) / len(items)
                self.progress(pct, i + 1, len(items))

            self.log("Job finished.")

        except Exception as e:
            logging.exception("Processing failed")
            self.log(f"Error: {e}")
            self.session.failed_items += 1

    def _fetch_items(self):
        if self.session.datasource.type == "local":
            path = Path(self.session.datasource.local_path)
            if not path.exists():
                raise FileNotFoundError(f"Folder not found: {path}")
            
            # Scan for images
            exts = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
            files = [p for p in path.iterdir() if p.suffix.lower() in exts]
            return files

        elif self.session.datasource.type == "daminion":
            if not self.session.daminion_client:
                raise ValueError("Daminion client not connected")
            
            self.log("Fetching items from Daminion...")
            
            # Fetch based on scope
            # TODO: Add support for 'selection' or 'collection' via session config
            # For now, default to grabbing a batch of recent items or shared collection
            
            # Example: Get last 50 items
            # items, total = self.session.daminion_client.get_media_items(start_id=1, batch_size=50)
            
            # Better: Get all items paginated (limit to 50 for testing)
            items = self.session.daminion_client.get_all_items_paginated(batch_size=50, max_items=50)
            
            self.log(f"Retrieved {len(items)} items from Daminion.")
            return items
        
        return []

    def _init_local_model(self):
        engine = self.session.engine
        self.log(f"Loading local model: {engine.model_id}...")
        
        try:
            self.model = huggingface_utils.load_model(
                model_id=engine.model_id,
                task=engine.task,
                progress_queue=None # We handle progress via callback manually if needed, or update this to accept callback
            )
            self.log("Model loaded successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")

    def _process_single_item(self, item):
        path = None
        is_daminion = isinstance(item, dict)
        daminion_client = self.session.daminion_client
        temp_thumb = None

        try:
            engine = self.session.engine
            
            # 1. Load Image
            if is_daminion:
                item_id = item.get('id')
                filename = item.get('fileName') or f"Item {item_id}"
                self.log(f"Processing Daminion Item: {filename}...")
                
                # Download thumbnail
                temp_thumb = daminion_client.download_thumbnail(item_id)
                if not temp_thumb or not temp_thumb.exists():
                    raise RuntimeError(f"Could not download thumbnail for item {item_id}")
                path = temp_thumb
            else:
                path = item
                self.log(f"Processing: {path.name}...")

            # 2. Inference
            result = None
            
            if engine.provider == "local":
                # Local Inference
                # Simple dispatch for now
                if engine.task == config.MODEL_TASK_IMAGE_TO_TEXT:
                    # Captioning
                    with Image.open(path) as img:
                         if img.mode != "RGB": img = img.convert("RGB")
                         result = self.model(img)
                elif engine.task == config.MODEL_TASK_ZERO_SHOT:
                    # Zero-Shot Classification
                    # Requires candidate_labels
                    with Image.open(path) as img:
                         if img.mode != "RGB": img = img.convert("RGB")
                         result = self.model(img, candidate_labels=config.DEFAULT_CANDIDATE_LABELS)
                else:
                    # Classification
                     with Image.open(path) as img:
                         if img.mode != "RGB": img = img.convert("RGB")
                         result = self.model(img)

            elif engine.provider in ["huggingface", "openrouter"]:
                # API Inference
                provider_module = huggingface_utils if engine.provider == "huggingface" else openrouter_utils
                
                params = {}
                if engine.task == config.MODEL_TASK_ZERO_SHOT:
                    params["candidate_labels"] = config.DEFAULT_CANDIDATE_LABELS
                
                result = provider_module.run_inference_api(
                    model_id=engine.model_id,
                    image_path=str(path),
                    task=engine.task,
                    token=engine.api_key,
                    parameters=params
                )

            # 3. Extract Tags
            cat, kws, desc = image_processing.extract_tags_from_result(result, engine.task)
            
            # 4. Write Metadata
            if is_daminion:
                success = daminion_client.update_item_metadata(
                    item_id=item_id,
                    category=cat,
                    keywords=kws,
                    description=desc
                )
            else:
                success = image_processing.write_metadata(
                    image_path=path,
                    category=cat,
                    keywords=kws,
                    description=desc
                )
            
            status = "Success" if success else "Write Failed"
            tags_str = f"Cat: {cat}, Kws: {len(kws)}, Desc: {desc[:20]}..."
            self.log(f"Result: {tags_str}")
            
            self.session.results.append({
                "filename": filename if is_daminion else path.name,
                "status": status,
                "tags": tags_str
            })

        except Exception as e:
            name = item.get('fileName') if is_daminion else (item.name if isinstance(item, Path) else str(item))
            logging.error(f"Failed to process {name}: {e}")
            self.session.failed_items += 1
            self.log(f"Failed: {e}")
        finally:
            # Cleanup temp thumbnail if it was created
            if temp_thumb and temp_thumb.exists():
                try:
                    import os
                    os.remove(temp_thumb)
                except Exception:
                    pass
