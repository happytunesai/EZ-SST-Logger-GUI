# -*- coding: utf-8 -*-
"""
Funktionen zum Laden und Speichern der Anwendungskonfiguration.
"""
import json
import os
import logging

# Importiere Hilfsfunktionen und Konstanten
try:
    from lib.utils import encrypt_data, decrypt_data
    from lib.constants import (
        DEFAULT_LOCAL_MODEL, DEFAULT_OUTPUT_FORMAT, DEFAULT_MIN_BUFFER_SEC,
        DEFAULT_SILENCE_SEC, DEFAULT_ELEVENLABS_MODEL, WEBSOCKET_PORT,
        DEFAULT_STREAMERBOT_WS_URL, DEFAULT_STT_PREFIX,
        DEFAULT_LANGUAGE, # SUPPORTED_LANGUAGES entfernt
        DEFAULT_LOG_LEVEL, LOG_LEVEL_NAMES # Log-Level Konstanten importiert
    )
    from lib.logger_setup import logger
except ImportError as e:
     # Fallback, falls Importe fehlschlagen (sollte nicht passieren)
     print(f"Import Fehler in config_manager.py: {e}")
     logger = logging.getLogger("FallbackLogger")
     DEFAULT_LANGUAGE = "en"
     # SUPPORTED_LANGUAGES = {"en": "English"} # Entfernt
     DEFAULT_LOG_LEVEL = "INFO"
     LOG_LEVEL_NAMES = ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]


