"""Utilities for interacting with the Hugging Face Hub."""

import logging
import time
import os
import shutil
import base64
from pathlib import Path
from functools import partial
from tqdm import tqdm
from huggingface_hub import list_models, hf_hub_download, snapshot_download, HfApi, InferenceClient
from huggingface_hub.constants import HUGGINGFACE_HUB_CACHE
import requests
from requests.exceptions import HTTPError
from transformers import pipeline, AutoConfig, AutoTokenizer, AutoProcessor
from threading import RLock
from src.core import config
import json
import sys
import platform
import torch
from typing import Optional

def get_device_info():
    """
    Returns a dictionary containing detailed information about available compute devices.
    """
    info = {
        "devices": ["CPU"],
        "default": "CPU",
        "debug_info": {
            "torch_version": torch.__version__,
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "cuda_available": torch.cuda.is_available(),
            "mps_available": hasattr(torch.backends, "mps") and torch.backends.mps.is_available(),
        }
    }
    
    # Check CUDA
    if torch.cuda.is_available():
        info["devices"].append("CUDA")
        info["default"] = "CUDA"
        info["debug_info"]["cuda_version"] = torch.version.cuda
        info["debug_info"]["cuda_device_count"] = torch.cuda.device_count()
        info["debug_info"]["cuda_current_device"] = torch.cuda.current_device()
        info["debug_info"]["cuda_device_name"] = torch.cuda.get_device_name(0)
    else:
        info["debug_info"]["cuda_check_error"] = "False (available=False)"

    # Check MPS (Mac)
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        info["devices"].append("MPS")
        if info["default"] == "CPU": # Prefer MPS over CPU if no CUDA
            info["default"] = "MPS"
            
    return info


class TqdmToQueue(tqdm):
    """A custom tqdm class that sends progress updates to a queue."""
    _lock = RLock()
    _q = None
    _update_type = None
    _overall_total_size = 0
    _overall_downloaded_bytes = 0

    def __init__(self, *args, **kwargs):
        if 'q' in kwargs:
            TqdmToQueue._q = kwargs.pop('q')
        if 'update_type' in kwargs:
            TqdmToQueue._update_type = kwargs.pop('update_type')
        super().__init__(*args, **kwargs)

    def update(self, n=1):
        super().update(n)
        with TqdmToQueue._lock:
            TqdmToQueue._overall_downloaded_bytes += n
            if TqdmToQueue._q and TqdmToQueue._update_type:
                TqdmToQueue._q.put((TqdmToQueue._update_type, (TqdmToQueue._overall_downloaded_bytes, TqdmToQueue._overall_total_size)))

    @classmethod
    def get_lock(cls):
        return cls._lock

    @classmethod
    def reset_overall_progress(cls):
        with cls._lock:
            cls._overall_downloaded_bytes = 0

    @classmethod
    def set_overall_total_size(cls, size):
        with cls._lock:
            cls._overall_total_size = size

def get_cache_dir():
    """Returns the Hugging Face cache directory."""
    return HUGGINGFACE_HUB_CACHE

def clear_cache():
    """Clears the Hugging Face Hub cache directory."""
    cache_path = Path(HUGGINGFACE_HUB_CACHE)
    if cache_path.exists():
        shutil.rmtree(cache_path)
        logging.info("Hugging Face cache cleared.")

def get_model_cache_dir(model_id):
    """Returns the cache directory for a given model."""
    return os.path.join(HUGGINGFACE_HUB_CACHE, f"models--{model_id.replace('/', '--')}")

