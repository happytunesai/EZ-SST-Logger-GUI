# -*- coding: utf-8 -*-
"""
Functions for loading and saving application configuration.
MODIFIED: Uses get_persistent_data_path for correct paths in PyInstaller builds.
"""
import json
import os
import logging
import sys # Needed for sys.frozen / sys.executable in fallback

# Import utility functions and constants
try:
    # Import the NEW function get_persistent_data_path
    from lib.utils import encrypt_data, decrypt_data, get_persistent_data_path
    from lib.constants import (
        DEFAULT_LOCAL_MODEL, DEFAULT_OUTPUT_FORMAT, DEFAULT_MIN_BUFFER_SEC,
        DEFAULT_SILENCE_SEC, DEFAULT_ELEVENLABS_MODEL, WEBSOCKET_PORT,
        DEFAULT_STREAMERBOT_WS_URL, DEFAULT_STT_PREFIX,
        DEFAULT_LANGUAGE,
        DEFAULT_LOG_LEVEL,DEFAULT_REPLACEMENT_BOTNAME, LOG_LEVEL_NAMES,
        CONFIG_DIR # Needed for relative path construction
    )
    from lib.logger_setup import logger
    # Import translation function
    from lib.language_manager import tr
except ImportError as e:
    # Fallback if imports fail (should not happen in normal operation)
    print(f"Import Error in config_manager.py: {e}")
    logger = logging.getLogger("FallbackLogger")
    # Define minimal fallback values
    DEFAULT_LANGUAGE = "en"
    DEFAULT_LOG_LEVEL = "INFO"
    LOG_LEVEL_NAMES = ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]
    CONFIG_DIR = "config"
    # Fallback implementation for path function if import fails
    def get_persistent_data_path():
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return os.path.dirname(sys.executable)
        else:
            return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # Fallback for crypto functions
    def encrypt_data(data, key): return None
    def decrypt_data(data, key): return None
    # Fallback for tr function
    def tr(key, **kwargs): return key.format(**kwargs) if kwargs else key
    # Defaults for other constants
    DEFAULT_LOCAL_MODEL = "base"
    DEFAULT_OUTPUT_FORMAT = "txt"
    DEFAULT_MIN_BUFFER_SEC = 5.0
    DEFAULT_SILENCE_SEC = 2.0
    DEFAULT_ELEVENLABS_MODEL = "scribe_v1"
    WEBSOCKET_PORT = 8765
    DEFAULT_STREAMERBOT_WS_URL = "ws://127.0.0.1:1337/"
    DEFAULT_STT_PREFIX = "Bot speaks: "


