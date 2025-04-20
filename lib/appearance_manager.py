# -*- coding: utf-8 -*-
"""
Manages the application's visual appearance (Light/Dark mode, Color Themes).
Uses tr() for logging and includes path functions for theme file loading.
"""

import customtkinter as ctk
import os
import sys # Needed for fallback path functions
import logging

# Try importing shared components, define fallbacks if necessary
try:
    from lib.logger_setup import logger
    # Try importing the real tr function first
    from lib.language_manager import tr
    from lib.constants import (
        DEFAULT_APPEARANCE_MODE, DEFAULT_COLOR_THEME,
        AVAILABLE_APPEARANCE_MODES, AVAILABLE_COLOR_THEMES
    )
    # Wichtig: get_base_path hier importieren
    from lib.utils import get_base_path
    # Optional: get_persistent_data_path, falls User-Themes unterstützt werden sollen
    # from lib.utils import get_persistent_data_path
except ImportError:
    # Fallback if essential imports fail
    logger = logging.getLogger("FallbackAppearanceLogger")
    logging.basicConfig(level=logging.INFO)
    # Define fallback tr ONLY if the import from language_manager failed
    def tr(key, **kwargs):
        text = key.replace('log_am_', '').replace('_', ' ').capitalize()
        if kwargs:
            try: text = text.format(**kwargs)
            except KeyError: pass
        return text + " (fallback)"
    # Define fallback constants
    DEFAULT_APPEARANCE_MODE = "System"
    DEFAULT_COLOR_THEME = "blue"
    AVAILABLE_APPEARANCE_MODES = ["System", "Light", "Dark"]
    AVAILABLE_COLOR_THEMES = ["blue", "green", "dark-blue"]
    # Define fallback path functions
    def get_base_path():
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'): return sys._MEIPASS
        else: return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    # def get_persistent_data_path(): # Nur wenn benötigt
    #     if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'): return os.path.dirname(sys.executable)
    #     else: return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    # Log the fallback situation using the fallback tr
    logger.warning(tr("log_am_import_fallback")) # New Key needed in languages

# --- Helper Function to find Theme Path ---

def _get_theme_path(theme_name):
    """
    Finds the full path to a theme file or returns the name if it's a built-in theme.

    Args:
        theme_name (str): The name of the theme (e.g., "blue", "pink").

    Returns:
        str or None: The full path to the theme file, the name of a built-in theme,
        or None if the theme is invalid or not found.
    """
    if not isinstance(theme_name, str) or not theme_name:
        logger.warning("Invalid theme name received in _get_theme_path.")
        return None # Ungültiger Name

    # Check if it's a built-in theme name
    if theme_name in ["blue", "green", "dark-blue"]:
        logger.debug(f"Theme '{theme_name}' is a built-in theme.")
        return theme_name # Standard-Themes werden direkt übergeben

    # Check if it's already a valid file path (e.g., from config)
    # Note: This currently isn't used but could be added if needed
    # if os.path.exists(theme_name) and theme_name.lower().endswith(".json"):
    #     logger.debug(f"Theme '{theme_name}' is already a valid path.")
    #     return theme_name

    # Construct the path to the JSON file in the 'themes' subdirectory relative to the app's base path
    try:
        # Verwende get_base_path(), um das Projektverzeichnis zu finden
        base = get_base_path()
        # Korrekt benannter Ordner ist 'themes'
        theme_file_path = os.path.join(base, "themes", f"{theme_name}.json")
        logger.debug(f"Checking for custom theme file at: {theme_file_path}")
        if os.path.exists(theme_file_path):
            logger.debug(f"Found custom theme file: {theme_file_path}")
            return theme_file_path # Gebe den vollen Pfad zurück
        else:
            # Use a specific tr key if available, otherwise use f-string
            try:
                logger.warning(tr("log_am_theme_file_not_found", path=theme_file_path))
            except KeyError:
                logger.warning(f"Custom theme file not found: {theme_file_path}")
            return None # Nicht gefunden
    except Exception as e:
        # Use specific tr key if available
        try:
            logger.error(tr("log_am_theme_path_error", theme=theme_name, error=str(e)))
        except KeyError:
            logger.error(f"Error constructing theme path for '{theme_name}': {e}")
        return None

# --- Functions to Apply Settings ---

