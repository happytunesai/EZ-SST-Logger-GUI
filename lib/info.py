# -*- coding: utf-8 -*-
"""
Module for creating the Info/About Tab content.
Includes PyInstaller-compatible path resolution, i18n logging,
and a conditional update button.
"""
import customtkinter as ctk
import webbrowser
import requests
import threading
import logging
from tkinter import messagebox
import os
import sys

# Import necessary parts from your project
try:
    from lib.logger_setup import logger
    from lib.language_manager import tr
    from lib.constants import APP_VERSION
    from . import gui_layout
    from lib.utils import get_base_path
except ImportError as e:
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.critical(f"CRITICAL: Could not import necessary modules (logger, tr, APP_VERSION, or gui_layout) in info.py: {e}")
    def tr(key, **kwargs):
        text = key
        for k, v in kwargs.items(): text = text.replace(f"{{{k}}}", str(v))
        return text
    APP_VERSION = "?.?.?"

# --- Constants ---
REPO_URL = "https://github.com/happytunesai/EZ-STT-Logger-GUI"
ADDON_URL = "https://github.com/happytunesai/PNGTuber-GPT"
GITHUB_API_URL = f"https://api.github.com/repos/happytunesai/EZ-STT-Logger-GUI/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/happytunesai/EZ-STT-Logger-GUI/releases"

# --- Helper Functions ---
def _open_link(url):
    """Opens the given URL in the default web browser."""
    try:
        webbrowser.open_new_tab(url)
        logger.info(tr("log_info_link_opened", url=url))
    except Exception as e:
        logger.error(tr("log_info_link_open_error", url=url, error=e))
        messagebox.showerror(tr("error_title"), tr("error_opening_link", url=url, error=str(e)))

# <<< MODIFIZIERT: Akzeptiert jetzt auch den Update-Button >>>
def _check_github_release(status_label_widget, update_button_widget):
    """
    Checks for the latest release version on GitHub in the background.
    Updates the provided label and potentially shows/hides the update button.
    """
    # <<< MODIFIZIERT: Umbenannt und erweitert >>>
    def update_release_ui(text_key, show_update_button=False, level="info", **kwargs):
        """Safely updates the label and button visibility from the thread."""
        try:
            # Führe die UI-Updates im Tkinter-Hauptthread aus
            status_label_widget.master.after(0, lambda: _update_ui_elements(
                text_key, show_update_button, level, **kwargs
            ))
        except Exception as e:
            logger.error(tr("log_info_label_update_error", error=e))

    def _update_ui_elements(text_key, show_update_button, level, **kwargs):
        """Helper function executed in the main thread"""
        # Update Label
        status_label_widget.configure(
            text=tr(text_key, **kwargs),
            text_color=get_text_color(level)
        )
        # Update Button Visibility
        if show_update_button:
            # Setze den Command, bevor der Button sichtbar wird
            update_button_widget.configure(command=lambda: _open_link(GITHUB_RELEASES_URL))
            # Platziere den Button (z.B. rechts neben dem Label)
            update_button_widget.pack(side='left', padx=(10, 0), pady=0)
        else:
            # Verstecke den Button
            update_button_widget.pack_forget()


    update_release_ui("status_checking_release") # Zeige "Checking..." und verstecke Button
    logger.debug(tr("log_info_release_check_start", url=GITHUB_API_URL))

    is_newer = False # Standardwert
    latest_version = "N/A"
    current_version = APP_VERSION.lstrip('v')

    try:
        response = requests.get(GITHUB_API_URL, timeout=10)
        response.raise_for_status()

        latest_release = response.json()
        latest_version = latest_release.get("tag_name", "N/A").lstrip('v')

        logger.info(tr("log_info_release_versions", latest=latest_version, current=current_version))

        try:
            from packaging import version as pv
            is_newer = pv.parse(latest_version) > pv.parse(current_version)
        except ImportError:
            logger.warning(tr("log_info_packaging_missing"))
            is_newer = latest_version > current_version
        except Exception as parse_err:
            logger.warning(tr("log_info_version_parse_error", error=parse_err))
            is_newer = latest_version > current_version

        if is_newer:
            # <<< MODIFIZIERT: Zeige Button an >>>
            update_release_ui("status_new_release_available", show_update_button=True, level="success", latest_version=latest_version)
            logger.info(tr("log_info_release_newer", latest=latest_version))
        else:
            update_release_ui("status_latest_release", show_update_button=False, current_version=current_version)
            logger.info(tr("log_info_release_latest", current=current_version))

    except requests.exceptions.Timeout:
        logger.error(tr("log_info_release_timeout", url=GITHUB_API_URL))
        update_release_ui("status_release_check_error", show_update_button=False, error=tr("error_timeout"), level="error")
    except requests.exceptions.RequestException as e:
        logger.error(tr("log_info_release_request_error", error=e))
        update_release_ui("status_release_check_error", show_update_button=False, error=str(e), level="error")
    except Exception as e:
        logger.exception(tr("log_info_release_unexpected_error", error=e))
        update_release_ui("status_release_check_error", show_update_button=False, error=tr("error_unknown"), level="error")


