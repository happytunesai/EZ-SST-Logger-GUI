# -*- coding: utf-8 -*-
"""
GUI class for the EZ STT Logger application using CustomTkinter.
Implements internationalization (i18n) with dynamic language loading
and log level control. Enables dynamic starting/stopping of services.
"""
import customtkinter as ctk
from tkinter import filedialog
import tkinter as tk
import os
import sys
import subprocess
import threading
import queue
import json
import re
import time
import logging

# Import local modules/objects
from lib.logger_setup import logger
from lib.constants import (
    APP_VERSION, ICON_FILE, AVAILABLE_LOCAL_MODELS, DEFAULT_LOCAL_MODEL,
    DEFAULT_OUTPUT_FORMAT, DEFAULT_MIN_BUFFER_SEC, DEFAULT_SILENCE_SEC,
    DEFAULT_ELEVENLABS_MODEL, WEBSOCKET_PORT, DEFAULT_STREAMERBOT_WS_URL,
    DEFAULT_STT_PREFIX, FILTER_FILE, FILTER_FILE_EL, REPLACEMENTS_FILE,
    CONFIG_FILE, DEFAULT_SAMPLERATE, DEFAULT_CHANNELS, DEFAULT_ENERGY_THRESHOLD,
    DEFAULT_TRANSCRIPTION_FILE, DEFAULT_LANGUAGE, CONFIG_DIR, # SUPPORTED_LANGUAGES removed
    LOG_LEVELS, LOG_LEVEL_NAMES, DEFAULT_LOG_LEVEL
)
from lib.utils import list_audio_devices_for_gui
from lib.text_processing import (
    load_filter_patterns, load_replacements, save_replacements
)
from lib.websocket_utils import start_websocket_server_thread, start_streamerbot_client_thread
from lib.audio_processing import recording_worker
from lib.config_manager import save_config
# Import language functions (tr is the main one used here)
from lib.language_manager import tr, set_current_language, load_language


