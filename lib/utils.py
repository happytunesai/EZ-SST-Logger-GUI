# -*- coding: utf-8 -*-
"""
Hilfsfunktionen für Verschlüsselung und Audio-Geräteerkennung.
"""
import os
import sys
import queue # Wird für Typ-Annotation benötigt, wenn gui_q übergeben wird

# Importiere abhängige Bibliotheken mit Fehlerbehandlung
try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    print("KRITISCHER FEHLER: 'cryptography' nicht gefunden. Bitte installieren: pip install cryptography")
    # Erlaube den Import, aber die Funktionen werden fehlschlagen
    Fernet = None
    InvalidToken = None

try:
    import sounddevice as sd
except ImportError:
     print("KRITISCHER FEHLER: 'sounddevice' nicht gefunden. Bitte installieren: pip install sounddevice")
     sd = None

# Importiere den globalen Logger
from lib.logger_setup import logger

# --- Verschlüsselung ---

def load_or_generate_key(key_path, gui_q=None):
    """
    Lädt einen Verschlüsselungsschlüssel aus einer Datei oder generiert einen neuen.
    Sendet optional Fehlermeldungen an eine GUI-Queue.
    """
    if not Fernet:
        logger.critical("Verschlüsselungsbibliothek (cryptography) nicht geladen. Schlüsseloperationen nicht möglich.")
        if gui_q:
            gui_q.put(("error", "Cryptography fehlt!"))
        return None

    if os.path.exists(key_path):
        try:
            with open(key_path, 'rb') as f:
                key = f.read()
            # Basisvalidierung: Fernet-Schlüssel sind base64-kodiert und 44 Bytes lang
            if len(key) == 44 and b'=' in key:
                logger.info(f"Verschlüsselungsschlüssel aus '{key_path}' geladen.")
                return key
            else:
                logger.warning(f"Inhalt von '{key_path}' scheint ungültig (Länge/Format). Generiere neuen Schlüssel.")
        except Exception as e:
            logger.warning(f"Fehler beim Lesen des Schlüssels aus '{key_path}': {e}. Generiere neuen Schlüssel.")

    logger.info("Generiere neuen Verschlüsselungsschlüssel...")
    key = Fernet.generate_key()
    try:
        with open(key_path, 'wb') as f:
            f.write(key)
        logger.info(f"Neuer Schlüssel in '{key_path}' gespeichert.")
        # Wichtige Nachricht für den Benutzer anzeigen
        print("\n" + "="*60)
        print(f"!! WICHTIG: Bewahre die Datei '{key_path}' sicher auf! !!")
        print("   Ohne diese Datei kann der API-Schlüssel nicht entschlüsselt werden.")
        print("   Füge diese Datei NICHT zu Git oder anderen öffentlichen Repositories hinzu.")
        print("="*60 + "\n")
    except IOError as e:
        logger.error(f"Speichern des Schlüssels in '{key_path}' fehlgeschlagen: {e}")
        # Informiere die GUI über den Fehler, falls eine Queue übergeben wurde
        if gui_q:
            gui_q.put(("error", f"Schlüsseldatei nicht schreibbar: {e}. API Key unsicher!"))
    return key

def encrypt_data(data_bytes, key):
    """Verschlüsselt Daten mit dem gegebenen Fernet-Schlüssel."""
    if not Fernet:
        logger.error("Verschlüsselung fehlgeschlagen: Cryptography nicht geladen.")
        return None
    if not key or not data_bytes:
        logger.debug("Verschlüsselung übersprungen: Kein Schlüssel oder keine Daten.")
        return None
    try:
        f = Fernet(key)
        return f.encrypt(data_bytes)
    except Exception as e:
        logger.error(f"Fehler bei Verschlüsselung: {e}")
        return None

def decrypt_data(encrypted_bytes, key):
    """Entschlüsselt Daten mit dem gegebenen Fernet-Schlüssel."""
    if not Fernet:
        logger.error("Entschlüsselung fehlgeschlagen: Cryptography nicht geladen.")
        return None
    if not key or not encrypted_bytes:
        logger.debug("Entschlüsselung übersprungen: Kein Schlüssel oder keine Daten.")
        return None
    try:
        f = Fernet(key)
        return f.decrypt(encrypted_bytes)
    except InvalidToken:
        logger.error("Fehler bei Entschlüsselung: Ungültiges Token (falscher Schlüssel oder korrupte Daten?).")
        return None
    except Exception as e:
        logger.error(f"Fehler bei Entschlüsselung: {e}")
        return None

