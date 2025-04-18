# -*- coding: utf-8 -*-
"""
Functions for text processing: Loading/applying filters and replacements.
MODIFIED: Uses get_persistent_data_path for correct paths in PyInstaller builds
and tr() for logging.
"""
import os
import re
import json
import logging # Needed for fallback logger

# Import constants, logger, tr function, and the new path function
try:
    from lib.constants import (
        FILTER_FILE, FILTER_FILE_EL, REPLACEMENTS_FILE,
        DEFAULT_FILTER_PATTERNS_STR, DEFAULT_FILTER_PATTERNS_EL, DEFAULT_REPLACEMENTS
    )
    from lib.logger_setup import logger
    from lib.language_manager import tr
    # Import the function to get the correct path for persistent data
    from lib.utils import get_persistent_data_path
except ImportError as e:
    print(f"Import error in text_processing.py: {e}")
    # Define fallbacks for critical constants
    FILTER_FILE = "filter/filter_patterns.txt"
    FILTER_FILE_EL = "filter/filter_patterns_el.txt"
    REPLACEMENTS_FILE = "filter/replacements.json"
    DEFAULT_FILTER_PATTERNS_STR = []
    DEFAULT_FILTER_PATTERNS_EL = []
    DEFAULT_REPLACEMENTS = {}

    # Setup basic logging fallback
    logger = logging.getLogger("FallbackTextProcessingLogger")
    logging.basicConfig(level=logging.INFO) # Make fallback visible

    # Fallback translation function
    def tr(key, **kwargs):
        return key.format(**kwargs) if kwargs else key

    # Fallback path resolution for persistent data
    def get_persistent_data_path():
        # Best guess fallback
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as bundled executable: Use directory containing the executable
            return os.path.dirname(sys.executable)
        else:
            # Running from source: Try to guess project root from this file's location
            # This might be inaccurate depending on structure, but it's a fallback
            return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# --- Filter Patterns ---

