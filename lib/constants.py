# -*- coding: utf-8 -*-
"""
Konstanten für die EZ STT Logger Anwendung.
Pfade sind relativ zum Projekt-Hauptverzeichnis (wo main.py liegt).
"""
import os # Hinzugefügt für os.path.join

# --- Verzeichnisse ---
CONFIG_DIR = "config"
FILTER_DIR = "filter"
LOG_DIR = "logs"

# --- Dateipfade ---
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
KEY_FILE = os.path.join(CONFIG_DIR, "secret.key")
FILTER_FILE = os.path.join(FILTER_DIR, "filter_patterns.txt")
FILTER_FILE_EL = os.path.join(FILTER_DIR, "filter_patterns_el.txt")
REPLACEMENTS_FILE = os.path.join(FILTER_DIR, "replacements.json")
ICON_FILE = "logo.ico" # Pfad relativ zum Hauptverzeichnis
DEFAULT_TRANSCRIPTION_FILE = "transcription_log.txt"

# --- Netzwerkeinstellungen ---
WEBSOCKET_PORT = 8765
DEFAULT_STREAMERBOT_WS_URL = "ws://127.0.0.1:8080/"

# --- Standardwerte & Konfiguration ---
DEFAULT_STT_PREFIX = "Here speaks StreamerXY and this is the SST message: "
APP_VERSION = "0.9.7" # Updated version
DEFAULT_SAMPLERATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_ENERGY_THRESHOLD = 50 # Threshold for detecting sound (arbitrary scale)
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
    "(?i)Tuning[Ww]ay": "Botname",
    "(?i)Tuning way": "Botname",
    "(?i)Tun in Wah": "Botname",
    "(?i)Tuning Bay": "Botname",
    "(?i)Turing way": "Botname",
}

# --- Verfügbare lokale Modelle ---
AVAILABLE_LOCAL_MODELS = ["tiny", "base", "small", "medium", "large"]