class WhisperGUI(ctk.CTk):
    """Main GUI application class."""

    # FIX: Add available_languages parameter
    def __init__(self, app_config, key, queues, flags, handlers, available_languages):
        """
        Initializes the GUI.
        Args:
            app_config (dict): The loaded configuration dictionary.
            key (bytes): The encryption key.
            queues (dict): Dictionary of queues ('audio_q', 'gui_q', 'streamerbot_q').
            flags (dict): Dictionary of thread control flags.
            handlers (dict): Dictionary of logging handlers ('console', 'file').
            available_languages (dict): Dictionary of discovered valid languages {code: name}.
        """
        super().__init__()
        self.config = app_config
        self.encryption_key = key
        self.queues = queues
        self.gui_q = queues['gui_q']
        self.flags = flags
        self.stop_recording_flag = flags['stop_recording']
        self.streamerbot_client_stop_event = flags['stop_streamerbot']
        self.console_handler = handlers.get('console')
        self.file_handler = handlers.get('file') # Currently unused, but keep for potential future use

        # Store the dynamically discovered languages
        self.available_languages = available_languages if available_languages else {}
        if not self.available_languages:
             # Log using the initially loaded language (set in main.py)
             logger.error(tr("log_gui_no_languages_received"))

        # current_lang_code is already set globally by main.py based on config and availability
        self.current_lang_code = app_config.get("language_ui", DEFAULT_LANGUAGE)
        # Load language dict for initial setup (already loaded globally by set_current_language in main.py)
        # self.lang_dict = load_language(self.current_lang_code) # Not needed, tr() uses global dict

        # FIX: Remove creation of log_level_display_names here, moved to _update_ui_texts

        # Create fixed mapping for tab names (based on initial language)
        self._initial_tab_keys_to_mode_map = {
            "tab_local": "local", "tab_openai": "openai", "tab_elevenlabs": "elevenlabs",
            "tab_websocket": "websocket", "tab_integration": "integration"
        }
        # Use tr() which accesses the globally loaded language dict
        self._initial_tab_name_to_mode_map = {
            tr(key): mode for key, mode in self._initial_tab_keys_to_mode_map.items()
        }
        logger.debug(tr("log_gui_tab_mapping_created", mapping=self._initial_tab_name_to_mode_map))

        # Internal state
        self.is_recording = False
        self.available_mics = {}
        self.loaded_filter_patterns = []
        self.loaded_filter_patterns_el = []
        self.loaded_replacements = {}

        # Background thread references
        self.websocket_server_thread = None
        self.websocket_stop_event = None
        self.streamerbot_client_thread = None
        self.recording_thread = None

        # Build GUI
        self._setup_window()
        self._create_widgets() # Includes language selector using self.available_languages
        # FIX: Update UI texts initially to create log_level_display_names map
        self._update_ui_texts()
        self._load_initial_gui_data()
        self._start_background_tasks()
        self._update_status("status_ready", log=False)

        # Start queues/checks
        self.after(100, self._process_gui_queue)
        self.after(500, self._check_record_button_state)


    def _setup_window(self):
        """Configures the main window."""
        logger.debug(tr("log_gui_setup_window"))
        try:
            if os.path.exists(ICON_FILE): self.iconbitmap(ICON_FILE)
            else: logger.warning(tr("log_gui_icon_not_found", icon_file=ICON_FILE))
        except Exception as e: logger.warning(tr("log_gui_icon_error", error=e))

        self.title(tr("app_title", version=APP_VERSION))
        self.geometry("850x780")
        self.minsize(750, 550)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        logger.debug(tr("log_gui_window_setup_complete"))


    def _create_widgets(self):
        """Creates and arranges all widgets."""
        logger.debug(tr("log_gui_creating_widgets"))
        # --- Frames ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1) # Output frame row expands

        self.top_config_frame = ctk.CTkFrame(self.main_frame)
        self.top_config_frame.grid(row=0, column=0, pady=(0,10), padx=0, sticky="ew")
        self.top_config_frame.columnconfigure(0, weight=0) # Labels
        self.top_config_frame.columnconfigure(1, weight=1) # Entries/Combos expand
        self.top_config_frame.columnconfigure(2, weight=0) # Buttons etc.
        self.top_config_frame.columnconfigure(3, weight=0) # Buttons etc.
        self.top_config_frame.columnconfigure(4, weight=0) # Right button frame
        self.top_config_frame.columnconfigure(5, weight=0) # Language selector

        # --- Create Widget Sections ---
        self._create_tab_view()
        self._create_common_config_widgets()
        self._create_right_button_frame()
        self._create_language_selector() # Uses self.available_languages now
        self._create_output_frame()
        self._create_status_bar()
        self._create_log_level_selector()

        logger.debug(tr("log_gui_widgets_created"))

    # --- (Methods _create_tab_view to _create_right_button_frame remain largely unchanged, using tr()) ---
    def _create_tab_view(self):
        self.tab_view = ctk.CTkTabview(self.top_config_frame)
        self.tab_view.grid(row=0, column=0, columnspan=6, padx=5, pady=5, sticky="ew")
        # Add tabs using translated names based on initial language
        self.tab_local_ref = self.tab_view.add(tr("tab_local"))
        self.tab_openai_ref = self.tab_view.add(tr("tab_openai"))
        self.tab_elevenlabs_ref = self.tab_view.add(tr("tab_elevenlabs"))
        self.tab_websocket_ref = self.tab_view.add(tr("tab_websocket"))
        self.tab_integration_ref = self.tab_view.add(tr("tab_integration"))
        # Create content within tabs
        self._create_local_tab(self.tab_local_ref)
        self._create_openai_tab(self.tab_openai_ref)
        self._create_elevenlabs_tab(self.tab_elevenlabs_ref)
        self._create_websocket_tab(self.tab_websocket_ref)
        self._create_integration_tab(self.tab_integration_ref)
        # Set initial tab based on config
        initial_mode = self.config.get("mode", "local")
        initial_tab_key = f"tab_{initial_mode}"
        try:
            initial_tab_name = tr(initial_tab_key)
            self.tab_view.set(initial_tab_name)
            logger.debug(tr("log_gui_initial_tab_set", tab_name=initial_tab_name))
        except Exception as e:
             logger.warning(tr("log_gui_initial_tab_error", tab_name=tr(initial_tab_key), error=e))
             try:
                 fallback_name = tr("tab_local")
                 self.tab_view.set(fallback_name)
             except Exception as e_fallback:
                 logger.error(tr("log_gui_fallback_tab_error", error=e_fallback))

    def _create_local_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        self.model_label = ctk.CTkLabel(tab, text=tr("label_model_whisper"))
        self.model_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.model_combobox = ctk.CTkComboBox(tab, values=AVAILABLE_LOCAL_MODELS, width=150)
        self.model_combobox.set(self.config.get("local_model", DEFAULT_LOCAL_MODEL))
        self.model_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    def _create_openai_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        self.openai_api_key_label = ctk.CTkLabel(tab, text=tr("label_api_key_openai"))
        self.openai_api_key_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.openai_api_key_entry = ctk.CTkEntry(tab, placeholder_text=tr("placeholder_api_key_openai"), width=400, show="*")
        self.openai_api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        openai_key = self.config.get("openai_api_key", "") or os.getenv("OPENAI_API_KEY", "")
        if openai_key: self.openai_api_key_entry.insert(0, openai_key)

    def _create_elevenlabs_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        self.elevenlabs_api_key_label = ctk.CTkLabel(tab, text=tr("label_api_key_elevenlabs"))
        self.elevenlabs_api_key_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.elevenlabs_api_key_entry = ctk.CTkEntry(tab, placeholder_text=tr("placeholder_api_key_elevenlabs"), width=400, show="*")
        self.elevenlabs_api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        el_key = self.config.get("elevenlabs_api_key", "") or os.getenv("ELEVENLABS_API_KEY", "")
        if el_key: self.elevenlabs_api_key_entry.insert(0, el_key)
        self.elevenlabs_model_id_label = ctk.CTkLabel(tab, text=tr("label_model_id_elevenlabs"))
        self.elevenlabs_model_id_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.elevenlabs_model_id_entry = ctk.CTkEntry(tab, placeholder_text=tr("placeholder_model_id_elevenlabs"), width=200)
        self.elevenlabs_model_id_entry.insert(0, self.config.get("elevenlabs_model_id", DEFAULT_ELEVENLABS_MODEL))
        self.elevenlabs_model_id_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.filter_parentheses_checkbox = ctk.CTkCheckBox(tab, text=tr("checkbox_filter_parentheses"))
        if self.config.get("filter_parentheses", False): self.filter_parentheses_checkbox.select()
        self.filter_parentheses_checkbox.grid(row=2, column=0, columnspan=2, padx=5, pady=(10,5), sticky="w")

    def _create_websocket_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        self.ws_incoming_label = ctk.CTkLabel(tab, text=tr("label_websocket_incoming"), font=ctk.CTkFont(weight="bold"))
        self.ws_incoming_label.grid(row=0, column=0, columnspan=3, padx=5, pady=(10,0), sticky="w")
        self.websocket_enable_checkbox = ctk.CTkCheckBox(tab, text=tr("checkbox_websocket_enable"), command=self._on_websocket_enable_change)
        if self.config.get("websocket_enabled", False): self.websocket_enable_checkbox.select()
        self.websocket_enable_checkbox.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.ws_port_label = ctk.CTkLabel(tab, text=tr("label_websocket_port"))
        self.ws_port_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.websocket_port_entry = ctk.CTkEntry(tab, width=80)
        self.websocket_port_entry.insert(0, str(self.config.get("websocket_port", WEBSOCKET_PORT)))
        self.websocket_port_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.ws_port_info_label = ctk.CTkLabel(tab, text=tr("label_websocket_port_info", port=WEBSOCKET_PORT))
        self.ws_port_info_label.grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.ws_cmd_info_label = ctk.CTkLabel(tab, text=tr("label_websocket_command_info"))
        self.ws_cmd_info_label.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="w")

    def _create_integration_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        self.sb_outgoing_label = ctk.CTkLabel(tab, text=tr("label_integration_outgoing"), font=ctk.CTkFont(weight="bold"))
        self.sb_outgoing_label.grid(row=0, column=0, columnspan=3, padx=5, pady=(10,0), sticky="w")
        self.streamerbot_ws_enable_checkbox = ctk.CTkCheckBox(tab, text=tr("checkbox_integration_enable"), command=self._on_streamerbot_enable_change)
        if self.config.get("streamerbot_ws_enabled", False): self.streamerbot_ws_enable_checkbox.select()
        self.streamerbot_ws_enable_checkbox.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.sb_url_label = ctk.CTkLabel(tab, text=tr("label_integration_url"))
        self.sb_url_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.streamerbot_ws_url_entry = ctk.CTkEntry(tab, placeholder_text=tr("placeholder_integration_url"), width=300)
        self.streamerbot_ws_url_entry.insert(0, self.config.get("streamerbot_ws_url", DEFAULT_STREAMERBOT_WS_URL))
        self.streamerbot_ws_url_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.sb_url_info_label = ctk.CTkLabel(tab, text=tr("label_integration_url_info"))
        self.sb_url_info_label.grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.sb_prefix_label = ctk.CTkLabel(tab, text=tr("label_integration_prefix"))
        self.sb_prefix_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.stt_prefix_entry = ctk.CTkEntry(tab, width=400)
        self.stt_prefix_entry.insert(0, self.config.get("stt_prefix", DEFAULT_STT_PREFIX))
        self.stt_prefix_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="w")

    def _create_common_config_widgets(self):
        common_grid_row = 1
        self.mic_label = ctk.CTkLabel(self.top_config_frame, text=tr("label_mic"))
        self.mic_label.grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.mic_combobox = ctk.CTkComboBox(self.top_config_frame, values=[tr("combobox_mic_loading")], command=self._on_mic_change, width=300, state="readonly")
        self.mic_combobox.grid(row=common_grid_row, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.refresh_button = ctk.CTkButton(self.top_config_frame, text=tr("button_mic_reload"), width=100, command=self.populate_mic_dropdown)
        self.refresh_button.grid(row=common_grid_row, column=3, padx=(5,5), pady=5, sticky="e")
        common_grid_row += 1
        self.language_stt_label = ctk.CTkLabel(self.top_config_frame, text=tr("label_language_stt"))
        self.language_stt_label.grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.language_entry = ctk.CTkEntry(self.top_config_frame, placeholder_text=tr("placeholder_language_stt"), width=150)
        self.language_entry.insert(0, self.config.get("language", ""))
        self.language_entry.grid(row=common_grid_row, column=1, padx=5, pady=5, sticky="w")
        common_grid_row += 1
        self.format_label = ctk.CTkLabel(self.top_config_frame, text=tr("label_format"))
        self.format_label.grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        format_frame = ctk.CTkFrame(self.top_config_frame, fg_color="transparent")
        format_frame.grid(row=common_grid_row, column=1, columnspan=2, padx=0, pady=0, sticky="w")
        self.format_var = ctk.StringVar(value=self.config.get("output_format", DEFAULT_OUTPUT_FORMAT))
        self.txt_radio = ctk.CTkRadioButton(format_frame, text=tr("radio_format_txt"), variable=self.format_var, value="txt")
        self.txt_radio.pack(side="left", padx=(0, 10), pady=5)
        self.json_radio = ctk.CTkRadioButton(format_frame, text=tr("radio_format_json"), variable=self.format_var, value="json")
        self.json_radio.pack(side="left", padx=5, pady=5)
        common_grid_row += 1
        self.output_file_label = ctk.CTkLabel(self.top_config_frame, text=tr("label_output_file"))
        self.output_file_label.grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.filepath_entry = ctk.CTkEntry(self.top_config_frame, placeholder_text=tr("placeholder_output_file", filename=DEFAULT_TRANSCRIPTION_FILE), width=250)
        saved_path = self.config.get("output_filepath", "")
        if saved_path: self.filepath_entry.insert(0, saved_path)
        else:
            self.filepath_entry.insert(0, DEFAULT_TRANSCRIPTION_FILE)
            logger.info(tr("log_gui_no_output_path", default_path=DEFAULT_TRANSCRIPTION_FILE))
        self.filepath_entry.grid(row=common_grid_row, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.browse_button = ctk.CTkButton(self.top_config_frame, text=tr("button_browse"), width=80, command=self._browse_output_file)
        self.browse_button.grid(row=common_grid_row, column=3, padx=(5,5), pady=5, sticky="w")
        common_grid_row += 1
        self.min_buffer_label = ctk.CTkLabel(self.top_config_frame, text=tr("label_min_buffer"))
        self.min_buffer_label.grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.min_buffer_entry = ctk.CTkEntry(self.top_config_frame, width=60)
        self.min_buffer_entry.insert(0, str(self.config.get("min_buffer_duration", DEFAULT_MIN_BUFFER_SEC)))
        self.min_buffer_entry.grid(row=common_grid_row, column=1, padx=5, pady=5, sticky="w")
        self.silence_label = ctk.CTkLabel(self.top_config_frame, text=tr("label_silence_threshold"))
        self.silence_label.grid(row=common_grid_row, column=2, padx=(15, 5), pady=5, sticky="w")
        self.silence_threshold_entry = ctk.CTkEntry(self.top_config_frame, width=60)
        self.silence_threshold_entry.insert(0, str(self.config.get("silence_threshold", DEFAULT_SILENCE_SEC)))
        self.silence_threshold_entry.grid(row=common_grid_row, column=3, padx=5, pady=5, sticky="w")
        common_grid_row += 1
        self.clear_log_checkbox = ctk.CTkCheckBox(self.top_config_frame, text=tr("checkbox_clear_log"))
        if self.config.get("clear_log_on_start", False): self.clear_log_checkbox.select()
        self.clear_log_checkbox.grid(row=common_grid_row, column=1, columnspan=3, padx=5, pady=(10,5), sticky="w")

    def _create_right_button_frame(self):
        right_button_frame = ctk.CTkFrame(self.top_config_frame, fg_color="transparent")
        right_button_frame.grid(row=1, column=4, rowspan=6, padx=(5,5), pady=5, sticky="ns")
        self.record_button_frame = ctk.CTkFrame(right_button_frame, fg_color="transparent")
        self.record_button_frame.pack(pady=(0,10), fill="x")
        self.start_stop_button = ctk.CTkButton(self.record_button_frame, text=tr("button_start_recording"), command=self.toggle_recording, width=140, height=35)
        self.start_stop_button.pack(pady=(0,5))
        self.indicator_light = ctk.CTkFrame(self.record_button_frame, width=20, height=20, fg_color="grey", corner_radius=10)
        self.indicator_light.pack(pady=5)
        self.edit_filter_button = ctk.CTkButton(right_button_frame, text=tr("button_edit_filter"), width=140, command=self._edit_filter_file)
        self.edit_filter_button.pack(pady=5, fill="x")
        self.edit_replacements_button = ctk.CTkButton(right_button_frame, text=tr("button_edit_replacements"), width=140, command=self._edit_replacements_file)
        self.edit_replacements_button.pack(pady=5, fill="x")

    def _create_language_selector(self):
        """Creates the language selection dropdown menu using discovered languages."""
        lang_frame = ctk.CTkFrame(self.top_config_frame, fg_color="transparent")
        lang_frame.grid(row=1, column=5, rowspan=1, padx=(5, 10), pady=5, sticky="ne")

        self.language_ui_label = ctk.CTkLabel(lang_frame, text=tr("label_language_ui"))
        self.language_ui_label.pack(pady=(0,2))

        # FIX: Use dynamically discovered languages from self.available_languages
        language_options = list(self.available_languages.values()) if self.available_languages else ["N/A"]
        # Get display name for current language code (already set in __init__)
        current_display_language = self.available_languages.get(self.current_lang_code, "??")

        self.language_optionmenu = ctk.CTkOptionMenu(
            lang_frame,
            values=language_options,
            command=self._on_language_change,
            width=120
        )
        # Fallback logic if current language isn't found (e.g., after deleting a file)
        if current_display_language == "??" or current_display_language not in language_options:
             fallback_lang_name = self.available_languages.get(DEFAULT_LANGUAGE)
             if fallback_lang_name and fallback_lang_name in language_options:
                 logger.warning(tr("log_gui_current_lang_invalid", code=self.current_lang_code, fallback=DEFAULT_LANGUAGE))
                 current_display_language = fallback_lang_name
             elif language_options and language_options != ["N/A"]:
                 logger.warning(tr("log_gui_current_and_default_lang_invalid", current=self.current_lang_code, default=DEFAULT_LANGUAGE, first=language_options[0]))
                 current_display_language = language_options[0] # Fallback to first available
             else:
                 logger.error(tr("log_gui_no_valid_language_found"))
                 current_display_language = "Error" # Should not happen if scan worked

        self.language_optionmenu.set(current_display_language)
        self.language_optionmenu.pack()

    def _create_output_frame(self):
        self.output_frame = ctk.CTkFrame(self.main_frame)
        self.output_frame.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.rowconfigure(0, weight=1)
        self.textbox = ctk.CTkTextbox(self.output_frame, wrap="word", state="disabled", font=("Segoe UI", 12))
        self.textbox.grid(row=0, column=0, padx=5, pady=(0,5), sticky="nsew")
        self.textbox.tag_config("error_tag", foreground="red")
        self.textbox.tag_config("warning_tag", foreground="orange")
        self.textbox.tag_config("info_tag", foreground="gray")
        self.textbox.bind("<Button-3>", self._show_context_menu)
        self.clear_log_button = ctk.CTkButton(self.output_frame, text=tr("button_clear_output"), command=self._clear_textbox, width=120)
        self.clear_log_button.grid(row=1, column=0, pady=(0,5))

    def _create_status_bar(self):
        self.status_frame = ctk.CTkFrame(self.main_frame, height=30)
        self.status_frame.grid(row=2, column=0, pady=(5,0), padx=0, sticky="ew")
        self.status_frame.columnconfigure(0, weight=1)
        self.status_frame.columnconfigure(1, weight=0)
        self.status_label = ctk.CTkLabel(self.status_frame, text="...", anchor="w")
        self.status_label.grid(row=0, column=0, padx=5, pady=2, sticky="ew")

    def _create_log_level_selector(self):
        log_level_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        log_level_frame.grid(row=0, column=1, padx=(10, 5), pady=0, sticky="e")
        self.log_level_label = ctk.CTkLabel(log_level_frame, text=tr("label_log_level"), padx=5)
        self.log_level_label.pack(side="left", padx=(0, 5))
        # log_level_display_names should be created in _update_ui_texts initially
        level_display_options = list(self.log_level_display_names.values()) if hasattr(self, 'log_level_display_names') else [DEFAULT_LOG_LEVEL]
        current_log_level_str = self.config.get("log_level", DEFAULT_LOG_LEVEL)
        current_log_level_display = self.log_level_display_names.get(current_log_level_str, tr("log_level_info")) if hasattr(self, 'log_level_display_names') else current_log_level_str
        self.log_level_optionmenu = ctk.CTkOptionMenu(
            log_level_frame, values=level_display_options, command=self._on_log_level_change, width=110
        )
        if current_log_level_display not in level_display_options:
             logger.warning(tr("log_gui_log_level_not_found", level=current_log_level_str, display=current_log_level_display))
             current_log_level_display = self.log_level_display_names.get(DEFAULT_LOG_LEVEL, tr("log_level_info")) if hasattr(self, 'log_level_display_names') else DEFAULT_LOG_LEVEL
        self.log_level_optionmenu.set(current_log_level_display)
        self.log_level_optionmenu.pack(side="left")

    # --- Initialization and background tasks ---
    def _load_initial_gui_data(self):
        logger.debug(tr("log_gui_loading_initial_data"))
        self.populate_mic_dropdown()
        self.loaded_filter_patterns = load_filter_patterns(FILTER_FILE)
        self.loaded_filter_patterns_el = load_filter_patterns(FILTER_FILE_EL)
        self.loaded_replacements = load_replacements(REPLACEMENTS_FILE)
        logger.debug(tr("log_gui_initial_data_loaded"))

    def _start_background_tasks(self):
        logger.debug(tr("log_gui_starting_background_tasks"))
        if self.config.get("websocket_enabled", False): self._start_websocket_server()
        if self.config.get("streamerbot_ws_enabled", False): self._start_streamerbot_client()
        self._update_initial_status()

    # --- Widget Interaction Callbacks ---
    def _on_language_change(self, selected_language_display_name):
        """Called when a new language is selected from the dropdown."""
        logger.debug(tr("log_gui_language_change_requested", language=selected_language_display_name))
        selected_lang_code = None
        # FIX: Iterate through dynamically discovered languages
        for code, name in self.available_languages.items():
            if name == selected_language_display_name:
                selected_lang_code = code
                break

        if selected_lang_code and selected_lang_code != self.current_lang_code:
            logger.info(tr("log_gui_language_changing", code=selected_lang_code, name=selected_language_display_name))
            # Load the new language globally (updates current_lang_dict used by tr)
            set_current_language(selected_lang_code) # Use the function that updates globals
            self.current_lang_code = selected_lang_code # Update internal state
            self.config["language_ui"] = selected_lang_code # Update config in memory

            # Update all UI texts with the new language
            # This will also recreate self.log_level_display_names
            self._update_ui_texts()
        elif not selected_lang_code:
             logger.error(tr("log_gui_language_code_not_found", language=selected_language_display_name))

    def _on_log_level_change(self, selected_level_display_name):
        """Called when a new log level is selected."""
        logger.debug(tr("log_gui_log_level_change_requested", level=selected_level_display_name))
        selected_level_str = None
        # Find the internal string name (e.g., "INFO") for the display name (e.g., "Info")
        for level_str, display_name in self.log_level_display_names.items():
            if display_name == selected_level_display_name:
                selected_level_str = level_str
                break

        if selected_level_str:
            new_level = LOG_LEVELS.get(selected_level_str)
            if new_level is not None and self.console_handler:
                try:
                    self.console_handler.setLevel(new_level)
                    self.config["log_level"] = selected_level_str # Save string name
                    logger.info(tr("log_gui_log_level_set", level_str=selected_level_str, level_name=selected_level_display_name))
                    self._update_status("status_log_level_set", log_level=selected_level_display_name, is_key=True)
                except Exception as e:
                    logger.error(tr("log_gui_log_level_set_error", error=e))
                    self._update_status("status_error_generic", error=e, level="error", is_key=True)
            elif not self.console_handler:
                 logger.error(tr("log_gui_console_handler_missing"))
                 self._update_status("status_error_generic", error="Console handler missing", level="error", is_key=True)
            else:
                 logger.error(tr("log_gui_invalid_log_level", level=selected_level_str))
                 self._update_status("status_error_generic", error=f"Invalid level {selected_level_str}", level="error", is_key=True)
        else:
             logger.error(tr("log_gui_log_level_str_not_found", level=selected_level_display_name))

    def _on_websocket_enable_change(self):
        """Called when the WebSocket server checkbox is changed."""
        is_enabled = bool(self.websocket_enable_checkbox.get())
        logger.info(tr("log_gui_websocket_checkbox_changed", state=tr("status_enabled" if is_enabled else "status_disabled")))
        self.config["websocket_enabled"] = is_enabled
        if is_enabled: self._start_websocket_server()
        else: self._stop_websocket_server()
        self._update_initial_status()

    def _on_streamerbot_enable_change(self):
        """Called when the Streamer.bot checkbox is changed."""
        is_enabled = bool(self.streamerbot_ws_enable_checkbox.get())
        logger.info(tr("log_gui_streamerbot_checkbox_changed", state=tr("status_enabled" if is_enabled else "status_disabled")))
        self.config["streamerbot_ws_enabled"] = is_enabled
        if is_enabled: self._start_streamerbot_client()
        else: self._stop_streamerbot_client()
        self._update_initial_status()

    def _update_ui_texts(self):
        """Updates all text-based widgets with the current language."""
        logger.debug(tr("log_gui_updating_ui_texts"))
        self.title(tr("app_title", version=APP_VERSION))
        logger.warning(tr("log_gui_tab_names_update_warning"))

        # FIX: Recreate log level display names map with current language
        self.log_level_display_names = {
            level_name: tr(f"log_level_{level_name.lower()}")
            for level_name in LOG_LEVEL_NAMES
        }

        # --- Update all widget texts using tr() ---
        self.model_label.configure(text=tr("label_model_whisper"))
        self.openai_api_key_label.configure(text=tr("label_api_key_openai"))
        self.openai_api_key_entry.configure(placeholder_text=tr("placeholder_api_key_openai"))
        self.elevenlabs_api_key_label.configure(text=tr("label_api_key_elevenlabs"))
        self.elevenlabs_api_key_entry.configure(placeholder_text=tr("placeholder_api_key_elevenlabs"))
        self.elevenlabs_model_id_label.configure(text=tr("label_model_id_elevenlabs"))
        self.elevenlabs_model_id_entry.configure(placeholder_text=tr("placeholder_model_id_elevenlabs"))
        self.filter_parentheses_checkbox.configure(text=tr("checkbox_filter_parentheses"))
        self.ws_incoming_label.configure(text=tr("label_websocket_incoming"))
        self.websocket_enable_checkbox.configure(text=tr("checkbox_websocket_enable"))
        self.ws_port_label.configure(text=tr("label_websocket_port"))
        self.ws_port_info_label.configure(text=tr("label_websocket_port_info", port=WEBSOCKET_PORT))
        self.ws_cmd_info_label.configure(text=tr("label_websocket_command_info"))
        self.sb_outgoing_label.configure(text=tr("label_integration_outgoing"))
        self.streamerbot_ws_enable_checkbox.configure(text=tr("checkbox_integration_enable"))
        self.sb_url_label.configure(text=tr("label_integration_url"))
        self.streamerbot_ws_url_entry.configure(placeholder_text=tr("placeholder_integration_url"))
        self.sb_url_info_label.configure(text=tr("label_integration_url_info"))
        self.sb_prefix_label.configure(text=tr("label_integration_prefix"))
        self.mic_label.configure(text=tr("label_mic"))
        self.refresh_button.configure(text=tr("button_mic_reload"))
        self.language_stt_label.configure(text=tr("label_language_stt"))
        self.language_entry.configure(placeholder_text=tr("placeholder_language_stt"))
        self.format_label.configure(text=tr("label_format"))
        self.txt_radio.configure(text=tr("radio_format_txt"))
        self.json_radio.configure(text=tr("radio_format_json"))
        self.output_file_label.configure(text=tr("label_output_file"))
        self.filepath_entry.configure(placeholder_text=tr("placeholder_output_file", filename=DEFAULT_TRANSCRIPTION_FILE))
        self.browse_button.configure(text=tr("button_browse"))
        self.min_buffer_label.configure(text=tr("label_min_buffer"))
        self.silence_label.configure(text=tr("label_silence_threshold"))
        self.clear_log_checkbox.configure(text=tr("checkbox_clear_log"))
        self._check_record_button_state() # Updates record button text
        self.edit_filter_button.configure(text=tr("button_edit_filter"))
        self.edit_replacements_button.configure(text=tr("button_edit_replacements"))
        self.clear_log_button.configure(text=tr("button_clear_output"))
        self.language_ui_label.configure(text=tr("label_language_ui"))
        self.log_level_label.configure(text=tr("label_log_level"))

        # FIX: Update language dropdown options and value
        language_options = list(self.available_languages.values()) if self.available_languages else ["N/A"]
        current_display_language = self.available_languages.get(self.current_lang_code, "??")
        self.language_optionmenu.configure(values=language_options)
        # Fallback logic if current language isn't found
        if current_display_language == "??" or current_display_language not in language_options:
             fallback_lang_name = self.available_languages.get(DEFAULT_LANGUAGE)
             if fallback_lang_name and fallback_lang_name in language_options:
                 current_display_language = fallback_lang_name
             elif language_options and language_options != ["N/A"]:
                 current_display_language = language_options[0]
             else:
                 current_display_language = "Error"
        self.language_optionmenu.set(current_display_language)

        # FIX: Update log level dropdown options and value
        level_display_options = list(self.log_level_display_names.values())
        current_log_level_str = self.config.get("log_level", DEFAULT_LOG_LEVEL)
        current_log_level_display = self.log_level_display_names.get(current_log_level_str, tr("log_level_info"))
        self.log_level_optionmenu.configure(values=level_display_options)
        if current_log_level_display not in level_display_options:
             current_log_level_display = self.log_level_display_names.get(DEFAULT_LOG_LEVEL, tr("log_level_info"))
        self.log_level_optionmenu.set(current_log_level_display)

        self._update_initial_status()
        logger.debug(tr("log_gui_ui_texts_updated"))

    # --- (Rest der Methoden bleibt weitgehend gleich) ---
    # ... (Methoden von _update_initial_status bis on_closing) ...

    def _update_initial_status(self):
         ws_enabled = self.config.get("websocket_enabled", False)
         sb_enabled = self.config.get("streamerbot_ws_enabled", False)
         base_status = tr("status_ready")
         suffix = ""
         if not ws_enabled:
              ws_part = tr("status_ready_ws_disabled").replace(base_status, "").strip()
              suffix += ws_part
         if not sb_enabled:
              sb_part = tr("status_ready_sb_disabled").strip()
              if suffix and sb_part: suffix += " "
              suffix += sb_part
         suffix = suffix.strip()
         if suffix: self._update_status(f"{base_status} ({suffix})", log=False, is_key=False)
         else: self._update_status("status_ready", log=False, is_key=True)

    def _on_mic_change(self, choice):
        if choice in self.available_mics:
            mic_display_name = choice.split(":", 1)[-1].strip()
            self._update_status("status_mic_selected", mic_name=mic_display_name, is_key=True)
        else:
            self._update_status("status_mic_invalid", level="warning", is_key=True)

    def _browse_output_file(self):
        file_format = self.format_var.get()
        default_extension = f".{file_format}"
        txt_desc = tr("dialog_file_type_txt")
        json_desc = tr("dialog_file_type_json")
        all_desc = tr("dialog_file_type_all")
        file_types = [(f"{txt_desc}", "*.txt"), (f"{json_desc}", "*.json"), (f"{all_desc}", "*.*")]
        current_path = self.filepath_entry.get()
        initial_dir = os.path.dirname(current_path) if current_path else "."
        initial_file = os.path.basename(current_path) if current_path else DEFAULT_TRANSCRIPTION_FILE
        if not os.path.isdir(initial_dir): initial_dir = "."
        filepath = filedialog.asksaveasfilename(
            title=tr("dialog_select_output_file"),
            initialdir=initial_dir, initialfile=initial_file,
            defaultextension=default_extension, filetypes=file_types
        )
        if filepath:
            self.filepath_entry.delete(0, "end")
            self.filepath_entry.insert(0, filepath)
            self._update_status("status_output_file_selected", filename=os.path.basename(filepath), is_key=True)
            logger.info(tr("log_gui_output_file_selected", filepath=filepath))

    def _edit_filter_file(self):
        current_mode = self._tab_name_to_mode_safe(self.tab_view.get())
        target_file = FILTER_FILE_EL if current_mode == "elevenlabs" else FILTER_FILE
        if not os.path.exists(target_file): load_filter_patterns(target_file)
        if not os.path.exists(target_file):
            self._update_status("status_error_filter_not_found", filename=os.path.basename(target_file), level="error", is_key=True)
            return
        self._open_file_in_editor(target_file)

    def _edit_replacements_file(self):
        target_file = REPLACEMENTS_FILE
        if not os.path.exists(target_file): load_replacements(target_file)
        if not os.path.exists(target_file):
            self._update_status("status_error_replacements_not_found", level="error", is_key=True)
            return
        self._open_file_in_editor(target_file)

    def _open_file_in_editor(self, filepath):
        filename = os.path.basename(filepath)
        try:
            logger.info(tr("log_gui_opening_file", filepath=filepath))
            self._update_status("status_opening_editor", filename=filename, is_key=True)
            if sys.platform == "win32": os.startfile(filepath)
            elif sys.platform == "darwin": subprocess.call(["open", filepath])
            else: subprocess.call(["xdg-open", filepath])
            self.after(1000, lambda: self._update_status("status_opened_editor", filename=filename, log=False, is_key=True))
        except FileNotFoundError:
            self._update_status("status_error_file_not_found", filename=filename, level="error", is_key=True)
            logger.error(tr("log_gui_file_not_found", filepath=filepath))
        except OSError as e:
            self._update_status("status_error_opening_file", error=e, level="error", is_key=True)
            logger.error(tr("log_gui_os_error_opening_file", filepath=filepath, error=e))
        except Exception as e:
            self._update_status("status_error_opening_file", error=e, level="error", is_key=True)
            logger.exception(tr("log_gui_unknown_error_opening_file", filepath=filepath))

    def _clear_textbox(self):
        try:
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.configure(state="disabled")
            self._update_status("status_output_cleared", is_key=True)
        except Exception as e:
            logger.exception(tr("log_gui_textbox_clear_error"))
            self._update_status("status_error_clearing_output", level="error", is_key=True)

    def _show_context_menu(self, event):
        try:
            menu = tk.Menu(self, tearoff=0)
            has_selection = False
            try:
                if self.textbox.tag_ranges("sel"): has_selection = True
            except tk.TclError: pass
            if has_selection:
                menu.add_command(label=tr("context_copy"), command=self._copy_selection_to_clipboard)
                menu.add_separator()
                menu.add_command(label=tr("context_add_filter"), command=self._add_selection_to_filter)
                menu.add_command(label=tr("context_add_replacement"), command=self._add_tuneingway_replacement_from_selection) # Name might need update in tr()
            else:
                menu.add_command(label=tr("context_copy_all"), command=self._copy_all_to_clipboard)
            menu.add_separator()
            menu.add_command(label=tr("context_clear_output"), command=self._clear_textbox)
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_selection_to_clipboard(self):
        try:
            selected_text = self.textbox.get("sel.first", "sel.last")
            if selected_text:
                self.clipboard_clear(); self.clipboard_append(selected_text)
                self._update_status("status_selection_copied", log=False, is_key=True)
        except tk.TclError: self._update_status("status_no_selection", level="info", log=False, is_key=True)
        except Exception as e: logger.error(tr("log_gui_copy_selection_error", error=e)); self._update_status("status_error_copy", level="error", is_key=True)

    def _copy_all_to_clipboard(self):
        try:
            all_text = self.textbox.get("1.0", "end-1c")
            if all_text:
                self.clipboard_clear(); self.clipboard_append(all_text)
                self._update_status("status_all_copied", log=False, is_key=True)
        except Exception as e: logger.error(tr("log_gui_copy_all_error", error=e)); self._update_status("status_error_copy", level="error", is_key=True)

    def _add_selection_to_filter(self):
        try:
            selected_text = self.textbox.get("sel.first", "sel.last").strip()
            if not selected_text: self._update_status("status_no_selection", level="info", is_key=True); return
            current_mode = self._tab_name_to_mode_safe(self.tab_view.get())
            target_file = FILTER_FILE_EL if current_mode == "elevenlabs" else FILTER_FILE
            filename = os.path.basename(target_file)
            with open(target_file, "a", encoding="utf-8") as f: f.write("\n" + selected_text)
            self._update_status("status_filter_added", text=selected_text[:30], filename=filename, is_key=True)
            logger.info(tr("log_gui_filter_added_context", text=selected_text, target_file=target_file))
            if target_file == FILTER_FILE: self.loaded_filter_patterns = load_filter_patterns(FILTER_FILE)
            else: self.loaded_filter_patterns_el = load_filter_patterns(FILTER_FILE_EL)
        except tk.TclError: self._update_status("status_no_selection", level="info", is_key=True)
        except IOError as e: logger.error(tr("log_gui_filter_write_error", target_file=target_file, error=e)); self._update_status("status_error_saving_filter", error=e, level="error", is_key=True)
        except Exception as e: logger.exception(tr("log_gui_filter_add_error")); self._update_status("status_error_saving_filter", error=e, level="error", is_key=True)

    def _add_tuneingway_replacement_from_selection(self): # Name needs update if target changed
        try:
            selected_text = self.textbox.get("sel.first", "sel.last").strip()
        except tk.TclError: self._update_status("status_no_selection", level="info", is_key=True); return
        if not selected_text: self._update_status("status_empty_selection", level="info", is_key=True); return
        pattern = f"(?i)\\b{re.escape(selected_text)}\\b"
        correct_name = "BotnameXY" # Use the neutral placeholder now
        if pattern in self.loaded_replacements and self.loaded_replacements[pattern] == correct_name:
            self._update_status("status_replacement_exists", text=selected_text[:20], level="info", is_key=True)
            return
        self.loaded_replacements[pattern] = correct_name
        logger.info(tr("log_gui_replacement_added_context", pattern=pattern, replacement=correct_name))
        if save_replacements(self.loaded_replacements, REPLACEMENTS_FILE):
            self._update_status("status_replacement_added", text=selected_text[:20], level="success", is_key=True)
        else:
            self._update_status("status_error_saving_replacements", text=selected_text[:20], level="error", is_key=True)

    def populate_mic_dropdown(self):
        self._update_status("status_mic_search", level="info", is_key=True)
        self.mic_combobox.configure(values=[tr("combobox_mic_loading")], state="disabled")
        self.update_idletasks()
        threading.Thread(target=self._populate_mic_thread_target, args=(self.gui_q,), daemon=True).start()

    def _populate_mic_thread_target(self, gui_q):
        try:
            self.available_mics = list_audio_devices_for_gui(gui_q)
            mic_names = list(self.available_mics.keys())
            saved_mic_name = self.config.get("mic_name")
            def update_gui():
                no_mics_text = tr("combobox_mic_nodata")
                error_text = tr("combobox_mic_error")
                self.mic_combobox.configure(values=mic_names if mic_names else [no_mics_text], state="readonly" if mic_names else "disabled")
                if mic_names:
                    selected_mic = None
                    if saved_mic_name and saved_mic_name in mic_names: selected_mic = saved_mic_name
                    else:
                        default_mic_name = next((name for name in mic_names if "(Standard)" in name), None)
                        if default_mic_name: selected_mic = default_mic_name
                        else: selected_mic = mic_names[0]
                    if selected_mic:
                        self.mic_combobox.set(selected_mic)
                        self._update_status("status_mics_loaded_selected", is_key=True)
                    else:
                        self.mic_combobox.set(error_text)
                        self._update_status("status_mics_loaded_error", level="warning", is_key=True)
                else:
                    self.mic_combobox.set(no_mics_text)
            self.after(0, update_gui)
        except Exception as e:
             logger.exception(tr("log_gui_mic_thread_error"))
             self.after(0, lambda: self._update_status("status_mics_error", level="error", is_key=True))
             self.after(0, lambda: self.mic_combobox.configure(values=[tr("combobox_mic_error")], state="disabled"))

    def _check_record_button_state(self):
        try:
            current_tab_name = self.tab_view.get()
            current_mode = self._tab_name_to_mode_safe(current_tab_name)
            if self.is_recording:
                self.indicator_light.configure(fg_color="red")
                stop_text = tr("button_stop_recording")
                if current_mode in ["websocket", "integration"]: self.start_stop_button.configure(state="disabled", text=stop_text)
                else: self.start_stop_button.configure(state="normal", text=stop_text)
            else:
                self.indicator_light.configure(fg_color="grey")
                start_text = tr("button_start_recording")
                if current_mode in ["websocket", "integration"]: self.start_stop_button.configure(state="disabled", text=start_text)
                else: self.start_stop_button.configure(state="normal", text=start_text)
            self.after(500, self._check_record_button_state)
        except Exception as e:
             if isinstance(e, tk.TclError) and "invalid command name" in str(e): logger.debug(tr("log_gui_tkerror_check_button"))
             else: logger.warning(tr("log_gui_check_button_error", error=e))

    def toggle_recording(self):
        logger.debug(tr("log_gui_toggle_recording_called", status=tr("log_gui_recording_active" if self.is_recording else "log_gui_recording_inactive")))
        if self.is_recording:
            logger.info(tr("log_gui_stopping_recording"))
            self._update_status("status_stopping_recording", level="info", is_key=True)
            self.flags['stop_recording'].set()
            self.start_stop_button.configure(text=tr("button_stopping_recording"), state="disabled")
            logger.debug(tr("log_gui_stop_requested"))
        else:
            logger.info(tr("log_gui_starting_recording"))
            logger.debug(tr("log_gui_validating_start_conditions"))
            if not self._validate_start_conditions():
                logger.warning(tr("log_gui_start_conditions_failed"))
                return
            logger.debug(tr("log_gui_gathering_runtime_config"))
            current_config = self._gather_runtime_config_dict()
            if not current_config:
                logger.error(tr("log_gui_config_gathering_failed"))
                return
            try:
                logger.debug(tr("log_gui_preparing_worker_args"))
                worker_args = self._prepare_worker_args(current_config)
            except ValueError as e:
                 logger.error(tr("log_gui_worker_args_error", error=e))
                 self._update_status("status_error_invalid_input", error=e, level="error", is_key=True)
                 return
            logger.debug(tr("log_gui_clearing_stop_flag"))
            self.flags['stop_recording'].clear()
            self.is_recording = True
            self._check_record_button_state()
            self._update_status("status_starting_recording", level="info", is_key=True)
            logger.debug(tr("log_gui_starting_worker_thread", mode=worker_args['processing_mode']))
            self.recording_thread = threading.Thread(
                target=recording_worker, kwargs=worker_args, daemon=True, name="RecordingWorkerThread"
            )
            self.recording_thread.start()
            logger.info(tr("log_gui_worker_thread_started"))
        self._check_record_button_state()

    def _validate_start_conditions(self):
        mic_name = self.mic_combobox.get()
        if not mic_name or mic_name == tr("combobox_mic_loading") or mic_name == tr("combobox_mic_nodata") or mic_name not in self.available_mics:
            self._update_status("status_error_mic_select_fail", level="error", is_key=True); return False
        output_file = self.filepath_entry.get().strip()
        if output_file:
            output_dir = os.path.dirname(output_file) or "."
            if not os.path.exists(output_dir):
                try: os.makedirs(output_dir, exist_ok=True); logger.info(tr("log_gui_output_dir_created", output_dir=output_dir))
                except OSError as e: self._update_status("status_error_output_dir_create", error=e, level="error", is_key=True); return False
            if not os.access(output_dir, os.W_OK):
                 self._update_status("status_error_output_dir_write", level="error", is_key=True); return False
        processing_mode = self._tab_name_to_mode_safe(self.tab_view.get())
        if processing_mode == "openai" and not self.openai_api_key_entry.get():
            self._update_status("status_error_api_key_openai", level="error", is_key=True); return False
        if processing_mode == "elevenlabs":
             if not self.elevenlabs_api_key_entry.get(): self._update_status("status_error_api_key_elevenlabs", level="error", is_key=True); return False
             if not self.elevenlabs_model_id_entry.get(): self._update_status("status_error_model_id_elevenlabs", level="error", is_key=True); return False
        try: float(self.min_buffer_entry.get()); float(self.silence_threshold_entry.get())
        except ValueError: self._update_status("status_error_numeric_buffer", level="error", is_key=True); return False
        return True

    def _gather_runtime_config_dict(self):
         try:
             config_dict = {
                 "mode": self._tab_name_to_mode_safe(self.tab_view.get()),
                 "openai_api_key": self.openai_api_key_entry.get(),
                 "elevenlabs_api_key": self.elevenlabs_api_key_entry.get(),
                 "mic_name": self.mic_combobox.get(),
                 "local_model": self.model_combobox.get(),
                 "language": self.language_entry.get().strip(),
                 "language_ui": self.current_lang_code,
                 "log_level": self.config.get("log_level", DEFAULT_LOG_LEVEL),
                 "output_format": self.format_var.get(),
                 "output_filepath": self.filepath_entry.get().strip(),
                 "clear_log_on_start": bool(self.clear_log_checkbox.get()),
                 "min_buffer_duration": float(self.min_buffer_entry.get()),
                 "silence_threshold": float(self.silence_threshold_entry.get()),
                 "elevenlabs_model_id": self.elevenlabs_model_id_entry.get(),
                 "filter_parentheses": bool(self.filter_parentheses_checkbox.get()),
                 "websocket_enabled": bool(self.websocket_enable_checkbox.get()),
                 "websocket_port": int(self.websocket_port_entry.get()),
                 "streamerbot_ws_enabled": bool(self.streamerbot_ws_enable_checkbox.get()),
                 "streamerbot_ws_url": self.streamerbot_ws_url_entry.get(),
                 "stt_prefix": self.stt_prefix_entry.get()
             }
             float(config_dict["min_buffer_duration"])
             float(config_dict["silence_threshold"])
             int(config_dict["websocket_port"])
             return config_dict
         except (tk.TclError, AttributeError, ValueError) as e:
              logger.error(tr("log_gui_runtime_config_error", error=e))
              self._update_status("status_error_reading_settings", error=e, level="error", is_key=True)
              return None

    def _prepare_worker_args(self, current_config):
        processing_mode = current_config['mode']
        filter_patterns_to_use = self.loaded_filter_patterns_el if processing_mode == "elevenlabs" else self.loaded_filter_patterns
        args = {
            "processing_mode": processing_mode,
            "openai_api_key": current_config['openai_api_key'],
            "elevenlabs_api_key": current_config['elevenlabs_api_key'],
            "device_id": self.available_mics.get(current_config['mic_name']),
            "samplerate": DEFAULT_SAMPLERATE,
            "channels": DEFAULT_CHANNELS,
            "model_name": current_config['local_model'],
            "language": current_config['language'] or None,
            "output_file": current_config['output_filepath'],
            "file_format": current_config['output_format'],
            "energy_threshold": DEFAULT_ENERGY_THRESHOLD,
            "min_buffer_sec": current_config['min_buffer_duration'],
            "silence_sec": current_config['silence_threshold'],
            "elevenlabs_model_id": current_config['elevenlabs_model_id'],
            "filter_parentheses": current_config['filter_parentheses'],
            "send_to_streamerbot_flag": current_config['streamerbot_ws_enabled'],
            "stt_prefix": current_config['stt_prefix'],
            "audio_q": self.queues['audio_q'],
            "gui_q": self.queues['gui_q'],
            "streamerbot_queue": self.queues['streamerbot_q'],
            "stop_recording_flag": self.flags['stop_recording'],
            "loaded_replacements": self.loaded_replacements,
            "filter_patterns": filter_patterns_to_use,
        }
        if args["device_id"] is None: raise ValueError(tr("log_gui_error_mic_id_not_found"))
        logger.debug(tr("log_gui_worker_preparation", output_file=args['output_file']))
        return args

    def _process_gui_queue(self):
        try:
            while True:
                msg_type, msg_data = self.queues['gui_q'].get_nowait()
                is_key_prefix = isinstance(msg_data, str) and (msg_data.startswith("status_") or msg_data.startswith("combobox_"))
                if msg_type == "transcription":
                    self.textbox.configure(state="normal")
                    self.textbox.insert("end", msg_data + "\n")
                    self.textbox.configure(state="disabled")
                    self.textbox.see("end")
                elif msg_type == "status":
                    self._update_status(msg_data, level="info", log=False, is_key=is_key_prefix)
                elif msg_type == "error":
                    is_error_key = isinstance(msg_data, str) and msg_data.startswith("status_error_")
                    kwargs = {} if is_error_key else {'error': msg_data}
                    key_or_msg = msg_data if is_error_key else "status_error_generic"
                    self._update_status(key_or_msg, level="error", log=True, is_key=True, **kwargs)
                elif msg_type == "warning":
                     is_warn_key = isinstance(msg_data, str) and msg_data.startswith("status_warn_")
                     self._update_status(msg_data, level="warning", log=True, is_key=is_warn_key)
                elif msg_type == "toggle_recording_external":
                    logger.info(tr("log_gui_external_toggle_command"))
                    logger.debug(tr("log_gui_calling_toggle_recording"))
                    self.toggle_recording()
                    logger.debug(tr("log_gui_toggle_recording_call_finished"))
                elif msg_type == "finished":
                    logger.info(tr("log_gui_worker_finished"))
                    self.is_recording = False
                    self.recording_thread = None
                    self._check_record_button_state()
                else: logger.warning(tr("log_gui_unknown_message_type", type=msg_type))
                self.queues['gui_q'].task_done()
        except queue.Empty: pass
        except Exception as e: logger.exception(tr("log_gui_queue_processing_error"))
        self.after(100, self._process_gui_queue)

    def _update_status(self, message_or_key, level="info", log=True, is_key=True, **kwargs):
        if is_key:
            message = tr(message_or_key, **kwargs)
        else:
            try: message = str(message_or_key).format(**kwargs) if kwargs else str(message_or_key)
            except: message = str(message_or_key)
        status_text = message if len(message) < 150 else message[:147] + "..."
        try:
            self.status_label.configure(text=status_text)
            color_map = {"error": ("black", "red"), "warning": ("black", "#FF8C00")}
            try: default_fg = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
            except: default_fg = ("black", "white")
            self.status_label.configure(text_color=color_map.get(level, default_fg))
        except tk.TclError: logger.warning(tr("log_gui_status_label_update_error")); return
        if log:
            log_func = getattr(logger, level, logger.info)
            log_func(tr("log_gui_status", message=message))

    # --- Management of background tasks ---
    def _start_websocket_server(self):
        if not self.config.get("websocket_enabled", False): return
        if self.websocket_server_thread and self.websocket_server_thread.is_alive(): return
        try: port = int(self.websocket_port_entry.get())
        except (ValueError, tk.TclError): port = WEBSOCKET_PORT
        self._update_status("status_ws_server_starting", port=port, level="info", is_key=True)
        self.websocket_server_thread, self.websocket_stop_event = start_websocket_server_thread(port, self.queues['gui_q'])

    def _stop_websocket_server(self):
        if self.websocket_server_thread and self.websocket_server_thread.is_alive() and self.websocket_stop_event:
            logger.info(tr("log_gui_sending_ws_stop_signal"))
            try:
                loop = getattr(self.websocket_stop_event, '_custom_loop_ref', None)
                if loop and loop.is_running():
                     loop.call_soon_threadsafe(self.websocket_stop_event.set)
                     logger.info(tr("log_gui_ws_stop_event_set_via_loop"))
                else:
                     logger.warning(tr("log_gui_ws_loop_not_found"))
                     self.websocket_stop_event.set()
            except Exception as e: logger.error(tr("log_gui_ws_stop_event_error", error=e))
        self.websocket_server_thread = None
        self.websocket_stop_event = None

    def _start_streamerbot_client(self):
        if not self.config.get("streamerbot_ws_enabled", False): return
        if self.streamerbot_client_thread and self.streamerbot_client_thread.is_alive(): return
        ws_url = self.streamerbot_ws_url_entry.get()
        if not ws_url.startswith(("ws://", "wss://")):
            self._update_status("status_error_sb_url_invalid", url=ws_url, level="error", is_key=True); return
        self._update_status("status_sb_client_starting", url=ws_url, level="info", is_key=True)
        self.flags['stop_streamerbot'].clear()
        self.streamerbot_client_thread = start_streamerbot_client_thread(
            ws_url, self.queues['streamerbot_q'], self.flags['stop_streamerbot'], self.queues['gui_q']
        )

    def _stop_streamerbot_client(self):
        if self.streamerbot_client_thread and self.streamerbot_client_thread.is_alive():
            logger.info(tr("log_gui_sending_sb_stop_signal"))
            self.flags['stop_streamerbot'].set()
        self.streamerbot_client_thread = None

    # --- Helper methods ---
    def _mode_to_tab_name(self, mode_str):
        key = f"tab_{mode_str}"
        return tr(key)

    def _tab_name_to_mode_safe(self, tab_name):
        mode = self._initial_tab_name_to_mode_map.get(tab_name)
        if mode:
            return mode
        else:
            logger.warning(tr("log_gui_tab_mode_not_found", tab_name=tab_name))
            return "local"

    # --- Close handler ---
    def on_closing(self):
        logger.info(tr("log_gui_closing_initiated"))
        if self.is_recording:
            self._update_status("status_closing", level="info", is_key=True)
            logger.debug(tr("log_gui_setting_stop_flag"))
            self.flags['stop_recording'].set()
            if self.recording_thread and self.recording_thread.is_alive():
                logger.info(tr("log_gui_waiting_for_recording_thread"))
                self.recording_thread.join(timeout=2)
                if self.recording_thread.is_alive(): logger.warning(tr("log_gui_recording_thread_timeout"))
                else: logger.info(tr("log_gui_recording_thread_terminated"))
            else: logger.debug(tr("log_gui_no_active_recording_thread"))
            self.is_recording = False
        logger.debug(tr("log_gui_stopping_background_threads"))
        self._stop_websocket_server()
        self._stop_streamerbot_client()
        logger.debug(tr("log_gui_saving_final_config"))
        final_config = self._gather_runtime_config_dict()
        if final_config:
             if save_config(CONFIG_FILE, final_config, self.encryption_key): logger.info(tr("log_gui_final_config_saved"))
             else: logger.error(tr("log_gui_final_config_save_error"))
        else: logger.error(tr("log_gui_final_config_gather_error"))
        logger.debug(tr("log_gui_waiting_before_destroy"))
        time.sleep(0.2)
        logger.info(tr("log_gui_destroying_window"))
        self.destroy()
        logger.info(tr("log_gui_application_terminated"))

