# -*- coding: utf-8 -*-
"""
Konfiguration des Logging-Systems für die Anwendung.
"""
import logging
import sys
import os
from datetime import datetime

# Importiere Konstanten
# Stelle sicher, dass der Importpfad korrekt ist
try:
    from lib.constants import LOG_DIR, LOG_LEVELS, DEFAULT_LOG_LEVEL
except ImportError:
    # Fallback, falls als eigenständiges Skript ausgeführt
    print("Fallback für Konstanten in logger_setup.py")
    LOG_DIR = "logs"
    DEFAULT_LOG_LEVEL = "INFO"
    LOG_LEVELS = { "INFO": logging.INFO, "DEBUG": logging.DEBUG }


# Globaler Logger - wird von setup_logging initialisiert und konfiguriert
logger = logging.getLogger("EZ_STT_Logger")
# Globale Referenzen auf Handler sind nicht mehr nötig, da sie zurückgegeben werden

def setup_logging(initial_console_level_str=DEFAULT_LOG_LEVEL):
    """
    Konfiguriert das Logging-System und gibt Logger und Handler zurück.

    Args:
        initial_console_level_str (str): Der initiale Log-Level für die Konsole
                                         als String (z.B. "INFO", "DEBUG").

    Returns:
        tuple: (logger, console_handler, file_handler)
               Gibt den konfigurierten Logger und die erstellten Handler zurück.
               Handler können None sein, wenn ihre Erstellung fehlschlägt.
    """
    # Lokale Variablen für Handler innerhalb dieser Funktion
    console_handler = None
    file_handler = None

    log_formatter = logging.Formatter('%(asctime)s [%(levelname)-5.5s] %(threadName)s: %(message)s')

    # Verzeichnis sicherstellen
    if not os.path.exists(LOG_DIR):
        try: os.makedirs(LOG_DIR)
        except OSError as e: print(f"FEHLER: Konnte Log-Verzeichnis '{LOG_DIR}' nicht erstellen: {e}"); log_dir_path = "."
        else: log_dir_path = LOG_DIR
    else: log_dir_path = LOG_DIR

    log_filename = os.path.join(log_dir_path, f"ez_stt_logger_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

    # File Handler (Level bleibt DEBUG, um alles in die Datei zu schreiben)
    try:
        # Schließe alten Handler, falls vorhanden (wichtig bei Neustart/Reload)
        # Prüfe, ob der Handler existiert und im Logger ist
        for h in logger.handlers[:]: # Iteriere über Kopie der Liste
            if isinstance(h, logging.FileHandler) and h.baseFilename == log_filename:
                 logger.removeHandler(h)
                 h.close()
                 print("Alten FileHandler entfernt.") # Debug
                 break # Annahme: nur ein FileHandler

        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG) # Datei loggt immer alles ab DEBUG
    except IOError as e:
        print(f"FEHLER: Konnte Logdatei '{log_filename}' nicht öffnen: {e}")
        file_handler = None

    # Console Handler (Level aus Argument/Config)
    # Konvertiere String-Level zu logging-Konstante
    console_level = LOG_LEVELS.get(initial_console_level_str.upper(), logging.INFO)
    try:
        # Schließe alten Handler, falls vorhanden
        for h in logger.handlers[:]:
             if isinstance(h, logging.StreamHandler):
                  logger.removeHandler(h)
                  h.close()
                  print("Alten ConsoleHandler entfernt.") # Debug
                  break # Annahme: nur ein ConsoleHandler

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(console_level) # Setze initialen Level
    except Exception as e:
         print(f"FEHLER: Konnte Konsolen-Handler nicht erstellen: {e}")
         console_handler = None

    # Logger Konfiguration
    logger.setLevel(logging.DEBUG) # Logger selbst fängt alles ab DEBUG auf
    logger.handlers.clear() # Entferne alle alten Handler sicherheitshalber
    if file_handler: logger.addHandler(file_handler)
    if console_handler: logger.addHandler(console_handler) # Füge neuen Handler hinzu

    # Initiale Log-Nachrichten (werden jetzt mit korrektem Level ausgegeben)
    logger.info("="*20 + " Logging gestartet " + "="*20)
    logger.info(f"Logdatei: {log_filename}")
    logger.info(f"Konsolen Log-Level initialisiert auf: {logging.getLevelName(console_level)}")
    if not file_handler: logger.warning("Dateilogging ist aufgrund eines Fehlers deaktiviert.")

    # Gebe Logger und die erstellten Handler zurück
    return logger, console_handler, file_handler

# Initialisierung nicht mehr hier, wird von main.py gesteuert
