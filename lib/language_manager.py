# -*- coding: utf-8 -*-
"""
Verwaltet das Laden und Abrufen von Sprachressourcen.
"""
import json
import os
from lib.logger_setup import logger
from lib.constants import LANGUAGE_DIR, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

# Globale Variable für das aktuell geladene Sprachwörterbuch
# Alternativ könnte dies in einer Klasse gekapselt oder immer übergeben werden.
current_lang_dict = {}
current_lang_code = DEFAULT_LANGUAGE

def load_language(lang_code):
    """
    Lädt eine Sprachdatei (JSON) und gibt das resultierende Dictionary zurück.
    Fällt auf die Standardsprache zurück, wenn die angeforderte Sprache nicht gefunden wird.
    """
    global current_lang_dict, current_lang_code
    if lang_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"Sprachcode '{lang_code}' nicht unterstützt. Fallback auf '{DEFAULT_LANGUAGE}'.")
        lang_code = DEFAULT_LANGUAGE

    filepath = os.path.join(LANGUAGE_DIR, f"{lang_code}.json")
    default_filepath = os.path.join(LANGUAGE_DIR, f"{DEFAULT_LANGUAGE}.json")
    loaded_dict = {}

    try:
        logger.info(f"Lade Sprachdatei: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_dict = json.load(f)
        current_lang_code = lang_code
        logger.info(f"Sprache '{lang_code}' erfolgreich geladen.")

    except FileNotFoundError:
        logger.error(f"Sprachdatei '{filepath}' nicht gefunden.")
        if lang_code != DEFAULT_LANGUAGE:
            logger.warning(f"Versuche Fallback auf Standardsprache '{DEFAULT_LANGUAGE}'...")
            try:
                with open(default_filepath, 'r', encoding='utf-8') as f:
                    loaded_dict = json.load(f)
                current_lang_code = DEFAULT_LANGUAGE
                logger.info(f"Standardsprache '{DEFAULT_LANGUAGE}' erfolgreich geladen.")
            except FileNotFoundError:
                logger.error(f"Standardsprachdatei '{default_filepath}' ebenfalls nicht gefunden! UI-Texte fehlen möglicherweise.")
                current_lang_code = None # Keine Sprache geladen
            except (json.JSONDecodeError, IOError) as e:
                 logger.error(f"Fehler beim Laden/Parsen der Standardsprachdatei '{default_filepath}': {e}")
                 current_lang_code = None
        else:
             # Default-Datei nicht gefunden
             current_lang_code = None

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Fehler beim Laden/Parsen der Sprachdatei '{filepath}': {e}")
        # Optional: Versuche Fallback auf Default hier auch?
        current_lang_code = None # Keine gültige Sprache geladen

    current_lang_dict = loaded_dict # Aktualisiere globales Dict
    return loaded_dict # Gebe das geladene Dict zurück (nützlich für GUI-Init)


def get_string(key, **kwargs):
    """
    Ruft einen String anhand seines Schlüssels aus dem aktuell geladenen Sprachwörterbuch ab.
    Unterstützt Keyword-Argumente für die Formatierung.

    Args:
        key (str): Der Schlüssel des gewünschten Strings.
        **kwargs: Optionale Keyword-Argumente zum Formatieren des Strings (z.B. version=...).

    Returns:
        str: Der übersetzte und formatierte String, oder der Schlüssel selbst bei Fehlern.
    """
    text = current_lang_dict.get(key, key) # Fallback auf den Schlüssel selbst, wenn nicht gefunden
    if not isinstance(text, str): # Falls der Wert im JSON keine Zeichenkette ist
        logger.warning(f"Wert für Schlüssel '{key}' in Sprache '{current_lang_code}' ist kein String: {text}")
        return key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Fehlender Formatierungsplatzhalter '{e}' im Text für Schlüssel '{key}' (Sprache: {current_lang_code}). Originaltext: '{text}'")
        except Exception as e:
            logger.error(f"Fehler bei String-Formatierung für Schlüssel '{key}': {e}. Originaltext: '{text}'")
    return text

def set_current_language(lang_code):
    """Lädt die angegebene Sprache und macht sie zur aktuellen Sprache."""
    load_language(lang_code)

# Lade die Standardsprache beim ersten Import des Moduls
# load_language(DEFAULT_LANGUAGE)
# Besser: In main.py laden, nachdem Config gelesen wurde, um User-Präferenz zu nutzen.