def load_config(config_path, key):
    """Lädt die Konfiguration aus einer JSON-Datei und entschlüsselt sensible Felder."""
    logger.info(f"Lade Konfiguration aus '{config_path}'...")
    defaults = {
        "mode": "local",
        "openai_api_key_encrypted": None,
        "elevenlabs_api_key_encrypted": None,
        "mic_name": None,
        "local_model": DEFAULT_LOCAL_MODEL,
        "language": "",
        "language_ui": DEFAULT_LANGUAGE, # Bleibt als Default wichtig
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
             raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        config.update(loaded_config)

        # --- Entschlüsselung ---
        openai_key_encrypted_str = config.get("openai_api_key_encrypted")
        decrypted_openai_key = ""
        if openai_key_encrypted_str and key:
            try:
                decrypted_bytes = decrypt_data(openai_key_encrypted_str.encode('utf-8'), key)
                if decrypted_bytes: decrypted_openai_key = decrypted_bytes.decode('utf-8'); logger.info("OpenAI API-Schlüssel erfolgreich entschlüsselt.")
                else: logger.warning("OpenAI API-Schlüssel konnte nicht entschlüsselt werden.")
            except Exception as decrypt_err: logger.error(f"Fehler bei der Entschlüsselung des OpenAI Keys: {decrypt_err}")
        elif openai_key_encrypted_str: logger.warning("OpenAI API-Schlüssel in Config gefunden, aber kein Entschlüsselungsschlüssel vorhanden.")

        elevenlabs_key_encrypted_str = config.get("elevenlabs_api_key_encrypted")
        decrypted_elevenlabs_key = ""
        if elevenlabs_key_encrypted_str and key:
            try:
                decrypted_bytes = decrypt_data(elevenlabs_key_encrypted_str.encode('utf-8'), key)
                if decrypted_bytes: decrypted_elevenlabs_key = decrypted_bytes.decode('utf-8'); logger.info("ElevenLabs API-Schlüssel erfolgreich entschlüsselt.")
                else: logger.warning("ElevenLabs API-Schlüssel konnte nicht entschlüsselt werden.")
            except Exception as decrypt_err: logger.error(f"Fehler bei der Entschlüsselung des ElevenLabs Keys: {decrypt_err}")
        elif elevenlabs_key_encrypted_str: logger.warning("ElevenLabs API-Schlüssel in Config gefunden, aber kein Entschlüsselungsschlüssel vorhanden.")

        config["openai_api_key"] = decrypted_openai_key
        config["elevenlabs_api_key"] = decrypted_elevenlabs_key
        config.pop("openai_api_key_encrypted", None)
        config.pop("elevenlabs_api_key_encrypted", None)
        # --- Ende Entschlüsselung ---

        logger.info("Konfiguration erfolgreich geladen und verarbeitet.")

    except FileNotFoundError:
        logger.info(f"Konfigurationsdatei '{config_path}' nicht gefunden. Verwende Standardeinstellungen.")
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Fehler beim Lesen oder Parsen der Konfigurationsdatei '{config_path}': {e}. Verwende Standardeinstellungen.")
        config = defaults.copy()
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
    except Exception as e:
        logger.exception("Unerwarteter Fehler beim Laden der Konfiguration. Verwende Standardeinstellungen.")
        config = defaults.copy()
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""

    # Validiere Log-Level (Sprache wird in main.py validiert)
    if config.get("log_level") not in LOG_LEVEL_NAMES:
        logger.warning(f"Ungültiger Log-Level '{config.get('log_level')}' in Config gefunden. Setze auf Standard '{DEFAULT_LOG_LEVEL}'.")
        config["log_level"] = DEFAULT_LOG_LEVEL

    return config

def save_config(config_path, config_dict, key):
    """
    Speichert das Konfigurations-Dictionary in einer JSON-Datei und verschlüsselt sensible Felder.
    Gibt True bei Erfolg zurück, False bei Fehler.
    """
    logger.info(f"Speichere Konfiguration in '{config_path}'...")
    config_to_save = config_dict.copy()
    config_dir = os.path.dirname(config_path)

    # --- Verschlüsselung ---
    openai_key_plain = config_to_save.pop("openai_api_key", "")
    encrypted_openai_key_str = None
    if openai_key_plain and key:
        encrypted_bytes = encrypt_data(openai_key_plain.encode('utf-8'), key)
        if encrypted_bytes: encrypted_openai_key_str = encrypted_bytes.decode('utf-8'); logger.debug("OpenAI API-Schlüssel für Speicherung verschlüsselt.")
        else: logger.error("Fehler bei der Verschlüsselung des OpenAI API-Keys. Wird NICHT gespeichert.")
    elif openai_key_plain: logger.error("OpenAI API-Key vorhanden, aber kein Verschlüsselungsschlüssel. Wird NICHT gespeichert.")
    config_to_save["openai_api_key_encrypted"] = encrypted_openai_key_str

    elevenlabs_key_plain = config_to_save.pop("elevenlabs_api_key", "")
    encrypted_elevenlabs_key_str = None
    if elevenlabs_key_plain and key:
        encrypted_bytes = encrypt_data(elevenlabs_key_plain.encode('utf-8'), key)
        if encrypted_bytes: encrypted_elevenlabs_key_str = encrypted_bytes.decode('utf-8'); logger.debug("ElevenLabs API-Schlüssel für Speicherung verschlüsselt.")
        else: logger.error("Fehler bei der Verschlüsselung des ElevenLabs API-Keys. Wird NICHT gespeichert.")
    elif elevenlabs_key_plain: logger.error("ElevenLabs API-Key vorhanden, aber kein Verschlüsselungsschlüssel. Wird NICHT gespeichert.")
    config_to_save["elevenlabs_api_key_encrypted"] = encrypted_elevenlabs_key_str
    # --- Ende Verschlüsselung ---

    # Stelle numerische Werte und Log-Level sicher
    try:
        config_to_save["min_buffer_duration"] = float(config_to_save.get("min_buffer_duration", DEFAULT_MIN_BUFFER_SEC))
        config_to_save["silence_threshold"] = float(config_to_save.get("silence_threshold", DEFAULT_SILENCE_SEC))
        config_to_save["websocket_port"] = int(config_to_save.get("websocket_port", WEBSOCKET_PORT))
        # Sprache wird nicht mehr validiert hier, nur Log-Level
        if config_to_save.get("log_level") not in LOG_LEVEL_NAMES:
             logger.warning(f"Versuche ungültigen Log-Level '{config_to_save.get('log_level')}' zu speichern. Setze auf Default '{DEFAULT_LOG_LEVEL}'.")
             config_to_save["log_level"] = DEFAULT_LOG_LEVEL
        elif "log_level" not in config_to_save:
             config_to_save["log_level"] = DEFAULT_LOG_LEVEL
        # Stelle sicher, dass language_ui existiert (wird von GUI gesetzt)
        if "language_ui" not in config_to_save:
             config_to_save["language_ui"] = DEFAULT_LANGUAGE

    except (ValueError, TypeError) as e:
         logger.error(f"Fehler Konvertierung numerischer Werte beim Speichern: {e}.")
         config_to_save["min_buffer_duration"] = DEFAULT_MIN_BUFFER_SEC
         config_to_save["silence_threshold"] = DEFAULT_SILENCE_SEC
         config_to_save["websocket_port"] = WEBSOCKET_PORT
         config_to_save["log_level"] = DEFAULT_LOG_LEVEL

    # Speichere die Konfiguration
    try:
        if config_dir:
             os.makedirs(config_dir, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        logger.info("Konfiguration erfolgreich gespeichert.")
        return True
    except IOError as e:
        logger.error(f"FEHLER beim Speichern der Konfiguration in '{config_path}': {e}")
        return False
    except Exception as e:
        logger.exception("Unerwarteter Fehler beim Speichern der Konfiguration")
        return False
