# -*- coding: utf-8 -*-
"""
Manages the application's visual appearance (Light/Dark mode, Color Themes).
Uses tr() for logging and includes path functions for theme file loading.
"""

import customtkinter as ctk
import os
import sys
import logging
from lib.utils import get_base_path, get_persistent_data_path

# Try importing shared components, define fallbacks if necessary
try:
    from lib.logger_setup import logger
    # Try importing the real tr function first
    from lib.language_manager import tr
    from lib.constants import (
        DEFAULT_APPEARANCE_MODE, DEFAULT_COLOR_THEME,
        AVAILABLE_APPEARANCE_MODES, AVAILABLE_COLOR_THEMES
    )
except ImportError:
    # Fallback if essential imports fail
    logger = logging.getLogger("FallbackAppearanceLogger")
    logging.basicConfig(level=logging.INFO)
    # Define fallback tr ONLY if the import from language_manager failed
    def tr(key, **kwargs):
        text = key.replace('log_am_', '').replace('_', ' ').capitalize()
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text + " (fallback)"

    # Define fallback constants
    DEFAULT_APPEARANCE_MODE = "System"
    DEFAULT_COLOR_THEME = "blue"
    AVAILABLE_APPEARANCE_MODES = ["System", "Light", "Dark"]
    AVAILABLE_COLOR_THEMES = ["blue", "green", "dark-blue"]

    # Define fallback path functions
    def get_base_path():
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    def get_persistent_data_path():
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return os.path.dirname(sys.executable)
        return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    # Log the fallback situation using the fallback tr
    logger.warning(tr("log_am_import_fallback"))


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
        return None

    # 1) Extern: Persistent themes folder next to EXE
    try:
        base_ext = get_persistent_data_path()
        ext_path = os.path.join(base_ext, "themes", f"{theme_name}.json")
        if os.path.isfile(ext_path):
            logger.debug(f"Found external theme file: {ext_path}")
            return ext_path
    except Exception as e:
        logger.error(f"Error accessing external theme path: {e}")

    # 2) Intern: bundled _MEIPASS (onefile)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        try:
            int_path = os.path.join(sys._MEIPASS, "themes", f"{theme_name}.json")
            if os.path.isfile(int_path):
                logger.debug(f"Found internal theme file: {int_path}")
                return int_path
        except Exception as e:
            logger.error(f"Error accessing internal theme path: {e}")

    # 3) Built-in theme name
    if theme_name in AVAILABLE_COLOR_THEMES:
        logger.debug(f"Using built-in theme: {theme_name}")
        return theme_name

    logger.warning(f"Theme '{theme_name}' not found in external, internal, or built-in themes.")
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
        logger.warning(tr("log_am_invalid_mode_config", mode=appearance_mode, fallback=DEFAULT_APPEARANCE_MODE))
        appearance_mode = DEFAULT_APPEARANCE_MODE

    try:
        ctk.set_appearance_mode(appearance_mode)
        logger.info(tr("log_am_mode_set_initial", mode=appearance_mode))
    except Exception as e:
        logger.error(tr("log_am_mode_set_error", mode=appearance_mode, error=str(e)))

    # --- Apply Color Theme ---
    color_theme_name = config.get("color_theme", DEFAULT_COLOR_THEME)
    theme_path_or_name = _get_theme_path(color_theme_name)

    if theme_path_or_name is None:
        logger.warning(tr("log_am_invalid_theme_config", theme=color_theme_name, fallback=DEFAULT_COLOR_THEME))
        color_theme_name = DEFAULT_COLOR_THEME
        theme_path_or_name = DEFAULT_COLOR_THEME

    try:
        ctk.set_default_color_theme(theme_path_or_name)
        logger.info(tr("log_am_theme_set_initial", theme=color_theme_name))
    except Exception as e:
        logger.error(tr("log_am_theme_set_error", theme=color_theme_name, error=str(e)))



def change_appearance_mode(new_mode):
    """
    Changes the appearance mode dynamically.

    Args:
        new_mode (str): The desired mode ("Light", "Dark", "System").

    Returns:
        str: The validated mode that was applied, or None if setting failed badly.
    """
    validated_mode = new_mode if new_mode in AVAILABLE_APPEARANCE_MODES else DEFAULT_APPEARANCE_MODE
    if new_mode not in AVAILABLE_APPEARANCE_MODES:
        logger.warning(tr("log_am_invalid_mode_select", mode=new_mode, fallback=DEFAULT_APPEARANCE_MODE))

    try:
        ctk.set_appearance_mode(validated_mode)
        logger.info(tr("log_am_mode_changed", mode=validated_mode))
        return validated_mode
    except Exception as e:
        logger.error(tr("log_am_mode_set_error", mode=validated_mode, error=str(e)))
        try:
            ctk.set_appearance_mode(DEFAULT_APPEARANCE_MODE)
            logger.warning(tr("log_am_mode_change_failed_fallback", mode=DEFAULT_APPEARANCE_MODE))
        except Exception:
            pass
        return None



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
    theme_path_or_name = _get_theme_path(validated_theme_name)

    if theme_path_or_name is None:
        logger.warning(tr("log_am_invalid_theme_select", theme=new_theme_name, fallback=DEFAULT_COLOR_THEME))
        validated_theme_name = DEFAULT_COLOR_THEME
        theme_path_or_name = DEFAULT_COLOR_THEME

    try:
        ctk.set_default_color_theme(theme_path_or_name)
        logger.info(tr("log_am_theme_changed", theme=validated_theme_name))
        logger.warning(tr("log_am_theme_restart_needed"))
        return validated_theme_name
    except Exception as e:
        logger.error(tr("log_am_theme_set_error", theme=validated_theme_name, error=str(e)))
        try:
            ctk.set_default_color_theme(DEFAULT_COLOR_THEME)
            logger.warning(tr("log_am_theme_change_failed_fallback", theme=DEFAULT_COLOR_THEME))
        except Exception:
            pass
        return None
