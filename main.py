# -*- coding: utf-8 -*-
"""
Main entry point for the EZ STT Logger application.
Initializes the necessary components and starts the GUI.
"""
import os
import sys
import queue
import threading
import time
import logging

# --- Local module imports ---
from lib.logger_setup import logger, setup_logging
from lib.constants import (
    CONFIG_FILE, KEY_FILE, LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR,
    DEFAULT_LANGUAGE, DEFAULT_LOG_LEVEL
)
from lib.utils import load_or_generate_key
from lib.config_manager import load_config
from lib.gui import WhisperGUI
from lib.language_manager import set_current_language, load_language, tr

# --- Global queues and flags ---
audio_q = queue.Queue()
gui_q = queue.Queue()
streamerbot_queue = queue.Queue()
stop_recording_flag = threading.Event()
streamerbot_client_stop_event = threading.Event()

queues = { 'audio_q': audio_q, 'gui_q': gui_q, 'streamerbot_q': streamerbot_queue }
flags = { 'stop_recording': stop_recording_flag, 'stop_streamerbot': streamerbot_client_stop_event }
handlers = { 'console': None, 'file': None }

# --- Main function ---
def main():
    """Initializes the application and starts the main loop."""
    global handlers

    # Ensure required directories exist
    for dir_path in [LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR]:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(tr("log_created_directory", path=dir_path))
            except OSError as e:
                print(tr("log_failed_directory", path=dir_path, error=str(e)))

    # Load or generate encryption key
    encryption_key = load_or_generate_key(KEY_FILE, gui_q)
    if not encryption_key:
        print(tr("log_key_missing"))

    # Load configuration
    app_config = load_config(CONFIG_FILE, encryption_key)

    # Initialize logging using config
    initial_log_level_str = app_config.get("log_level", DEFAULT_LOG_LEVEL)
    _, console_handler, file_handler = setup_logging(initial_console_level_str=initial_log_level_str)
    handlers['console'] = console_handler
    handlers['file'] = file_handler

    # Set UI language
    initial_lang_code = app_config.get("language_ui", DEFAULT_LANGUAGE)
    set_current_language(initial_lang_code)

    # Clear log file on start if configured
    if app_config.get("clear_log_on_start", False):
        log_file_path = handlers['file'].baseFilename if handlers['file'] else None
        if log_file_path and os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'w') as f:
                    f.truncate(0)
                logger.info(tr("log_logfile_cleared", path=log_file_path))
            except IOError as e:
                logger.error(tr("log_logfile_clear_error", path=log_file_path, error=str(e)))
            except Exception as e:
                logger.exception(tr("log_logfile_clear_unexpected", path=log_file_path))
        elif log_file_path:
            logger.warning(tr("log_logfile_not_found", path=log_file_path))
        else:
            logger.warning(tr("log_logfile_no_handler"))

    # Start GUI
    try:
        logger.info(tr("log_app_started"))
        app = WhisperGUI(app_config, encryption_key, queues, flags, handlers)
        app.mainloop()
        logger.info(tr("log_app_ended"))
    except Exception as e:
        logger.exception(tr("log_gui_exception"))

# --- Entry point ---
if __name__ == '__main__':
    main()
    logger.info(tr("log_app_exiting"))
    sys.exit(0)
