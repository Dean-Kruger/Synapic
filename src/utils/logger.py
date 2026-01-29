"""
Centralized Logging and Security Filtering
==========================================

This module provides a robust logging infrastructure for the Synapic 
application, with a heavy emphasis on security and thread-safety. It 
centralizes all diagnostic output while ensuring that PII (Personally 
Identifiable Information) and credentials never reach the log files.

Key Features:
-------------
- Sensitive Data Masking: Automatic redaction of API keys, passwords, and 
  tokens using regex and recursive dictionary filtering.
- Thread-Safe Redirection: Captures stdout/stderr via a background queue 
  to prevent UI freezes and log interleaving.
- API Instrumentation: Decorators and helpers for logging REST requests/responses 
  with automatic timing and status tracking.
- Contextual Logging: Specialized formatting including timestamps, module 
  origin, and line numbers.

Dependencies:
-------------
- logging: Standard library for output routing.
- re: Used for pattern-based masking of sensitive strings.
- threading: Orchestrates background flush operations for captured streams.

Author: Synapic Project
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
import queue
import threading


# Log directory configuration
# Get the project root directory (3 levels up from this file: utils -> src -> project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
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
    """
    Filtering hook to intercept and redact sensitive information.
    
    This filter is attached to both file and console handlers. It scans
    log records for patterns matching credentials (API keys, Bearer tokens,
    passwords) and replaces them with masks (e.g., '***' or '***4a1b') 
    before the data is persisted or displayed.
    """
    
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
    Recursively redact sensitive fields from complex data structures.
    
    This function traverses dictionaries and lists, identifying keys that 
    correspond to known credential labels (e.g., 'password', 'api_key'). 
    It also performs string-level regex matching for discovered URIs or 
    standalone keys.
    
    Args:
        data: The input data structure (dict, list, str, etc.) to be scrubbed.
        mask_value: The string used to replace sensitive content.
        
    Returns:
        A copy of the input data with sensitive values masked.
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


class StreamToLogger:
    """
    Proxy object to redirect standard system streams to the logging engine.
    
    It intercepts `sys.stdout` and `sys.stderr` and routes them through 
    a non-blocking background queue. This prevents the application from 
    deadlocking during heavy terminal output and ensures logs are 
    serialized correctly across multiple threads.
    """
    def __init__(self, logger: logging.Logger, log_level: int, original_stream):
        self.logger = logger
        self.log_level = log_level
        self.original_stream = original_stream
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.running = True
        
        # Start background thread for processing log messages
        self.thread = threading.Thread(target=self._process_queue, daemon=True)
        self.thread.start()

    def write(self, buf):
        """Write to console and queue for logging."""
        # Thread-safe write to original stream (console)
        with self.lock:
            if self.original_stream:
                try:
                    self.original_stream.write(buf)
                    self.original_stream.flush()
                except Exception:
                    pass  # Ignore console write errors
        
        # Queue for background logging (non-blocking)
        if buf.strip():  # Only queue non-empty messages
            self.queue.put(buf)

    def flush(self):
        """Flush the original stream."""
        with self.lock:
            if self.original_stream:
                try:
                    self.original_stream.flush()
                except Exception:
                    pass
    
    def _process_queue(self):
        """Background thread that processes queued log messages."""
        while self.running:
            try:
                # Wait for messages with a short timeout to check self.running frequently
                buf = self.queue.get(timeout=0.05)
                
                # Log each line separately
                for line in buf.rstrip().splitlines():
                    if line.strip():
                        self.logger.log(self.log_level, line.rstrip())
                
                # Mark as done to allow join() to work correctly if used with task_done()
                self.queue.task_done()
                        
            except queue.Empty:
                continue
            except Exception:
                # Avoid logging to the same system if it's failing
                pass
    
    def shutdown(self):
        """Stop the background thread and flush remaining messages."""
        if not self.running:
            return
            
        self.running = False
        
        # Process any remaining messages in the queue (graceful flush)
        try:
            while not self.queue.empty():
                try:
                    buf = self.queue.get_nowait()
                    for line in buf.rstrip().splitlines():
                        if line.strip():
                            self.logger.log(self.log_level, line.rstrip())
                    self.queue.task_done()
                except (queue.Empty, ValueError):
                    break
        except Exception:
            pass
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            try:
                self.thread.join(timeout=0.5)
            except Exception:
                pass


def setup_logging(
    log_level: int = logging.DEBUG,
    console_level: int = logging.INFO,
    log_format: Optional[str] = None
) -> Path:
    """
    Initialize the application-wide logging singleton.
    
    Configs include:
    - Root Logger: Set to DEBUG to capture all system events.
    - File Handler: Persists detailed DEBUG logs to 'logs/synapic.log'.
    - Console Handler: Displays human-readable INFO logs to terminal.
    - System Redirection: Hooks sys.stdout/stderr into the log stream.
    
    Args:
        log_level: Granularity for the persistent log file.
        console_level: Granularity for the terminal output.
        log_format: Optional custom formatting string.
        
    Returns:
        Path: The absolute path to the generated log file.
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
    
    # Redirect stdout and stderr to also write to log file
    global _stdout_logger, _stderr_logger
    _stdout_logger = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO, sys.stdout)
    _stderr_logger = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR, sys.stderr)
    sys.stdout = _stdout_logger
    sys.stderr = _stderr_logger
    
    # Log the initialization
    logging.info("=" * 80)
    logging.info(f"Synapic Application Started - Log file: {log_file}")
    logging.info("=" * 80)
    
    return log_file


# Global references to logger instances for cleanup
_stdout_logger: Optional[StreamToLogger] = None
_stderr_logger: Optional[StreamToLogger] = None


def shutdown_logging():
    """
    Shutdown the logging system and cleanup background threads.
    Should be called before application exit.
    """
    global _stdout_logger, _stderr_logger
    
    logging.info("Shutting down logging system...")
    
    # Shutdown stream loggers
    if _stdout_logger:
        _stdout_logger.shutdown()
    if _stderr_logger:
        _stderr_logger.shutdown()
    
    # Flush all handlers
    for handler in logging.root.handlers:
        handler.flush()
    
    logging.info("Logging system shutdown complete")






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
    Decorator for automated instrumentation of REST/API methods.
    
    Wraps a function to automatically log:
    1. The entry point and sanitized arguments.
    2. The execution status (Success/Failure) upon completion.
    3. Total turnaround time (latency) in seconds.
    4. Full stack traces for any unhandled exceptions.
    
    Args:
        func: The API function to be instrumented.
        api_name: Context label for the log entry (e.g., 'Daminion').
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
