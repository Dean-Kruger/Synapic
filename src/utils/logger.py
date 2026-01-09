"""
Centralized logging configuration and utilities for the Synapic application.

Provides:
- Automatic log file creation with timestamps
- Sensitive data masking (API keys, passwords, tokens)
- Structured logging for configuration and API calls
- Both file and console logging handlers
"""

import logging
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from functools import wraps
import time
import json


# Log directory configuration
LOG_DIR = Path.home() / ".synapic" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Sensitive field patterns to mask
SENSITIVE_FIELDS = {
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 
    'apikey', 'auth', 'authorization', 'credentials', 'daminion_pass'
}

# Regex patterns for sensitive data in strings
SENSITIVE_PATTERNS = [
    (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), '***'),  # API keys starting with sk-
    (re.compile(r'(Bearer\s+[a-zA-Z0-9\-._~+/]+=*)'), 'Bearer ***'),  # Bearer tokens
    (re.compile(r'([a-zA-Z0-9]{32,})'), lambda m: f"***{m.group(1)[-4:]}"),  # Long alphanumeric (likely keys)
]


class SensitiveDataFilter(logging.Filter):
    """Filter that masks sensitive data in log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in the log message."""
        if isinstance(record.msg, str):
            record.msg = self._mask_string(record.msg)
        
        # Also mask in args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_sensitive_data(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive_data(arg) if isinstance(arg, (dict, str)) else arg 
                    for arg in record.args
                )
        
        return True
    
    def _mask_string(self, text: str) -> str:
        """Apply regex patterns to mask sensitive data in strings."""
        for pattern, replacement in SENSITIVE_PATTERNS:
            if callable(replacement):
                text = pattern.sub(replacement, text)
            else:
                text = pattern.sub(replacement, text)
        return text


def mask_sensitive_data(data: Any, mask_value: str = "***") -> Any:
    """
    Recursively mask sensitive data in dictionaries, lists, and strings.
    
    Args:
        data: Data to mask (dict, list, str, or other)
        mask_value: Value to use for masking
        
    Returns:
        Masked copy of the data
    """
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            
            # Check if this is a sensitive field
            if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
                # For API keys, show last 4 characters
                if 'key' in key_lower or 'token' in key_lower:
                    if isinstance(value, str) and len(value) > 4:
                        masked[key] = f"{mask_value}{value[-4:]}"
                    else:
                        masked[key] = mask_value
                else:
                    # For passwords, completely mask
                    masked[key] = mask_value
            else:
                # Recursively mask nested structures
                masked[key] = mask_sensitive_data(value, mask_value)
        return masked
    
    elif isinstance(data, (list, tuple)):
        masked_list = [mask_sensitive_data(item, mask_value) for item in data]
        return type(data)(masked_list)
    
    elif isinstance(data, str):
        # Apply regex patterns to strings
        result = data
        for pattern, replacement in SENSITIVE_PATTERNS:
            if callable(replacement):
                result = pattern.sub(replacement, result)
            else:
                result = pattern.sub(replacement, result)
        return result
    
    else:
        return data


def setup_logging(
    log_level: int = logging.DEBUG,
    console_level: int = logging.INFO,
    log_format: Optional[str] = None
) -> Path:
    """
    Initialize the logging system with file and console handlers.
    
    Args:
        log_level: Logging level for file handler (default: DEBUG)
        console_level: Logging level for console handler (default: INFO)
        log_format: Custom log format string (optional)
        
    Returns:
        Path to the log file
    """
    # Use a single log file that overwrites on each run
    log_file = LOG_DIR / "synapic.log"
    
    # Remove previous log file if it exists
    if log_file.exists():
        try:
            log_file.unlink()
        except Exception:
            pass  # If we can't delete it, we'll overwrite it anyway
    
    # Default format if not provided
    if log_format is None:
        log_format = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(filename)s:%(lineno)d] - %(message)s'
        )
    
    # Create formatter
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, handlers will filter
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # File handler - captures DEBUG and above
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(file_handler)
    
    # Console handler - captures INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)
    
    # Log the initialization
    logging.info("=" * 80)
    logging.info(f"Synapic Application Started - Log file: {log_file}")
    logging.info("=" * 80)
    
    return log_file