def load_config(config_path_relative, key):
    """
    Loads the configuration from a JSON file from the persistent storage location
    and decrypts sensitive fields.
    Args:
        config_path_relative (str): The relative path to the config file (e.g., "config/config.json").
        key (bytes): The key for decryption.
    Returns:
        dict: The loaded configuration dictionary.
    """
    persistent_dir = get_persistent_data_path() # <-- NEW: Get base path for persistent data
    absolute_config_path = os.path.join(persistent_dir, config_path_relative) # <-- NEW: Construct absolute path
    # Use tr() for logging
    logger.info(tr("log_config_loading", path=absolute_config_path))

    defaults = {
        "mode": "local",
        "openai_api_key_encrypted": None, # Will be replaced by plain text after loading (if decrypted)
        "elevenlabs_api_key_encrypted": None, # Will be replaced by plain text after loading (if decrypted)
        "mic_name": None,
        "local_model": DEFAULT_LOCAL_MODEL,
        "language": "",
        "language_ui": DEFAULT_LANGUAGE,
        "log_level": DEFAULT_LOG_LEVEL,
        "output_format": DEFAULT_OUTPUT_FORMAT,
        "output_filepath": "",
        "clear_log_on_start": False,
        "min_buffer_duration": DEFAULT_MIN_BUFFER_SEC,
        "silence_threshold": DEFAULT_SILENCE_SEC,
        "elevenlabs_model_id": DEFAULT_ELEVENLABS_MODEL,
        "filter_parentheses": True,
        "websocket_enabled": False,
        "websocket_port": WEBSOCKET_PORT,
        "streamerbot_ws_enabled": False,
        "streamerbot_ws_url": DEFAULT_STREAMERBOT_WS_URL,
        "stt_prefix": DEFAULT_STT_PREFIX,
        "replacement_botname": DEFAULT_REPLACEMENT_BOTNAME
    }
    config = defaults.copy()

    # First check if the file exists at the persistent location
    if not os.path.exists(absolute_config_path):
        # Use tr() for logging
        logger.info(tr("log_config_fallback_defaults", path=absolute_config_path))
        # Ensure plain text keys are empty if no file is loaded
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
        # Remove encrypted keys from defaults as none were loaded
        config.pop("openai_api_key_encrypted", None)
        config.pop("elevenlabs_api_key_encrypted", None)
        return config

    # If file exists, try to load it
    try:
        with open(absolute_config_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        # Update defaults with loaded values
        config.update(loaded_config)

        # --- Decryption ---
        decrypted_openai_key = ""
        # Use .get() to safely access potentially missing keys
        openai_key_encrypted_str = config.get("openai_api_key_encrypted")
        if openai_key_encrypted_str and key:
            try:
                decrypted_bytes = decrypt_data(openai_key_encrypted_str.encode('utf-8'), key)
                if decrypted_bytes:
                    decrypted_openai_key = decrypted_bytes.decode('utf-8')
                    logger.info(tr("log_config_openai_decrypted"))
                else:
                    # Case: decrypt_data returns None (e.g., InvalidToken)
                    logger.warning(tr("log_config_openai_decrypt_failed"))
            except Exception as decrypt_err:
                logger.error(tr("log_config_openai_decrypt_error", error=str(decrypt_err)))
        elif openai_key_encrypted_str:
            logger.warning(tr("log_config_openai_key_found_but_no_decryption"))

        decrypted_elevenlabs_key = ""
        elevenlabs_key_encrypted_str = config.get("elevenlabs_api_key_encrypted")
        if elevenlabs_key_encrypted_str and key:
            try:
                decrypted_bytes = decrypt_data(elevenlabs_key_encrypted_str.encode('utf-8'), key)
                if decrypted_bytes:
                    decrypted_elevenlabs_key = decrypted_bytes.decode('utf-8')
                    logger.info(tr("log_config_elevenlabs_decrypted"))
                else:
                    logger.warning(tr("log_config_elevenlabs_decrypt_failed"))
            except Exception as decrypt_err:
                logger.error(tr("log_config_elevenlabs_decrypt_error", error=str(decrypt_err)))
        elif elevenlabs_key_encrypted_str:
            logger.warning(tr("log_config_elevenlabs_key_found_but_no_decryption"))

        # Add decrypted (or empty) keys and remove encrypted versions from the final dict
        config["openai_api_key"] = decrypted_openai_key
        config["elevenlabs_api_key"] = decrypted_elevenlabs_key
        config.pop("openai_api_key_encrypted", None)
        config.pop("elevenlabs_api_key_encrypted", None)
        # --- End Decryption ---

        logger.info(tr("log_config_loaded"))

    except (json.JSONDecodeError, IOError) as e:
        # Error reading/parsing EXISTING persistent file
        logger.error(tr("log_config_parse_error", path=absolute_config_path, error=str(e)))
        config = defaults.copy() # Fallback to defaults on error
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
        config.pop("openai_api_key_encrypted", None)
        config.pop("elevenlabs_api_key_encrypted", None)
    except Exception as e:
        # Log the path in the exception message itself
        logger.exception(f"Unexpected error loading configuration from '{absolute_config_path}'. Using defaults.")
        config = defaults.copy() # Fallback to defaults on error
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
        config.pop("openai_api_key_encrypted", None)
        config.pop("elevenlabs_api_key_encrypted", None)

    # --- Validation (Log Level) ---
    if config.get("log_level") not in LOG_LEVEL_NAMES:
        logger.warning(tr("log_config_invalid_log_level", value=config.get('log_level'), fallback=DEFAULT_LOG_LEVEL))
        config["log_level"] = DEFAULT_LOG_LEVEL
    # Ensure language_ui exists (should be covered by defaults)
    if "language_ui" not in config:
        config["language_ui"] = DEFAULT_LANGUAGE

    return config


def save_config(config_path_relative, config_dict, key):
    """
    Saves the configuration dictionary to a JSON file at the persistent storage location
    and encrypts sensitive fields.
    Args:
        config_path_relative (str): The relative path to the config file (e.g., "config/config.json").
        config_dict (dict): The configuration dictionary to save.
        key (bytes): The key for encryption.
    Returns:
        bool: True on success, False on error.
    """
    persistent_dir = get_persistent_data_path() # <-- NEW: Get base path for persistent data
    absolute_config_path = os.path.join(persistent_dir, config_path_relative) # <-- NEW: Construct absolute path
    config_dir = os.path.dirname(absolute_config_path) # Determine directory for makedirs
    logger.info(tr("log_config_saving", path=absolute_config_path))

    # Create a copy to avoid modifying the original dictionary passed in
    config_to_save = config_dict.copy()

    # --- Encryption ---
    # Pop plain text keys from the dictionary to be saved, encrypt, and add encrypted version
    openai_key_plain = config_to_save.pop("openai_api_key", "")
    encrypted_openai_key_str = None
    if openai_key_plain and key:
        encrypted_bytes = encrypt_data(openai_key_plain.encode('utf-8'), key)
        if encrypted_bytes:
            encrypted_openai_key_str = encrypted_bytes.decode('utf-8')
            logger.debug(tr("log_config_openai_encrypted"))
        else:
            logger.error(tr("log_config_openai_encrypt_failed"))
            # Optionally notify GUI here or in the calling function
    elif openai_key_plain:
        # NEW tr key needed, e.g., log_config_save_plaintext_warning
        logger.warning(tr("log_config_openai_no_key")) # Reusing similar key for now
        # Key won't be saved to avoid storing plain text
    # Add the (potentially None) encrypted key to the dictionary to be saved
    config_to_save["openai_api_key_encrypted"] = encrypted_openai_key_str

    elevenlabs_key_plain = config_to_save.pop("elevenlabs_api_key", "")
    encrypted_elevenlabs_key_str = None
    if elevenlabs_key_plain and key:
        encrypted_bytes = encrypt_data(elevenlabs_key_plain.encode('utf-8'), key)
        if encrypted_bytes:
            encrypted_elevenlabs_key_str = encrypted_bytes.decode('utf-8')
            logger.debug(tr("log_config_elevenlabs_encrypted"))
        else:
            logger.error(tr("log_config_elevenlabs_encrypt_failed"))
    elif elevenlabs_key_plain:
        # NEW tr key needed, e.g., log_config_save_plaintext_warning
        logger.warning(tr("log_config_elevenlabs_no_key")) # Reusing similar key
    config_to_save["elevenlabs_api_key_encrypted"] = encrypted_elevenlabs_key_str
    # --- End Encryption ---

    # --- Ensure Data Types & Validation ---
    try:
        # Ensure these fields are saved as floats
        config_to_save["min_buffer_duration"] = float(config_to_save.get("min_buffer_duration", DEFAULT_MIN_BUFFER_SEC))
        config_to_save["silence_threshold"] = float(config_to_save.get("silence_threshold", DEFAULT_SILENCE_SEC))
        # Ensure port is saved as an integer
        config_to_save["websocket_port"] = int(config_to_save.get("websocket_port", WEBSOCKET_PORT))

        # Validate log level
        log_level_to_save = config_to_save.get("log_level")
        if log_level_to_save not in LOG_LEVEL_NAMES:
            logger.warning(tr("log_config_invalid_log_level_save", value=log_level_to_save, fallback=DEFAULT_LOG_LEVEL))
            config_to_save["log_level"] = DEFAULT_LOG_LEVEL
        # Set default if key is missing entirely
        elif "log_level" not in config_to_save:
            config_to_save["log_level"] = DEFAULT_LOG_LEVEL

        # Ensure language_ui exists (should be set by GUI)
        if "language_ui" not in config_to_save:
            # NEW tr key needed, e.g., log_config_missing_key_save
            logger.warning(tr("log_config_missing_key_save", key="language_ui", fallback=DEFAULT_LANGUAGE)) # Assuming new key exists
            config_to_save["language_ui"] = DEFAULT_LANGUAGE

    except (ValueError, TypeError) as e:
        logger.error(tr("log_config_save_conversion_error", error=str(e)))
        # Revert to defaults on conversion error
        config_to_save["min_buffer_duration"] = DEFAULT_MIN_BUFFER_SEC
        config_to_save["silence_threshold"] = DEFAULT_SILENCE_SEC
        config_to_save["websocket_port"] = WEBSOCKET_PORT
        config_to_save["log_level"] = DEFAULT_LOG_LEVEL
        # Language should already exist, but just in case:
        if "language_ui" not in config_to_save: config_to_save["language_ui"] = DEFAULT_LANGUAGE

    # --- Save the configuration ---
    try:
        # Ensure the directory exists at the persistent location
        # exist_ok=True prevents errors if the directory already exists
        if config_dir: # Only run if a directory path exists (prevents error for filenames without dir)
            os.makedirs(config_dir, exist_ok=True)

        # Write the file
        with open(absolute_config_path, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        logger.info(tr("log_config_saved"))
        return True
    except IOError as e:
        logger.error(tr("log_config_save_error", path=absolute_config_path, error=str(e)))
        # Optional: Notify GUI here or in the calling function (e.g., gui.py)
        return False
    except Exception as e:
        # Log path in the exception message itself
        logger.exception(f"Unexpected error saving configuration to '{absolute_config_path}'")
        return False
    