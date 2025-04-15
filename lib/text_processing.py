# -*- coding: utf-8 -*-
"""
Funktionen zur Textverarbeitung: Laden/Anwenden von Filtern und Ersetzungen.
"""
import os
import re
import json

# Importiere Konstanten und Logger
from lib.constants import (
    FILTER_FILE, FILTER_FILE_EL, REPLACEMENTS_FILE,
    DEFAULT_FILTER_PATTERNS_STR, DEFAULT_REPLACEMENTS
)
from lib.logger_setup import logger

def load_filter_patterns(filter_path):
    """Lädt Regex-Filter-Patterns aus einer Datei."""
    patterns = []
    defaults_to_write = []

    # Bestimme, welche Standard-Patterns basierend auf dem Dateipfad verwendet werden sollen
    if filter_path == FILTER_FILE:
        defaults_to_write = DEFAULT_FILTER_PATTERNS_STR
    elif filter_path == FILTER_FILE_EL:
        # Derzeit keine spezifischen Standardfilter für ElevenLabs
        defaults_to_write = []

    # Erstelle die Datei mit Defaults, falls sie nicht existiert
    if not os.path.exists(filter_path):
        logger.info(f"Filterdatei '{filter_path}' nicht gefunden. Erstelle Datei mit Standardmustern (falls vorhanden)...")
        try:
            with open(filter_path, 'w', encoding='utf-8') as f:
                if defaults_to_write:
                    for pattern_str in defaults_to_write:
                        f.write(pattern_str + "\n")
                    logger.info(f"Standard-Filterdatei '{filter_path}' erstellt.")
                else:
                     logger.info(f"Leere Filterdatei '{filter_path}' erstellt (keine Defaults für diesen Typ).")
        except IOError as e:
            logger.error(f"Konnte Standardfilterdatei '{filter_path}' nicht erstellen: {e}")
            # Fallback: Kompiliere Standard-Patterns direkt, wenn Dateierstellung fehlschlug
            for pattern_str in defaults_to_write:
                try:
                    patterns.append(re.compile(pattern_str, re.IGNORECASE))
                except re.error as re_e:
                    logger.error(f"Ungültiges Standard-Regex '{pattern_str}': {re_e}")
            return patterns # Gebe kompilierte Defaults zurück

    # Lade Patterns aus der existierenden oder neu erstellten Datei
    logger.info(f"Lade Filter-Patterns aus '{filter_path}'...")
    try:
        with open(filter_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                pattern_str = line.strip()
                # Ignoriere leere Zeilen und Kommentare
                if pattern_str and not pattern_str.startswith('#'):
                    try:
                        # Kompiliere das Regex-Pattern (ignoriere Groß-/Kleinschreibung)
                        patterns.append(re.compile(pattern_str, re.IGNORECASE))
                    except re.error as e:
                        logger.warning(f"Ungültiges Regex in '{filter_path}' Zeile {i+1}: '{pattern_str}' - {e}. Wird ignoriert.")
        logger.info(f"{len(patterns)} Filter-Patterns aus '{os.path.basename(filter_path)}' geladen.")
    except IOError as e:
        logger.error(f"Konnte Filterdatei '{filter_path}' nicht lesen: {e}. Keine Filter für diesen Typ aktiv.")
    except Exception as e:
         logger.exception(f"Unerwarteter Fehler beim Laden der Filterdatei '{filter_path}'")

    return patterns

def filter_transcription(text, patterns_to_use, filter_parentheses):
    """
    Wendet die übergebenen Filter an und entfernt optional Text in Klammern.
    Args:
        text (str): Der zu filternde Text.
        patterns_to_use (list): Eine Liste kompilierter Regex-Objekte.
        filter_parentheses (bool): Ob Inhalte in (...) und [...] entfernt werden sollen.
    Returns:
        str: Der gefilterte Text.
    """
    if not text:
        return "" # Gebe leeren String zurück, wenn Eingabe leer ist

    cleaned_text = text
    # Optional: Entferne zuerst Inhalte in Klammern
    if filter_parentheses:
        # Entferne Inhalte in runden Klammern, inklusive der Klammern selbst
        cleaned_text = re.sub(r"\([^)]*\)", "", cleaned_text).strip()
        # Entferne auch Inhalte in eckigen Klammern (oft für Geräusche/Musik)
        cleaned_text = re.sub(r"\[[^\]]*\]", "", cleaned_text).strip()

    # Teile in Zeilen auf, um zeilenweise zu filtern
    lines = cleaned_text.splitlines()
    filtered_lines = []

    for line in lines:
        temp_line = line.strip() # Arbeite mit bereinigten Zeilen

        # Überspringe leere Zeilen, die durch Filterung oder Originaleingabe entstanden sind
        if not temp_line:
            continue

        is_unwanted = False
        # Wende Regex-Filter an, wenn Patterns geladen sind
        if patterns_to_use:
            # Prüfe, ob irgendein Pattern auf die aktuelle Zeile passt
            is_unwanted = any(pattern.search(temp_line) for pattern in patterns_to_use)

        # Behalte die Zeile, wenn sie nicht leer ist und von keinem Filter getroffen wird
        if not is_unwanted:
            filtered_lines.append(temp_line)
        else:
            logger.debug(f"Zeile gefiltert: '{temp_line}'")

    # Füge die verbleibenden Zeilen wieder zusammen
    final_text = "\n".join(filtered_lines).strip()
    logger.debug(f"Filter Ergebnis: '{final_text[:100]}...'")
    return final_text

def load_replacements(replacements_path):
    """Lädt Ersetzungsregeln (Regex-Pattern -> Ersetzungsstring) aus einer JSON-Datei."""
    # Erstelle eine Standard-Ersetzungsdatei, falls sie nicht existiert
    if not os.path.exists(replacements_path):
        logger.info(f"Ersetzungsdatei '{replacements_path}' nicht gefunden. Erstelle Beispieldatei...")
        try:
            with open(replacements_path, 'w', encoding='utf-8') as f:
                # Schreibe das Standard-Ersetzungs-Dictionary in die neue Datei
                json.dump(DEFAULT_REPLACEMENTS, f, indent=4, ensure_ascii=False)
            logger.info(f"Beispiel-Ersetzungsdatei '{replacements_path}' erstellt.")
            return DEFAULT_REPLACEMENTS # Gebe die Defaults zurück, die zum Erstellen verwendet wurden
        except IOError as e:
            logger.error(f"Konnte Beispiel-Ersetzungsdatei '{replacements_path}' nicht erstellen: {e}")
            return {} # Gebe leeres Dict bei Erstellungsfehler zurück

    # Lade Ersetzungen aus der existierenden Datei
    logger.info(f"Lade Ersetzungen aus '{replacements_path}'...")
    try:
        with open(replacements_path, 'r', encoding='utf-8') as f:
            replacements = json.load(f)
        # Validiere, dass die geladenen Daten ein Dictionary sind
        if not isinstance(replacements, dict):
            logger.error(f"Inhalt von '{replacements_path}' ist kein gültiges JSON-Objekt (Dictionary erwartet).")
            return {} # Gebe leeres Dict zurück, wenn Format falsch ist
        logger.info(f"{len(replacements)} Ersetzungsregeln aus '{replacements_path}' geladen.")
        return replacements
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Konnte Ersetzungsdatei '{replacements_path}' nicht lesen oder parsen: {e}. Keine Ersetzungen aktiv.")
        return {} # Gebe leeres Dict bei Lese-/Parse-Fehler zurück
    except Exception as e:
        logger.exception(f"Unerwarteter Fehler beim Laden der Ersetzungen aus '{replacements_path}'")
        return {} # Gebe leeres Dict bei unerwartetem Fehler zurück

def save_replacements(replacements_dict, replacements_path):
    """
    Speichert das Ersetzungs-Dictionary in einer JSON-Datei und mischt es mit vorhandenem Inhalt.
    Gibt True bei Erfolg zurück, False bei Fehler.
    """
    logger.info(f"Speichere Ersetzungen in '{replacements_path}'...")
    merged_replacements = {}
    try:
        # Lade existierende Ersetzungen, falls die Datei existiert
        if os.path.exists(replacements_path):
            try:
                with open(replacements_path, 'r', encoding='utf-8') as f:
                    existing_replacements = json.load(f)
                    if isinstance(existing_replacements, dict):
                        merged_replacements = existing_replacements
                    else:
                        logger.warning(f"Bestehende Datei '{replacements_path}' enthält kein gültiges Dictionary. Wird überschrieben.")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Konnte bestehende Ersetzungen aus '{replacements_path}' nicht laden/parsen ({e}). Datei wird überschrieben.")

        # Aktualisiere das geladene/leere Dictionary mit den neuen Ersetzungen
        # Neue Regeln überschreiben existierende mit demselben Schlüssel (Pattern)
        merged_replacements.update(replacements_dict)

        # Schreibe das gemischte Dictionary zurück in die Datei
        with open(replacements_path, 'w', encoding='utf-8') as f:
            json.dump(merged_replacements, f, indent=4, ensure_ascii=False)
        logger.info(f"{len(merged_replacements)} Ersetzungsregeln in '{replacements_path}' gespeichert.")
        return True # Erfolg signalisieren
    except IOError as e:
        logger.error(f"Konnte Ersetzungsdatei '{replacements_path}' nicht schreiben: {e}")
        # GUI-Nachricht wird von der aufrufenden Funktion (GUI) gesendet
        return False # Fehler signalisieren
    except Exception as e:
        logger.exception("Unerwarteter Fehler beim Speichern der Ersetzungen")
        return False # Fehler signalisieren

def apply_replacements(text, replacements_dict):
    """Wendet die übergebenen Ersetzungsregeln auf den gegebenen Text an."""
    if not text or not replacements_dict:
        return text # Gebe Originaltext zurück, wenn kein Text oder keine Ersetzungen

    modified_text = text
    # Iteriere durch jedes Pattern-Ersetzungs-Paar im Dictionary
    for pattern_str, replacement_str in replacements_dict.items():
        try:
            # Führe Regex-Ersetzung durch (ignoriere Groß-/Kleinschreibung)
            modified_text = re.sub(pattern_str, replacement_str, modified_text, flags=re.IGNORECASE)
        except re.error as e:
            # Logge Warnung, wenn ein Regex-Pattern ungültig ist
            logger.warning(f"Fehler beim Anwenden der Regex-Ersetzung '{pattern_str}' -> '{replacement_str}': {e}")
        except Exception as e:
            # Logge Warnung für jeden anderen unerwarteten Fehler während der Ersetzung
            logger.warning(f"Unerwarteter Fehler bei der Ersetzung '{pattern_str}' -> '{replacement_str}': {e}")

    if modified_text != text:
        logger.debug(f"Ersetzungen angewendet. Ergebnis: '{modified_text[:100]}...'")
    return modified_text

