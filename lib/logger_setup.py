# -*- coding: utf-8 -*-
"""
Configures the logging system for the application.
"""
import logging
import sys
import os
from datetime import datetime

# Define a simple local fallback function for tr, used ONLY if imports fail below
def local_fallback_tr(key, **kwargs):
    """Basic fallback for translation if full system isn't ready."""
    text = key.replace('log_', '').replace('_', ' ').capitalize()
    if kwargs:
        try: text = text.format(**kwargs) # Basic format attempt
        except KeyError: pass # Ignore missing keys in fallback
    return text + " (fallback)" # Indicate it's a fallback message

# Try importing constants first
try:
    from lib.constants import LOG_DIR, LOG_LEVELS, DEFAULT_LOG_LEVEL
except ImportError:
    # This block executes if constants cannot be imported
    # Use the local fallback tr for the print message
    print(local_fallback_tr("log_import_error_constants")) # Use a generic key name
    # Define fallback constants
    LOG_DIR = "logs"
    DEFAULT_LOG_LEVEL = "INFO"
    LOG_LEVELS = { "INFO": logging.INFO, "DEBUG": logging.DEBUG }

# Global logger - configured by setup_logging
# Use the standard logger name defined in the original code
logger = logging.getLogger("EZ_STT_Logger")

def setup_logging(initial_console_level_str=DEFAULT_LOG_LEVEL):
    """
    Configures the logging system and returns logger and handlers.

    Args:
        initial_console_level_str (str): Initial log level for the console ("INFO", "DEBUG", ...)

    Returns:
        tuple: (logger, console_handler, file_handler)
    """
    console_handler = None
    file_handler = None

    # Standard log format
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)-5.5s] %(threadName)s: %(message)s')

    # Ensure log directory exists (using LOG_DIR constant)
    # No changes needed here unless path logic itself was wrong
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR)
            log_dir_path = LOG_DIR
        except OSError as e:
            # Use the local fallback tr for this early print statement
            print(local_fallback_tr("log_failed_directory", path=LOG_DIR, error=str(e)))
            log_dir_path = "." # Fallback to current dir if creation fails
    else:
        log_dir_path = LOG_DIR

    # Construct log filename
    log_filename = os.path.join(log_dir_path, f"ez_stt_logger_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

    # File handler (always logs everything at DEBUG level)
    # No changes needed here
    try:
        # Code to remove previous handlers (if any) - kept from original
        for h in logger.handlers[:]:
             if isinstance(h, logging.FileHandler) and h.baseFilename == log_filename:
                 logger.removeHandler(h)
                 h.close()
                 print("Removed previous file handler.") # Simple info message
                 break
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG) # Log everything to the file
    except IOError as e:
        # Use the local fallback tr for this early print statement
        print(local_fallback_tr("log_logfile_open_error", path=log_filename, error=str(e)))
        file_handler = None

    # Console handler
    # No changes needed here
    console_level = LOG_LEVELS.get(initial_console_level_str.upper(), logging.INFO)
    try:
        # Code to remove previous handlers (if any) - kept from original
        for h in logger.handlers[:]:
            if isinstance(h, logging.StreamHandler):
                logger.removeHandler(h)
                h.close()
                print("Removed previous console handler.") # Simple info message
                break
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(console_level) # Set level based on config/default
    except Exception as e:
        # Use the local fallback tr for this early print statement
        print(local_fallback_tr("log_console_handler_error", error=str(e)))
        console_handler = None

    # Configure logger instance
    # No changes needed here
    logger.setLevel(logging.DEBUG) # Logger itself handles all levels >= DEBUG
    logger.handlers.clear() # Clear existing handlers before adding new ones
    if file_handler:
        logger.addHandler(file_handler)
    if console_handler:
        logger.addHandler(console_handler)

    # Initial log messages using the configured logger
    # These will use the *global* tr function, which should be properly
    # initialized by main.py *after* setup_logging is called.
    # If the global tr isn't ready yet, the keys themselves will be logged.
    logger.info("=" * 20 + " Logging started " + "=" * 20)
    # These rely on the global tr being set up by main.py AFTER this function runs
    # It's assumed main.py will import and set up the main 'tr' from language_manager correctly
    from lib.language_manager import tr as global_tr # Try to import the global tr here for clarity
    logger.info(global_tr("log_logfile_created", path=log_filename))
    logger.info(global_tr("log_console_level_initialized", level=logging.getLevelName(console_level)))
    if not file_handler:
        logger.warning(global_tr("log_file_logging_disabled"))

    return logger, console_handler, file_handler
