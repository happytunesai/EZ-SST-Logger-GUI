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
import shutil # For file copying operations

# --- First, get base path to resolve other modules and paths ---
def get_initial_base_path():
    """Initial path resolution before utils module can be imported"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    else:
        try:
            return os.path.abspath(os.path.dirname(__file__))
        except:
            return os.path.abspath(os.getcwd())

# --- Local module imports ---
try:
    sys.path.insert(0, get_initial_base_path())  # Ensure our modules are found first
    from lib.logger_setup import logger, setup_logging
    from lib.constants import (
        CONFIG_FILE, KEY_FILE, LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR,
        DEFAULT_LANGUAGE, DEFAULT_LOG_LEVEL,
        LANG_REFERENCE_CODE # Import reference language code
    )
    from lib.utils import load_or_generate_key, get_base_path
    from lib.config_manager import load_config
    from lib.gui import WhisperGUI
    # Import new/changed functions from language_manager
    from lib.language_manager import (
        set_current_language, load_language, tr,
        scan_languages, # Import scan function
        discovered_languages # Import the global dict to check if empty later
    )
except ImportError as e:
    print(f"Critical import error in main.py: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

# --- Global queues and flags (retained for passing to GUI) ---
audio_q = queue.Queue()
gui_q = queue.Queue()
streamerbot_queue = queue.Queue()
stop_recording_flag = threading.Event()
streamerbot_client_stop_event = threading.Event()

queues = { 'audio_q': audio_q, 'gui_q': gui_q, 'streamerbot_q': streamerbot_queue }
flags = { 'stop_recording': stop_recording_flag, 'stop_streamerbot': streamerbot_client_stop_event }
handlers = { 'console': None, 'file': None }

def extract_bundled_language_files():
    """
    Extract language files from the PyInstaller bundle to the language directory.
    This ensures language files are available when running as an executable.
    """
    # Only needed when running as a PyInstaller bundle
    if not getattr(sys, 'frozen', False):
        return
        
    print("Running as PyInstaller bundle - extracting language files...")
    base_path = get_base_path()
    bundle_lang_dir = os.path.join(base_path, 'language')
    
    # External language directory where we want to store the files for the user
    # When running as exe, we want language dir next to the executable
    exe_dir = os.path.dirname(sys.executable)
    external_lang_dir = os.path.join(exe_dir, LANGUAGE_DIR)
    
    # Create language dir if it doesn't exist
    os.makedirs(external_lang_dir, exist_ok=True)
    print(f"Ensuring language directory exists: {external_lang_dir}")
    
    # Check if bundle language directory exists
    if os.path.exists(bundle_lang_dir):
        try:
            print(f"Bundle language dir found at: {bundle_lang_dir}")
            # Copy all language files from the bundle to the external directory
            for file_name in os.listdir(bundle_lang_dir):
                if file_name.endswith('.json'):
                    src_file = os.path.join(bundle_lang_dir, file_name)
                    dst_file = os.path.join(external_lang_dir, file_name)
                    
                    # Only copy if target doesn't exist or is older
                    should_copy = False
                    if not os.path.exists(dst_file):
                        should_copy = True
                        reason = "file doesn't exist in target"
                    elif os.path.getmtime(src_file) > os.path.getmtime(dst_file):
                        should_copy = True
                        reason = "bundle file is newer"
                    
                    if should_copy:
                        shutil.copy2(src_file, dst_file)
                        print(f"Extracted language file: {file_name} ({reason})")
                    else:
                        print(f"Skipped language file: {file_name} (target exists and is up-to-date)")
        except Exception as e:
            print(f"Error extracting language files: {e}")
    else:
        print(f"Warning: Bundle language directory not found at {bundle_lang_dir}")

def prepare_filter_directory():
    """
    Create the filter directory if it doesn't exist.
    The actual filter files will be created by the application on first run.
    """
    # Only needed when running as a PyInstaller bundle
    if not getattr(sys, 'frozen', False):
        return
        
    print("Preparing filter directory...")
    
    # External filter directory where filter files will be generated
    exe_dir = os.path.dirname(sys.executable)
    external_filter_dir = os.path.join(exe_dir, FILTER_DIR)
    
    # Just create the directory if it doesn't exist
    if not os.path.exists(external_filter_dir):
        try:
            os.makedirs(external_filter_dir, exist_ok=True)
            print(f"Created filter directory: {external_filter_dir}")
        except Exception as e:
            print(f"Error creating filter directory: {e}")

def create_default_config_if_missing():
    """Create a default config.json file if it doesn't exist"""
    # Only needed when running as a PyInstaller bundle
    if not getattr(sys, 'frozen', False):
        return
        
    exe_dir = os.path.dirname(sys.executable)
    config_dir = os.path.join(exe_dir, CONFIG_DIR)
    config_path = os.path.join(config_dir, os.path.basename(CONFIG_FILE))
    
    # Create config dir if it doesn't exist
    os.makedirs(config_dir, exist_ok=True)
    
    # Only create config if it doesn't exist
    if not os.path.exists(config_path):
        print(f"Creating default config file at: {config_path}")
        default_config = {
            "mode": "local",
            "openai_api_key": "",
            "elevenlabs_api_key": "",
            "language_ui": DEFAULT_LANGUAGE,
            "log_level": DEFAULT_LOG_LEVEL,
            "local_model": "base",
            "language": "",
            "output_format": "txt",
            "output_filepath": "transcription_log.txt",
            "clear_log_on_start": False
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"Default config file created successfully")
        except Exception as e:
            print(f"Error creating default config file: {e}")

