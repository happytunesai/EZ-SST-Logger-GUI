# -*- coding: utf-8 -*-
"""
Funktionen zum Laden und Speichern der Anwendungskonfiguration.
"""
import json
import os

# Importiere Hilfsfunktionen und Konstanten
from lib.utils import encrypt_data, decrypt_data
from lib.constants import (
    DEFAULT_LOCAL_MODEL, DEFAULT_OUTPUT_FORMAT, DEFAULT_MIN_BUFFER_SEC,
    DEFAULT_SILENCE_SEC, DEFAULT_ELEVENLABS_MODEL, WEBSOCKET_PORT,
    DEFAULT_STREAMERBOT_WS_URL, DEFAULT_STT_PREFIX
)
# Importiere den globalen Logger
from lib.logger_setup import logger

def load_config(config_path, key):
    """Lädt die Konfiguration aus einer JSON-Datei und entschlüsselt sensible Felder."""
    logger.info(f"Lade Konfiguration aus '{config_path}'...")
    # Definiere Standardwerte direkt hier oder importiere sie aus constants.py
    defaults = {
        "mode": "local", # Verwende interne Modus-Bezeichner
        "openai_api_key_encrypted": None,
        "elevenlabs_api_key_encrypted": None,
        "mic_name": None,
        "local_model": DEFAULT_LOCAL_MODEL,
        "language": "",
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
    config = defaults.copy() # Beginne mit den Standardwerten

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)

        # Aktualisiere die Konfiguration mit geladenen Werten, behalte Defaults für fehlende Schlüssel
        config.update(loaded_config)

        # Entschlüssele OpenAI API Key
        openai_key_encrypted_str = config.get("openai_api_key_encrypted")
        decrypted_openai_key = ""
        if openai_key_encrypted_str and key:
            try:
                openai_key_encrypted_bytes = openai_key_encrypted_str.encode('utf-8')
                # Verwende die importierte decrypt_data Funktion
                decrypted_bytes = decrypt_data(openai_key_encrypted_bytes, key)
                if decrypted_bytes:
                    decrypted_openai_key = decrypted_bytes.decode('utf-8')
                    logger.info("OpenAI API-Schlüssel erfolgreich entschlüsselt.")
                else:
                    logger.warning("OpenAI API-Schlüssel konnte nicht entschlüsselt werden (möglicherweise falscher Schlüssel?).")
            except Exception as decrypt_err:
                logger.error(f"Fehler bei der Entschlüsselung des OpenAI Keys: {decrypt_err}")
        elif openai_key_encrypted_str:
             logger.warning("OpenAI API-Schlüssel in Config gefunden, aber kein Entschlüsselungsschlüssel vorhanden.")

        # Entschlüssele ElevenLabs API Key
        elevenlabs_key_encrypted_str = config.get("elevenlabs_api_key_encrypted")
        decrypted_elevenlabs_key = ""
        if elevenlabs_key_encrypted_str and key:
            try:
                elevenlabs_key_encrypted_bytes = elevenlabs_key_encrypted_str.encode('utf-8')
                # Verwende die importierte decrypt_data Funktion
                decrypted_bytes = decrypt_data(elevenlabs_key_encrypted_bytes, key)
                if decrypted_bytes:
                    decrypted_elevenlabs_key = decrypted_bytes.decode('utf-8')
                    logger.info("ElevenLabs API-Schlüssel erfolgreich entschlüsselt.")
                else:
                    logger.warning("ElevenLabs API-Schlüssel konnte nicht entschlüsselt werden (möglicherweise falscher Schlüssel?).")
            except Exception as decrypt_err:
                logger.error(f"Fehler bei der Entschlüsselung des ElevenLabs Keys: {decrypt_err}")
        elif elevenlabs_key_encrypted_str:
             logger.warning("ElevenLabs API-Schlüssel in Config gefunden, aber kein Entschlüsselungsschlüssel vorhanden.")

        # Speichere entschlüsselte Schlüssel direkt im Config-Dict für die Laufzeitnutzung
        # Diese werden NICHT in der Datei gespeichert (nur die verschlüsselten)
        config["openai_api_key"] = decrypted_openai_key
        config["elevenlabs_api_key"] = decrypted_elevenlabs_key

        # Entferne verschlüsselte Schlüssel aus der Laufzeit-Konfiguration
        config.pop("openai_api_key_encrypted", None)
        config.pop("elevenlabs_api_key_encrypted", None)

        logger.info("Konfiguration erfolgreich geladen und verarbeitet.")

    except FileNotFoundError:
        logger.info(f"Konfigurationsdatei '{config_path}' nicht gefunden. Verwende Standardeinstellungen.")
        # Stelle sicher, dass API-Keys leer sind, wenn die Config-Datei fehlt
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Fehler beim Lesen oder Parsen der Konfigurationsdatei '{config_path}': {e}. Verwende Standardeinstellungen.")
        config = defaults.copy() # Setze auf Defaults zurück bei Fehler
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""
    except Exception as e:
        logger.exception("Unerwarteter Fehler beim Laden der Konfiguration. Verwende Standardeinstellungen.")
        config = defaults.copy() # Setze auf Defaults zurück bei unerwartetem Fehler
        config["openai_api_key"] = ""
        config["elevenlabs_api_key"] = ""

    return config

