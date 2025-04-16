# -*- coding: utf-8 -*-
"""
Constants for the EZ STT Logger application.
Paths are relative to the project's main directory (where main.py is located).
"""
import os
import logging  # Import logging for level constants

# --- Directories ---
CONFIG_DIR = "config"
FILTER_DIR = "filter"
LOG_DIR = "logs"
LANGUAGE_DIR = "language"

# --- File paths ---
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
KEY_FILE = os.path.join(CONFIG_DIR, "secret.key")
FILTER_FILE = os.path.join(FILTER_DIR, "filter_patterns.txt")
FILTER_FILE_EL = os.path.join(FILTER_DIR, "filter_patterns_el.txt")
REPLACEMENTS_FILE = os.path.join(FILTER_DIR, "replacements.json")
ICON_FILE = "logo.ico"
DEFAULT_TRANSCRIPTION_FILE = "transcription_log.txt"

# --- Languages ---
DEFAULT_LANGUAGE = "de"
SUPPORTED_LANGUAGES = {"de": "Deutsch", "en": "English"}

# --- Logging --- NEW SECTION ---
DEFAULT_LOG_LEVEL = "INFO"  # Default level for the console
LOG_LEVELS = {  # Mapping from string to logging level constant
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
# List of level names (strings) for GUI selection
LOG_LEVEL_NAMES = list(LOG_LEVELS.keys())

# --- Network settings ---
WEBSOCKET_PORT = 8765
DEFAULT_STREAMERBOT_WS_URL = "ws://127.0.0.1:1337/"

# --- Default values & configuration ---
DEFAULT_STT_PREFIX = "StreamerXY speaks: "
APP_VERSION = "1.1.3.2"  # Updated version
DEFAULT_SAMPLERATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_ENERGY_THRESHOLD = 50
DEFAULT_MIN_BUFFER_SEC = 5.0
DEFAULT_SILENCE_SEC = 2.0
DEFAULT_ELEVENLABS_MODEL = "scribe_v1"
DEFAULT_LOCAL_MODEL = "base"
DEFAULT_OUTPUT_FORMAT = "txt"

# --- Default filters (if file doesn't exist) ---
DEFAULT_FILTER_PATTERNS_STR = [
    r"subtitles by", r"subs by", r"transcription by", r"amara\.org",
    r"www\.zeoranger\.co\.uk", r"ESO", r"googleusercontent\.com",
    r"new thinking allowed foundation", r"touhou project",
    r"transcription outsourcing, llc", r"learn english for free",
    r"engvid\.com", r"Stille und Hintergrundgeräusche",
    r"^\s*you\s*$", r"^\s*me\s*$", r"^\s*thank you\.?\s*$",
    r"^\s*bye-bye\.?\s*$", r"^\s*\[.*musik.*\]\s*$", r"^\s*\(.*applaus.*\)\s*$",
]

# --- Default replacements (if file doesn't exist) ---
DEFAULT_REPLACEMENTS = {
    # Replace common mishearings/misspellings of "StreamerXY"
    # (?i) = ignore case, \b = word boundary, \s* = any number of whitespace
    r"(?i)\bStreamer\s*X\s*Y\b": "StreamerXY",      # e.g. Streamer X Y, Streamer XY
    r"(?i)\bStreamer\s*Ex\s*Why\b": "StreamerXY",   # e.g. Streamer Ex Why
    r"(?i)\bStreamer\s*ix\s*why\b": "StreamerXY",   # e.g. Streamer ix why
    # Add other common errors here as needed
}

# --- Available local models ---
AVAILABLE_LOCAL_MODELS = ["tiny", "base", "small", "medium", "large"]