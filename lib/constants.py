# -*- coding: utf-8 -*-
"""
Constants for the EZ STT Logger application.
Paths are relative to the project's main directory (where main.py is located).
"""
import os
import logging

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
FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html"

# --- Languages ---
DEFAULT_LANGUAGE = "en" # Fallback language code if detection or config fails
LANG_META_NAME_KEY = "language_name" # Key for the display name in the JSON
LANG_META_CODE_KEY = "language_code" # Key for the language code (e.g., "de") in the JSON
LANG_REFERENCE_CODE = "en" # Language file used as reference for validation (e.g., 'en.json')

# --- Logging ---
DEFAULT_LOG_LEVEL = "INFO"
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
LOG_LEVEL_NAMES = list(LOG_LEVELS.keys())

# --- Network settings ---
WEBSOCKET_PORT = 8765
DEFAULT_STREAMERBOT_WS_URL = "ws://127.0.0.1:1337/" # User's port from log
DEFAULT_REPLACEMENT_BOTNAME = "BotnameXY" # Default name for context menu replacement

# --- Appearance Settings ---
DEFAULT_APPEARANCE_MODE = "Dark"  # Options: "System", "Light", "Dark"
DEFAULT_COLOR_THEME = "pink"      # Options: "blue", "green", "dark-blue", or path/to/theme.json
AVAILABLE_APPEARANCE_MODES = ["System", "Light", "Dark"]
# In lib/constants.py

AVAILABLE_COLOR_THEMES = [ # themes form https://github.com/a13xe/CTkThemesPack?tab=readme-ov-file
    "autumn",
    "blue",          # Default theme
    "breeze",
    "carrot",
    "cherry",
    "coffee",
    "dark-blue",     # Default theme
    "green",         # Default theme
    "lavender",
    "marsh",
    "metal",
    "midnight",
    "orange",
    "patina",
    "pink",
    "rime",
    "rose",
    "sky",
    "violet",
    "yellow"
]
# --- Default values & configuration ---
DEFAULT_STT_PREFIX = "StreamerXY speaks: " # User's prefix from log
APP_VERSION = "1.1.8" # Updated version
DEFAULT_SAMPLERATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_ENERGY_THRESHOLD = 50
DEFAULT_MIN_BUFFER_SEC = 5.0
DEFAULT_SILENCE_SEC = 2.0
DEFAULT_ELEVENLABS_MODEL = "scribe_v1"
DEFAULT_LOCAL_MODEL = "base"
DEFAULT_OUTPUT_FORMAT = "txt"

# --- Default filters for OpenAI API (filter_patterns.txt) ---
DEFAULT_FILTER_PATTERNS_STR = [
    r'^\.+$',
    r"subtitles by", r"subs by", r"transcription by", r"amara\.org",
    r"www\.zeoranger\.co\.uk", r"ESO", r"googleusercontent\.com",
    r"new thinking allowed foundation", r"touhou project",
    r"transcription outsourcing, llc", r"learn english for free",
    r"engvid\.com", r"Stille und Hintergrundgeräusche",
    r"^\s*bye-bye\.?\s*$", r"^\s*\[.*musik.*\]\s*$", r"^\s*\(.*applaus.*\)\s*$",
]
# --- Default filters for ElevenLabs (filter_patterns_el.txt) ---
DEFAULT_FILTER_PATTERNS_EL = [
    r'^\.+$'
]
# --- Default replacements (if file doesn't exist) ---
DEFAULT_REPLACEMENTS = {
    # Replace common mishearings/misspellings of your "Botname"
    # (?i) = ignore case, \b = word boundary, \s* = any number of whitespace
    r"(?i)\bBotname\s*X\s*Y\b": "BotnameXY",
    r"(?i)\bBot name\s*Ex\s*Why\b": "BotnameXY",
    r"(?i)\bBot homee\s*ix\s*why\b": "BotnameXY",
    # Add other common errors here as needed
}

# --- Available local models ---
AVAILABLE_LOCAL_MODELS = ["tiny", "base", "small", "medium", "large"]
