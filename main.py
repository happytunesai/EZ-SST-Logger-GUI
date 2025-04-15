# -*- coding: utf-8 -*-
"""
Haupt-Einstiegspunkt für die EZ STT Logger Anwendung.
Initialisiert die notwendigen Komponenten und startet die GUI.
"""
import os
import sys
import queue
import threading
import time
import logging

# --- Lokale Modulimporte aus dem 'lib' Ordner ---
# Logger zuerst importieren, aber setup_logging erst später aufrufen
from lib.logger_setup import logger, setup_logging
from lib.constants import (
    CONFIG_FILE, KEY_FILE, LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR,
    DEFAULT_LANGUAGE, DEFAULT_LOG_LEVEL # Importiere Defaults
)
from lib.utils import load_or_generate_key
from lib.config_manager import load_config
from lib.gui import WhisperGUI
from lib.language_manager import set_current_language, load_language

# --- Globale Queues und Flags ---
audio_q = queue.Queue()
gui_q = queue.Queue()
streamerbot_queue = queue.Queue()
stop_recording_flag = threading.Event()
streamerbot_client_stop_event = threading.Event()

queues = { 'audio_q': audio_q, 'gui_q': gui_q, 'streamerbot_q': streamerbot_queue }
flags = { 'stop_recording': stop_recording_flag, 'stop_streamerbot': streamerbot_client_stop_event }
# FIX: Dictionary für Handler hinzugefügt
handlers = { 'console': None, 'file': None }

# --- Hauptfunktion ---
def main():
    """Initialisiert die Anwendung und startet die Hauptschleife."""
    global handlers # Erlaube Modifikation des globalen Handler-Dicts

    # Stelle sicher, dass die Verzeichnisse existieren
    for dir_path in [LOG_DIR, CONFIG_DIR, FILTER_DIR, LANGUAGE_DIR]:
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                # Loggen hier noch nicht möglich
                print(f"Verzeichnis '{dir_path}' erstellt oder existiert bereits.")
            except OSError as e:
                 print(f"FEHLER: Konnte Verzeichnis '{dir_path}' nicht erstellen: {e}")

    # Lade/Generiere Schlüssel
    encryption_key = load_or_generate_key(KEY_FILE, gui_q)
    if not encryption_key:
         print("KRITISCHER FEHLER: Konnte keinen Verschlüsselungsschlüssel laden/generieren.")
         # Hier evtl. sys.exit(1)?

    # Lade Konfiguration
    app_config = load_config(CONFIG_FILE, encryption_key)

    # --- Initialisiere Logging mit Level aus Config ---
    # FIX: Lese initialen Log-Level aus Config
    initial_log_level_str = app_config.get("log_level", DEFAULT_LOG_LEVEL)
    # FIX: Rufe setup_logging auf und erhalte die Handler zurück
    _, console_handler, file_handler = setup_logging(initial_console_level_str=initial_log_level_str)
    # FIX: Speichere Handler-Referenzen im Dictionary
    handlers['console'] = console_handler
    handlers['file'] = file_handler
    # Ab hier kann normal geloggt werden

    # Setze die initiale Sprache basierend auf der Konfiguration
    initial_lang_code = app_config.get("language_ui", DEFAULT_LANGUAGE)
    set_current_language(initial_lang_code)

    # Leere Logdatei beim Start, falls konfiguriert
    if app_config.get("clear_log_on_start", False):
        # FIX: Verwende Handler aus dem Dictionary
        log_file_path = handlers['file'].baseFilename if handlers['file'] else None
        if log_file_path and os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'w') as f: f.truncate(0)
                logger.info(f"Logdatei '{log_file_path}' wurde aufgrund der Konfiguration geleert.")
            except IOError as e: logger.error(f"Fehler beim Leeren der Logdatei '{log_file_path}': {e}")
            except Exception as e: logger.exception(f"Unerwarteter Fehler beim Leeren der Logdatei '{log_file_path}'")
        elif log_file_path: logger.warning(f"Logdatei '{log_file_path}' zum Leeren nicht gefunden.")
        else: logger.warning("Konnte Logdatei nicht leeren: Kein Dateihandler gefunden.")


    # Erstelle und starte die GUI-Anwendung
    try:
        logger.info("Starte die WhisperGUI...")
        # FIX: Übergib das handlers Dictionary an die GUI
        app = WhisperGUI(app_config, encryption_key, queues, flags, handlers)
        app.mainloop()
        logger.info("GUI Hauptschleife beendet.")
    except Exception as e:
         logger.exception("Schwerwiegender Fehler in der Hauptanwendungsschleife.")

# --- Standard Python Einstiegspunkt ---
if __name__ == '__main__':
    main()
    logger.info("main.py Skriptausführung beendet.")
    sys.exit(0)

