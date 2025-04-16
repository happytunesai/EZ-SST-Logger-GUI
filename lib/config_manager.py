# -*- coding: utf-8 -*-
"""
Functions for loading and saving the application configuration.
"""
import json
import os
import logging

# Import helpers and constants
try:
    from lib.utils import encrypt_data, decrypt_data
    from lib.constants import (
        DEFAULT_LOCAL_MODEL, DEFAULT_OUTPUT_FORMAT, DEFAULT_MIN_BUFFER_SEC,
        DEFAULT_SILENCE_SEC, DEFAULT_ELEVENLABS_MODEL, WEBSOCKET_PORT,
        DEFAULT_STREAMERBOT_WS_URL, DEFAULT_STT_PREFIX,
        DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES,
        DEFAULT_LOG_LEVEL, LOG_LEVEL_NAMES
    )
    from lib.logger_setup import logger
    from lib.language_manager import tr
except ImportError as e:
    print(f"Import error in config_manager.py: {e}")
    logger = logging.getLogger("FallbackLogger")

    def tr(key, **kwargs):
        return key.format(**kwargs) if kwargs else key

    DEFAULT_LANGUAGE = "en"
    SUPPORTED_LANGUAGES = {"en": "English"}
    DEFAULT_LOG_LEVEL = "INFO"
    LOG_LEVEL_NAMES = ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]

def load_config(config_path, key):
    """Loads config from a JSON file and decrypts sensitive fields."""
    logger.info(tr("log_config_loading", path=config_path))
    defaults = {
        "mode": "local",
        "openai_api_key_encrypted": None,
        "elevenlabs_api_key_encrypted": None,
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
        "filter_parentheses": False,
        "websocket_enabled": False,
        "websocket_port": WEBSOCKET_PORT,
        "streamerbot_ws_enabled": False,
        "streamerbot_ws_url": DEFAULT_STREAMERBOT_WS_URL,
        "stt_prefix": DEFAULT_STT_PREFIX
    }
    config = defaults.copy()

    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(tr("log_config_file_not_found", path=config_path))

        with open(config_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        config.update(loaded_config)

        # Decrypt sensitive fields
        openai_key_encrypted_str = config.get("openai_api_key_encrypted")
        decrypted_openai_key = ""
        if openai_key_encrypted_str and key:
            try:
                decrypted_bytes = decrypt_data(openai_key_encrypted_str.encode('utf-8'), key)
                if decrypted_bytes:
                    decrypted_openai_key = decrypted_bytes.decode('utf-8')
                    logger.info(tr("log_config_openai_decrypted"))
                else:
                    logger.warning(tr("log_config_openai_decrypt_failed"))
            except Exception as decrypt_err:
                logger.error(tr("log_config_openai_decrypt_error", error=str(decrypt_err)))
        elif openai_key_encrypted_str:
            logger.warning(tr("log_config_openai_key_found_but_no_decryption"))

        elevenlabs_key_encrypted_str = config.get("elevenlabs_api_key_encrypted")
        decrypted_elevenlabs_key = ""
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

        config["openai_api_key"] = decrypted_openai_key
        config["elevenlabs_api_key"] = decrypted_elevenlabs_key
        config.pop("openai_api_key_encrypted", None)
        config.pop("elevenlabs_api_key_encrypted", None)

        logger.info(tr("log_config_loaded"))

    except FileNotFoundError:
        logger.info(tr("log_config_fallback_defaults", path=config_path))
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
    except (json.JSONDecodeError, IOError) as e:
        logger.error(tr("log_config_parse_error", path=config_path, error=str(e)))
        config = defaults.copy()
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
    except Exception as e:
        logger.exception(tr("log_config_unexpected_error"))
        config = defaults.copy()
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""

    if config.get("language_ui") not in SUPPORTED_LANGUAGES:
        logger.warning(tr("log_config_invalid_language", value=config.get("language_ui"), fallback=DEFAULT_LANGUAGE))
        config["language_ui"] = DEFAULT_LANGUAGE
    if config.get("log_level") not in LOG_LEVEL_NAMES:
        logger.warning(tr("log_config_invalid_log_level", value=config.get("log_level"), fallback=DEFAULT_LOG_LEVEL))
        config["log_level"] = DEFAULT_LOG_LEVEL

    return config

def save_config(config_path, config_dict, key):
    """Saves the config dictionary into a JSON file and encrypts sensitive fields."""
    logger.info(tr("log_config_saving", path=config_path))
    config_to_save = config_dict.copy()
    config_dir = os.path.dirname(config_path)

    # Encrypt sensitive fields
    openai_key_plain = config_to_save.pop("openai_api_key", "")
    encrypted_openai_key_str = None
    if openai_key_plain and key:
        encrypted_bytes = encrypt_data(openai_key_plain.encode('utf-8'), key)
        if encrypted_bytes:
            encrypted_openai_key_str = encrypted_bytes.decode('utf-8')
            logger.debug(tr("log_config_openai_encrypted"))
        else:
            logger.error(tr("log_config_openai_encrypt_failed"))
    elif openai_key_plain:
        logger.error(tr("log_config_openai_no_key"))

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
        logger.error(tr("log_config_elevenlabs_no_key"))

    config_to_save["elevenlabs_api_key_encrypted"] = encrypted_elevenlabs_key_str

    # Ensure numeric/log fields are valid
    try:
        config_to_save["min_buffer_duration"] = float(config_to_save.get("min_buffer_duration", DEFAULT_MIN_BUFFER_SEC))
        config_to_save["silence_threshold"] = float(config_to_save.get("silence_threshold", DEFAULT_SILENCE_SEC))
        config_to_save["websocket_port"] = int(config_to_save.get("websocket_port", WEBSOCKET_PORT))
        if "language_ui" not in config_to_save:
            config_to_save["language_ui"] = DEFAULT_LANGUAGE
        if config_to_save.get("log_level") not in LOG_LEVEL_NAMES:
            logger.warning(tr("log_config_invalid_log_level_save", value=config_to_save.get("log_level"), fallback=DEFAULT_LOG_LEVEL))
            config_to_save["log_level"] = DEFAULT_LOG_LEVEL
        elif "log_level" not in config_to_save:
            config_to_save["log_level"] = DEFAULT_LOG_LEVEL
    except (ValueError, TypeError) as e:
        logger.error(tr("log_config_save_conversion_error", error=str(e)))
        config_to_save["min_buffer_duration"] = DEFAULT_MIN_BUFFER_SEC
        config_to_save["silence_threshold"] = DEFAULT_SILENCE_SEC
        config_to_save["websocket_port"] = WEBSOCKET_PORT
        config_to_save["log_level"] = DEFAULT_LOG_LEVEL

    try:
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        logger.info(tr("log_config_saved"))
        return True
    except IOError as e:
        logger.error(tr("log_config_save_error", path=config_path, error=str(e)))
        return False
    except Exception as e:
        logger.exception(tr("log_config_save_unexpected"))
        return False
