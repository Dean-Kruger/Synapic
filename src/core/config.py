"""
Application Configuration and Constants
=======================================

This module contains all global configuration values, constants, and defaults used
throughout the Synapic application. It serves as a single source of truth for:

- Model task types and their display names
- File format specifications
- Network and retry parameters
- Image processing thresholds
- UI configuration defaults

Key Components:
- Model Tasks: Defines supported AI model task types (classification, captioning, zero-shot)
- Capability Mapping: Maps task types to human-readable capability descriptions
- Processing Limits: Sets boundaries for image size, keyword count, and confidence thresholds
- Stop Words: Common English words excluded from keyword extraction
- Cache Paths: Hugging Face model cache directory configuration

Dependencies:
- huggingface_hub.constants: For standard HF cache location (with fallback)

Note:
    All constants use UPPER_SNAKE_CASE naming convention. Modify these values to
    change application-wide behavior without touching business logic.

Author: Dean
"""

# ============================================================================
# HUGGING FACE CACHE CONFIGURATION
# ============================================================================
# Determine the Hugging Face cache directory. Try to use the official location
# from huggingface_hub library if available, otherwise fall back to a manual path.
# This ensures compatibility even when running in minimal environments (e.g., CI).

try:
    from huggingface_hub import constants
    HF_CACHE_DIR = constants.HUGGINGFACE_HUB_CACHE
except Exception:
    # Fallback when huggingface_hub isn't available (editor/CI environments)
    import os
    HF_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
# Basic application window configuration. Note: GEOMETRY is currently unused
# as the main app uses customtkinter's default sizing.

APP_NAME = "Advanced Image Tagger"
GEOMETRY = "800x600"  # Legacy: kept for backward compatibility

# ============================================================================
# MODEL DISCOVERY AND SEARCH
# ============================================================================
# Configuration for Hugging Face Hub model search and discovery.

# Limit the number of models shown in search results to keep the UI responsive
# and avoid overwhelming users with too many options.
MODEL_SEARCH_LIMIT = 20

# ============================================================================
# ZERO-SHOT CLASSIFICATION DEFAULTS
# ============================================================================
# Default category labels used when running zero-shot image classification.
# Users can override these in the UI, but these serve as sensible starting values.

DEFAULT_CANDIDATE_LABELS = ["photography", "art", "nature", "portrait", "landscape", "urban", "people", "animal"]

# ============================================================================
# MODEL TASK TYPES AND DISPLAY NAMES
# ============================================================================
# Defines the supported AI model task types and their human-readable names.
# These constants are used throughout the application for model selection and UI display.

# Standard Hugging Face task identifiers
MODEL_TASK_IMAGE_CLASSIFICATION = "image-classification"  # Automatically generates keywords
MODEL_TASK_ZERO_SHOT = "zero-shot-image-classification"   # User-defined category matching
MODEL_TASK_IMAGE_TO_TEXT = "image-to-text"                # Generates descriptive captions

# Maps technical task names to user-friendly display names (used in UI)
TASK_DISPLAY_MAP = {
    MODEL_TASK_IMAGE_CLASSIFICATION: "Keywords (Auto)",
    MODEL_TASK_ZERO_SHOT: "Categories (Custom)",
    MODEL_TASK_IMAGE_TO_TEXT: "Description"
}

# Maps task types to their primary capability (used in model search results)
CAPABILITY_MAP = {
    MODEL_TASK_IMAGE_CLASSIFICATION: "Keywording",
    MODEL_TASK_ZERO_SHOT: "Categorisation",
    MODEL_TASK_IMAGE_TO_TEXT: "Description",
    "image-text-to-text": "Multi-modal",          # Vision-language models (e.g., Qwen, LLaVA)
    "visual-question-answering": "Multi-modal"    # VQA models
}

# Reverse mapping: display name -> task type (for UI selection conversion)
DISPLAY_TASK_MAP = {v: k for k, v in TASK_DISPLAY_MAP.items()}

# ============================================================================
# IMAGE PROCESSING CONFIGURATION
# ============================================================================
# Settings that control image analysis, filtering, and keyword extraction.

# File formats accepted for processing (glob patterns)
SUPPORTED_IMAGE_EXTENSIONS = ("*.jpg", "*.jpeg", "*.png")

# Minimum confidence score for zero-shot classifications to be included in results
# Higher values (0.9) ensure only very confident predictions are used
ZERO_SHOT_CONFIDENCE_THRESHOLD = 0.9

# Maximum file size for images (safety limit to prevent memory issues)
MAX_IMAGE_SIZE_MB = 50

# Cap the number of keywords generated per image to avoid tag spam
MAX_KEYWORDS_PER_IMAGE = 20

# ============================================================================
# NETWORK AND RETRY CONFIGURATION
# ============================================================================
# Settings for API requests, network timeouts, and retry logic.

# Number of times to retry failed network requests before giving up
MAX_RETRIES = 3

# Base delay between retry attempts (may be increased exponentially)
RETRY_DELAY_SECONDS = 1.0

# Maximum time to wait for network responses before timing out
NETWORK_TIMEOUT_SECONDS = 30

# ============================================================================
# MODEL DOWNLOAD CONFIGURATION
# ============================================================================
# Settings for Hugging Face model downloads and cache management.

# Files to skip when downloading models (non-essential for inference)
MODEL_FILE_EXCLUSIONS = (".gitattributes", "README.md")

# Model name patterns that indicate incompatible quantization formats
# These models require special libraries (auto-gptq, autoawq, llama-cpp) and
# cannot be loaded with standard transformers pipelines
INCOMPATIBLE_MODEL_PATTERNS = [
    "-gptq",      # GPTQ quantized models (require auto-gptq)
    "-awq",       # AWQ quantized models (require autoawq)
    "-gguf",      # GGUF format models (require llama-cpp-python)
    "-ggml",      # GGML format models (legacy llama.cpp format)
    "-exl2",      # EXL2 quantized models (require exllamav2)
    "-bnb",       # BitsAndBytes quantized models
    "-4bit",      # Generic 4-bit quantized
    "-8bit",      # Generic 8-bit quantized
    "int4",       # Integer 4-bit quantization
    "int8",       # Integer 8-bit quantization
]

# String used to identify cache directories (for validation)
CACHE_DIRECTORY_IDENTIFIER = ".cache"

# ============================================================================
# KEYWORD EXTRACTION STOP WORDS
# ============================================================================
# Common English words that should be filtered out from AI-generated keywords.
# These are articles, pronouns, prepositions, and other high-frequency words
# that don't contribute meaningful metadata value.

STOP_WORDS = [
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's",
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm",
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most",
    "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
    "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who",
    "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're",
    "you've", "your", "yours", "yourself", "yourselves"
]