# --- Main function ---
def main():
    """Initializes the application and starts the main loop."""
    global handlers

    # Initialize variables to ensure their scope
    initial_lang_code = None
    final_discovered_langs = {}

    # Get base path for the application for proper path resolution
    base_path = get_base_path()
    print(f"Application base path: {base_path}")
    
    # Extract bundled files when running as executable
    extract_bundled_language_files()
    prepare_filter_directory()
    create_default_config_if_missing()
    
    # Ensure required directories exist with absolute paths
    for dir_name in [LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR]:
        # When running as an exe, create directories next to the executable
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            dir_path = os.path.join(exe_dir, dir_name)
        else:
            dir_path = dir_name if os.path.isabs(dir_name) else os.path.join(base_path, dir_name)
            
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"Directory '{dir_path}' created or already exists.")
            except OSError as e:
                print(f"ERROR: Could not create directory '{dir_path}': {e}")

    # Get absolute paths for key config files
    if getattr(sys, 'frozen', False):
        # When running as an exe, look for files next to the executable
        exe_dir = os.path.dirname(sys.executable)
        key_file_path = os.path.join(exe_dir, CONFIG_DIR, os.path.basename(KEY_FILE))
        config_file_path = os.path.join(exe_dir, CONFIG_DIR, os.path.basename(CONFIG_FILE))
    else:
        key_file_path = KEY_FILE if os.path.isabs(KEY_FILE) else os.path.join(base_path, KEY_FILE)
        config_file_path = CONFIG_FILE if os.path.isabs(CONFIG_FILE) else os.path.join(base_path, CONFIG_FILE)
    
    print(f"Using key file: {key_file_path}")
    print(f"Using config file: {config_file_path}")
    
    # Load or generate encryption key
    encryption_key = load_or_generate_key(key_file_path, gui_q)
    if not encryption_key:
        print("CRITICAL ERROR: Could not load/generate encryption key.")

    # --- Load Reference Language Keys ---
    reference_keys = set()
    ref_lang_code = LANG_REFERENCE_CODE
    try:
        # Call load_language with is_reference_load=True
        temp_ref_dict = load_language(ref_lang_code, is_reference_load=True)
        if temp_ref_dict:
            reference_keys = set(temp_ref_dict.keys())
            print(f"Successfully loaded reference keys from language '{ref_lang_code}'.")
        else:
            # Logger is not fully initialized yet, use print
            print(f"ERROR: Reference language '{ref_lang_code}' could not be loaded properly. Cannot validate other languages.")
    except Exception as e:
        print(f"ERROR: Failed to load reference language keys: {e}. Cannot validate languages.")

    # --- Scan for available and valid languages ---
    # scan_languages now logs internally
    final_discovered_langs = scan_languages(reference_keys)
    if not final_discovered_langs:
        print(f"ERROR: No valid languages discovered. Application might not display texts correctly.")
    else:
        print(f"Discovered languages: {list(final_discovered_langs.keys())}")

    # --- Load configuration ---
    # load_config now logs internally
    app_config = load_config(config_file_path, encryption_key)

    # --- Initialize Logging with Level from Config ---
    initial_log_level_str = app_config.get("log_level", DEFAULT_LOG_LEVEL)
    # setup_logging now logs internally
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
            except IOError as e: 
                logger.error(tr("log_logfile_clear_error", path=log_file_path, error=str(e)))
            except Exception as e: 
                logger.exception(tr("log_logfile_clear_unexpected", path=log_file_path))
        elif log_file_path: 
            logger.warning(tr("log_logfile_not_found", path=log_file_path))
        else: 
            logger.warning(tr("log_logfile_no_handler"))

    # --- Start GUI ---
    try:
        logger.info(tr("log_app_started"))
        # Pass the discovered languages dictionary to the GUI
        app = WhisperGUI(app_config, encryption_key, queues, flags, handlers, available_languages=final_discovered_langs)
        app.mainloop()
        logger.info(tr("log_app_ended"))
    except Exception as e:
        logger.exception(tr("log_gui_exception"))

    # Log exit and call sys.exit inside main() scope
    if initial_lang_code: # Check if language was ever set
        logger.info(tr("log_app_exiting"))
    else:
        logger.info("Application exiting (no language loaded).") # Fallback message
    sys.exit(0)

# --- Entry point ---
if __name__ == '__main__':
    main()
    # Code execution should not reach here because sys.exit(0) is called in main()