def get_dir_size(path: Path) -> int:
    """Calculate the total size of a directory in bytes."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(Path(entry.path))
    except (OSError, PermissionError):
        pass
    return total

def format_size(size_bytes: int) -> str:
    """Format bytes as a human-readable string."""
    if size_bytes == 0: return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(units)-1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.1f} {units[i]}"

def get_remote_model_size(model_id: str, token: Optional[str] = None) -> int:
    """Fetch the total size of a model from the Hub in bytes."""
    try:
        api = HfApi(token=token)
        model_info = api.model_info(repo_id=model_id)
        return sum(s.size for s in (model_info.siblings or []) if s.size is not None)
    except Exception as e:
        logging.warning(f"Failed to get size for {model_id}: {e}")
        return 0

def is_model_downloaded(model_id, token=None):
    """Check if a model is fully downloaded."""
    try:
        api = HfApi(token=token)
        model_info = api.model_info(repo_id=model_id)
        model_cache_dir = get_model_cache_dir(model_id)
        # Check for snapshot directory
        snapshot_dir = os.path.join(model_cache_dir, 'snapshots')
        if not os.path.exists(snapshot_dir):
            return False
        # Get the latest snapshot
        snapshots = os.listdir(snapshot_dir)
        if not snapshots:
            return False
        latest_snapshot = sorted(snapshots)[-1]
        
        if model_info.siblings:
            for file_info in model_info.siblings:
                if file_info.rfilename.endswith(config.MODEL_FILE_EXCLUSIONS):
                    continue
                file_path = os.path.join(snapshot_dir, latest_snapshot, file_info.rfilename)
                if not os.path.exists(file_path):
                    logging.info(f"Model {model_id} is not fully downloaded. Missing file: {file_info.rfilename}")
                    return False
            return True
    except HTTPError as e:
        if e.response.status_code == 404:
            logging.warning(f"Model not found on Hub: {model_id}")
        else:
            logging.error(f"HTTPError checking model {model_id}: {e}")
        return False
    except Exception as e:
        logging.error(f"Error checking if model {model_id} is downloaded: {e}")
        return False

def get_downloaded_models(task, token=None):
    """Get a list of downloaded models for a given task."""
    logging.info(f"Searching for downloaded models with task: '{task}'")
    try:
        # Limit results to reduce network load and UI clutter
        models = list_models(filter=task, library="transformers", sort="downloads", direction=-1, limit=config.MODEL_SEARCH_LIMIT, token=token)
        downloaded_models = []
        for model in models or []:
            if is_model_downloaded(model.id, token=token):
                downloaded_models.append(model.id)
        logging.info(f"Found {len(downloaded_models)} downloaded models.")
        return downloaded_models
    except Exception as e:
        logging.exception("Failed to find downloaded models.")
        return []

def find_models_worker(task, q, token=None):
    """Worker thread to fetch model list from Hugging Face Hub."""
    logging.info(f"Worker searching for top {config.MODEL_SEARCH_LIMIT} models with task: '{task}'")
    try:
        # Request the top N models by downloads to keep the UI responsive.
        models = list_models(filter=task, library="transformers", sort="downloads", direction=-1, limit=config.MODEL_SEARCH_LIMIT, token=token)
        all_found = [m.id for m in models or []]
        
        logging.info(f"Hub returned {len(all_found)} raw models: {all_found}")
        
        model_ids = all_found[:config.MODEL_SEARCH_LIMIT]
        logging.info(f"Filtering to top {len(model_ids)}: {model_ids}")

        downloaded_models = []
        for model_id in model_ids:
             is_down = is_model_downloaded(model_id, token=token)
             logging.info(f"Checking if {model_id} is downloaded: {is_down}")
             if is_down:
                 downloaded_models.append(model_id)
        
        logging.info(f"Final list to GUI - Found: {len(model_ids)}, Downloaded: {len(downloaded_models)}")
        q.put(("models_found", (model_ids, downloaded_models)))
    except Exception as e:
        logging.exception("Failed to find models.")
        q.put(("error", f"Failed to find models: {e}"))

def get_suggested_task(model_config: dict) -> str:
    """
    Suggests a pipeline task based on model configuration (architectures, pipeline_tag).
    """
    # 1. Check explicit pipeline_tag (from Hub metadata, might be in config if saved by some tools)
    if "pipeline_tag" in model_config:
        return model_config["pipeline_tag"]

    # 2. Check architectures
    archs = model_config.get("architectures", [])
    for arch in archs:
        arch_lower = arch.lower()
        if "forimageclassification" in arch_lower:
            return config.MODEL_TASK_IMAGE_CLASSIFICATION
        if "forconditionalgeneration" in arch_lower:
            return config.MODEL_TASK_IMAGE_TO_TEXT
        if "visionencoderdecoder" in arch_lower:
            return config.MODEL_TASK_IMAGE_TO_TEXT
        if "clipmodel" in arch_lower or "siglipmodel" in arch_lower:
            return config.MODEL_TASK_ZERO_SHOT
    
    # 3. Check model_type for known multi-modal models
    mtype = model_config.get("model_type", "").lower()
    if mtype in ["blip", "blip-2", "git", "qwen2_vl", "llava"]:
        return config.MODEL_TASK_IMAGE_TO_TEXT
    
    # Default fallback
    return config.MODEL_TASK_IMAGE_CLASSIFICATION

def find_local_models() -> dict[str, dict]:
    """
    Finds all locally cached models by scanning the cache.

    Returns:
        A dictionary of model information, with model_id as key.
    """
    local_models = {}
    cache_path = Path(HUGGINGFACE_HUB_CACHE)
    if not cache_path.exists():
        return {}

    for model_dir in cache_path.glob("models--*"):
        if not model_dir.is_dir():
            continue

        model_id = model_dir.name[len("models--"):].replace("--", "/")
        try:
            snapshot_dirs = [d for d in (model_dir / "snapshots").iterdir() if d.is_dir()]
            if not snapshot_dirs:
                continue

            latest_snapshot = max(snapshot_dirs, key=lambda p: p.stat().st_mtime)
            config_path = latest_snapshot / "config.json"

            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    model_config = json.load(f)
                
                # Calculate size of the entire model directory (snapshots + metadata)
                size_bytes = get_dir_size(model_dir)
                
                # Infer suggested task
                suggested_task = get_suggested_task(model_config)
                
                local_models[model_id] = {
                    'config': model_config,
                    'path': latest_snapshot,
                    'size_bytes': size_bytes,
                    'size_str': format_size(size_bytes),
                    'suggested_task': suggested_task
                }
        except Exception as e:
            logging.debug(f"Could not inspect model {model_id}: {e}")
            continue
    
    return local_models


def find_local_models_by_task(task: str) -> list[str]:
    """
    Finds locally cached models compatible with a given task by scanning the cache.

    Args:
        task: The pipeline task to filter by (e.g., 'image-classification').

    Returns:
        A list of model IDs that are cached locally and support the task.
    """
    all_local_models = find_local_models()
    task_specific_models = []
    for model_id, model_info in all_local_models.items():
        if model_info['config'].get("pipeline_tag") == task:
            task_specific_models.append(model_id)
            
    logging.info(f"Found {len(task_specific_models)} local models for task '{task}'.")
    return task_specific_models


def show_model_info_worker(model_id, q, token=None):
    """Worker thread to download a model's README file."""
    logging.info(f"Fetching README for model: {model_id}")
    try:
        readme_path = hf_hub_download(repo_id=model_id, filename="README.md", token=token)
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
        logging.info(f"Successfully fetched README for model: {model_id}")
        q.put(("model_info_found", readme_content))
    except Exception as e:
        logging.warning(f"Could not retrieve README for {model_id}. Error: {e}")
        q.put(("model_info_found", f"Could not retrieve README for {model_id}.\n\n{e}"))