# --- Audio-Geräte ---

def list_audio_devices_for_gui(gui_q=None):
    """
    Fragt verfügbare Audio-Eingabegeräte ab und gibt ein Dictionary zurück.
    Sendet optional Status/Fehlermeldungen an eine GUI-Queue.
    """
    if not sd:
        logger.critical("Sounddevice-Bibliothek nicht geladen. Audio-Geräte können nicht aufgelistet werden.")
        if gui_q:
             gui_q.put(("status", "Fehler: Sounddevice fehlt!"))
             gui_q.put(("error", "Sounddevice Lib fehlt!"))
        return {}

    logger.info("Suche nach Audio-Geräten...")
    input_devices_dict = {}
    default_device_index = -1

    try:
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()
    except Exception as e:
        logger.exception("FEHLER bei Abfrage der Audiogeräte")
        if gui_q:
            gui_q.put(("status", "Fehler: Audiogeräte-Abfrage fehlgeschlagen!"))
            gui_q.put(("error", f"Fehler beim Zugriff auf Audiogeräte: {e}"))
        return {}

    # Versuche, den Index des Standard-Eingabegeräts zu finden
    try:
        default_input_device_info = sd.query_devices(kind='input')
        if default_input_device_info and isinstance(default_input_device_info, dict):
            full_devices_list = sd.query_devices() # Hole die volle Liste erneut für Index-Mapping
            for i, dev in enumerate(full_devices_list):
                # Vergleiche relevante Felder, um das Standardgerät in der vollen Liste zu finden
                if dev['name'] == default_input_device_info['name'] and \
                   dev['hostapi'] == default_input_device_info['hostapi'] and \
                   dev['max_input_channels'] > 0:
                    default_device_index = i
                    logger.debug(f"Standard-Eingabegerät gefunden: Index {i} - {dev['name']}")
                    break # Stoppe, sobald gefunden
        else:
             logger.info("Kein explizites Standard-Eingabegerät von sounddevice gemeldet.")
    except Exception as e:
        logger.warning(f"Ermittlung des Standard-Eingabegeräts nicht möglich: {e}")

    logger.debug(f"Anzahl gefundener Geräte insgesamt: {len(devices)}")
    found_input_count = 0
    for i, device in enumerate(devices):
        is_input = device.get('max_input_channels', 0) > 0
        host_api_ok = True # Standardmäßig annehmen, dass OK

        # --- Host API Prüfung (besonders für Windows MME Probleme) ---
        try:
            hostapi_index = device.get('hostapi', -1)
            if hostapi_index != -1 and hostapi_index < len(host_apis):
                hostapi_name = host_apis[hostapi_index]['name']
                # Beispiel: MME unter Windows ausschließen, falls es Probleme verursacht
                if sys.platform == 'win32' and 'MME' in hostapi_name:
                    logger.debug(f"Gerät {i} ({device['name']}) verwendet MME Host API - wird übersprungen.")
                    host_api_ok = False
            else:
                logger.debug(f"Gerät {i} ({device['name']}) hat keine gültige Host-API-Information.")
                # Je nach Strenge könnte man hier auch host_api_ok = False setzen
        except Exception as e_hostapi:
            logger.warning(f"Prüfung der Host-API für Gerät {i} fehlgeschlagen: {e_hostapi}")
            # Als potenziell problematisch behandeln? host_api_ok = False

        # --- Zur Liste hinzufügen, wenn es ein Eingabegerät ist und die Prüfungen besteht ---
        if is_input and host_api_ok:
            found_input_count += 1
            device_name = f"ID {i}: {device['name']}"
            # "(Standard)" anhängen, wenn dies das Standardgerät ist
            if i == default_device_index:
                device_name += " (Standard)"
            input_devices_dict[device_name] = i
            logger.debug(f"  -> Gültiges Eingabegerät: {device_name}")
        elif is_input:
             logger.debug(f"  -> Übersprungenes Eingabegerät (Host API): ID {i}: {device['name']}")

    logger.info(f"Anzahl gültiger Eingabegeräte gefunden: {found_input_count}")
    if not input_devices_dict:
        logger.error("Keine geeigneten Mikrofone gefunden.")
        if gui_q:
            gui_q.put(("status", "Fehler: Keine Mikrofone gefunden!"))
            gui_q.put(("error", "Keine Mikrofone gefunden. Prüfe Anschluss/Treiber/Host-API."))

    return input_devices_dict