def log_config(config_name: str, config_data: Dict[str, Any], logger: Optional[logging.Logger] = None):
    """
    Log configuration settings with automatic sensitive data masking.
    
    Args:
        config_name: Name of the configuration being logged
        config_data: Dictionary of configuration settings
        logger: Optional logger instance (uses root logger if not provided)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    masked_config = mask_sensitive_data(config_data)
    
    logger.info(f"Configuration: {config_name}")
    logger.debug(f"{config_name} details: {json.dumps(masked_config, indent=2, default=str)}")


def log_api_call(func: Optional[Callable] = None, *, api_name: str = "API"):
    """
    Decorator to log API calls with request/response details and timing.
    
    Can be used with or without parameters:
        @log_api_call
        def my_function(): ...
        
        @log_api_call(api_name="Daminion")
        def my_function(): ...
    
    Args:
        func: Function to decorate (when used without parameters)
        api_name: Name of the API for logging context
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(f.__module__)
            
            # Extract relevant info for logging
            func_name = f.__name__
            
            # Mask sensitive data in kwargs
            masked_kwargs = mask_sensitive_data(kwargs)
            
            # Log the API call start
            logger.info(f"{api_name} call: {func_name}")
            logger.debug(f"{api_name} {func_name} - kwargs: {masked_kwargs}")
            
            start_time = time.time()
            error_occurred = False
            
            try:
                result = f(*args, **kwargs)
                return result
            
            except Exception as e:
                error_occurred = True
                logger.error(
                    f"{api_name} {func_name} failed: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                raise
            
            finally:
                elapsed = time.time() - start_time
                status = "FAILED" if error_occurred else "SUCCESS"
                logger.info(
                    f"{api_name} {func_name} completed - Status: {status}, "
                    f"Duration: {elapsed:.3f}s"
                )
        
        return wrapper
    
    # Handle both @log_api_call and @log_api_call(api_name="...")
    if func is None:
        return decorator
    else:
        return decorator(func)


def log_api_request(
    logger: logging.Logger,
    method: str,
    endpoint: str,
    headers: Optional[Dict] = None,
    data: Optional[Any] = None,
    params: Optional[Dict] = None
):
    """
    Log an outgoing API request with masked sensitive data.
    
    Args:
        logger: Logger instance to use
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint URL
        headers: Request headers
        data: Request body data
        params: Query parameters
    """
    logger.info(f"API Request: {method} {endpoint}")
    
    if headers:
        masked_headers = mask_sensitive_data(headers)
        logger.debug(f"Request headers: {masked_headers}")
    
    if params:
        masked_params = mask_sensitive_data(params)
        logger.debug(f"Request params: {masked_params}")
    
    if data:
        masked_data = mask_sensitive_data(data)
        logger.debug(f"Request body: {json.dumps(masked_data, indent=2, default=str)}")


def log_api_response(
    logger: logging.Logger,
    status_code: int,
    response_data: Optional[Any] = None,
    elapsed_time: Optional[float] = None
):
    """
    Log an API response with timing information.
    
    Args:
        logger: Logger instance to use
        status_code: HTTP status code
        response_data: Response body data
        elapsed_time: Request duration in seconds
    """
    timing_info = f" ({elapsed_time:.3f}s)" if elapsed_time else ""
    logger.info(f"API Response: {status_code}{timing_info}")
    
    if response_data:
        # Mask any sensitive data that might be in the response
        masked_response = mask_sensitive_data(response_data)
        
        # Truncate large responses for readability
        response_str = json.dumps(masked_response, indent=2, default=str)
        if len(response_str) > 1000:
            response_str = response_str[:1000] + "\n... (truncated)"
        
        logger.debug(f"Response body: {response_str}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
