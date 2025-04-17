# -*- coding: utf-8 -*-
"""
Helper module for GUI layout constants and functions.
Centralizes all sizing, padding, and font values for easy adjustment.
"""

import customtkinter as ctk # Keep ctk import if needed elsewhere, otherwise remove
from lib.language_manager import tr

# --- Font Configuration ---
# NOTE: Ensure the 'Roboto'''Montserrat''Poppins' 'Arial' font is installed on the system.
# customtkinter might fall back to a default font if it's not found.
DEFAULT_FONT_FAMILY = "Montserrat"
DEFAULT_FONT_SIZE = 12
HEADING_FONT_SIZE = 12 # Keep heading size same as default, just bold
FONT_NORMAL = (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
FONT_BOLD   = (DEFAULT_FONT_FAMILY, HEADING_FONT_SIZE, "bold")

# --- Height constants (in pixels) ---
TABVIEW_MAX_HEIGHT = 200
CONFIG_CONTROL_HEIGHT = 222  # adjusted to match desired middle box height
RIGHT_PANEL_HEIGHT = 217     # match new config height
STATUS_BAR_HEIGHT = 34

# --- Padding tuples ---
MAINFRAME_PAD = (10, 10)
FRAME_PAD_VERTICAL = (2, 2)
TAB_PAD_VERTICAL = (0, 1)
CONFIG_PAD_VERTICAL = (2, 2)
RIGHT_PANEL_PAD = (10, 5)


def configure_main_frame(main_frame):
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(0, weight=0, minsize=TABVIEW_MAX_HEIGHT)
    main_frame.rowconfigure(1, weight=0, minsize=CONFIG_CONTROL_HEIGHT)
    main_frame.rowconfigure(2, weight=1, minsize=180)
    main_frame.rowconfigure(3, weight=0, minsize=STATUS_BAR_HEIGHT)


def apply_tabview_layout(tab_container, tab_view):
    tab_container.grid_propagate(False)
    tab_view.configure(height=TABVIEW_MAX_HEIGHT)
    tab_view.pack(expand=True, fill="x")



def apply_config_control_layout(frame):
    frame.configure(height=CONFIG_CONTROL_HEIGHT)
    frame.grid_propagate(False)


def apply_right_panel_layout(panel):
    panel.configure(height=RIGHT_PANEL_HEIGHT)
    panel.grid_propagate(False)


def rebuild_tab_view(gui_instance):
    """Rebuild the tab view with updated localized tab names and mappings."""
    gui_instance._create_tab_name_mappings()
    # Ensure the master exists before destroying
    if gui_instance.tab_view and gui_instance.tab_view.master:
        gui_instance.tab_view.master.destroy()
    gui_instance._create_tab_view(gui_instance.main_frame)