# -*- coding: utf-8 -*-
"""
Handles loading, discovering, validating and retrieving language resources.
"""
import json
import os
from lib.logger_setup import logger
# Importiere relevante Konstanten
from lib.constants import (
    LANGUAGE_DIR, DEFAULT_LANGUAGE,
    LANG_META_NAME_KEY, LANG_META_CODE_KEY, LANG_REFERENCE_CODE
)

# Globale Variablen für die aktuell geladene Sprache und gefundene Sprachen
current_lang_dict = {}
current_lang_code = DEFAULT_LANGUAGE
discovered_languages = {} # Wird von scan_languages gefüllt: {"de": "Deutsch", "en": "English", ...}
reference_language_keys = set() # Wird von scan_languages gefüllt

def validate_language_file(filepath, reference_keys):
    """
    Validates a language JSON file.

    Args:
        filepath (str): Path to the JSON file.
        reference_keys (set): A set of keys that must exist in the file.

    Returns:
        tuple: (is_valid, lang_code, lang_name) or (False, None, None)
               Returns validity status, language code, and display name if valid.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.warning(f"Validation failed: Content of '{filepath}' is not a JSON object.")
            return False, None, None

        # Check for metadata keys
        lang_name = data.get(LANG_META_NAME_KEY)
        lang_code = data.get(LANG_META_CODE_KEY)

        if not lang_name or not isinstance(lang_name, str):
            logger.warning(f"Validation failed: Missing or invalid '{LANG_META_NAME_KEY}' in '{filepath}'.")
            return False, None, None
        if not lang_code or not isinstance(lang_code, str):
            logger.warning(f"Validation failed: Missing or invalid '{LANG_META_CODE_KEY}' in '{filepath}'.")
            return False, None, None

        # Check if filename matches the code inside
        expected_filename = f"{lang_code}.json"
        if os.path.basename(filepath) != expected_filename:
            logger.warning(f"Validation warning: Filename '{os.path.basename(filepath)}' does not match language_code '{lang_code}' found inside.")

        # Check if all reference keys are present (only if reference_keys is not empty)
        if reference_keys: # Avoid checking if reference keys couldn't be loaded
            file_keys = set(data.keys())
            missing_keys = reference_keys - file_keys
            if missing_keys:
                logger.warning(f"Validation failed: Language file '{filepath}' is missing keys: {missing_keys}")
                return False, None, None

        logger.debug(f"Validation successful for '{filepath}' ({lang_code}: {lang_name}).")
        return True, lang_code, lang_name

    except FileNotFoundError:
        logger.error(f"Validation failed: File not found '{filepath}' (should not happen if called from scan).")
        return False, None, None
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Validation failed: Error reading/parsing '{filepath}': {e}")
        return False, None, None
    except Exception as e:
        logger.exception(f"Unexpected error validating '{filepath}'")
        return False, None, None


def scan_languages(ref_keys):
    """
    Scans the LANGUAGE_DIR for valid .json language files, validates them,
    and populates the discovered_languages dictionary.

    Args:
        ref_keys (set): A set of keys from the reference language file.

    Returns:
        dict: The dictionary of discovered valid languages (code: name).
    """
    global discovered_languages, reference_language_keys
    discovered_languages = {} # Reset on each scan
    reference_language_keys = ref_keys # Store reference keys globally
    logger.info(f"Scanning for language files in '{LANGUAGE_DIR}'...")

    if not os.path.isdir(LANGUAGE_DIR):
        logger.error(f"Language directory '{LANGUAGE_DIR}' not found. Cannot scan for languages.")
        return discovered_languages

    if not reference_language_keys:
         logger.warning(f"Reference language keys are empty. Validation might be incomplete.")
         # Proceed without key validation if reference failed, but still check metadata

    for filename in os.listdir(LANGUAGE_DIR):
        if filename.lower().endswith(".json"):
            filepath = os.path.join(LANGUAGE_DIR, filename)
            logger.debug(f"Found potential language file: {filename}")
            # Pass the reference keys for validation
            is_valid, lang_code, lang_name = validate_language_file(filepath, reference_language_keys)
            if is_valid:
                if lang_code in discovered_languages:
                     logger.warning(f"Duplicate language code '{lang_code}' found in '{filename}'. Previous entry '{discovered_languages[lang_code]}' will be overwritten.")
                discovered_languages[lang_code] = lang_name

    if not discovered_languages:
        logger.error(f"No valid language files found in '{LANGUAGE_DIR}'.")
    else:
        logger.info(f"Discovered valid languages: {discovered_languages}")

    return discovered_languages


# FIX: Add is_reference_load parameter
def load_language(lang_code, is_reference_load=False):
    """
    Loads a language file (JSON) based on its code and sets it as the active dictionary.
    Uses the dynamically discovered list and falls back to the default language,
    unless is_reference_load is True.
    """
    global current_lang_dict, current_lang_code

    available_langs = discovered_languages # Use the globally stored dict

    # FIX: Skip check against available_langs if loading the reference file
    if not is_reference_load:
        if lang_code not in available_langs:
            logger.warning(f"Requested language code '{lang_code}' not found or invalid. Trying fallback '{DEFAULT_LANGUAGE}'.")
            lang_code = DEFAULT_LANGUAGE
            if lang_code not in available_langs:
                 logger.error(f"Default language code '{DEFAULT_LANGUAGE}' also not found or invalid! No UI texts will be loaded.")
                 current_lang_dict = {}
                 current_lang_code = None
                 return current_lang_dict # Return empty dict

    # Proceed with loading the selected (or reference) language file
    filepath = os.path.join(LANGUAGE_DIR, f"{lang_code}.json")
    loaded_dict = {}

    try:
        logger.info(f"Loading language file: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_dict = json.load(f)
        # Only update globals if it's not the initial reference load OR
        # if it IS the reference load and it's also the default language
        if not is_reference_load or lang_code == DEFAULT_LANGUAGE:
             current_lang_code = lang_code
             current_lang_dict = loaded_dict
        logger.info(f"Language file '{filepath}' loaded successfully.")

    except FileNotFoundError:
         logger.error(f"Language file '{filepath}' not found!")
         # If reference load failed, return empty dict. Otherwise, clear globals.
         if is_reference_load:
             return {}
         else:
             current_lang_dict = {}
             current_lang_code = None
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading/parsing language file '{filepath}': {e}")
        if is_reference_load:
            return {}
        else:
            current_lang_dict = {}
            current_lang_code = None
    except Exception as e:
         logger.exception(f"Unexpected error loading language file '{filepath}'")
         if is_reference_load:
             return {}
         else:
             current_lang_dict = {}
             current_lang_code = None

    # Return the loaded dictionary (useful for reference key loading)
    # For normal loads, the globals current_lang_dict/current_lang_code are also set.
    return loaded_dict

def get_string(key, **kwargs):
    """
    Retrieves a string from the current language dictionary using a key.
    Supports formatting with optional keyword arguments.
    """
    # Fallback to key if dictionary is empty or key missing
    text = current_lang_dict.get(key, key)
    if not isinstance(text, str):
        logger.warning(f"Value for key '{key}' in language '{current_lang_code}' is not a string: {text}")
        return key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing formatting key '{e}' in string for key '{key}' (language: {current_lang_code}). Original: '{text}'")
        except Exception as e:
            logger.error(f"String formatting error for key '{key}': {e}. Original: '{text}'")
    return text

def set_current_language(lang_code):
    """
    Loads the given language and sets it as current.
    """
    # Call load_language normally (is_reference_load defaults to False)
    load_language(lang_code)

def tr(key, **kwargs):
    """
    Shortcut for get_string – usable globally in the app.
    """
    return get_string(key, **kwargs)

