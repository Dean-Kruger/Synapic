"""
Application configuration and constants.
"""

try:
    from huggingface_hub import constants
    HF_CACHE_DIR = constants.HUGGINGFACE_HUB_CACHE
except Exception:
    # Fallback when huggingface_hub isn't available (editor/CI environments)
    import os
    HF_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")

# --- Application ---
APP_NAME = "Advanced Image Tagger"
GEOMETRY = "800x600"

# --- Hugging Face ---
# The default cache directory for Hugging Face models.
# HF_CACHE_DIR is set above when importing constants or to a sensible
# fallback path if that import fails.

# --- Model Search ---
# Limit the number of models returned in search results to avoid UI overload.
MODEL_SEARCH_LIMIT = 20

# --- Zero Shot Defaults ---
DEFAULT_CANDIDATE_LABELS = ["photography", "art", "nature", "portrait", "landscape", "urban", "people", "animal"]

# --- Model Tasks ---
MODEL_TASK_IMAGE_CLASSIFICATION = "image-classification"
MODEL_TASK_ZERO_SHOT = "zero-shot-image-classification"
MODEL_TASK_IMAGE_TO_TEXT = "image-to-text"

# Task Display Names
TASK_DISPLAY_MAP = {
    MODEL_TASK_IMAGE_CLASSIFICATION: "Keywords (Auto)",
    MODEL_TASK_ZERO_SHOT: "Categories (Custom)",
    MODEL_TASK_IMAGE_TO_TEXT: "Description"
}

CAPABILITY_MAP = {
    MODEL_TASK_IMAGE_CLASSIFICATION: "Keywording",
    MODEL_TASK_ZERO_SHOT: "Categorisation",
    MODEL_TASK_IMAGE_TO_TEXT: "Description",
    "image-text-to-text": "Multi-modal",
    "visual-question-answering": "Multi-modal"
}

DISPLAY_TASK_MAP = {v: k for k, v in TASK_DISPLAY_MAP.items()}

# --- Image Processing ---
SUPPORTED_IMAGE_EXTENSIONS = ("*.jpg", "*.jpeg", "*.png")
ZERO_SHOT_CONFIDENCE_THRESHOLD = 0.9
MAX_IMAGE_SIZE_MB = 50
MAX_KEYWORDS_PER_IMAGE = 20

# --- Network & Retry ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
NETWORK_TIMEOUT_SECONDS = 30

# --- File Exclusions ---
MODEL_FILE_EXCLUSIONS = (".gitattributes", "README.md")

# --- Cache Validation ---
CACHE_DIRECTORY_IDENTIFIER = ".cache"

# --- Stop Words for Keyword Extraction ---
# A list of common English words to exclude from generated keywords.
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
