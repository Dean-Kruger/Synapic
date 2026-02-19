"""
Processing Pipeline Module
===========================

This module implements the core processing pipeline that orchestrates the entire
image tagging workflow. It manages the multi-threaded execution of AI model inference
and metadata writing operations.

Key Components:
- ProcessingManager: Main orchestrator class that runs in a background thread
- Item fetching: Retrieves images from local filesystem or Daminion
- Model initialization: Loads AI models for local inference
- Processing loop: Iterates through items, runs inference, writes metadata
- Progress tracking: Reports status to UI via callbacks

Threading Model:
- Main thread: UI event loop
- Background thread: Processing pipeline (created by ProcessingManager.start())
- The background thread can be interrupted via stop_event

Workflow Stages:
1. Fetch items (local folder scan or Daminion query)
2. Initialize model (if using local inference)
3. Process each item:
   a. Load image
   b. Run AI inference
   c. Extract tags from results
   d. Write metadata (EXIF/IPTC or Daminion)
   e. Verify metadata (optional)
4. Update statistics and progress

Author: Dean
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional
from PIL import Image

# Internal modules
from .session import Session
from . import huggingface_utils
from . import openrouter_utils
from . import image_processing
from . import config

# Optional Groq integration (for Groq SDK-based inference)
try:
    from src.integrations.groq_package_client import GroqPackageClient
    GROQ_AVAILABLE = True
except ImportError:
    GroqPackageClient = None
    GROQ_AVAILABLE = False

# Optional Ollama integration (official client with host config)
try:
    from src.integrations.ollama_client import OllamaClient
    OLLAMA_AVAILABLE = True
except ImportError:
    OllamaClient = None
    OLLAMA_AVAILABLE = False

# Optional Nvidia integration
try:
    from src.integrations.nvidia_client import NvidiaClient
    NVIDIA_AVAILABLE = True
except ImportError:
    NvidiaClient = None
    NVIDIA_AVAILABLE = False

# Optional metadata verification (for testing/debugging)
# This module may not be available in packaged distributions
try:
    import tests.verify_metadata as verifier
except ImportError:
    # Fallback if tests is not in path (e.g. when packaged)
    verifier = None


# ============================================================================
# PROCESSING MANAGER
# ============================================================================

class ProcessingManager:
    """
    Main processing orchestrator that runs the AI tagging pipeline.
    
    This class manages the entire processing workflow in a background thread,
    allowing the UI to remain responsive. It coordinates between:
    - Data source (local files or Daminion)
    - AI engine (local models or cloud APIs)
    - Metadata writing (EXIF/IPTC or Daminion API)
    
    The processing runs asynchronously and can be aborted by the user at any time.
    Progress and log messages are sent to the UI via callback functions.
    
    Attributes:
        session: Session object containing all configuration and state
        log: Callback function for sending log messages to UI
        progress: Callback function for updating progress bar (percentage, current, total)
        stop_event: Threading event used to signal abortion
        thread: Background thread running the processing job
        logger: Python logger for file-based logging
        model: Loaded AI model (only for local inference)
    
    Example:
        >>> manager = ProcessingManager(session, log_callback, progress_callback)
        >>> manager.start()  # Starts background thread
        >>> # ... user can abort ...
        >>> manager.abort()  # Signals thread to stop
    """
    
    def __init__(self, session: Session, log_callback: Callable[[str], None], progress_callback: Callable[[float, int, int], None]):
        """
        Initialize the processing manager.
        
        Args:
            session: Session object with datasource and engine configuration
            log_callback: Function to call with log messages for UI display
            progress_callback: Function to call with progress updates (percentage, current, total)
        """
        self.session = session
        self.log = log_callback  # UI log callback
        self.progress = progress_callback  # UI progress callback
        self.stop_event = threading.Event()  # Signal for aborting
        self.thread = None  # Background processing thread
        self.logger = logging.getLogger(__name__)  # File logger

    def start(self):
        """
        Start the processing job in a background thread.
        
        This method creates and starts a daemon thread that runs the entire
        processing pipeline. The thread will automatically terminate when the
        main program exits.
        
        The processing workflow is:
        1. Reset statistics
        2. Fetch items from datasource
        3. Initialize model (if local)
        4. Process each item
        5. Report completion
        """
        self.logger.info("Starting processing job")
        self.logger.info(f"Datasource: {self.session.datasource.type}, Engine: {self.session.engine.provider}")
        self.logger.info(f"Model: {self.session.engine.model_id}, Task: {self.session.engine.task}")
        
        # Clear any previous abort signal
        self.stop_event.clear()
        
        # Create and start background thread
        # daemon=True ensures thread terminates when main program exits
        self.thread = threading.Thread(target=self._run_job, daemon=True)
        self.thread.start()

    def abort(self):
        """
        Request abortion of the current processing job.
        
        This method sets a flag that the background thread checks between
        each item. The thread will stop processing new items but will
        complete the current item before exiting.
        
        Note: This is a graceful shutdown - the current item will finish processing.
        """
        if self.stop_event.is_set():
            return
            
        self.logger.warning("Processing job abort requested")
        self.stop_event.set()  # Signal the background thread to stop
        self.log("Stopping job... please wait.")

    def shutdown(self, timeout=2.0):
        """
        Ensure the processing manager shuts down completely.
        Called during application exit.
        
        Args:
            timeout: Maximum time to wait for the thread to join
        """
        if self.thread and self.thread.is_alive():
            self.logger.info("ProcessingManager shutdown initiated")
            self.abort()
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                self.logger.warning(f"Processing thread did not terminate within {timeout}s - proceeding anyway")

    def _run_job(self):
        """
        Main processing loop (runs in background thread).
        
        This method orchestrates the entire processing workflow:
        1. Fetches items from the configured datasource
        2. Initializes the AI model (if using local inference)
        3. Processes each item sequentially
        4. Updates progress after each item
        5. Handles errors and abortion gracefully
        
        The method runs in a separate thread and communicates with the UI
        via the log and progress callbacks.
        """
        try:
            self.log("Job started.")
            self.session.reset_stats()  # Clear previous run statistics

            # ================================================================
            # STAGE 1: FETCH ITEMS
            # ================================================================
            items = self._fetch_items()
            if not items:
                self.log("No items found to process.")
                return

            # Update session statistics
            self.session.total_items = len(items)
            self.logger.info(f"Processing job initialized - {len(items)} items queued")
            self.log(f"Found {len(items)} items to process.")
            self.progress(0, 0, len(items))  # Initialize progress bar

            # ================================================================
            # STAGE 2: INITIALIZE MODEL (LOCAL ONLY)
            # ================================================================
            # For local inference, load the model into memory once
            # For API-based inference, no initialization needed
            if self.session.engine.provider == "local":
                self._init_local_model()

            # ================================================================
            # STAGE 3: PROCESS EACH ITEM
            # ================================================================
            for i, item in enumerate(items):
                # Check if user requested abortion
                if self.stop_event.is_set():
                    self.logger.info(f"Job aborted by user after processing {i} items")
                    self.log("Job aborted by user.")
                    break

                # Process this item (inference + metadata writing)
                self._process_single_item(item)
                
                # Update progress tracking
                self.session.processed_items += 1
                pct = (i + 1) / len(items)
                self.progress(pct, i + 1, len(items))

            self.logger.debug("Hit end of processing loop")
            # ================================================================================
            # STAGE 4: COMPLETION & CLEANUP
            # ================================================================================
            self.logger.info(f"Processing job completed - Processed: {self.session.processed_items}, Failed: {self.session.failed_items}")
            self.log("Job finished.")

            # Explicitly unload model to free memory/VRAM
            if hasattr(self, 'model') and self.model:
                self.logger.info("Unloading local model and performing memory cleanup")
                self.model = None  # Release reference
                
                # Force garbage collection
                import gc
                gc.collect()
                
                # Clear CUDA cache if GPU was used
                if self.session.engine.device == "cuda":
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                            self.logger.info("CUDA cache cleared")
                    except ImportError:
                        pass
                
                self.log("Memory cleanup completed.")

        except Exception as e:
            # Catch any unexpected errors in the processing pipeline
            self.logger.exception("Processing job failed with exception")
            logging.exception("Processing failed")
            self.log(f"Error: {e}")
            self.session.failed_items += 1

    def _fetch_items(self):
        """
        Fetch items to process from the configured datasource.
        
        This method handles two types of datasources:
        1. Local filesystem - Scans a folder for image files
        2. Daminion DAM - Queries the Daminion server for items
        
        For local sources, it scans for common image formats (.jpg, .jpeg, .png, .tif, .tiff)
        either recursively or in a single directory.
        
        For Daminion sources, it builds a complex query based on:
        - Scope (all items, saved search, collection, etc.)
        - Status filter (approved, rejected, unassigned)
        - Untagged fields filter (items missing keywords, categories, or descriptions)
        - Search terms
        - Maximum item limit
        
        Returns:
            list: List of items to process. For local: list of Path objects.
                  For Daminion: list of item dictionaries with metadata.
        
        Raises:
            FileNotFoundError: If local path doesn't exist
            ValueError: If Daminion client is not connected
        """
        ds = self.session.datasource
        
        # ================================================================
        # LOCAL FILESYSTEM SOURCE
        # ================================================================
        if ds.type == "local":
            path = Path(ds.local_path)
            if not path.exists():
                raise FileNotFoundError(f"Folder not found: {path}")
            
            # Define supported image file extensions
            exts = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
            
            # Scan directory (recursive or shallow)
            if ds.local_recursive:
                 self.logger.info(f"Performing recursive scan of {path}")
                 # rglob("*") recursively finds all files in subdirectories
                 files = [p for p in path.rglob("*") if p.suffix.lower() in exts]
            else:
                 self.logger.info(f"Performing shallow scan of {path}")
                 # iterdir() only scans the immediate directory
                 files = [p for p in path.iterdir() if p.suffix.lower() in exts]
            
            self.logger.info(f"Found {len(files)} image files in local folder: {path} (recursive={ds.local_recursive})")
            return files

        # ================================================================
        # DAMINION DAM SOURCE
        # ================================================================
        elif ds.type == "daminion":
            # Ensure Daminion client is connected
            if not self.session.daminion_client:
                raise ValueError("Daminion client not connected")
            
            self.logger.info(f"Fetching items from Daminion - Scope: {ds.daminion_scope}, Status: {ds.status_filter}")
            self.log("Fetching items from Daminion...")
            
            # Build list of fields to filter for untagged items
            # Only items missing ALL selected fields will be included
            untagged_fields = []
            if ds.daminion_untagged_keywords: untagged_fields.append("Keywords")
            if ds.daminion_untagged_categories: untagged_fields.append("Category")
            if ds.daminion_untagged_description: untagged_fields.append("Description")
            
            # Determine maximum items to fetch (0 = unlimited)
            max_to_fetch = ds.max_items if ds.max_items > 0 else None
            
            # Query Daminion with all configured filters
            items = self.session.daminion_client.get_items_filtered(
                scope=ds.daminion_scope,
                saved_search_id=ds.daminion_saved_search_id or ds.daminion_saved_search,
                collection_id=ds.daminion_collection_id or ds.daminion_catalog_id,
                search_term=ds.daminion_search_term,
                untagged_fields=untagged_fields,
                status_filter=ds.status_filter,
                max_items=max_to_fetch
            )
            
            self.logger.info(f"Retrieved {len(items)} items from Daminion")
            self.log(f"Retrieved {len(items)} items from Daminion.")
            return items
        
        # Unknown datasource type
        return []

    def _init_local_model(self):
        """
        Initialize and load the AI model for local inference.
        
        This method is only called when using local inference (not API-based).
        It loads the model from Hugging Face's cache into memory and prepares
        it for inference on the selected device (CPU or GPU).
        
        The method:
        1. Checks model compatibility (rejects GPTQ, AWQ, etc.)
        2. Converts device string ('cpu'/'cuda') to integer format for pipeline
        3. Loads the model using huggingface_utils
        4. Auto-detects and corrects the task if needed
        5. Stores the model in self.model for reuse across all items
        
        Device mapping:
        - 'cpu' -> -1 (use CPU for inference)
        - 'cuda' -> 0 (use GPU device 0 for inference)
        
        Raises:
            RuntimeError: If model loading fails or model is incompatible
        
        Note:
            The model is loaded once and reused for all items in the batch,
            which is much more efficient than loading per-item.
        """
        engine = self.session.engine
        
        # Check model compatibility before attempting to load
        if not huggingface_utils.is_model_compatible(engine.model_id):
            reason = huggingface_utils.get_incompatibility_reason(engine.model_id)
            error_msg = (
                f"Cannot load model '{engine.model_id}': {reason}\n\n"
                "This model requires special libraries not included in Synapic.\n"
                "Please select a different model from the local cache."
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.logger.info(f"Initializing local model: {engine.model_id}")
        self.log(f"Loading local model: {engine.model_id}...")
        
        # Convert device string to integer format expected by transformers pipeline
        # -1 = CPU, 0 = CUDA device 0 (first GPU)
        device_int = -1 if engine.device == "cpu" else 0
        self.logger.info(f"Using device: {engine.device} (device_int={device_int})")
        
        try:
            # Load model from Hugging Face cache
            # This may download the model if not already cached
            self.model = huggingface_utils.load_model(
                model_id=engine.model_id,
                task=engine.task,
                progress_queue=None,  # No progress tracking for batch load
                device=device_int
            )
            
            # Auto-detect actual task from loaded model
            # Some models may have a different task than configured
            # (e.g., VLMs use 'image-text-to-text' instead of 'image-to-text')
            actual_task = getattr(self.model, "task", None)
            if actual_task and actual_task != engine.task:
                self.logger.info(f"Syncing session task from '{engine.task}' to actual pipeline task '{actual_task}'")
                engine.task = actual_task

            self.logger.info(f"Local model loaded successfully: {engine.model_id} (Task: {engine.task}, Device: {engine.device})")
            self.log(f"Model loaded successfully (Task: {engine.task}, Device: {engine.device}).")
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")

    def _process_single_item(self, item):
        """
        Process a single image item through the complete AI tagging pipeline.
        
        This method orchestrates the four-stage processing workflow:
        1. **Image Loading**: Load from local file or download Daminion thumbnail
        2. **AI Inference**: Run the image through the configured AI model
        3. **Tag Extraction**: Parse model output and filter by confidence threshold
        4. **Metadata Writing**: Write tags to EXIF/IPTC or update Daminion
        
        Args:
            item: Either a Path object (local file) or dict (Daminion item with 'id', 'fileName')
        
        Processing Flow:
            - Detects item type (local vs Daminion) and loads image accordingly
            - Routes to appropriate inference method (local model vs API)
            - Handles different model types (VLM, captioning, classification, zero-shot)
            - Applies confidence threshold filtering to extracted tags
            - Writes metadata to destination (file or Daminion)
            - Optionally verifies Daminion metadata updates
            - Updates session statistics and results
        
        Error Handling:
            - Logs detailed error information for debugging
            - Increments failed_items counter
            - Continues processing remaining items (doesn't abort job)
            - Cleans up temporary files even on failure
        
        Note:
            For Daminion items, thumbnails are downloaded to temp files and
            cleaned up after processing to avoid disk space issues.
        """
        path = None
        is_daminion = isinstance(item, dict)  # Daminion items are dicts, local items are Path objects
        daminion_client = self.session.daminion_client
        temp_thumb = None  # Track temporary thumbnail file for cleanup

        try:
            engine = self.session.engine
            
            # ===============================================================
            # STAGE 1: IMAGE LOADING
            # ===============================================================
            # Load the image from either local filesystem or Daminion server
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

            # ===============================================================
            # STAGE 2: AI INFERENCE
            # ===============================================================
            # Run the image through the AI model to generate tags
            # The inference method depends on the configured provider:
            # - 'local': Use locally loaded model (self.model)
            # - 'huggingface'/'openrouter': Call API endpoint
            result = None
            
            if engine.provider == "local":
                # ---------------------------------------------------------------
                # LOCAL INFERENCE (Model loaded in memory)
                # ---------------------------------------------------------------
                # The model was loaded in _init_local_model() and is reused
                # for all items in the batch for efficiency
                
                if engine.task in [config.MODEL_TASK_IMAGE_TO_TEXT, "image-text-to-text"]:
                    # Image Captioning / Vision-Language Models (VLMs)
                    # Handles both standard captioning (BLIP, GIT) and modern VLMs (Qwen2-VL)
                    with Image.open(path) as img:
                         if img.mode != "RGB": img = img.convert("RGB")
                         
                         # Check if the pipeline is modern image-text-to-text (e.g. Qwen2-VL)
                         # These models expect chat-style messages with structured prompts
                         if hasattr(self.model, "task") and self.model.task == "image-text-to-text":
                             # Construct chat-style prompt as expected by modern VLMs (Qwen2-VL, etc.)
                             # The prompt requests structured JSON output for easier parsing
                             messages = [
                                 {
                                     "role": "user", 
                                     "content": [
                                         {"type": "image", "image": img},
                                         {"type": "text", "text": "Analyze the image and return a JSON object with keys: 'description' (detailed caption), 'category' (single broad category), and 'keywords' (list of 5-10 tags). Return ONLY the raw JSON string."}
                                     ]
                                 }
                             ]
                             try:
                                 # For image-text-to-text pipelines, pass the formatted messages
                                 # Note: The pipeline will handle the image extraction from the messages
                                 result = self.model(text=messages, generate_kwargs={"max_new_tokens": 512})
                             except Exception as e:
                                 self.logger.error(f"VLM inference failed: {e}")
                                 raise
                         else:
                             # Standard image-to-text models (BLIP, GIT, etc.)
                             # These models accept a simple prompt string
                             try:
                                 # Provide a default prompt and limit length
                                 result = self.model(img, prompt="Describe the image.", generate_kwargs={"max_new_tokens": 512})
                             except Exception as e:
                                 # Some models don't accept prompts, fall back to simple call
                                 self.logger.debug(f"Prompted inference failed ({e}), falling back to simple call.")
                                 result = self.model(img)
                                 
                elif engine.task == config.MODEL_TASK_ZERO_SHOT:
                    # Zero-Shot Image Classification
                    # Classifies image into one of the provided candidate labels
                    # without requiring training on those specific categories
                    with Image.open(path) as img:
                         if img.mode != "RGB": img = img.convert("RGB")
                         result = self.model(img, candidate_labels=config.DEFAULT_CANDIDATE_LABELS)
                         
                else:
                    # Standard Image Classification
                    # Uses pre-trained categories from the model's training
                    with Image.open(path) as img:
                         if img.mode != "RGB": img = img.convert("RGB")
                         result = self.model(img)

            elif engine.provider == "groq_package":
                # ---------------------------------------------------------------
                # GROQ SDK INFERENCE (Cloud-based via Groq Python SDK)
                # ---------------------------------------------------------------
                # Uses the Groq Python SDK to send images to Groq's vision models
                # Requires GROQ_API_KEY environment variable or configured in session
                
                if not GROQ_AVAILABLE:
                    raise RuntimeError("Groq SDK not available. Please install it with: pip install groq")
                
                # Set GROQ_API_KEY environment variable from session config if provided
                # This allows the GroqPackageClient to authenticate without a global env var
                import os
                groq_api_key = engine.groq_api_key  # property returns current active key
                if groq_api_key:
                    os.environ["GROQ_API_KEY"] = groq_api_key
                    self.logger.debug(f"Set GROQ_API_KEY from session config")
                
                # Initialize Groq client with current key
                groq_client = GroqPackageClient(api_key=groq_api_key)
                if not groq_client.is_available():
                    self.logger.error(f"Groq SDK unavailable. GROQ_AVAILABLE={GROQ_AVAILABLE}, has_groq_class={groq_client._groq_class is not None}")
                    raise RuntimeError("Groq SDK is not available or not properly configured. Check that 'groq' package is installed.")
                
                # Default model for vision tasks (Groq's vision model)
                model_id = engine.model_id or "meta-llama/llama-4-scout-17b-16e-instruct"
                
                # Create a detailed prompt for image analysis
                prompt = (
                    "Analyze this image and provide a detailed response in JSON format with these keys:\n"
                    "- 'description': A detailed description of the image content\n"
                    "- 'category': A single broad category (e.g., 'Nature', 'Architecture', 'People')\n"
                    "- 'keywords': A list of 5-10 relevant tags/keywords\n\n"
                    "Return ONLY the raw JSON object, no additional text."
                )
                
                # Call Groq API with the image — uses key rotation on quota/rate-limit errors
                num_keys = len(engine.get_groq_key_list())
                if num_keys > 1:
                    self.logger.info(f"Using Groq API key rotation ({num_keys} keys available)")
                    response_text = groq_client.chat_with_image_rotating(
                        engine_config=engine,
                        model=model_id,
                        prompt=prompt,
                        image_path=str(path)
                    )
                else:
                    response_text = groq_client.chat_with_image(
                        model=model_id,
                        prompt=prompt,
                        image_path=str(path)
                    )
                
                # Format result to match expected structure for tag extraction
                result = [{"generated_text": response_text}]

            elif engine.provider == "ollama":
                # ---------------------------------------------------------------
                # OLLAMA INFERENCE (Local or Remote)
                # ---------------------------------------------------------------
                # Uses the official Ollama Python library to connect to an Ollama server.
                # Supports configurable host (e.g. localhost or remote IP).
                
                if not OLLAMA_AVAILABLE:
                    raise RuntimeError("Ollama client not available. Please install 'ollama' package.")
                
                # Initialize Ollama client with configured host and api key
                # If host is empty, it defaults to standard localhost:11434
                ollama_client = OllamaClient(
                    host=engine.ollama_host,
                    api_key=engine.ollama_api_key
                )
                if not ollama_client.is_available():
                    raise RuntimeError(
                        "Ollama client could not be initialized. "
                        "Check that 'ollama' package is installed and server is reachable."
                    )
                
                # Use configured model
                model_id = engine.model_id or "llama3:latest"
                
                # Create a detailed prompt for image analysis
                prompt = (
                    "Analyze this image and provide a detailed response in "
                    "JSON format with these keys:\n"
                    "- 'description': A detailed description of the image content\n"
                    "- 'category': A single broad category "
                    "(e.g., 'Nature', 'Architecture', 'People')\n"
                    "- 'keywords': A list of 5-10 relevant tags/keywords\n\n"
                    "Return ONLY the raw JSON object, no additional text."
                )
                
                # Call Ollama with the image path
                response_text = ollama_client.chat_with_image(
                    model_name=model_id,
                    prompt=prompt,
                    image_path=str(path)
                )
                
                # Format result to match expected structure for tag extraction
                result = [{"generated_text": response_text}]

            elif engine.provider == "nvidia":
                # ---------------------------------------------------------------
                # NVIDIA NIM INFERENCE (Cloud-based via Nvidia Integrate API)
                # ---------------------------------------------------------------
                if not NVIDIA_AVAILABLE:
                    raise RuntimeError("Nvidia client not available.")
                
                # Initialize Nvidia client with configured API key
                nvidia_client = NvidiaClient(api_key=engine.nvidia_api_key)
                if not nvidia_client.is_available():
                    raise RuntimeError("Nvidia API key not configured.")
                
                # Use configured model
                model_id = engine.model_id or "mistralai/mistral-large-3-675b-instruct-2512"
                
                # Create a detailed prompt for image analysis
                # We reuse the same detailed prompt pattern
                prompt = (
                    "Analyze this image and provide a detailed response in "
                    "JSON format with these keys:\n"
                    "- 'description': A detailed description of the image content\n"
                    "- 'category': A single broad category "
                    "(e.g., 'Nature', 'Architecture', 'People')\n"
                    "- 'keywords': A list of 5-10 relevant tags/keywords\n\n"
                    "Return ONLY the raw JSON object, no additional text."
                )
                
                # Call Nvidia NIM with the image path
                response_text = nvidia_client.chat_with_image(
                    model_name=model_id,
                    prompt=prompt,
                    image_path=str(path)
                )
                
                # Format result to match expected structure for tag extraction
                result = [{"generated_text": response_text}]

            elif engine.provider in ["huggingface", "openrouter"]:
                # ---------------------------------------------------------------
                # API INFERENCE (Cloud-based)
                # ---------------------------------------------------------------
                # Send image to API endpoint for processing
                # No local model loading required
                provider_module = huggingface_utils if engine.provider == "huggingface" else openrouter_utils
                
                # Configure inference parameters
                params = {"max_new_tokens": 1024}
                if engine.task == config.MODEL_TASK_ZERO_SHOT:
                    params["candidate_labels"] = config.DEFAULT_CANDIDATE_LABELS
                
                result = provider_module.run_inference_api(
                    model_id=engine.model_id,
                    image_path=str(path),
                    task=engine.task,
                    token=engine.api_key,
                    parameters=params
                )

            # ===============================================================
            # STAGE 3: TAG EXTRACTION
            # ===============================================================
            # Parse the model's output and extract structured metadata
            # The extraction logic handles different output formats:
            # - JSON objects (from VLMs)
            # - Classification results with scores
            # - Plain text descriptions
            
            # Convert threshold from UI scale (1-100) to model scale (0.0-1.0)
            # Tags with confidence scores below this threshold are filtered out
            threshold = engine.confidence_threshold / 100.0
            
            # Extract category, keywords, and description from model result
            # The extract_tags_from_result function handles:
            # - Parsing JSON from VLM responses
            # - Filtering classification results by threshold
            # - Extracting top predictions as keywords
            cat, kws, desc = image_processing.extract_tags_from_result(result, engine.task, threshold=threshold)
            self.logger.debug(f"Extracted tags - Category: {cat}, Keywords: {len(kws)}, Description length: {len(desc) if desc else 0}")
            
            # If extraction returned no useful data, write a placeholder so the item
            # is marked as processed and won't be reprocessed in subsequent runs
            if not cat and not kws and not desc:
                desc = "[AI: No Result]"
                self.logger.info(f"No tags extracted for item, using placeholder: {desc}")
                self.log(f"No results - marking with placeholder")
            
            # ===============================================================
            # STAGE 4: METADATA WRITING
            # ===============================================================
            # Write the extracted tags to the appropriate destination:
            # - Daminion: Update item metadata via API
            # - Local: Write to EXIF/IPTC metadata in image file
            
            if is_daminion:
                # Update Daminion item metadata via API
                # This sends the tags to the Daminion server for storage
                success = daminion_client.update_item_metadata(
                    item_id=item_id,
                    category=cat,
                    keywords=kws,
                    description=desc
                )
                
                # Optional: Verify that the metadata was actually written
                # This is useful for debugging API issues or data corruption
                if success and verifier:
                    self.logger.info(f"Verifying metadata for Daminion item {item_id}...")
                    verified = verifier.verify_metadata_update(
                        client=daminion_client,
                        item_id=item_id,
                        expected_cat=cat,
                        expected_kws=kws,
                        expected_desc=desc
                    )
                    if verified:
                        self.logger.info(f"Metadata verification successful for item {item_id}")
                        self.log(f"Verification: Passed")
                    else:
                        self.logger.warning(f"Metadata verification failed for item {item_id}")
                        self.log(f"Verification: FAILED (Check details in log file)")
                        # We don't fail the whole item if verification fails, 
                        # just log it as a warning for manual review

            else:
                # Write metadata to local image file (EXIF/IPTC)
                # This embeds the tags directly in the image file
                success = image_processing.write_metadata(
                    image_path=path,
                    category=cat,
                    keywords=kws,
                    description=desc
                )
            
            # ===============================================================
            # RESULT TRACKING
            # ===============================================================
            # Log the processing result and add to session results
            status = "Success" if success else "Write Failed"
            tags_str = f"Cat: {cat}, Kws: {len(kws)}, Desc: {desc[:20]}..."
            self.logger.info(f"Item processed successfully - Status: {status}, Tags: {tags_str}")
            self.log(f"Result: {tags_str}")
            
            # Store result for export/review in Step 4
            self.session.results.append({
                "filename": filename if is_daminion else path.name,
                "status": status,
                "tags": tags_str
            })

        except Exception as e:
            # ===============================================================
            # ERROR HANDLING
            # ===============================================================
            # Log detailed error information for debugging
            # The job continues processing remaining items even if one fails
            name = item.get('fileName') if is_daminion else (item.name if isinstance(item, Path) else str(item))
            self.logger.error(f"Failed to process item '{name}': {type(e).__name__}: {str(e)}")
            self.logger.exception("Full traceback:")
            logging.error(f"Failed to process {name}: {e}")
            
            # Update failure statistics
            self.session.failed_items += 1
            self.log(f"Failed: {e}")
            
        finally:
            # ===============================================================
            # CLEANUP
            # ===============================================================
            # Always clean up temporary files, even if processing failed
            # This prevents disk space issues when processing large batches
            if temp_thumb and temp_thumb.exists():
                try:
                    import os
                    os.remove(temp_thumb)
                    self.logger.debug(f"Cleaned up temporary thumbnail: {temp_thumb}")
                except Exception:
                    # Ignore cleanup errors - not critical
                    pass