def load_filter_patterns(filter_path_relative):
    """
    Loads regex filter patterns from a file stored in the persistent data location.
    Creates the file with defaults if it doesn't exist there.
    Args:
        filter_path_relative (str): The relative path (e.g., "filter/filter_patterns.txt").
    Returns:
        list: A list of compiled regex objects.
    """
    patterns = []
    defaults_to_write = []
    persistent_dir = get_persistent_data_path() # <-- Use new function
    absolute_filter_path = os.path.join(persistent_dir, filter_path_relative) # <-- Construct absolute path

    # Use tr() for logging path (NEW KEY NEEDED: log_tp_abs_filter_path)
    # logger.debug(tr("log_tp_abs_filter_path", path=absolute_filter_path))
    logger.debug(f"Using absolute filter path: {absolute_filter_path}") # Keep f-string if key missing

    # Determine which default patterns to use based on relative file path
    if filter_path_relative == FILTER_FILE:
        defaults_to_write = DEFAULT_FILTER_PATTERNS_STR
    elif filter_path_relative == FILTER_FILE_EL:
        defaults_to_write = DEFAULT_FILTER_PATTERNS_EL

    # Create the file with defaults at the persistent location if it doesn't exist
    if not os.path.exists(absolute_filter_path):
        logger.info(tr("log_tp_filter_file_not_found", filter_path=absolute_filter_path))
        try:
            # Ensure directory exists at the persistent location
            filter_dir = os.path.dirname(absolute_filter_path)
            if filter_dir:
                os.makedirs(filter_dir, exist_ok=True)

            # Write defaults to the new file
            with open(absolute_filter_path, 'w', encoding='utf-8') as f:
                if defaults_to_write:
                    for pattern_str in defaults_to_write:
                        f.write(pattern_str + "\n")
                    logger.info(tr("log_tp_filter_default_created", filter_path=absolute_filter_path))
                else:
                    logger.info(tr("log_tp_filter_empty_created", filter_path=absolute_filter_path))
        except IOError as e:
            logger.error(tr("log_tp_filter_create_error", filter_path=absolute_filter_path, error=str(e)))
            # Fallback: Compile default patterns directly if file creation failed
            for pattern_str in defaults_to_write:
                try:
                    patterns.append(re.compile(pattern_str, re.IGNORECASE))
                except re.error as re_e:
                    logger.error(tr("log_tp_filter_invalid_regex", pattern=pattern_str, error=str(re_e)))
            return patterns # Return compiled defaults

    # Load patterns from existing or newly created file at the persistent location
    logger.info(tr("log_tp_filter_loading", filter_path=absolute_filter_path))
    try:
        with open(absolute_filter_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                pattern_str = line.strip()
                # Ignore empty lines and comments
                if pattern_str and not pattern_str.startswith('#'):
                    try:
                        # Compile regex pattern (ignore case)
                        patterns.append(re.compile(pattern_str, re.IGNORECASE))
                    except re.error as e:
                        logger.warning(tr("log_tp_filter_invalid_line",
                                        filter_path=absolute_filter_path, # Log full path for context
                                        line=i+1,
                                        pattern=pattern_str,
                                        error=str(e)))
        # Log basename for brevity in success message
        logger.info(tr("log_tp_filter_loaded",
                    count=len(patterns),
                    filename=os.path.basename(absolute_filter_path)))
    except IOError as e:
        logger.error(tr("log_tp_filter_read_error", filter_path=absolute_filter_path, error=str(e)))
    except Exception as e:
        logger.exception(tr("log_tp_filter_load_unexpected", filter_path=absolute_filter_path))

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
            # NEW KEY NEEDED: log_tp_line_filtered
            # logger.debug(tr("log_tp_line_filtered", line=temp_line))
            logger.debug(f"Line filtered: '{temp_line}'") # Keep f-string if key missing

    # Rejoin the remaining lines
    final_text = "\n".join(filtered_lines).strip()
    # Log truncated result for brevity
    logger.debug(tr("log_tp_filter_applied", result=final_text[:100] + "..." if len(final_text) > 100 else final_text))
    return final_text

# --- Replacements ---

def load_replacements(replacements_path_relative):
    """
    Loads replacement rules from a JSON file stored in the persistent data location.
    Creates the file with defaults if it doesn't exist there.
    Args:
        replacements_path_relative (str): Relative path (e.g., "filter/replacements.json").
    Returns:
        dict: The loaded replacement dictionary (pattern: replacement).
    """
    persistent_dir = get_persistent_data_path() # <-- Use new function
    absolute_replacements_path = os.path.join(persistent_dir, replacements_path_relative) # <-- Construct absolute path

    # Use tr() for logging path (NEW KEY NEEDED: log_tp_abs_replacements_path)
    # logger.debug(tr("log_tp_abs_replacements_path", path=absolute_replacements_path))
    logger.debug(f"Using absolute replacements path: {absolute_replacements_path}") # Keep f-string if key missing

    # Create a default replacement file at the persistent location if it doesn't exist
    if not os.path.exists(absolute_replacements_path):
        logger.info(tr("log_tp_replacements_file_not_found", replacements_path=absolute_replacements_path))
        try:
            # Ensure directory exists at the persistent location
            replacements_dir = os.path.dirname(absolute_replacements_path)
            if replacements_dir:
                os.makedirs(replacements_dir, exist_ok=True)

            # Write the default replacement dictionary to the new file
            with open(absolute_replacements_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_REPLACEMENTS, f, indent=4, ensure_ascii=False)
            logger.info(tr("log_tp_replacements_created", replacements_path=absolute_replacements_path))
            return DEFAULT_REPLACEMENTS # Return the defaults used for creation
        except IOError as e:
            logger.error(tr("log_tp_replacements_create_error", replacements_path=absolute_replacements_path, error=str(e)))
            return {} # Return empty dict on creation error

    # Load replacements from the existing file at the persistent location
    logger.info(tr("log_tp_replacements_loading", filename=os.path.basename(absolute_replacements_path)))
    try:
        with open(absolute_replacements_path, 'r', encoding='utf-8') as f:
            replacements = json.load(f)
        # Validate that the loaded data is a dictionary
        if not isinstance(replacements, dict):
            logger.error(tr("log_tp_replacements_invalid_format", replacements_path=absolute_replacements_path))
            return {} # Return empty dict if format is wrong
        # Log basename for brevity in success message
        logger.info(tr("log_tp_replacements_loaded",
                    count=len(replacements),
                    filename=os.path.basename(absolute_replacements_path))) # <-- Use filename
        return replacements
    except (json.JSONDecodeError, IOError) as e:
        logger.error(tr("log_tp_replacements_read_error", replacements_path=absolute_replacements_path, error=str(e)))
        return {} # Return empty dict on read/parse error
    except Exception as e:
        logger.exception(tr("log_tp_replacements_load_unexpected", replacements_path=absolute_replacements_path))
        return {} # Return empty dict on unexpected error


def save_replacements(replacements_dict, replacements_path_relative):
    """
    Saves the replacement dictionary to a JSON file at the persistent data location,
    merging with existing content.
    Args:
        replacements_dict (dict): Dictionary of replacements to save/update.
        replacements_path_relative (str): Relative path (e.g., "filter/replacements.json").
    Returns:
        bool: True on success, False on error.
    """
    persistent_dir = get_persistent_data_path() # <-- Use new function
    absolute_replacements_path = os.path.join(persistent_dir, replacements_path_relative) # <-- Construct absolute path

    # Use tr() for logging path (NEW KEY NEEDED: log_tp_abs_replacements_path_saving)
    # logger.debug(tr("log_tp_abs_replacements_path_saving", path=absolute_replacements_path))
    logger.debug(f"Using absolute replacements path for saving: {absolute_replacements_path}") # Keep f-string

    logger.info(tr("log_tp_replacements_saving", filename=os.path.basename(absolute_replacements_path)))
    merged_replacements = {}
    try:
        # Load existing replacements from the persistent location if the file exists
        if os.path.exists(absolute_replacements_path):
            try:
                with open(absolute_replacements_path, 'r', encoding='utf-8') as f:
                    existing_replacements = json.load(f)
                    if isinstance(existing_replacements, dict):
                        merged_replacements = existing_replacements
                    else:
                        logger.warning(tr("log_tp_replacements_merge_error", replacements_path=absolute_replacements_path))
            except (json.JSONDecodeError, IOError) as e:
                # NEW KEY NEEDED: log_tp_replacements_merge_load_error
                logger.warning(f"Could not load/parse existing replacements from '{absolute_replacements_path}' ({str(e)}). File will be overwritten.")

        # Ensure directory exists at the persistent location
        replacements_dir = os.path.dirname(absolute_replacements_path)
        if replacements_dir:
            os.makedirs(replacements_dir, exist_ok=True)

        # Update the loaded/empty dictionary with new replacements
        # New rules overwrite existing ones with the same key (pattern)
        merged_replacements.update(replacements_dict)

        # Write the merged dictionary back to the file at the persistent location
        with open(absolute_replacements_path, 'w', encoding='utf-8') as f:
            json.dump(merged_replacements, f, indent=4, ensure_ascii=False)
        # Log basename for brevity in success message
        logger.info(tr("log_tp_replacements_saved",
                    count=len(merged_replacements),
                    filename=os.path.basename(absolute_replacements_path))) # <-- Use filename
        return True # Signal success
    except IOError as e:
        logger.error(tr("log_tp_replacements_save_error", replacements_path=absolute_replacements_path, error=str(e)))
        # GUI message will be sent by the calling function (GUI)
        return False # Signal error
    except Exception as e:
        logger.exception(tr("log_tp_replacements_save_unexpected"))
        return False # Signal error


def apply_replacements(text, replacements_dict):
    """
    Applies the provided replacement rules to the given text.
    Args:
        text (str): The text to modify.
        replacements_dict (dict): Dictionary where keys are regex patterns and values are replacements.
    Returns:
        str: The modified text.
    """
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
        # Log truncated result for brevity
        logger.debug(tr("log_tp_replacements_applied",
                    result=modified_text[:100] + "..." if len(modified_text) > 100 else modified_text))
    return modified_text
