# -*- coding: utf-8 -*-
"""
Main entry point for the EZ STT Logger application.
Initializes the necessary components and starts the GUI.
Includes dynamic language scanning.
"""
import os
import sys
import queue
import threading
import time
import logging
import json # Needed for loading reference keys

# --- Local module imports ---
from lib.logger_setup import logger, setup_logging
from lib.constants import (
    CONFIG_FILE, KEY_FILE, LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR,
    DEFAULT_LANGUAGE, DEFAULT_LOG_LEVEL,
    LANG_REFERENCE_CODE # Import reference language code
)
from lib.utils import load_or_generate_key
from lib.config_manager import load_config
from lib.gui import WhisperGUI
# Importiere neue/geänderte Funktionen aus language_manager
from lib.language_manager import (
    set_current_language, load_language, tr,
    scan_languages, # Import scan function
    discovered_languages # Import the global dict to check if empty later
)

# --- Global queues and flags (Behalten für Übergabe an GUI) ---
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

    # Variable initialisieren, um ihren Scope sicherzustellen
    initial_lang_code = None
    final_discovered_langs = {}

    # Ensure required directories exist
    for dir_path in [LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR]:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"Directory '{dir_path}' created or already exists.")
            except OSError as e:
                 print(f"ERROR: Could not create directory '{dir_path}': {e}")

    # Load or generate encryption key
    encryption_key = load_or_generate_key(KEY_FILE, gui_q)
    if not encryption_key:
         print("CRITICAL ERROR: Could not load/generate encryption key.")

    # --- Load Reference Language Keys ---
    reference_keys = set()
    ref_file_path = os.path.join(LANGUAGE_DIR, f"{LANG_REFERENCE_CODE}.json")
    try:
        # FIX: Call load_language with is_reference_load=True
        temp_ref_dict = load_language(LANG_REFERENCE_CODE, is_reference_load=True)
        if temp_ref_dict:
            reference_keys = set(temp_ref_dict.keys())
            # print(f"Successfully loaded reference keys from '{ref_file_path}'.") # Loggt jetzt intern
        else:
             # Logger ist hier noch nicht voll initialisiert, print verwenden
             print(f"ERROR: Reference language file '{ref_file_path}' could not be loaded properly. Cannot validate other languages.")
    except Exception as e:
         print(f"ERROR: Failed to load reference language keys from '{ref_file_path}': {e}. Cannot validate languages.")

    # --- Scan for available and valid languages ---
    # scan_languages loggt jetzt intern
    final_discovered_langs = scan_languages(reference_keys)
    if not final_discovered_langs:
         print(f"ERROR: No valid languages discovered in '{LANGUAGE_DIR}'. Application might not display texts correctly.")

    # --- Load configuration ---
    # load_config loggt jetzt intern
    app_config = load_config(CONFIG_FILE, encryption_key)

    # --- Initialize Logging with Level from Config ---
    initial_log_level_str = app_config.get("log_level", DEFAULT_LOG_LEVEL)
    # setup_logging loggt jetzt intern
    _, console_handler, file_handler = setup_logging(initial_console_level_str=initial_log_level_str)
    handlers['console'] = console_handler
    handlers['file'] = file_handler
    # Logging is now fully configured

    # --- Determine and set initial UI language ---
    config_lang_code = app_config.get("language_ui", DEFAULT_LANGUAGE)
    initial_lang_code = DEFAULT_LANGUAGE # Start with default

    if config_lang_code in final_discovered_langs:
        initial_lang_code = config_lang_code
        logger.info(f"Using language '{initial_lang_code}' from configuration.")
    else:
        logger.warning(f"Configured language '{config_lang_code}' not found or invalid among discovered languages ({list(final_discovered_langs.keys())}).")
        if DEFAULT_LANGUAGE in final_discovered_langs:
             initial_lang_code = DEFAULT_LANGUAGE
             logger.warning(f"Falling back to default language '{initial_lang_code}'.")
        elif final_discovered_langs:
             first_available_code = list(final_discovered_langs.keys())[0]
             initial_lang_code = first_available_code
             logger.warning(f"Default language '{DEFAULT_LANGUAGE}' not available. Falling back to first discovered language '{initial_lang_code}'.")
        else:
             logger.error("No languages available to set. UI might be broken.")
             initial_lang_code = None

    # Load the determined language (or handle None case if needed)
    if initial_lang_code:
        # Call set_current_language normally (uses load_language without the flag)
        set_current_language(initial_lang_code)
        app_config["language_ui"] = initial_lang_code
    else:
        logger.error("No language could be loaded. UI might be broken.")


    # --- Clear log file on start if configured ---
    if app_config.get("clear_log_on_start", False):
        log_file_path = handlers['file'].baseFilename if handlers['file'] else None
        if log_file_path and os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'w') as f: f.truncate(0)
                # Use tr() now that language is loaded (or should be)
                logger.info(tr("log_logfile_cleared", path=log_file_path))
            except IOError as e: logger.error(tr("log_logfile_clear_error", path=log_file_path, error=str(e)))
            except Exception as e: logger.exception(tr("log_logfile_clear_unexpected", path=log_file_path))
        elif log_file_path: logger.warning(tr("log_logfile_not_found", path=log_file_path))
        else: logger.warning(tr("log_logfile_no_handler"))

    # --- Start GUI ---
    try:
        logger.info(tr("log_app_started"))
        # Pass the discovered languages dictionary to the GUI
        app = WhisperGUI(app_config, encryption_key, queues, flags, handlers, available_languages=final_discovered_langs)
        app.mainloop()
        logger.info(tr("log_app_ended"))
    except Exception as e:
         logger.exception(tr("log_gui_exception"))

    # FIX: Moved exit log and call inside main() scope
    if initial_lang_code: # Check if language was ever set
        logger.info(tr("log_app_exiting"))
    else:
        logger.info("Application exiting (no language loaded).") # Fallback message
    sys.exit(0)


# --- Entry point ---
if __name__ == '__main__':
    main()
    # Code execution should not reach here because sys.exit(0) is called in main()