def apply_initial_appearance(config):
    """
    Applies the appearance mode and color theme based on the loaded configuration.
    Should be called ONCE at startup BEFORE the main GUI window is created.

    Args:
        config (dict): The loaded application configuration dictionary.
    """
    # --- Apply Appearance Mode (Light/Dark/System) ---
    appearance_mode = config.get("appearance_mode", DEFAULT_APPEARANCE_MODE)
    if appearance_mode not in AVAILABLE_APPEARANCE_MODES:
        # Use specific tr key if available
        try: logger.warning(tr("log_am_invalid_mode_config", mode=appearance_mode, fallback=DEFAULT_APPEARANCE_MODE))
        except KeyError: logger.warning(f"Invalid appearance mode '{appearance_mode}' in config, falling back to '{DEFAULT_APPEARANCE_MODE}'.")
        appearance_mode = DEFAULT_APPEARANCE_MODE

    try:
        ctk.set_appearance_mode(appearance_mode)
        # Use specific tr key if available
        try: logger.info(tr("log_am_mode_set_initial", mode=appearance_mode))
        except KeyError: logger.info(f"Initial appearance mode set to '{appearance_mode}'.")
    except Exception as e:
        # Use specific tr key if available
        try: logger.error(tr("log_am_mode_set_error", mode=appearance_mode, error=str(e)))
        except KeyError: logger.error(f"Error setting initial appearance mode to '{appearance_mode}': {e}")

    # --- Apply Color Theme ---
    color_theme_name = config.get("color_theme", DEFAULT_COLOR_THEME)
    # **Get the path or name using the helper function**
    theme_path_or_name = _get_theme_path(color_theme_name)

    # Fallback if theme is invalid or not found
    if theme_path_or_name is None:
        # Use specific tr key if available
        try: logger.warning(tr("log_am_invalid_theme_config", theme=color_theme_name, fallback=DEFAULT_COLOR_THEME))
        except KeyError: logger.warning(f"Invalid or not found theme '{color_theme_name}' in config, falling back to '{DEFAULT_COLOR_THEME}'.")
        color_theme_name = DEFAULT_COLOR_THEME
        theme_path_or_name = DEFAULT_COLOR_THEME # Fallback auf Standardnamen

    # Apply the theme using the path or name
    try:
        ctk.set_default_color_theme(theme_path_or_name)
        # Use specific tr key if available
        try: logger.info(tr("log_am_theme_set_initial", theme=color_theme_name))
        except KeyError: logger.info(f"Initial color theme set to '{color_theme_name}'.")
    except Exception as e:
        # Use specific tr key if available
        try: logger.error(tr("log_am_theme_set_error", theme=color_theme_name, error=str(e)))
        except KeyError: logger.error(f"Error setting initial color theme '{color_theme_name}': {e}")


def change_appearance_mode(new_mode):
    """
    Changes the appearance mode dynamically.

    Args:
        new_mode (str): The desired mode ("Light", "Dark", "System").

    Returns:
        str: The validated mode that was applied, or None if setting failed badly.
    """
    validated_mode = new_mode
    if new_mode not in AVAILABLE_APPEARANCE_MODES:
        try: logger.warning(tr("log_am_invalid_mode_select", mode=new_mode, fallback=DEFAULT_APPEARANCE_MODE))
        except KeyError: logger.warning(f"Invalid appearance mode selected '{new_mode}', falling back to '{DEFAULT_APPEARANCE_MODE}'.")
        validated_mode = DEFAULT_APPEARANCE_MODE

    try:
        ctk.set_appearance_mode(validated_mode)
        try: logger.info(tr("log_am_mode_changed", mode=validated_mode))
        except KeyError: logger.info(f"Appearance mode changed to '{validated_mode}'.")
        return validated_mode # Return the mode that was successfully set
    except Exception as e:
        try: logger.error(tr("log_am_mode_set_error", mode=validated_mode, error=str(e)))
        except KeyError: logger.error(f"Error setting appearance mode to '{validated_mode}': {e}")
        # Attempt to revert to default on error, but still signal failure by returning None
        try:
            ctk.set_appearance_mode(DEFAULT_APPEARANCE_MODE)
            try: logger.warning(tr("log_am_mode_change_failed_fallback", mode=DEFAULT_APPEARANCE_MODE))
            except KeyError: logger.warning(f"Failed to set mode '{validated_mode}', reverted to default '{DEFAULT_APPEARANCE_MODE}'.")
        except Exception as fallback_e:
            logger.error(f"Failed even to revert to default appearance mode: {fallback_e}")
        return None # Indicate failure


def change_color_theme(new_theme_name):
    """
    Changes the color theme dynamically. Finds custom themes in 'themes' folder.
    NOTE: Requires app restart for full visual effect.

    Args:
        new_theme_name (str): The name of the theme ("blue", "pink", etc.).

    Returns:
        str: The validated theme name that was applied, or None if setting failed badly.
    """
    validated_theme_name = new_theme_name
    # **Get the path or name using the helper function**
    theme_path_or_name = _get_theme_path(validated_theme_name)

    # Fallback if theme is invalid or not found
    if theme_path_or_name is None:
        try: logger.warning(tr("log_am_invalid_theme_select", theme=new_theme_name, fallback=DEFAULT_COLOR_THEME))
        except KeyError: logger.warning(f"Invalid or not found theme selected '{new_theme_name}', falling back to '{DEFAULT_COLOR_THEME}'.")
        validated_theme_name = DEFAULT_COLOR_THEME
        theme_path_or_name = DEFAULT_COLOR_THEME # Fallback auf Standardnamen

    # Apply the theme using the path or name
    try:
        ctk.set_default_color_theme(theme_path_or_name)
        try: logger.info(tr("log_am_theme_changed", theme=validated_theme_name))
        except KeyError: logger.info(f"Color theme changed to '{validated_theme_name}'.")
        # Log restart warning always after change attempt
        try: logger.warning(tr("log_am_theme_restart_needed"))
        except KeyError: logger.warning("Full theme change requires application restart.")
        # Return the name of the theme that was intended/set (for saving to config)
        return validated_theme_name
    except Exception as e:
        try: logger.error(tr("log_am_theme_set_error", theme=validated_theme_name, error=str(e)))
        except KeyError: logger.error(f"Error setting color theme '{validated_theme_name}': {e}")
        # Attempt to revert to default on error, but still signal failure by returning None
        try:
            ctk.set_default_color_theme(DEFAULT_COLOR_THEME) # Fallback auf Standard
            try: logger.warning(tr("log_am_theme_change_failed_fallback", theme=DEFAULT_COLOR_THEME))
            except KeyError: logger.warning(f"Failed to set theme '{validated_theme_name}', reverted to default '{DEFAULT_COLOR_THEME}'.")
        except Exception as fallback_e:
            logger.error(f"Failed even to revert to default color theme: {fallback_e}")
        return None # Indicate failure by returning None