def download_model_worker(model_id, q, token=None):
    """Worker thread specifically for downloading a model with accurate progress reporting."""
    logging.info(f"Starting model download worker for: {model_id}")
    try:
        if is_model_downloaded(model_id, token=token):
            logging.info(f"Model {model_id} already fully downloaded.")
            q.put(("model_download_progress", (100, 100))) # Force full progress
            q.put(("download_complete", model_id))
            return

        q.put(("status_update", f"Checking files for {model_id}..."))
        
        # Determine missing bytes to make progress bar accurate
        api = HfApi(token=token)
        model_info = api.model_info(repo_id=model_id)
        
        model_cache_dir = get_model_cache_dir(model_id)
        snapshot_dir = os.path.join(model_cache_dir, 'snapshots')
        
        total_to_download = 0
        for sibling in (model_info.siblings or []):
            if sibling.rfilename.endswith(config.MODEL_FILE_EXCLUSIONS):
                continue
            
            already_exists = False
            if os.path.exists(snapshot_dir):
                for snap in os.listdir(snapshot_dir):
                    if os.path.exists(os.path.join(snapshot_dir, snap, sibling.rfilename)):
                        already_exists = True
                        break
            
            if not already_exists:
                total_to_download += (sibling.size or 0)

        # Fallback if calculation is zero (e.g. metadata only)
        if total_to_download == 0:
            total_to_download = sum(s.size for s in (model_info.siblings or []) if s.size)

        q.put(("total_model_size", total_to_download))
        logging.info(f"Target download size: {total_to_download} bytes.")
        
        TqdmToQueue.reset_overall_progress()
        TqdmToQueue.set_overall_total_size(total_to_download)
        TqdmToQueue._q = q
        TqdmToQueue._update_type = "model_download_progress"
        
        q.put(("status_update", f"Downloading {model_id}..."))
        
        snapshot_download(
            repo_id=model_id,
            tqdm_class=TqdmToQueue, # type: ignore
            token=token
        )
        
        # Final update to ensure it hits 100%
        q.put(("model_download_progress", (total_to_download, total_to_download)))
        
        logging.info(f"Model download complete for {model_id}.")
        q.put(("download_complete", model_id))
    except Exception as e:
        logging.exception(f"Failed to download model: {model_id}")
        q.put(("error", f"Failed to download model: {e}"))

