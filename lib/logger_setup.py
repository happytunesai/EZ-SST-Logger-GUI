# -*- coding: utf-8 -*-
"""
Konfiguration des Logging-Systems für die Anwendung.
"""
import logging
import sys
import os
from datetime import datetime

# Importiere Konstanten
from lib.constants import LOG_DIR

# Globaler Logger - wird von setup_logging initialisiert
# Andere Module können ihn mit `from logger_setup import logger` importieren
logger = logging.getLogger("EZ_STT_Logger")

def setup_logging():
    """Konfiguriert das Logging-System und gibt den Logger zurück."""
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)-5.5s] %(threadName)s: %(message)s')

    # Stelle sicher, dass das Log-Verzeichnis existiert
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR)
        except OSError as e:
            print(f"FEHLER: Konnte Log-Verzeichnis '{LOG_DIR}' nicht erstellen: {e}")
            # Fallback zum aktuellen Verzeichnis, falls Erstellung fehlschlägt
            log_dir_path = "."
        else:
            log_dir_path = LOG_DIR
    else:
        log_dir_path = LOG_DIR

    log_filename = os.path.join(log_dir_path, f"ez_stt_logger_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

    # File Handler
    log_file_handler = None
    try:
        log_file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        log_file_handler.setFormatter(log_formatter)
        log_file_handler.setLevel(logging.DEBUG) # Alles in die Datei loggen
    except IOError as e:
        print(f"FEHLER: Konnte Logdatei '{log_filename}' nicht öffnen: {e}")

    # Console Handler
    log_console_handler = logging.StreamHandler(sys.stdout)
    log_console_handler.setFormatter(log_formatter)
    log_console_handler.setLevel(logging.INFO) # INFO und höher auf der Konsole anzeigen

    # Logger Konfiguration (verwendet den globalen Logger)
    logger.setLevel(logging.DEBUG) # Niedrigstes Level für den Logger selbst
    logger.handlers.clear() # Entferne evtl. vorhandene Handler (wichtig bei Re-Initialisierung)

    if log_file_handler:
        logger.addHandler(log_file_handler)
    logger.addHandler(log_console_handler)

    # Initiale Log-Nachrichten
    logger.info("="*20 + " Logging gestartet " + "="*20)
    logger.info(f"Logdatei: {log_filename}")
    if not log_file_handler:
         logger.warning("Dateilogging ist aufgrund eines Fehlers deaktiviert.")

    return logger # Gebe den konfigurierten Logger zurück (obwohl er global ist)

# Führe die Einrichtung beim Importieren des Moduls aus, um sicherzustellen, dass der Logger verfügbar ist.
# Dies ist eine gängige Methode, kann aber angepasst werden, wenn die Initialisierung später erfolgen soll.
setup_logging()

