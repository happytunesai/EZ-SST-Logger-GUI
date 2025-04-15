# -*- coding: utf-8 -*-
"""
Konstanten für die EZ STT Logger Anwendung.
Pfade sind relativ zum Projekt-Hauptverzeichnis (wo main.py liegt).
"""
import os
import logging # Importiere logging für Level-Konstanten

# --- Verzeichnisse ---
CONFIG_DIR = "config"
FILTER_DIR = "filter"
LOG_DIR = "logs"
LANGUAGE_DIR = "language"

# --- Dateipfade ---
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
KEY_FILE = os.path.join(CONFIG_DIR, "secret.key")
FILTER_FILE = os.path.join(FILTER_DIR, "filter_patterns.txt")
FILTER_FILE_EL = os.path.join(FILTER_DIR, "filter_patterns_el.txt")
REPLACEMENTS_FILE = os.path.join(FILTER_DIR, "replacements.json")
ICON_FILE = "logo.ico"
DEFAULT_TRANSCRIPTION_FILE = "transcription_log.txt"

# --- Sprachen ---
DEFAULT_LANGUAGE = "de"
SUPPORTED_LANGUAGES = {"de": "Deutsch", "en": "English"}

# --- Logging --- NEUER ABSCHNITT ---
DEFAULT_LOG_LEVEL = "INFO" # Standard-Level für die Konsole
LOG_LEVELS = { # Mapping von String zu logging Level Konstante
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
# Liste der Level-Namen (Strings) für die GUI-Auswahl
LOG_LEVEL_NAMES = list(LOG_LEVELS.keys())

# --- Netzwerkeinstellungen ---
WEBSOCKET_PORT = 8765
DEFAULT_STREAMERBOT_WS_URL = "ws://127.0.0.1:1337/"

# --- Standardwerte & Konfiguration ---
DEFAULT_STT_PREFIX = "Here speaks StreamerXY and this is the SST message: "
APP_VERSION = "1.1.1" # Updated version
DEFAULT_SAMPLERATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_ENERGY_THRESHOLD = 50
DEFAULT_MIN_BUFFER_SEC = 5.0
DEFAULT_SILENCE_SEC = 2.0
DEFAULT_ELEVENLABS_MODEL = "scribe_v1"
DEFAULT_LOCAL_MODEL = "base"
DEFAULT_OUTPUT_FORMAT = "txt"

# --- Standard-Filter (wenn Datei nicht existiert) ---
DEFAULT_FILTER_PATTERNS_STR = [
    r"subtitles by", r"subs by", r"transcription by", r"amara\.org",
    r"www\.zeoranger\.co\.uk", r"ESO", r"googleusercontent\.com",
    r"new thinking allowed foundation", r"touhou project",
    r"transcription outsourcing, llc", r"learn english for free",
    r"engvid\.com", r"Stille und Hintergrundgeräusche",
    r"^\s*you\s*$", r"^\s*me\s*$", r"^\s*thank you\.?\s*$",
    r"^\s*bye-bye\.?\s*$", r"^\s*\[.*musik.*\]\s*$", r"^\s*\(.*applaus.*\)\s*$",
]

# --- Standard-Ersetzungen (wenn Datei nicht existiert) ---
DEFAULT_REPLACEMENTS = {
    # Ersetze gängige Falschhörungen/Schreibweisen von "StreamerXY"
    # (?i) = ignoriere Groß/Kleinschreibung, \b = Wortgrenze, \s* = beliebig viele Leerzeichen
    r"(?i)\bStreamer\s*X\s*Y\b": "StreamerXY",      # z.B. Streamer X Y, Streamer XY
    r"(?i)\bStreamer\s*Ex\s*Why\b": "StreamerXY",   # z.B. Streamer Ex Why
    r"(?i)\bStreamer\s*ix\s*why\b": "StreamerXY",   # z.B. Streamer ix why
    # Füge hier bei Bedarf weitere häufige Fehler hinzu
}

# --- Verfügbare lokale Modelle ---
AVAILABLE_LOCAL_MODELS = ["tiny", "base", "small", "medium", "large"]
