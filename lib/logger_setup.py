# -*- coding: utf-8 -*-
"""
Configures the logging system for the application.
"""
import logging
import sys
import os
from datetime import datetime

# Import constants
try:
    from lib.constants import LOG_DIR, LOG_LEVELS, DEFAULT_LOG_LEVEL
    from lib.language_manager import tr
except ImportError:
    print("Fallback for constants in logger_setup.py")
    LOG_DIR = "logs"
    DEFAULT_LOG_LEVEL = "INFO"
    LOG_LEVELS = { "INFO": logging.INFO, "DEBUG": logging.DEBUG }

    def tr(key, **kwargs):
        return key.format(**kwargs) if kwargs else key


# Global logger - configured by setup_logging
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

    log_formatter = logging.Formatter('%(asctime)s [%(levelname)-5.5s] %(threadName)s: %(message)s')

    # Ensure log directory exists
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR)
            log_dir_path = LOG_DIR
        except OSError as e:
            print(tr("log_failed_directory", path=LOG_DIR, error=str(e)))
            log_dir_path = "."
    else:
        log_dir_path = LOG_DIR

    log_filename = os.path.join(log_dir_path, f"ez_stt_logger_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

    # File handler (always logs everything at DEBUG level)
    try:
        for h in logger.handlers[:]:
            if isinstance(h, logging.FileHandler) and h.baseFilename == log_filename:
                logger.removeHandler(h)
                h.close()
                print("Removed previous file handler.")
                break
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG)
    except IOError as e:
        print(tr("log_logfile_open_error", path=log_filename, error=str(e)))
        file_handler = None

    # Console handler
    console_level = LOG_LEVELS.get(initial_console_level_str.upper(), logging.INFO)
    try:
        for h in logger.handlers[:]:
            if isinstance(h, logging.StreamHandler):
                logger.removeHandler(h)
                h.close()
                print("Removed previous console handler.")
                break
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(console_level)
    except Exception as e:
        print(tr("log_console_handler_error", error=str(e)))
        console_handler = None

    # Configure logger
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    if file_handler:
        logger.addHandler(file_handler)
    if console_handler:
        logger.addHandler(console_handler)

    # Initial log messages
    logger.info("=" * 20 + " Logging started " + "=" * 20)
    logger.info(tr("log_logfile_created", path=log_filename))
    logger.info(tr("log_console_level_initialized", level=logging.getLevelName(console_level)))
    if not file_handler:
        logger.warning(tr("log_file_logging_disabled"))

    return logger, console_handler, file_handler