def save_config(config_path, config_dict, key):
    """
    Speichert das Konfigurations-Dictionary in einer JSON-Datei und verschlüsselt sensible Felder.
    Gibt True bei Erfolg zurück, False bei Fehler.
    """
    logger.info(f"Speichere Konfiguration in '{config_path}'...")
    config_to_save = config_dict.copy() # Arbeite mit einer Kopie

    # Verschlüssele OpenAI API Key, falls vorhanden
    openai_key_plain = config_to_save.pop("openai_api_key", "") # Hole und entferne Klartext-Key
    encrypted_openai_key_str = None
    if openai_key_plain and key:
        # Verwende die importierte encrypt_data Funktion
        encrypted_bytes = encrypt_data(openai_key_plain.encode('utf-8'), key)
        if encrypted_bytes:
            encrypted_openai_key_str = encrypted_bytes.decode('utf-8')
            logger.debug("OpenAI API-Schlüssel für Speicherung verschlüsselt.")
        else:
            logger.error("Fehler bei der Verschlüsselung des OpenAI API-Keys. Wird NICHT gespeichert.")
            # Gib hier möglicherweise False zurück, um den Fehler anzuzeigen?
            # return False # Oder lasse es zu, den Rest zu speichern
    elif openai_key_plain:
        logger.error("OpenAI API-Key vorhanden, aber kein Verschlüsselungsschlüssel. Wird NICHT gespeichert.")
    config_to_save["openai_api_key_encrypted"] = encrypted_openai_key_str # Speichere verschlüsselten (oder None)

    # Verschlüssele ElevenLabs API Key, falls vorhanden
    elevenlabs_key_plain = config_to_save.pop("elevenlabs_api_key", "") # Hole und entferne Klartext-Key
    encrypted_elevenlabs_key_str = None
    if elevenlabs_key_plain and key:
        # Verwende die importierte encrypt_data Funktion
        encrypted_bytes = encrypt_data(elevenlabs_key_plain.encode('utf-8'), key)
        if encrypted_bytes:
            encrypted_elevenlabs_key_str = encrypted_bytes.decode('utf-8')
            logger.debug("ElevenLabs API-Schlüssel für Speicherung verschlüsselt.")
        else:
            logger.error("Fehler bei der Verschlüsselung des ElevenLabs API-Keys. Wird NICHT gespeichert.")
            # return False
    elif elevenlabs_key_plain:
        logger.error("ElevenLabs API-Key vorhanden, aber kein Verschlüsselungsschlüssel. Wird NICHT gespeichert.")
    config_to_save["elevenlabs_api_key_encrypted"] = encrypted_elevenlabs_key_str # Speichere verschlüsselten (oder None)

    # Stelle sicher, dass numerische Werte korrekt typisiert sind vor dem Speichern
    try:
        config_to_save["min_buffer_duration"] = float(config_to_save.get("min_buffer_duration", DEFAULT_MIN_BUFFER_SEC))
        config_to_save["silence_threshold"] = float(config_to_save.get("silence_threshold", DEFAULT_SILENCE_SEC))
        config_to_save["websocket_port"] = int(config_to_save.get("websocket_port", WEBSOCKET_PORT))
    except (ValueError, TypeError) as e:
         logger.error(f"Fehler bei der Konvertierung numerischer Konfigurationswerte beim Speichern: {e}. Verwende Defaults für fehlerhafte Werte.")
         # Setze auf Defaults zurück, um ungültige Datei zu vermeiden
         config_to_save["min_buffer_duration"] = DEFAULT_MIN_BUFFER_SEC
         config_to_save["silence_threshold"] = DEFAULT_SILENCE_SEC
         config_to_save["websocket_port"] = WEBSOCKET_PORT
         # Gib False zurück, da die gespeicherte Konfig nicht exakt der UI entspricht
         # return False # Oder lasse Speicherung zu, aber mit korrigierten Werten

    # Speichere die Konfiguration
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        logger.info("Konfiguration erfolgreich gespeichert.")
        return True # Erfolg signalisieren
    except IOError as e:
        logger.error(f"FEHLER beim Speichern der Konfiguration in '{config_path}': {e}")
        # Sende keine GUI-Nachricht von hier, main.py oder gui.py sollten das tun
        return False # Fehler signalisieren
    except Exception as e:
        logger.exception("Unerwarteter Fehler beim Speichern der Konfiguration")
        return False # Fehler signalisieren