def get_text_color(level="info"):
    """Returns the appropriate text color for the status level."""
    if level == "error": return "red"
    elif level == "success": return "green" # Verwende hier grün für Erfolgsmeldungen
    elif level == "warning": return "orange"
    else: return "gray" # Safe fallback

# --- Main Function for Tab Creation ---
def create_info_tab(tab_frame, app_instance):
    """Creates the widgets within the Info tab frame."""
    tab_frame.grid_columnconfigure(0, weight=1)
    tab_frame.grid_rowconfigure(4, weight=1)

    # --- App Version ---
    version_label = ctk.CTkLabel(tab_frame, text=tr("app_title", version=APP_VERSION), font=gui_layout.FONT_BOLD)
    version_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

    # --- Repo Link ---
    repo_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
    repo_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
    repo_label = ctk.CTkLabel(repo_frame, text=tr("label_repo_link") + ":", font=gui_layout.FONT_NORMAL)
    repo_label.pack(side="left", padx=(0, 5))
    repo_link_button = ctk.CTkButton(repo_frame, text=REPO_URL, font=gui_layout.FONT_NORMAL,
                                    command=lambda: _open_link(REPO_URL),
                                    fg_color="transparent", text_color=("blue", "#1E90FF"),
                                    hover=False, anchor="w")
    repo_link_button.pack(side="left", fill="x", expand=True)

    # --- Addon Link ---
    addon_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
    addon_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
    addon_label = ctk.CTkLabel(addon_frame, text=tr("label_addon_link") + ":", font=gui_layout.FONT_NORMAL)
    addon_label.pack(side="left", padx=(0, 5))
    addon_link_button = ctk.CTkButton(addon_frame, text=ADDON_URL, font=gui_layout.FONT_NORMAL,
                                    command=lambda: _open_link(ADDON_URL),
                                    fg_color="transparent", text_color=("blue", "#1E90FF"),
                                    hover=False, anchor="w")
    addon_link_button.pack(side="left", fill="x", expand=True)

    # --- Release Check ---
    release_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
    release_frame.grid(row=3, column=0, padx=10, pady=15, sticky="ew") # sticky="ew" damit der Frame die Breite nutzt

    # Label für Statusanzeige
    release_status_label = ctk.CTkLabel(release_frame, text="", font=gui_layout.FONT_NORMAL, anchor="w")
    release_status_label.pack(side="left", padx=(0, 10)) # Packe links in den Frame

    # --- NEU: Der Update-Button (zunächst ohne pack/grid) ---
    update_button = ctk.CTkButton(
        release_frame,
        text=tr("button_download_update"),
        font=gui_layout.FONT_NORMAL,
        fg_color="#28A745",       # Grüner Hintergrund
        hover_color="#218838",    # Dunkleres Grün beim Hovern
        # command wird später in _update_ui_elements gesetzt
    )
    # update_button wird noch NICHT gepackt!

    # Button zum manuellen Prüfen
    release_check_button = ctk.CTkButton(
        release_frame,
        text=tr("button_check_release"),
        font=gui_layout.FONT_NORMAL,
        width=150,
        # <<< MODIFIZIERT: Lambda übergibt jetzt beide Widgets >>>
        command=lambda: threading.Thread(
            target=_check_github_release,
            args=(release_status_label, update_button), # Übergebe Label und neuen Button
            daemon=True
        ).start()
    )
    release_check_button.pack(side="left", padx=(10, 0)) # Packe rechts neben den (potenziellen) Update-Button

    # Optional: Start initial check when the tab is created?
    # threading.Thread(target=_check_github_release, args=(release_status_label, update_button), daemon=True).start()