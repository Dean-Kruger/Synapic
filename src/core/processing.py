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
        self.logger = logging.getLogger(__name__)

    def start(self):
        self.logger.info("Starting processing job")
        self.logger.info(f"Datasource: {self.session.datasource.type}, Engine: {self.session.engine.provider}")
        self.logger.info(f"Model: {self.session.engine.model_id}, Task: {self.session.engine.task}")
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_job, daemon=True)
        self.thread.start()

    def abort(self):
        self.logger.warning("Processing job abort requested")
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
            self.logger.info(f"Processing job initialized - {len(items)} items queued")
            self.log(f"Found {len(items)} items to process.")
            self.progress(0, 0, len(items))

            # 2. Initialize Engine (if Local)
            if self.session.engine.provider == "local":
                self._init_local_model()

            # 3. Process Loop
            for i, item in enumerate(items):
                if self.stop_event.is_set():
                    self.logger.info(f"Job aborted by user after processing {i} items")
                    self.log("Job aborted by user.")
                    break

                self._process_single_item(item)
                
                # Update progress
                self.session.processed_items += 1
                pct = (i + 1) / len(items)
                self.progress(pct, i + 1, len(items))

            
            self.logger.info(f"Processing job completed - Processed: {self.session.processed_items}, Failed: {self.session.failed_items}")
            self.log("Job finished.")

        except Exception as e:
            self.logger.exception("Processing job failed with exception")
            logging.exception("Processing failed")
            self.log(f"Error: {e}")
            self.session.failed_items += 1

    def _fetch_items(self):
        ds = self.session.datasource
        if ds.type == "local":
            path = Path(ds.local_path)
            if not path.exists():
                raise FileNotFoundError(f"Folder not found: {path}")
            
            # Scan for images
            exts = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
            
            if ds.local_recursive:
                 self.logger.info(f"Performing recursive scan of {path}")
                 files = [p for p in path.rglob("*") if p.suffix.lower() in exts]
            else:
                 self.logger.info(f"Performing shallow scan of {path}")
                 files = [p for p in path.iterdir() if p.suffix.lower() in exts]
            
            self.logger.info(f"Found {len(files)} image files in local folder: {path} (recursive={ds.local_recursive})")
            return files

        elif ds.type == "daminion":
            if not self.session.daminion_client:
                raise ValueError("Daminion client not connected")
            
            self.logger.info(f"Fetching items from Daminion - Scope: {ds.daminion_scope}, Approval: {ds.daminion_approval_status}")
            self.log("Fetching items from Daminion...")
            
            # Build untagged fields list
            untagged_fields = []
            if ds.daminion_untagged_keywords: untagged_fields.append("Keywords")
            if ds.daminion_untagged_categories: untagged_fields.append("Categories")
            if ds.daminion_untagged_description: untagged_fields.append("Description")
            
            # Determine max items based on scope
            # For testing/demo, we might want to cap 'all' but allow 'saved_search' or 'collection' to be larger
            max_to_fetch = None if ds.daminion_scope != "all" else 100
            
            items = self.session.daminion_client.get_items_filtered(
                scope=ds.daminion_scope,
                saved_search_id=ds.daminion_saved_search,
                collection_id=ds.daminion_catalog_id,
                untagged_fields=untagged_fields,
                approval_status=ds.daminion_approval_status,
                max_items=max_to_fetch
            )
            
            self.logger.info(f"Retrieved {len(items)} items from Daminion")
            self.log(f"Retrieved {len(items)} items from Daminion.")
            return items
        
        return []

    def _init_local_model(self):
        engine = self.session.engine
        self.logger.info(f"Initializing local model: {engine.model_id}")
        self.log(f"Loading local model: {engine.model_id}...")
        
        try:
            self.model = huggingface_utils.load_model(
                model_id=engine.model_id,
                task=engine.task,
                progress_queue=None
            )
            
            # Sync task if it was auto-corrected by load_model
            actual_task = getattr(self.model, "task", None)
            if actual_task and actual_task != engine.task:
                self.logger.info(f"Syncing session task from '{engine.task}' to actual pipeline task '{actual_task}'")
                engine.task = actual_task

            self.logger.info(f"Local model loaded successfully: {engine.model_id} (Task: {engine.task})")
            self.log(f"Model loaded successfully (Task: {engine.task}).")
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
                self.logger.debug(f"Processing Daminion item {item_id}: {filename}")
                self.log(f"Processing Daminion Item: {filename}...")
                
                # Download thumbnail
                temp_thumb = daminion_client.download_thumbnail(item_id)
                if not temp_thumb or not temp_thumb.exists():
                    raise RuntimeError(f"Could not download thumbnail for item {item_id}")
                path = temp_thumb
            else:
                path = item
                self.logger.debug(f"Processing local file: {path}")
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
                         
                         # Modern VLMs (e.g. Qwen2-VL) require a prompt, otherwise 
                         # they fail during preprocessing with KeyError: 'input_ids'.
                         # Standard models like BLIP/GIT often support prompts too.
                         try:
                             # Provide a default prompt and limit length
                             result = self.model(img, prompt="Describe the image.", generate_kwargs={"max_new_tokens": 128})
                         except Exception as e:
                             self.logger.debug(f"Prompted inference failed ({e}), falling back to simple call.")
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
            self.logger.debug(f"Extracted tags - Category: {cat}, Keywords: {len(kws)}, Description length: {len(desc) if desc else 0}")
            
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
            self.logger.info(f"Item processed successfully - Status: {status}, Tags: {tags_str}")
            self.log(f"Result: {tags_str}")
            
            self.session.results.append({
                "filename": filename if is_daminion else path.name,
                "status": status,
                "tags": tags_str
            })

        except Exception as e:
            name = item.get('fileName') if is_daminion else (item.name if isinstance(item, Path) else str(item))
            self.logger.error(f"Failed to process item '{name}': {type(e).__name__}: {str(e)}")
            self.logger.exception("Full traceback:")
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
