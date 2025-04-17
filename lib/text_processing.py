# -*- coding: utf-8 -*-
"""
Functions for text processing: Loading/applying filters and replacements.
"""
import os
import re
import json

# Import constants and logger
from lib.constants import (
    FILTER_FILE, FILTER_FILE_EL, REPLACEMENTS_FILE,
    DEFAULT_FILTER_PATTERNS_STR,DEFAULT_FILTER_PATTERNS_EL, DEFAULT_REPLACEMENTS
)
from lib.logger_setup import logger
from lib.language_manager import tr

def load_filter_patterns(filter_path):
    """Loads regex filter patterns from a file."""
    patterns = []
    defaults_to_write = []

    # Determine which default patterns to use based on file path
    if filter_path == FILTER_FILE:
        defaults_to_write = DEFAULT_FILTER_PATTERNS_STR
    elif filter_path == FILTER_FILE_EL:
        defaults_to_write = DEFAULT_FILTER_PATTERNS_EL

    # Create the file with defaults if it doesn't exist
    if not os.path.exists(filter_path):
        logger.info(tr("log_tp_filter_file_not_found", filter_path=filter_path))
        try:
            with open(filter_path, 'w', encoding='utf-8') as f:
                if defaults_to_write:
                    for pattern_str in defaults_to_write:
                        f.write(pattern_str + "\n")
                    logger.info(tr("log_tp_filter_default_created", filter_path=filter_path))
                else:
                    logger.info(tr("log_tp_filter_empty_created", filter_path=filter_path))
        except IOError as e:
            logger.error(tr("log_tp_filter_create_error", filter_path=filter_path, error=str(e)))
            # Fallback: Compile default patterns directly if file creation failed
            for pattern_str in defaults_to_write:
                try:
                    patterns.append(re.compile(pattern_str, re.IGNORECASE))
                except re.error as re_e:
                    logger.error(tr("log_tp_filter_invalid_regex", pattern=pattern_str, error=str(re_e)))
            return patterns # Return compiled defaults

    # Load patterns from existing or newly created file
    logger.info(tr("log_tp_filter_loading", filter_path=filter_path))
    try:
        with open(filter_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                pattern_str = line.strip()
                # Ignore empty lines and comments
                if pattern_str and not pattern_str.startswith('#'):
                    try:
                        # Compile regex pattern (ignore case)
                        patterns.append(re.compile(pattern_str, re.IGNORECASE))
                    except re.error as e:
                        logger.warning(tr("log_tp_filter_invalid_line", 
                                          filter_path=filter_path, 
                                          line=i+1, 
                                          pattern=pattern_str, 
                                          error=str(e)))
        logger.info(tr("log_tp_filter_loaded", 
                      count=len(patterns), 
                      filename=os.path.basename(filter_path)))
    except IOError as e:
        logger.error(tr("log_tp_filter_read_error", filter_path=filter_path, error=str(e)))
    except Exception as e:
        logger.exception(tr("log_tp_filter_load_unexpected", filter_path=filter_path))

    return patterns

def filter_transcription(text, patterns_to_use, filter_parentheses):
    """
    Applies the provided filters and optionally removes text in parentheses.
    Args:
        text (str): The text to filter.
        patterns_to_use (list): A list of compiled regex objects.
        filter_parentheses (bool): Whether to remove content in (...) and [...].
    Returns:
        str: The filtered text.
    """
    if not text:
        return "" # Return empty string if input is empty

    cleaned_text = text
    # Optional: First remove contents in parentheses
    if filter_parentheses:
        # Remove content in round parentheses, including the parentheses themselves
        cleaned_text = re.sub(r"\([^)]*\)", "", cleaned_text).strip()
        # Also remove content in square brackets (often for sounds/music)
        cleaned_text = re.sub(r"\[[^\]]*\]", "", cleaned_text).strip()

    # Split into lines to filter line by line
    lines = cleaned_text.splitlines()
    filtered_lines = []

    for line in lines:
        temp_line = line.strip() # Work with cleaned lines

        # Skip empty lines created by filtering or from original input
        if not temp_line:
            continue

        is_unwanted = False
        # Apply regex filters if patterns are loaded
        if patterns_to_use:
            # Check if any pattern matches the current line
            is_unwanted = any(pattern.search(temp_line) for pattern in patterns_to_use)

        # Keep the line if it's not empty and not matched by any filter
        if not is_unwanted:
            filtered_lines.append(temp_line)
        else:
            logger.debug(f"Line filtered: '{temp_line}'")

    # Rejoin the remaining lines
    final_text = "\n".join(filtered_lines).strip()
    logger.debug(tr("log_tp_filter_applied", result=final_text[:100] + "..." if len(final_text) > 100 else final_text))
    return final_text

def load_replacements(replacements_path):
    """Loads replacement rules (regex pattern -> replacement string) from a JSON file."""
    # Create a default replacement file if it doesn't exist
    if not os.path.exists(replacements_path):
        logger.info(tr("log_tp_replacements_file_not_found", replacements_path=replacements_path))
        try:
            with open(replacements_path, 'w', encoding='utf-8') as f:
                # Write the default replacement dictionary to the new file
                json.dump(DEFAULT_REPLACEMENTS, f, indent=4, ensure_ascii=False)
            logger.info(tr("log_tp_replacements_created", replacements_path=replacements_path))
            return DEFAULT_REPLACEMENTS # Return the defaults used for creation
        except IOError as e:
            logger.error(tr("log_tp_replacements_create_error", replacements_path=replacements_path, error=str(e)))
            return {} # Return empty dict on creation error

    # Load replacements from the existing file
    logger.info(tr("log_tp_replacements_loading", replacements_path=replacements_path))
    try:
        with open(replacements_path, 'r', encoding='utf-8') as f:
            replacements = json.load(f)
        # Validate that the loaded data is a dictionary
        if not isinstance(replacements, dict):
            logger.error(tr("log_tp_replacements_invalid_format", replacements_path=replacements_path))
            return {} # Return empty dict if format is wrong
        logger.info(tr("log_tp_replacements_loaded", count=len(replacements), replacements_path=replacements_path))
        return replacements
    except (json.JSONDecodeError, IOError) as e:
        logger.error(tr("log_tp_replacements_read_error", replacements_path=replacements_path, error=str(e)))
        return {} # Return empty dict on read/parse error
    except Exception as e:
        logger.exception(tr("log_tp_replacements_load_unexpected", replacements_path=replacements_path))
        return {} # Return empty dict on unexpected error

def save_replacements(replacements_dict, replacements_path):
    """
    Saves the replacement dictionary to a JSON file, merging with existing content.
    Returns True on success, False on error.
    """
    logger.info(tr("log_tp_replacements_saving", replacements_path=replacements_path))
    merged_replacements = {}
    try:
        # Load existing replacements if the file exists
        if os.path.exists(replacements_path):
            try:
                with open(replacements_path, 'r', encoding='utf-8') as f:
                    existing_replacements = json.load(f)
                    if isinstance(existing_replacements, dict):
                        merged_replacements = existing_replacements
                    else:
                        logger.warning(tr("log_tp_replacements_merge_error", replacements_path=replacements_path))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load/parse existing replacements from '{replacements_path}' ({e}). File will be overwritten.")

        # Update the loaded/empty dictionary with new replacements
        # New rules overwrite existing ones with the same key (pattern)
        merged_replacements.update(replacements_dict)

        # Write the merged dictionary back to the file
        with open(replacements_path, 'w', encoding='utf-8') as f:
            json.dump(merged_replacements, f, indent=4, ensure_ascii=False)
        logger.info(tr("log_tp_replacements_saved", count=len(merged_replacements), replacements_path=replacements_path))
        return True # Signal success
    except IOError as e:
        logger.error(tr("log_tp_replacements_save_error", replacements_path=replacements_path, error=str(e)))
        # GUI message will be sent by the calling function (GUI)
        return False # Signal error
    except Exception as e:
        logger.exception(tr("log_tp_replacements_save_unexpected"))
        return False # Signal error

def apply_replacements(text, replacements_dict):
    """Applies the provided replacement rules to the given text."""
    if not text or not replacements_dict:
        return text # Return original text if no text or no replacements

    modified_text = text
    # Iterate through each pattern-replacement pair in the dictionary
    for pattern_str, replacement_str in replacements_dict.items():
        try:
            # Perform regex replacement (ignore case)
            modified_text = re.sub(pattern_str, replacement_str, modified_text, flags=re.IGNORECASE)
        except re.error as e:
            # Log warning if a regex pattern is invalid
            logger.warning(tr("log_tp_replacements_rule_error", 
                             pattern=pattern_str, 
                             replacement=replacement_str, 
                             error=str(e)))
        except Exception as e:
            # Log warning for any other unexpected error during replacement
            logger.warning(tr("log_tp_replacements_unexpected_error", 
                             pattern=pattern_str, 
                             replacement=replacement_str, 
                             error=str(e)))

    if modified_text != text:
        logger.debug(tr("log_tp_replacements_applied", 
                       result=modified_text[:100] + "..." if len(modified_text) > 100 else modified_text))
    return modified_text