def load_model_with_progress(model_id, task, q, token=None, device=-1):
    """Worker thread to load a model with progress reporting."""
    logging.info(f"Starting model load for: {model_id} on device {device}")
    
    try:
        if not is_model_downloaded(model_id, token=token):
            q.put(("status_update", f"Checking files for {model_id}..."))
            
            api = HfApi(token=token)
            model_info = api.model_info(repo_id=model_id)
            
            # Simple missing bytes calculation for progress accuracy
            total_missing = sum(s.size for s in (model_info.siblings or []) if s.size)
            
            q.put(("total_model_size", total_missing))
            TqdmToQueue.reset_overall_progress()
            TqdmToQueue.set_overall_total_size(total_missing)
            TqdmToQueue._q = q
            TqdmToQueue._update_type = "model_download_progress"
            
            q.put(("status_update", f"Downloading {model_id}..."))
            local_model_path = snapshot_download(repo_id=model_id, tqdm_class=TqdmToQueue, token=token)
            q.put(("model_download_progress", (total_missing, total_missing)))
        else:
            logging.info(f"Model {model_id} already downloaded.")
            model_cache_dir = get_model_cache_dir(model_id)
            snapshot_dir = os.path.join(model_cache_dir, 'snapshots')
            snapshots = os.listdir(snapshot_dir)
            if snapshots:
                latest_snapshot = sorted(snapshots)[-1]
                local_model_path = os.path.join(snapshot_dir, latest_snapshot)
            else:
                local_model_path = snapshot_download(repo_id=model_id, tqdm_class=TqdmToQueue, token=token)

        q.put(("status_update", f"Initializing model {model_id}..."))
        
        # Auto-Task Detection
        try:
            cfg_path = os.path.join(local_model_path, "config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as cf:
                    cfg = json.load(cf)
                suggested = get_suggested_task(cfg)
                if suggested != task:
                    if task == config.MODEL_TASK_IMAGE_CLASSIFICATION and suggested == config.MODEL_TASK_IMAGE_TO_TEXT:
                         task = suggested
                    elif task == config.MODEL_TASK_IMAGE_TO_TEXT and suggested == config.MODEL_TASK_IMAGE_CLASSIFICATION:
                         task = suggested
        except Exception: pass

        # Load pipeline (transformers handles processor/tokenizer automatically for multi-modal)
        model = pipeline(task, model=local_model_path, device=device)
        
        logging.info(f"Model pipeline ({task}) loaded successfully for: {model_id}")
        q.put(("model_loaded", {"model": model, "model_name": model_id}))

    except Exception as e:
        logging.exception(f"Failed to load model: {model_id}")
        q.put(("error", f"Failed to load model: {e}"))


def find_models_by_task(task):
    """Synchronous helper to find models for a given task.

    Returns a tuple: (model_ids, downloaded_models)
    """
    logging.info(f"Searching for models (sync) with task: '{task}'")
    try:
        # Limit to the top N models to avoid overwhelming the UI and reduce network usage
        models = list_models(filter=task, library="transformers", sort="downloads", direction=-1, limit=config.MODEL_SEARCH_LIMIT)
        model_ids = [model.id for model in models or []][:config.MODEL_SEARCH_LIMIT]
        downloaded_models = [mid for mid in model_ids if is_model_downloaded(mid)]
        logging.info(f"Found {len(model_ids)} models (sync). {len(downloaded_models)} cached locally.")
        return model_ids, downloaded_models
    except Exception as e:
        logging.exception("Failed to find models (sync).")
        return [], []


def get_model_info(model_id):
    """Return the README (or a helpful message) for a model synchronously."""
    logging.info(f"Fetching README (sync) for model: {model_id}")
    try:
        readme_path = hf_hub_download(repo_id=model_id, filename="README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.warning(f"Could not retrieve README for {model_id}. Error: {e}")
        return f"Could not retrieve README for {model_id}.\n\n{e}"


def load_model(model_id, task, progress_queue=None, token=None, device=-1):
    """Synchronous model loader that mirrors the behavior of the worker version.

    If `progress_queue` is provided, status updates will be posted to it using
    the same message types the GUI expects.
    Returns the initialized pipeline object.
    """
    logging.info(f"Starting synchronous model load for: {model_id} on device {device}")
    try:
        q = progress_queue
        if q:
            q.put(("status_update", f"Downloading/initializing model {model_id} on device {device}..."))

        if not is_model_downloaded(model_id, token=token):
            logging.info(f"Downloading model files for {model_id} (sync)...")
            api = HfApi(token=token)
            model_info = api.model_info(repo_id=model_id)
            total_model_size = sum(sibling.size for sibling in (model_info.siblings or []) if sibling.size is not None)
            if q:
                q.put(("total_model_size", total_model_size))

            TqdmToQueue.reset_overall_progress()
            TqdmToQueue.set_overall_total_size(total_model_size)
            if q:
                TqdmToQueue._q = q
                TqdmToQueue._update_type = "model_download_progress"

            local_model_path = snapshot_download(
                repo_id=model_id,
                tqdm_class=TqdmToQueue, # type: ignore
                token=token
            )
            logging.info(f"Model download complete for {model_id} (sync).")
        else:
            logging.info(f"Model {model_id} is already downloaded (sync).")
            model_cache_dir = get_model_cache_dir(model_id)
            snapshot_dir = os.path.join(model_cache_dir, 'snapshots')
            snapshots = os.listdir(snapshot_dir)
            if snapshots:
                latest_snapshot = sorted(snapshots)[-1]
                local_model_path = os.path.join(snapshot_dir, latest_snapshot)
                logging.info(f"Using latest snapshot: {latest_snapshot}")
            else:
                # Should typically not happen if is_model_downloaded returned True, 
                # but good for safety.
                logging.warning(f"Snapshot directory exists but is empty for {model_id}. Re-downloading...")
                local_model_path = snapshot_download(
                    repo_id=model_id,
                    tqdm_class=TqdmToQueue, 
                    token=token
                )

        if q:
            q.put(("status_update", f"Initializing model {model_id}..."))
        
        # Validation and Auto-Task Detection
        try:
            cfg_path = os.path.join(local_model_path, "config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as cf:
                    cfg = json.load(cf)
                suggested = get_suggested_task(cfg)
                if suggested != task:
                    if task == config.MODEL_TASK_IMAGE_CLASSIFICATION and suggested == config.MODEL_TASK_IMAGE_TO_TEXT:
                         task = suggested
                    elif task == config.MODEL_TASK_IMAGE_TO_TEXT and suggested == config.MODEL_TASK_IMAGE_CLASSIFICATION:
                         task = suggested
        except Exception: pass
            
        # Initialize pipeline with processor for multi-modal stability
        # For modern VLMs (Qwen2-VL, LLaVA), 'image-text-to-text' is preferred
        pipeline_task = task
        try:
            cfg_path = os.path.join(local_model_path, "config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as cf:
                    m_cfg = json.load(cf)
                m_type = m_cfg.get("model_type", "").lower()
                if m_type in ["qwen2_vl", "llava"]:
                    pipeline_task = "image-text-to-text"
                    logging.info(f"Using '{pipeline_task}' pipeline for model type '{m_type}'")
        except Exception: pass

        # Load processor if it exists
        processor = None
        try:
            processor = AutoProcessor.from_pretrained(local_model_path)
            logging.debug("AutoProcessor loaded successfully.")
        except Exception:
            logging.debug("No AutoProcessor found, falling back to default pipeline behavior.")

        model = pipeline(pipeline_task, model=local_model_path, processor=processor, device=device)

        logging.info(f"Model pipeline ({pipeline_task}) loaded successfully for: {model_id} on device {device}")
        return model

    except Exception as e:
        logging.exception(f"Failed to load model (sync): {model_id}")
        if progress_queue:
            progress_queue.put(("error", f"Failed to load model: {e}"))
        raise

# -------------------------------------------------------------------------
# API Inference Support
# -------------------------------------------------------------------------

class RateLimitError(Exception):
    """Raised when Hugging Face API rate limit is exceeded."""
    def __init__(self, retry_after=None):
        self.retry_after = retry_after
        msg = f"Hugging Face API rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        msg += " Consider downloading the model for unlimited local inference."
        super().__init__(msg)

def rate_limit_handler(max_retries=3, initial_delay=1.0):
    """
    Decorator to handle rate limiting and network errors for API calls.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check for HTTP 429 (Rate Limit)
                    is_rate_limit = False
                    if hasattr(e, "response") and hasattr(e.response, "status_code"):
                         if e.response.status_code == 429:
                              is_rate_limit = True
                    # Also check for message content if exception type is generic
                    if "429" in str(e) or "Rate limit" in str(e):
                         is_rate_limit = True

                    if is_rate_limit:
                        if retries >= max_retries:
                            logging.error(f"Max retries exceeded for API call: {e}")
                            raise
                        
                        # Check for retry-after header
                        wait_time = delay
                        if hasattr(e, "response") and hasattr(e.response, "headers"):
                             if "retry-after" in e.response.headers:
                                  try:
                                      wait_time = float(e.response.headers["retry-after"]) + 1.0 # Add buffer
                                  except:
                                      pass

                        logging.warning(
                            f"⚠️ Rate limited by Hugging Face API. "
                            f"Waiting {wait_time:.0f}s before retry {retries+1}/{max_retries}... "
                            f"Consider downloading the model for unlimited local inference."
                        )
                        time.sleep(wait_time)
                        retries += 1
                        delay *= 2 # Exponential backoff for subsequent defaults
                    
                    elif hasattr(e, "response") and hasattr(e.response, "status_code") and e.response.status_code >= 500:
                         # Server error, retry
                         if retries >= max_retries:
                            logging.error(f"Max retries exceeded for server error: {e}")
                            raise
                         logging.warning(f"Server error {e.response.status_code}. Retrying {retries+1}/{max_retries}...")
                         time.sleep(delay)
                         retries += 1
                         delay *= 2
                    
                    else:
                        # Other errors (Auth, BadRequest) - do not retry
                        raise
        return wrapper
    return decorator


@rate_limit_handler(max_retries=3)
def run_inference_api(model_id, image_path, task, token, parameters=None):
    """
    Runs inference using the Hugging Face Inference API.
    
    Args:
        model_id: The model ID on HF Hub.
        image_path: Path to local image file.
        task: The task type (e.g. 'image-classification').
        token: HF API Token.
        parameters: Optional parameters dict.
        
    Returns:
        The raw JSON response from the API.
    """
    from src.utils.logger import log_api_request, log_api_response
    logger = logging.getLogger(__name__)
    
    logger.info(f"[HuggingFace API] Starting inference - Model: {model_id}, Task: {task}")
    start_time = time.time()
    
    client = InferenceClient(token=token)
    
    # Map internal task names to API tasks if needed, though they usually match.
    # We mainly need to handle the input type.
    
    # For image tasks, we pass the file.
    try:
        # Check image validity
        if not Path(image_path).exists():
             raise FileNotFoundError(f"Image not found: {image_path}")
        
        # InferenceClient.predict() or specific task methods can be used.
        # .image_classification() is specific.
        # .image_to_text() is specific.
        
        logger.debug(f"Image path: {image_path}")
        logger.debug(f"Parameters: {parameters}")
        
        if task == config.MODEL_TASK_IMAGE_CLASSIFICATION:
             try:
                # Fallback to manual POST to avoid StopIteration issues in some client versions
                with open(image_path, "rb") as img_f:
                    b64_image = base64.b64encode(img_f.read()).decode("utf-8")
                
                payload = {"inputs": b64_image}

                # Using the router endpoint
                api_url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
                headers = {"Authorization": f"Bearer {token}"}
                
                log_api_request(logger, "POST", api_url, headers=headers, data=payload)

                response = requests.post(api_url, headers=headers, json=payload)
                elapsed = time.time() - start_time
                
                log_api_response(logger, response.status_code, elapsed_time=elapsed)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"[HuggingFace API] Inference successful - Duration: {elapsed:.3f}s")
                return result

             except requests.exceptions.HTTPError as e:
                 if e.response.status_code in [404, 410]:
                     raise ValueError(f"Model {model_id} is not available on the free Hugging Face Inference API. Status: {e.response.status_code}")
                 raise e
             
        elif task == config.MODEL_TASK_ZERO_SHOT:
             # Zero shot requires candidate labels in parameters
             if not parameters or "candidate_labels" not in parameters:
                  raise ValueError("candidate_labels required for zero-shot api")
             
             try:
                 return client.zero_shot_image_classification(
                      image_path, 
                      model=model_id, 
                      candidate_labels=parameters["candidate_labels"]
                 )
             except Exception as e:
                 # Fallback for StopIteration or other client issues
                 logging.warning(f"Native zero-shot client failed ({type(e).__name__}), falling back to raw JSON API...")
                 
                 with open(image_path, "rb") as img_f:
                     b64_image = base64.b64encode(img_f.read()).decode("utf-8")
                 
                 payload = {
                     "inputs": b64_image,
                     "parameters": {"candidate_labels": parameters["candidate_labels"]}
                 }
                 
                 # Direct API call to bypass client library issues and deprecated endpoints
                 # Using the new router endpoint
                 api_url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
                 headers = {"Authorization": f"Bearer {token}"}
                 
                 response = requests.post(api_url, headers=headers, json=payload)
                 try:
                     response.raise_for_status()
                 except requests.exceptions.HTTPError as e:
                     if response.status_code in [404, 410]:
                         raise ValueError(f"Model {model_id} is not available on the free Hugging Face Inference API (Status {response.status_code}). Please use 'Local' mode or try a different model.")
                     raise e
                     
                 return response.json()


        elif task == config.MODEL_TASK_IMAGE_TO_TEXT:
            try:
                # The client.image_to_text() convenience method doesn't support all generation parameters
                # correctly or consistently across versions. We fallback to manual POST.
                 
                with open(image_path, "rb") as img_f:
                    b64_image = base64.b64encode(img_f.read()).decode("utf-8")

                gen_kwargs = parameters.get("generate_kwargs", {}) or {}
                
                payload = {
                     "inputs": b64_image,
                     "parameters": gen_kwargs
                }

                # Using the router endpoint
                api_url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
                headers = {"Authorization": f"Bearer {token}"}

                response = requests.post(api_url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.HTTPError as e:
                 if e.response.status_code in [404, 410]:
                     raise ValueError(f"Model {model_id} is not available on the free Hugging Face Inference API. Status: {e.response.status_code}")
                 raise e
        
        else:
             # Fallback to generic
             return client.post(json={"inputs": image_path}, model=model_id, task=task)

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[HuggingFace API] Inference failed after {elapsed:.3f}s: {type(e).__name__}: {str(e)}")
        logger.exception("Full traceback:")
        raise
