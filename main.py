# -*- coding: utf-8 -*-
"""
Haupt-Einstiegspunkt für die EZ STT Logger Anwendung.
Initialisiert die notwendigen Komponenten und startet die GUI.
"""
import os
import sys
import queue
import threading
import time # Für time.sleep am Ende, falls nötig
import logging

# --- Lokale Modulimporte aus dem 'lib' Ordner ---
from lib.logger_setup import setup_logging, logger # Logger initialisieren lassen
from lib.constants import CONFIG_FILE, KEY_FILE, LOG_DIR, CONFIG_DIR, FILTER_DIR # Benötigte Konstanten + Dirs
from lib.utils import load_or_generate_key # Schlüssel-Funktion
from lib.config_manager import load_config, save_config # Config-Funktionen
from lib.gui import WhisperGUI # Die Haupt-GUI-Klasse

# --- Globale Queues und Flags ---
audio_q = queue.Queue()
gui_q = queue.Queue()
streamerbot_queue = queue.Queue()
stop_recording_flag = threading.Event()
streamerbot_client_stop_event = threading.Event()

queues = {
    'audio_q': audio_q,
    'gui_q': gui_q,
    'streamerbot_q': streamerbot_queue
}
flags = {
    'stop_recording': stop_recording_flag,
    'stop_streamerbot': streamerbot_client_stop_event
}

# --- Hauptfunktion ---
def main():
    """Initialisiert die Anwendung und startet die Hauptschleife."""
    # Logger ist bereits durch Import von logger_setup initialisiert

    # Stelle sicher, dass die Verzeichnisse existieren
    # (LOG_DIR wird von logger_setup geprüft, hier für config/filter)
    for dir_path in [LOG_DIR, CONFIG_DIR, FILTER_DIR]:
        if not os.path.exists(dir_path):
            try:
                # exist_ok=True verhindert Fehler, falls Ordner doch schon existiert
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"Verzeichnis '{dir_path}' erstellt oder existiert bereits.")
            except OSError as e:
                 logger.error(f"Konnte Verzeichnis '{dir_path}' nicht erstellen: {e}")

    # Lade oder generiere Verschlüsselungsschlüssel
    encryption_key = load_or_generate_key(KEY_FILE, gui_q)
    if not encryption_key:
         logger.critical("FEHLER: Konnte keinen Verschlüsselungsschlüssel laden oder generieren. API Keys unsicher!")

    # Lade Konfiguration mit dem Schlüssel
    app_config = load_config(CONFIG_FILE, encryption_key)

    # Leere Logdatei beim Start, falls konfiguriert
    if app_config.get("clear_log_on_start", False):
        log_file_path = None
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                 log_file_path = handler.baseFilename
                 break
        if log_file_path and os.path.exists(log_file_path): # Prüfe Existenz vor dem Öffnen
            try:
                with open(log_file_path, 'w') as f: f.truncate(0)
                logger.info(f"Logdatei '{log_file_path}' wurde aufgrund der Konfiguration geleert.")
            except IOError as e: logger.error(f"Fehler beim Leeren der Logdatei '{log_file_path}': {e}")
            except Exception as e: logger.exception(f"Unerwarteter Fehler beim Leeren der Logdatei '{log_file_path}'")
        elif log_file_path:
             logger.warning(f"Logdatei '{log_file_path}' zum Leeren nicht gefunden.")
        else:
             logger.warning("Konnte Logdatei nicht leeren: Kein Dateihandler gefunden.")

    # Erstelle und starte die GUI-Anwendung
    try:
        logger.info("Starte die WhisperGUI...")
        app = WhisperGUI(app_config, encryption_key, queues, flags)
        app.mainloop()
        logger.info("GUI Hauptschleife beendet.")
    except Exception as e:
         logger.exception("Schwerwiegender Fehler in der Hauptanwendungsschleife.")

# --- Standard Python Einstiegspunkt ---
if __name__ == '__main__':
    main()
    logger.info("main.py Skriptausführung beendet.")
    sys.exit(0)
