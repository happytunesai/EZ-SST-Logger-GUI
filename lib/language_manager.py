# -*- coding: utf-8 -*-
"""
Handles loading and retrieving language resources.
"""
import json
import os
from lib.logger_setup import logger
from lib.constants import LANGUAGE_DIR, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

# Global variables for the currently loaded language dictionary
current_lang_dict = {}
current_lang_code = DEFAULT_LANGUAGE

def load_language(lang_code):
    """
    Loads a language file (JSON) and sets it as the active dictionary.
    Falls back to the default language if the requested file is missing.
    """
    global current_lang_dict, current_lang_code

    if lang_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"Language code '{lang_code}' is not supported. Falling back to '{DEFAULT_LANGUAGE}'.")
        lang_code = DEFAULT_LANGUAGE

    filepath = os.path.join(LANGUAGE_DIR, f"{lang_code}.json")
    default_filepath = os.path.join(LANGUAGE_DIR, f"{DEFAULT_LANGUAGE}.json")
    loaded_dict = {}

    try:
        logger.info(f"Loading language file: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_dict = json.load(f)
        current_lang_code = lang_code
        logger.info(f"Language '{lang_code}' loaded successfully.")

    except FileNotFoundError:
        logger.error(f"Language file '{filepath}' not found.")
        if lang_code != DEFAULT_LANGUAGE:
            logger.warning(f"Attempting fallback to default language '{DEFAULT_LANGUAGE}'...")
            try:
                with open(default_filepath, 'r', encoding='utf-8') as f:
                    loaded_dict = json.load(f)
                current_lang_code = DEFAULT_LANGUAGE
                logger.info(f"Default language '{DEFAULT_LANGUAGE}' loaded successfully.")
            except FileNotFoundError:
                logger.error(f"Default language file '{default_filepath}' also not found! UI texts may be missing.")
                current_lang_code = None
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading/parsing default language file '{default_filepath}': {e}")
                current_lang_code = None
        else:
            current_lang_code = None

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading/parsing language file '{filepath}': {e}")
        current_lang_code = None

    current_lang_dict = loaded_dict
    return loaded_dict

def get_string(key, **kwargs):
    """
    Retrieves a string from the current language dictionary using a key.
    Supports formatting with optional keyword arguments.

    Args:
        key (str): The translation key.
        **kwargs: Optional format parameters.

    Returns:
        str: The translated and formatted string, or the key itself on failure.
    """
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
    load_language(lang_code)

def tr(key, **kwargs):
    """
    Shortcut for get_string – usable globally in the app.
    """
    return get_string(key, **kwargs)
