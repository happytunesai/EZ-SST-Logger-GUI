# -*- coding: utf-8 -*-
"""
GUI class for the EZ STT Logger application using CustomTkinter.
Implements internationalization (i18n) with dynamic language loading
and log level control. Enables dynamic starting/stopping of services.
Layout integrated directly into this class based on grafik.png mockup (v3).
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
# Import layout constants AND FONT DEFINITIONS
from . import gui_layout
from . import info


# Import local modules/objects
# (Ensure these paths are correct relative to where gui.py is)
try:
    from lib.logger_setup import logger
    from lib.constants import CONFIG_DIR, CONFIG_FILE   # Ensure CONFIG_DIR is defined in constants.py
    from lib.constants import (
        APP_VERSION, ICON_FILE, AVAILABLE_LOCAL_MODELS, DEFAULT_LOCAL_MODEL,
        DEFAULT_OUTPUT_FORMAT, DEFAULT_MIN_BUFFER_SEC, DEFAULT_SILENCE_SEC,
        DEFAULT_ELEVENLABS_MODEL, WEBSOCKET_PORT, DEFAULT_STREAMERBOT_WS_URL,
        DEFAULT_STT_PREFIX, FILTER_FILE, FILTER_FILE_EL, REPLACEMENTS_FILE,
        CONFIG_FILE, DEFAULT_SAMPLERATE, DEFAULT_CHANNELS, DEFAULT_ENERGY_THRESHOLD,
        DEFAULT_TRANSCRIPTION_FILE, DEFAULT_LANGUAGE, CONFIG_DIR, DEFAULT_REPLACEMENT_BOTNAME,
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
    from lib.constants import APP_VERSION 
    from lib.utils import get_base_path
    from lib.constants import ICON_FILE
except ImportError as e:
    print(f"Fatal Error: Could not import necessary libraries. Please ensure 'lib' directory is accessible. Details: {e}")
    # Attempt basic logging if logger failed
    try: logging.basicConfig(level=logging.ERROR); logging.error(f"Import Error: {e}")
    except: pass
    DEFAULT_REPLACEMENT_BOTNAME = "BotnameXY"       # Default bot name for context menu replacement
    DEFAULT_LANGUAGE = "en" # Fallback language code if detection or config fails  
    APP_VERSION = "?.?.?" # Placeholder version 
    sys.exit(1)


class WhisperGUI(ctk.CTk):
    """Main GUI application class with integrated layout based on Mockup v3."""

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
        self.file_handler = handlers.get('file')

        self.available_languages = available_languages if available_languages else {}
        if not self.available_languages:
            logger.error(tr("log_gui_no_languages_received"))

        self.current_lang_code = app_config.get("language_ui", DEFAULT_LANGUAGE)
        self._update_log_level_display_names()
        self._create_tab_name_mappings()

        self.is_recording = False
        self.available_mics = {}
        self.loaded_filter_patterns = []
        self.loaded_filter_patterns_el = []
        self.loaded_replacements = {}

        self.websocket_server_thread = None
        self.websocket_stop_event = None
        self.streamerbot_client_thread = None
        self.recording_thread = None

        self._setup_window()
        self._create_widgets()
        self._load_initial_gui_data()
        self._start_background_tasks()
        self._update_status("status_ready", log=False)

        self.after(100, self._process_gui_queue)
        self.after(500, self._check_record_button_state)

    def _rebuild_tab_view(self):
        gui_layout.rebuild_tab_view(self)


    def _update_log_level_display_names(self):
        """Creates/Updates the mapping of log level strings to display names."""
        self.log_level_display_names = {
            level_name: tr(f"log_level_{level_name.lower()}")
            for level_name in LOG_LEVEL_NAMES
        }

    def _create_tab_name_mappings(self):
        """Creates mappings between tab names and mode strings."""
        self._initial_tab_keys_to_mode_map = {
            "tab_local": "local", "tab_openai": "openai", "tab_elevenlabs": "elevenlabs",
            "tab_websocket": "websocket", "tab_integration": "integration",
            "tab_info": "info"
        }
        self._initial_tab_name_to_mode_map = {
            tr(key): mode for key, mode in self._initial_tab_keys_to_mode_map.items()
        }
        logger.debug(tr("log_gui_tab_mapping_created", mapping=self._initial_tab_name_to_mode_map))

    def _setup_window(self):
        """Configures the main window."""
        logger.debug(tr("log_gui_setup_window"))
        try:
            icon_path = os.path.join(get_base_path(), ICON_FILE)
            logger.debug(f"Attempting to load window icon from: {icon_path}")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
                logger.debug("Window icon loaded successfully.")    
            else: logger.warning(tr("log_gui_icon_not_found", icon_file=icon_path))
        except Exception as e: logger.warning(tr("log_gui_icon_error", error=e))

        self.title(tr("app_title", version=APP_VERSION))
        self.geometry("900x750")
        self.minsize(800, 650)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Allow main_frame to expand

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        logger.debug(tr("log_gui_window_setup_complete"))

    # --- Widget Creation (Integrated Layout - Mockup v3) ---

    def _create_widgets(self):
        """Creates and arranges all widgets directly within this class based on Mockup v3."""
        logger.debug(tr("log_gui_creating_widgets"))

        # --- Main Container Frame ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, padx=gui_layout.MAINFRAME_PAD[0], pady=gui_layout.MAINFRAME_PAD[1], sticky="nsew")
        gui_layout.configure_main_frame(self.main_frame) # Configure main_frame layout


        # --- Row 0: Tab View ---
        self._create_tab_view(self.main_frame) # Tabs go directly in main_frame, row 0

        # --- Row 1: Config & Control Box ---
        config_control_frame = ctk.CTkFrame(self.main_frame)
        gui_layout.apply_config_control_layout(config_control_frame) # Apply layout to the config_control_frame
        config_control_frame.grid(row=1, column=0, pady=gui_layout.FRAME_PAD_VERTICAL, padx=0, sticky="ew") # Give more room vertically for the middle box
        config_control_frame.columnconfigure(0, weight=1) # Left config area expands
        config_control_frame.columnconfigure(1, weight=0) # Right panel fixed width

        # Frame to hold the left-side config sections within the box
        config_sections_frame = ctk.CTkFrame(config_control_frame, fg_color="transparent")
        config_sections_frame.grid(row=0, column=0, padx=(5,0), pady=5, sticky="nsew")
        config_sections_frame.columnconfigure(0, weight=1)

        # Create the individual config sections within their frame (reduced padding)
        self._create_microphone_section(config_sections_frame)    # Row 0
        self._create_language_section(config_sections_frame)      # Row 1
        self._create_output_config_section(config_sections_frame) # Row 2

        # Create the right panel (indicators and buttons) (reduced padding)
        self._create_right_panel(config_control_frame) # Goes directly in config_control_frame, col 1

        # --- Row 2: Output Area ---
        self._create_output_area(self.main_frame) # Goes in main_frame, row 2

        # --- Row 3: Status Bar Area (v3 with adjusted gap) ---
        self._create_status_bar_v3(self.main_frame) # Goes in main_frame, row 3

        # --- Post-Creation Setup ---
        self._set_initial_tab()
        self._update_initial_service_indicators()

        logger.debug(tr("log_gui_widgets_created"))

    def _create_tab_view(self, parent_frame):
        """Creates the tab view and its internal widgets."""
        tab_container = ctk.CTkFrame(parent_frame, fg_color="transparent")
        tab_container.grid(row=0, column=0, padx=0, pady=gui_layout.TAB_PAD_VERTICAL, sticky="ew") # Reduced bottom padding
        self.tab_view = ctk.CTkTabview(tab_container)   # Create the tabview widget
        gui_layout.apply_tabview_layout(tab_container, self.tab_view)

        self.tab_local_ref = self.tab_view.add(tr("tab_local"))
        self.tab_openai_ref = self.tab_view.add(tr("tab_openai"))
        self.tab_elevenlabs_ref = self.tab_view.add(tr("tab_elevenlabs"))
        self.tab_websocket_ref = self.tab_view.add(tr("tab_websocket"))
        self.tab_integration_ref = self.tab_view.add(tr("tab_integration"))
        self.tab_info_ref = self.tab_view.add(tr("tab_info"))

        # --- Create content within tabs ---
        # Local Tab
        self.tab_local_ref.columnconfigure(1, weight=0)
        self.model_label = ctk.CTkLabel(self.tab_local_ref, text=tr("label_model_whisper"), font=gui_layout.FONT_BOLD) # Bold
        self.model_label.grid(row=0, column=0, padx=10, pady=(5,5), sticky="w") # Reduced pady
        self.model_combobox = ctk.CTkComboBox(self.tab_local_ref, values=AVAILABLE_LOCAL_MODELS, width=150, font=gui_layout.FONT_NORMAL) # Normal font
        self.model_combobox.set(self.config.get("local_model", DEFAULT_LOCAL_MODEL))
        self.model_combobox.grid(row=0, column=1, padx=5, pady=(5,5), sticky="w") # Reduced pady

        # OpenAI Tab
        self.tab_openai_ref.columnconfigure(1, weight=1)
        self.openai_api_key_label = ctk.CTkLabel(self.tab_openai_ref, text=tr("label_api_key_openai"), font=gui_layout.FONT_BOLD) # Bold
        self.openai_api_key_label.grid(row=0, column=0, padx=10, pady=(5,5), sticky="w")
        self.openai_api_key_entry = ctk.CTkEntry(self.tab_openai_ref, placeholder_text=tr("placeholder_api_key_openai"), width=400, show="*", font=gui_layout.FONT_NORMAL) # Normal font
        self.openai_api_key_entry.grid(row=0, column=1, padx=5, pady=(5,5), sticky="ew")
        openai_key = self.config.get("openai_api_key", "") or os.getenv("OPENAI_API_KEY", "")
        if openai_key: self.openai_api_key_entry.insert(0, openai_key)

        # ElevenLabs Tab
        self.tab_elevenlabs_ref.columnconfigure(1, weight=1)
        self.elevenlabs_api_key_label = ctk.CTkLabel(self.tab_elevenlabs_ref, text=tr("label_api_key_elevenlabs"), font=gui_layout.FONT_BOLD) # Bold
        self.elevenlabs_api_key_label.grid(row=0, column=0, padx=10, pady=(5,5), sticky="w")
        self.elevenlabs_api_key_entry = ctk.CTkEntry(self.tab_elevenlabs_ref, placeholder_text=tr("placeholder_api_key_elevenlabs"), width=400, show="*", font=gui_layout.FONT_NORMAL) # Normal font
        self.elevenlabs_api_key_entry.grid(row=0, column=1, padx=5, pady=(5,5), sticky="ew")
        el_key = self.config.get("elevenlabs_api_key", "") or os.getenv("ELEVENLABS_API_KEY", "")
        if el_key: self.elevenlabs_api_key_entry.insert(0, el_key)
        self.elevenlabs_model_id_label = ctk.CTkLabel(self.tab_elevenlabs_ref, text=tr("label_model_id_elevenlabs"), font=gui_layout.FONT_BOLD) # Bold
        self.elevenlabs_model_id_label.grid(row=1, column=0, padx=10, pady=(2,2), sticky="w")
        self.elevenlabs_model_id_entry = ctk.CTkEntry(self.tab_elevenlabs_ref, placeholder_text=tr("placeholder_model_id_elevenlabs"), width=200, font=gui_layout.FONT_NORMAL) # Normal font
        self.elevenlabs_model_id_entry.insert(0, self.config.get("elevenlabs_model_id", DEFAULT_ELEVENLABS_MODEL))
        self.elevenlabs_model_id_entry.grid(row=1, column=1, padx=5, pady=(2,2), sticky="w")
        self.filter_parentheses_checkbox = ctk.CTkCheckBox(self.tab_elevenlabs_ref, text=tr("checkbox_filter_parentheses"), font=gui_layout.FONT_NORMAL) # Normal font
        if self.config.get("filter_parentheses", False): self.filter_parentheses_checkbox.select()
        self.filter_parentheses_checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=(5,5), sticky="w")

        # WebSocket Tab
        self.tab_websocket_ref.columnconfigure(1, weight=1)
        self.ws_incoming_label = ctk.CTkLabel(self.tab_websocket_ref, text=tr("label_websocket_incoming"), font=gui_layout.FONT_BOLD) # Bold (as requested indirectly)
        self.ws_incoming_label.grid(row=0, column=0, columnspan=3, padx=10, pady=(5,0), sticky="w")
        self.websocket_enable_checkbox = ctk.CTkCheckBox(self.tab_websocket_ref, text=tr("checkbox_websocket_enable"), command=self._on_websocket_enable_change, font=gui_layout.FONT_NORMAL) # Normal font
        if self.config.get("websocket_enabled", False): self.websocket_enable_checkbox.select()
        self.websocket_enable_checkbox.grid(row=1, column=0, columnspan=3, padx=10, pady=2, sticky="w")
        self.ws_port_label = ctk.CTkLabel(self.tab_websocket_ref, text=tr("label_websocket_port"), font=gui_layout.FONT_BOLD) # Bold
        self.ws_port_label.grid(row=2, column=0, padx=10, pady=2, sticky="w")
        self.websocket_port_entry = ctk.CTkEntry(self.tab_websocket_ref, width=80, font=gui_layout.FONT_NORMAL) # Normal font
        self.websocket_port_entry.insert(0, str(self.config.get("websocket_port", WEBSOCKET_PORT)))
        self.websocket_port_entry.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        self.ws_port_info_label = ctk.CTkLabel(self.tab_websocket_ref, text=tr("label_websocket_port_info", port=self.config.get("websocket_port", WEBSOCKET_PORT)), font=gui_layout.FONT_NORMAL) # Normal font
        self.ws_port_info_label.grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.ws_cmd_info_label = ctk.CTkLabel(self.tab_websocket_ref, text=tr("label_websocket_command_info"), font=gui_layout.FONT_NORMAL) # Normal font
        self.ws_cmd_info_label.grid(row=3, column=0, columnspan=3, padx=10, pady=(2,5), sticky="w")

        # Integration Tab
        self.tab_integration_ref.columnconfigure(1, weight=1)
        self.sb_outgoing_label = ctk.CTkLabel(self.tab_integration_ref, text=tr("label_integration_outgoing"), font=gui_layout.FONT_BOLD) # Bold (as requested indirectly)
        self.sb_outgoing_label.grid(row=0, column=0, columnspan=3, padx=10, pady=(5,0), sticky="w")
        self.streamerbot_ws_enable_checkbox = ctk.CTkCheckBox(self.tab_integration_ref, text=tr("checkbox_integration_enable"), command=self._on_streamerbot_enable_change, font=gui_layout.FONT_NORMAL) # Normal font
        if self.config.get("streamerbot_ws_enabled", False): self.streamerbot_ws_enable_checkbox.select()
        self.streamerbot_ws_enable_checkbox.grid(row=1, column=0, columnspan=3, padx=10, pady=2, sticky="w")
        self.sb_url_label = ctk.CTkLabel(self.tab_integration_ref, text=tr("label_integration_url"), font=gui_layout.FONT_BOLD) # Bold
        self.sb_url_label.grid(row=2, column=0, padx=10, pady=2, sticky="w")
        self.streamerbot_ws_url_entry = ctk.CTkEntry(self.tab_integration_ref, placeholder_text=tr("placeholder_integration_url"), width=300, font=gui_layout.FONT_NORMAL) # Normal font
        self.streamerbot_ws_url_entry.insert(0, self.config.get("streamerbot_ws_url", DEFAULT_STREAMERBOT_WS_URL))
        self.streamerbot_ws_url_entry.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        self.sb_url_info_label = ctk.CTkLabel(self.tab_integration_ref, text=tr("label_integration_url_info"), font=gui_layout.FONT_NORMAL) # Normal font
        self.sb_url_info_label.grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.sb_prefix_label = ctk.CTkLabel(self.tab_integration_ref, text=tr("label_integration_prefix"), font=gui_layout.FONT_BOLD) # Bold
        self.sb_prefix_label.grid(row=3, column=0, padx=10, pady=2, sticky="w")
        self.stt_prefix_entry = ctk.CTkEntry(self.tab_integration_ref, width=400, font=gui_layout.FONT_NORMAL) # Normal font
        self.stt_prefix_entry.insert(0, self.config.get("stt_prefix", DEFAULT_STT_PREFIX))
        self.stt_prefix_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=(2,5), sticky="w")
        # --- NEW: Botname for Context Menu Replacement ---
        # Needs new language key: label_replacement_botname
        self.replacement_botname_label = ctk.CTkLabel(self.tab_integration_ref, text=tr("label_replacement_botname"), font=gui_layout.FONT_BOLD)
        self.replacement_botname_label.grid(row=4, column=0, padx=10, pady=(5,5), sticky="w") # New row 4
        self.replacement_botname_entry = ctk.CTkEntry(self.tab_integration_ref, font=gui_layout.FONT_NORMAL)
        # Load initial value from config
        # DEFAULT_REPLACEMENT_BOTNAME needs to be imported or defined
        initial_botname = self.config.get("replacement_botname", DEFAULT_REPLACEMENT_BOTNAME)
        self.replacement_botname_entry.insert(0, initial_botname)
        self.replacement_botname_entry.grid(row=4, column=1, columnspan=2, padx=5, pady=(5,10), sticky="ew") # New row 4, sticky="ew" to expand
        # Note: Increased bottom pady (10) for spacing
        # --- End NEW: Botname ---

        # Info Tab
        try:
            info.create_info_tab(self.tab_info_ref, self)
            logger.debug(tr("log_gui_info_tab_created"))
        except Exception as e:
            logger.error(tr("log_gui_info_tab_create_error", error=e), exc_info=True)
    def _set_initial_tab(self):
        """Sets the initially selected tab based on configuration."""
        initial_mode = self.config.get("mode", "local")
        initial_tab_key = f"tab_{initial_mode}"
        try:
            initial_tab_name = tr(initial_tab_key)
            self.tab_view.set(initial_tab_name)
            logger.debug(tr("log_gui_initial_tab_set", tab_name=initial_tab_name))
        except Exception as e:
            logger.warning(tr("log_gui_initial_tab_error", tab_name=tr(initial_tab_key), error=e))
            try: # Fallback to local tab
                fallback_name = tr("tab_local")
                self.tab_view.set(fallback_name)
                logger.warning(tr("log_gui_fallback_tab_used", tab_name=fallback_name))
            except Exception as e_fallback:
                logger.error(tr("log_gui_fallback_tab_error", error=e_fallback))

    def _create_microphone_section(self, parent_frame):
        """ Creates the Microphone configuration block (shorter). """
        mic_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        mic_frame.grid(row=0, column=0, padx=0, pady=gui_layout.CONFIG_PAD_VERTICAL, sticky="ew") # Reduced pady
        mic_frame.columnconfigure(1, weight=1)

        self.mic_label = ctk.CTkLabel(mic_frame, text=tr("label_mic"), font=gui_layout.FONT_BOLD) # Bold
        self.mic_label.grid(row=0, column=0, padx=(0,5), pady=3, sticky="w") # Reduced pady

        self.mic_combobox = ctk.CTkComboBox( mic_frame, values=[tr("combobox_mic_loading")], command=self._on_mic_change, state="readonly", font=gui_layout.FONT_NORMAL ) # Normal font
        self.mic_combobox.grid(row=0, column=1, padx=5, pady=3, sticky="ew")

        self.refresh_button = ctk.CTkButton(mic_frame, text=tr("button_mic_reload"), width=80, command=self.populate_mic_dropdown, font=gui_layout.FONT_NORMAL) # Normal font
        self.refresh_button.grid(row=0, column=2, padx=(5,0), pady=3, sticky="e")

    def _create_language_section(self, parent_frame):
        """ Creates the Language configuration block (shorter). """
        lang_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        lang_frame.grid(row=1, column=0, padx=0, pady=gui_layout.CONFIG_PAD_VERTICAL, sticky="ew") # Reduced pady
        lang_frame.columnconfigure(1, weight=0)

        self.language_stt_label = ctk.CTkLabel(lang_frame, text=tr("label_language_stt"), font=gui_layout.FONT_BOLD) # Bold
        self.language_stt_label.grid(row=0, column=0, padx=(0,5), pady=3, sticky="w") # Reduced pady

        self.language_entry = ctk.CTkEntry(lang_frame, placeholder_text=tr("placeholder_language_stt"), width=150, font=gui_layout.FONT_NORMAL) # Normal font
        self.language_entry.insert(0, self.config.get("language", ""))
        self.language_entry.grid(row=0, column=1, padx=5, pady=3, sticky="w")

    def _create_output_config_section(self, parent_frame):
        """ Creates the Format, Output File, Buffers config block (shorter). """
        output_config_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        output_config_frame.grid(row=2, column=0, padx=0, pady=gui_layout.CONFIG_PAD_VERTICAL, sticky="ew") # Reduced bottom pady
        output_config_frame.columnconfigure(1, weight=1)

        # --- Row 0: Format ---
        self.format_label = ctk.CTkLabel(output_config_frame, text=tr("label_format"), font=gui_layout.FONT_BOLD) # Bold
        self.format_label.grid(row=0, column=0, padx=(0,5), pady=1, sticky="w") # Reduced pady

        format_radio_frame = ctk.CTkFrame(output_config_frame, fg_color="transparent")
        format_radio_frame.grid(row=0, column=1, columnspan=3, padx=5, pady=0, sticky="w") # Reduced pady

        self.format_var = ctk.StringVar(value=self.config.get("output_format", DEFAULT_OUTPUT_FORMAT))
        self.txt_radio = ctk.CTkRadioButton(format_radio_frame, text=tr("radio_format_txt"), variable=self.format_var, value="txt", font=gui_layout.FONT_NORMAL) # Normal font
        self.txt_radio.pack(side="left", padx=(0, 15))
        self.json_radio = ctk.CTkRadioButton(format_radio_frame, text=tr("radio_format_json"), variable=self.format_var, value="json", font=gui_layout.FONT_NORMAL) # Normal font
        self.json_radio.pack(side="left")

        # --- Row 1: Output File ---
        self.output_file_label = ctk.CTkLabel(output_config_frame, text=tr("label_output_file"), font=gui_layout.FONT_BOLD) # Bold
        self.output_file_label.grid(row=1, column=0, padx=(0,5), pady=1, sticky="w")

        self.filepath_entry = ctk.CTkEntry( output_config_frame, placeholder_text=tr("placeholder_output_file", filename=DEFAULT_TRANSCRIPTION_FILE), font=gui_layout.FONT_NORMAL ) # Normal font
        saved_path = self.config.get("output_filepath", "")
        self.filepath_entry.insert(0, saved_path if saved_path else DEFAULT_TRANSCRIPTION_FILE)
        self.filepath_entry.grid(row=1, column=1, padx=5, pady=1, sticky="ew")

        self.browse_button = ctk.CTkButton(output_config_frame, text=tr("button_browse"), width=80, command=self._browse_output_file, font=gui_layout.FONT_NORMAL) # Normal font
        self.browse_button.grid(row=1, column=2, padx=(5,0), pady=1, sticky="e")

        # --- Row 2: Buffers ---
        buffer_silence_frame = ctk.CTkFrame(output_config_frame, fg_color="transparent")
        buffer_silence_frame.grid(row=2, column=0, columnspan=3, padx=0, pady=1, sticky="ew") # Reduced pady

        self.min_buffer_label = ctk.CTkLabel(buffer_silence_frame, text=tr("label_min_buffer"), font=gui_layout.FONT_BOLD) # Bold
        self.min_buffer_label.pack(side="left", padx=(0,5))
        self.min_buffer_entry = ctk.CTkEntry(buffer_silence_frame, width=60, font=gui_layout.FONT_NORMAL) # Normal font
        self.min_buffer_entry.insert(0, str(self.config.get("min_buffer_duration", DEFAULT_MIN_BUFFER_SEC)))
        self.min_buffer_entry.pack(side="left", padx=(0, 20))
        self.silence_label = ctk.CTkLabel(buffer_silence_frame, text=tr("label_silence_threshold"), font=gui_layout.FONT_BOLD) # Bold
        self.silence_label.pack(side="left", padx=(0,5))
        self.silence_threshold_entry = ctk.CTkEntry(buffer_silence_frame, width=60, font=gui_layout.FONT_NORMAL) # Normal font
        self.silence_threshold_entry.insert(0, str(self.config.get("silence_threshold", DEFAULT_SILENCE_SEC)))
        self.silence_threshold_entry.pack(side="left")

        # --- Row 3: Clear Log Checkbox ---
        self.clear_log_checkbox = ctk.CTkCheckBox(output_config_frame, text=tr("checkbox_clear_log"), font=gui_layout.FONT_NORMAL) # Normal font
        if self.config.get("clear_log_on_start", False): self.clear_log_checkbox.select()
        self.clear_log_checkbox.grid(row=3, column=1, columnspan=2, padx=5, pady=(3, 3), sticky="w") # Reduced pady

    def _create_right_panel(self, parent_frame):
        """ Creates the right-side panel (shorter). """
        self.right_panel = ctk.CTkFrame(parent_frame, fg_color="#e6e6e6", width=160)    # Fixed width for the right panel
        gui_layout.apply_right_panel_layout(self.right_panel)   # Apply layout to the right panel
        self.right_panel.grid(row=0, column=1, padx=gui_layout.RIGHT_PANEL_PAD[0], pady=gui_layout.RIGHT_PANEL_PAD[1], sticky="ns") # Reduced pady
        self.right_panel.columnconfigure(0, weight=1) # Fixed width for the right panel

        # --- Indicators ---
        ws_indicator_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        ws_indicator_frame.grid(row=0, column=0, pady=(5, 1), padx=5, sticky="w") # Reduced pady
        self.ws_indicator_light = ctk.CTkFrame(ws_indicator_frame, width=15, height=15, fg_color="grey", corner_radius=10)
        self.ws_indicator_light.pack(side="left", padx=(0, 5))
        self.ws_indicator_label = ctk.CTkLabel(ws_indicator_frame, text="WebSocket", font=gui_layout.FONT_NORMAL) # Normal font
        self.ws_indicator_label.pack(side="left")

        sb_indicator_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        sb_indicator_frame.grid(row=1, column=0, pady=1, padx=5, sticky="w") # Reduced pady
        self.sb_indicator_light = ctk.CTkFrame(sb_indicator_frame, width=15, height=15, fg_color="grey", corner_radius=10)
        self.sb_indicator_light.pack(side="left", padx=(0, 5))
        self.sb_indicator_label = ctk.CTkLabel(sb_indicator_frame, text="Integration (SB)", font=gui_layout.FONT_NORMAL) # Normal font
        self.sb_indicator_label.pack(side="left")

        # --- Action Buttons ---
        self.start_stop_button = ctk.CTkButton( self.right_panel, text=tr("button_start_recording"), command=self.toggle_recording, width=140, height=35, font=gui_layout.FONT_NORMAL ) # Normal font
        self.start_stop_button.grid(row=3, column=0, pady=(10, 5), padx=10) # Reduced top pady

        self.indicator_light = ctk.CTkFrame(self.right_panel, width=20, height=20, fg_color="grey", corner_radius=10)
        self.indicator_light.grid(row=4, column=0, pady=(0, 5)) # Reduced bottom pady

        self.edit_filter_button = ctk.CTkButton( self.right_panel, text=tr("button_edit_filter"), width=140, command=self._edit_filter_file, font=gui_layout.FONT_NORMAL) # Normal font
        self.edit_filter_button.grid(row=5, column=0, pady=3, padx=10) # Reduced pady

        self.edit_replacements_button = ctk.CTkButton( self.right_panel, text=tr("button_edit_replacements"), width=140, command=self._edit_replacements_file, font=gui_layout.FONT_NORMAL) # Normal font
        self.edit_replacements_button.grid(row=6, column=0, pady=(3,5), padx=10) # Reduced pady

    def _create_output_area(self, parent_frame):
        """ Creates the output text area and clear button. """
        output_area_frame = ctk.CTkFrame(parent_frame)
        output_area_frame.grid(row=2, column=0, padx=0, pady=0, sticky="nsew") # Output area in row 2
        output_area_frame.columnconfigure(0, weight=1)
        output_area_frame.rowconfigure(0, weight=1)

        # Apply the normal font to the textbox
        self.textbox = ctk.CTkTextbox(output_area_frame, wrap="word", state="disabled", font=gui_layout.FONT_NORMAL) # Normal font (was Segoe UI)
        self.textbox.grid(row=0, column=0, padx=5, pady=(5,5), sticky="nsew")
        self.textbox.tag_config("error_tag", foreground="red")
        self.textbox.tag_config("warning_tag", foreground="orange")
        self.textbox.tag_config("info_tag", foreground="gray")
        self.textbox.bind("<Button-3>", self._show_context_menu)

        self.clear_log_button = ctk.CTkButton(output_area_frame, text=tr("button_clear_output"), command=self._clear_textbox, width=120, font=gui_layout.FONT_NORMAL) # Normal font
        self.clear_log_button.grid(row=1, column=0, pady=(5,10))

    def _create_status_bar_v3(self, parent_frame):
        """ Creates the status bar with two sections and seamless background. """
        # Main container for the status bar area - make it transparent
        status_area_frame = ctk.CTkFrame(parent_frame, height=gui_layout.STATUS_BAR_HEIGHT, fg_color="transparent")
        status_area_frame.grid(row=3, column=0, pady=(10,0), padx=0, sticky="ew")
        status_area_frame.columnconfigure(0, weight=1) # Left section expands
        status_area_frame.columnconfigure(1, weight=0) # Right section fixed

        # --- Left Section: Status Text ---
        # Give this frame the default background color
        status_text_frame = ctk.CTkFrame(status_area_frame) # Gets default theme color
        status_text_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew") # No padx between frames
        status_text_frame.columnconfigure(0, weight=1)
        status_text_frame.rowconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(status_text_frame, text="...", anchor="w", font=gui_layout.FONT_NORMAL) # Normal font
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        # --- Right Section: Selectors ---
        # Give this frame the default background color
        selectors_frame = ctk.CTkFrame(status_area_frame) # Gets default theme color
        selectors_frame.grid(row=0, column=1, padx=0, pady=0, sticky="nsew") # No padx between frames
        selectors_frame.columnconfigure(0, weight=0)
        selectors_frame.columnconfigure(1, weight=0)
        selectors_frame.columnconfigure(2, weight=0)
        selectors_frame.columnconfigure(3, weight=0)

        # Language Selector
        self.language_ui_label = ctk.CTkLabel(selectors_frame, text=tr("label_language_ui"), font=gui_layout.FONT_NORMAL) # Normal font
        self.language_ui_label.grid(row=0, column=0, padx=(10, 2), pady=5, sticky="e")
        language_options = list(self.available_languages.values()) if self.available_languages else ["N/A"]
        current_display_language = self.available_languages.get(self.current_lang_code, "??")
        self.language_optionmenu = ctk.CTkOptionMenu( selectors_frame, values=language_options, command=self._on_language_change, width=110, font=gui_layout.FONT_NORMAL ) # Normal font
        if current_display_language == "??" or current_display_language not in language_options:
            fallback_lang_name = self.available_languages.get(DEFAULT_LANGUAGE)
            if fallback_lang_name and fallback_lang_name in language_options: current_display_language = fallback_lang_name
            elif language_options and language_options != ["N/A"]: current_display_language = language_options[0]
            else: current_display_language = "Error"
        self.language_optionmenu.set(current_display_language)
        self.language_optionmenu.grid(row=0, column=1, padx=(0, 15), pady=5, sticky="e")

        # Log Level Selector
        self.log_level_label = ctk.CTkLabel(selectors_frame, text=tr("label_log_level"), font=gui_layout.FONT_NORMAL) # Normal font
        self.log_level_label.grid(row=0, column=2, padx=(10, 2), pady=5, sticky="e")
        level_display_options = list(self.log_level_display_names.values())
        current_log_level_str = self.config.get("log_level", DEFAULT_LOG_LEVEL)
        current_log_level_display = self.log_level_display_names.get(current_log_level_str, tr("log_level_info"))
        self.log_level_optionmenu = ctk.CTkOptionMenu( selectors_frame, values=level_display_options, command=self._on_log_level_change, width=90, font=gui_layout.FONT_NORMAL ) # Normal font
        if current_log_level_display not in level_display_options:
            current_log_level_display = self.log_level_display_names.get(DEFAULT_LOG_LEVEL, tr("log_level_info"))
        self.log_level_optionmenu.set(current_log_level_display)
        self.log_level_optionmenu.grid(row=0, column=3, padx=(0, 10), pady=5, sticky="e")

    def _update_initial_service_indicators(self):
        """Sets the initial color of service indicators based on config."""
        ws_enabled = self.config.get("websocket_enabled", False)
        sb_enabled = self.config.get("streamerbot_ws_enabled", False)
        try:
            if hasattr(self, 'ws_indicator_light'):
                self.ws_indicator_light.configure(fg_color="green" if ws_enabled else "grey")
            if hasattr(self, 'sb_indicator_light'):
                self.sb_indicator_light.configure(fg_color="green" if sb_enabled else "grey")
        except Exception as e:
            logger.warning(f"Could not update initial service indicators: {e}")

### start
# --- Rest of the methods (Callbacks, Logic, etc.) ---
    # Keep methods from _load_initial_gui_data to on_closing unchanged
    # Ensure all self.widget references are correct based on the creation methods above.
    # ...
    # --- Initialization and background tasks ---
    def _load_initial_gui_data(self):
        logger.debug(tr("log_gui_loading_initial_data"))
        self.populate_mic_dropdown() # Start populating mics
        # Load filters/replacements
        try:
            self.loaded_filter_patterns = load_filter_patterns(FILTER_FILE)
            self.loaded_filter_patterns_el = load_filter_patterns(FILTER_FILE_EL)
            self.loaded_replacements = load_replacements(REPLACEMENTS_FILE)
        except Exception as e:
            logger.error(f"Error loading filter/replacement files: {e}") # Keeping f-string as in original
            self._update_status("status_error_loading_filters", level="error", is_key=True)
        logger.debug(tr("log_gui_initial_data_loaded"))

    def _start_background_tasks(self):
        logger.debug(tr("log_gui_starting_background_tasks"))
        if self.config.get("websocket_enabled", False): self._start_websocket_server()
        if self.config.get("streamerbot_ws_enabled", False): self._start_streamerbot_client()
        # Update status after attempting starts
        self._update_initial_status()

    # --- Widget Interaction Callbacks ---
    def _on_language_change(self, selected_language_display_name):
        """Called when a new language is selected from the dropdown."""
        logger.debug(tr("log_gui_language_change_requested", language=selected_language_display_name))
        selected_lang_code = None
        # Find code corresponding to the selected display name
        for code, name in self.available_languages.items():
            if name == selected_language_display_name:
                selected_lang_code = code
                break

        if selected_lang_code and selected_lang_code != self.current_lang_code:
            logger.info(tr("log_gui_language_changing", code=selected_lang_code, name=selected_language_display_name))

            current_ui_values = None # Initialize variable
            current_mode = "local"  # Default fallback

            # --- Get current tab mode BEFORE rebuilding ---
            try:
                current_tab_name = self.tab_view.get()
                current_mode = self._tab_name_to_mode_safe(current_tab_name)
                # Using new tr key for log message
                logger.debug(tr("log_gui_current_tab_pre_change", name=current_tab_name, mode=current_mode))
            except Exception as e:
                # Using new tr key for log message
                logger.warning(tr("log_gui_get_tab_failed_pre_change", error=e))
                # current_mode remains "local" (fallback)

            # --- Gather current UI values and attempt to save config BEFORE rebuilding ---
            logger.debug(tr("log_gui_save_config_pre_rebuild"))
            gathered_values = self._gather_runtime_config_dict() # Gather first

            if gathered_values:
                current_ui_values = gathered_values # Assign if gather was successful
                try:
                    os.makedirs(CONFIG_DIR, exist_ok=True)
                    logger.debug(tr("log_gui_config_dir_ensured", config_dir=CONFIG_DIR))
                except OSError as e:
                    logger.error(tr("log_gui_create_config_dir_failed", config_dir=CONFIG_DIR, error=e))
                    self._update_status("status_error_config_dir_create", level="error", is_key=True)

                # Attempt to save the gathered configuration
                if save_config(CONFIG_FILE, current_ui_values, self.encryption_key):
                    logger.info(tr("log_gui_config_saved_pre_rebuild"))

                    # --- If save was successful, update in-memory config ---
                    # This ensures _create_tab_view uses the latest values
                    self.config.update({
                        "openai_api_key": current_ui_values.get("openai_api_key", ""),
                        "elevenlabs_api_key": current_ui_values.get("elevenlabs_api_key", ""),
                        "local_model": current_ui_values.get("local_model", DEFAULT_LOCAL_MODEL),
                        "elevenlabs_model_id": current_ui_values.get("elevenlabs_model_id", DEFAULT_ELEVENLABS_MODEL),
                        "filter_parentheses": current_ui_values.get("filter_parentheses", False),
                        "websocket_port": current_ui_values.get("websocket_port", WEBSOCKET_PORT),
                        "websocket_enabled": current_ui_values.get("websocket_enabled", False),
                        "streamerbot_ws_url": current_ui_values.get("streamerbot_ws_url", DEFAULT_STREAMERBOT_WS_URL),
                        "streamerbot_ws_enabled": current_ui_values.get("streamerbot_ws_enabled", False),
                        "stt_prefix": current_ui_values.get("stt_prefix", DEFAULT_STT_PREFIX),
                    })
                    # Using new tr key for log message
                    logger.debug(tr("log_gui_mem_config_updated"))
                else:
                    # Save failed
                    logger.error(tr("log_gui_config_save_error_pre_rebuild"))
                    self._update_status("status_error_saving_config", level="error", is_key=True)
            else:
                # Gather failed
                logger.warning(tr("log_gui_gather_config_failed_pre_rebuild"))

            # --- Proceed with language change and UI rebuild ---
            set_current_language(selected_lang_code)
            self.current_lang_code = selected_lang_code
            self.config["language_ui"] = selected_lang_code # Update in-memory config

            self._update_ui_texts()
            self._rebuild_tab_view() # Rebuild UI elements

            # --- Restore previously active tab AFTER rebuilding ---
            try:
                new_target_tab_name = self._mode_to_tab_name(current_mode)
                self.tab_view.set(new_target_tab_name)
                # Using new tr key for log message
                logger.debug(tr("log_gui_tab_restored", name=new_target_tab_name, mode=current_mode))
            except Exception as e:
                # Using new tr key for log message
                logger.error(tr("log_gui_restore_tab_failed", mode=current_mode, error=e))
                # Defaulting to the first tab is the fallback behavior if .set() fails

        elif not selected_lang_code:
            logger.error(tr("log_gui_language_code_not_found", language=selected_language_display_name))
### ende

    def _on_log_level_change(self, selected_level_display_name):
        """Called when a new log level is selected."""
        logger.debug(tr("log_gui_log_level_change_requested", level=selected_level_display_name))
        selected_level_str = None
        # Find the internal string name (e.g., "INFO")
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
        # Update indicator light
        if hasattr(self, 'ws_indicator_light'): self.ws_indicator_light.configure(fg_color="green" if is_enabled else "grey")
        self._update_initial_status() # Update overall status text

    def _on_streamerbot_enable_change(self):
        """Called when the Streamer.bot checkbox is changed."""
        is_enabled = bool(self.streamerbot_ws_enable_checkbox.get())
        logger.info(tr("log_gui_streamerbot_checkbox_changed", state=tr("status_enabled" if is_enabled else "status_disabled")))
        self.config["streamerbot_ws_enabled"] = is_enabled
        if is_enabled: self._start_streamerbot_client()
        else: self._stop_streamerbot_client()
        # Update indicator light
        if hasattr(self, 'sb_indicator_light'): self.sb_indicator_light.configure(fg_color="green" if is_enabled else "grey")
        self._update_initial_status() # Update overall status text

    def _update_ui_texts(self):
        """Updates all text-based widgets with the current language."""
        logger.debug(tr("log_gui_updating_ui_texts"))
        self.title(tr("app_title", version=APP_VERSION))
        # Warning about dynamic tab renaming being potentially problematic
        # logger.warning(tr("log_gui_tab_names_update_warning"))

        # Recreate log level display names map with current language
        self._update_log_level_display_names()

        # --- Update all widget texts using tr() AND APPLY FONTS ---
        try:
            # --- Local Tab Updates ---
            self.model_label.configure(text=tr("label_model_whisper"), font=gui_layout.FONT_BOLD)
            self.model_combobox.configure(font=gui_layout.FONT_NORMAL) # Re-apply normal font if needed
            # --- Open AI Tab Updates ---
            self.openai_api_key_label.configure(text=tr("label_api_key_openai"), font=gui_layout.FONT_BOLD)
            self.openai_api_key_entry.configure(placeholder_text=tr("placeholder_api_key_openai"), font=gui_layout.FONT_NORMAL)
            # --- Elevenlabs Tab Updates ---
            self.elevenlabs_api_key_label.configure(text=tr("label_api_key_elevenlabs"), font=gui_layout.FONT_BOLD)
            self.elevenlabs_api_key_entry.configure(placeholder_text=tr("placeholder_api_key_elevenlabs"), font=gui_layout.FONT_NORMAL)
            self.elevenlabs_model_id_label.configure(text=tr("label_model_id_elevenlabs"), font=gui_layout.FONT_BOLD)
            self.elevenlabs_model_id_entry.configure(placeholder_text=tr("placeholder_model_id_elevenlabs"), font=gui_layout.FONT_NORMAL)
            self.filter_parentheses_checkbox.configure(text=tr("checkbox_filter_parentheses"), font=gui_layout.FONT_NORMAL)
            # --- Websocket Tab Updates ---
            self.ws_incoming_label.configure(text=tr("label_websocket_incoming"), font=gui_layout.FONT_BOLD)
            self.websocket_enable_checkbox.configure(text=tr("checkbox_websocket_enable"), font=gui_layout.FONT_NORMAL)
            self.ws_port_label.configure(text=tr("label_websocket_port"), font=gui_layout.FONT_BOLD)
            self.websocket_port_entry.configure(font=gui_layout.FONT_NORMAL)
            self.ws_port_info_label.configure(font=gui_layout.FONT_NORMAL) # Text updated below
            self.ws_cmd_info_label.configure(text=tr("label_websocket_command_info"), font=gui_layout.FONT_NORMAL)
            # --- Integration Tab Updates ---
            self.sb_outgoing_label.configure(text=tr("label_integration_outgoing"), font=gui_layout.FONT_BOLD)
            self.streamerbot_ws_enable_checkbox.configure(text=tr("checkbox_integration_enable"), font=gui_layout.FONT_NORMAL)
            self.sb_url_label.configure(text=tr("label_integration_url"), font=gui_layout.FONT_BOLD)
            self.streamerbot_ws_url_entry.configure(placeholder_text=tr("placeholder_integration_url"), font=gui_layout.FONT_NORMAL)
            self.sb_url_info_label.configure(text=tr("label_integration_url_info"), font=gui_layout.FONT_NORMAL)
            self.sb_prefix_label.configure(text=tr("label_integration_prefix"), font=gui_layout.FONT_BOLD)
            self.stt_prefix_entry.configure(font=gui_layout.FONT_NORMAL)
            self.replacement_botname_label.configure(text=tr("label_replacement_botname"), font=gui_layout.FONT_BOLD)
            self.replacement_botname_entry.configure(font=gui_layout.FONT_NORMAL) # Ensure font is reapplied            

            # Update dynamic texts within loop
            try: # Safely update port info label
                current_port = self.websocket_port_entry.get()
                self.ws_port_info_label.configure(text=tr("label_websocket_port_info", port=current_port))
            except Exception: pass # Ignore if port entry not ready/invalid


            # Config Sections
            self.mic_label.configure(text=tr("label_mic"), font=gui_layout.FONT_BOLD)
            self.mic_combobox.configure(font=gui_layout.FONT_NORMAL) # Apply font
            self.refresh_button.configure(text=tr("button_mic_reload"), font=gui_layout.FONT_NORMAL)

            self.language_stt_label.configure(text=tr("label_language_stt"), font=gui_layout.FONT_BOLD)
            self.language_entry.configure(placeholder_text=tr("placeholder_language_stt"), font=gui_layout.FONT_NORMAL)

            self.format_label.configure(text=tr("label_format"), font=gui_layout.FONT_BOLD)
            self.txt_radio.configure(text=tr("radio_format_txt"), font=gui_layout.FONT_NORMAL)
            self.json_radio.configure(text=tr("radio_format_json"), font=gui_layout.FONT_NORMAL)

            self.output_file_label.configure(text=tr("label_output_file"), font=gui_layout.FONT_BOLD)
            self.filepath_entry.configure(placeholder_text=tr("placeholder_output_file", filename=DEFAULT_TRANSCRIPTION_FILE), font=gui_layout.FONT_NORMAL)
            self.browse_button.configure(text=tr("button_browse"), font=gui_layout.FONT_NORMAL)

            self.min_buffer_label.configure(text=tr("label_min_buffer"), font=gui_layout.FONT_BOLD)
            self.min_buffer_entry.configure(font=gui_layout.FONT_NORMAL)
            self.silence_label.configure(text=tr("label_silence_threshold"), font=gui_layout.FONT_BOLD)
            self.silence_threshold_entry.configure(font=gui_layout.FONT_NORMAL)
            self.clear_log_checkbox.configure(text=tr("checkbox_clear_log"), font=gui_layout.FONT_NORMAL)

            # Right Panel
            self.ws_indicator_label.configure(font=gui_layout.FONT_NORMAL) # Re-apply font
            self.sb_indicator_label.configure(font=gui_layout.FONT_NORMAL) # Re-apply font
            self.start_stop_button.configure(font=gui_layout.FONT_NORMAL) # Re-apply font (text updated elsewhere)
            self.edit_filter_button.configure(text=tr("button_edit_filter"), font=gui_layout.FONT_NORMAL)
            self.edit_replacements_button.configure(text=tr("button_edit_replacements"), font=gui_layout.FONT_NORMAL)

            # Output Area
            self.textbox.configure(font=gui_layout.FONT_NORMAL) # Re-apply font
            self.clear_log_button.configure(text=tr("button_clear_output"), font=gui_layout.FONT_NORMAL)

            # Status Bar
            self.status_label.configure(font=gui_layout.FONT_NORMAL) # Re-apply font
            self.language_ui_label.configure(text=tr("label_language_ui"), font=gui_layout.FONT_NORMAL)
            self.language_optionmenu.configure(font=gui_layout.FONT_NORMAL) # Apply font
            self.log_level_label.configure(text=tr("label_log_level"), font=gui_layout.FONT_NORMAL)
            self.log_level_optionmenu.configure(font=gui_layout.FONT_NORMAL) # Apply font


        except AttributeError as e:
            logger.error(f"Error configuring widget text/font during language update: {e}. Widget might not exist yet.")
        except Exception as e:
            logger.exception(f"Unexpected error during UI text/font update: {e}")


        # Update language dropdown options and value
        try:
            language_options = list(self.available_languages.values()) if self.available_languages else ["N/A"]
            current_display_language = self.available_languages.get(self.current_lang_code, "??")
            self.language_optionmenu.configure(values=language_options)
            # Fallback logic
            if current_display_language == "??" or current_display_language not in language_options:
                fallback_lang_name = self.available_languages.get(DEFAULT_LANGUAGE)
                if fallback_lang_name and fallback_lang_name in language_options: current_display_language = fallback_lang_name
                elif language_options and language_options != ["N/A"]: current_display_language = language_options[0]
                else: current_display_language = "Error"
            self.language_optionmenu.set(current_display_language)
        except AttributeError: logger.error("Language OptionMenu not ready for text update.")
        except Exception as e: logger.exception(f"Error updating language dropdown: {e}")

        # Update log level dropdown options and value
        try:
            level_display_options = list(self.log_level_display_names.values())
            current_log_level_str = self.config.get("log_level", DEFAULT_LOG_LEVEL)
            current_log_level_display = self.log_level_display_names.get(current_log_level_str, tr("log_level_info"))
            self.log_level_optionmenu.configure(values=level_display_options)
            # Fallback logic
            if current_log_level_display not in level_display_options:
                current_log_level_display = self.log_level_display_names.get(DEFAULT_LOG_LEVEL, tr("log_level_info"))
            self.log_level_optionmenu.set(current_log_level_display)
        except AttributeError: logger.error("Log Level OptionMenu not ready for text update.")
        except Exception as e: logger.exception(f"Error updating log level dropdown: {e}")

        # Update other dynamic elements if necessary
        self._check_record_button_state() # Update button text
        self._update_initial_status() # Update status bar text
        logger.debug(tr("log_gui_ui_texts_updated"))


    def _update_initial_status(self):
        ws_enabled = self.config.get("websocket_enabled", False)
        sb_enabled = self.config.get("streamerbot_ws_enabled", False)
        base_status = tr("status_ready")
        suffix = ""
        if not ws_enabled:
            # Try getting specific status part, fallback to generic disabled text
            try: ws_part = tr("status_ready_ws_disabled").replace(base_status, "").strip()
            except KeyError: ws_part = tr("status_disabled") + " (WS)" # Fallback
            suffix += ws_part
        if not sb_enabled:
            try: sb_part = tr("status_ready_sb_disabled").strip()
            except KeyError: sb_part = tr("status_disabled") + " (SB)" # Fallback
            if suffix and sb_part: suffix += " "
            suffix += sb_part
        suffix = suffix.strip()
        if suffix: self._update_status(f"{base_status} ({suffix})", log=False, is_key=False)
        else: self._update_status("status_ready", log=False, is_key=True)

    def _on_mic_change(self, choice):
        """Callback when microphone selection changes."""
        if choice in self.available_mics:
            # Extract display name robustly
            mic_display_name = choice.split(":", 1)[-1].strip() if ":" in choice else choice
            self._update_status("status_mic_selected", mic_name=mic_display_name, is_key=True)
            # Store the selected full name in config for persistence
            self.config['mic_name'] = choice
            logger.info(f"Microphone selected in GUI: {choice}")
        elif choice != tr("combobox_mic_loading"): # Avoid warning during load
            self._update_status("status_mic_invalid", level="warning", is_key=True)
            logger.warning(f"Invalid microphone selection in GUI: {choice}")

    def _browse_output_file(self):
        """Opens a file dialog to select the output file."""
        try:
            file_format = self.format_var.get()
        except AttributeError:
            logger.warning("Format variable not initialized yet for browse dialog.")
            file_format = DEFAULT_OUTPUT_FORMAT # Fallback

        default_extension = f".{file_format}"
        txt_desc = tr("dialog_file_type_txt")
        json_desc = tr("dialog_file_type_json")
        all_desc = tr("dialog_file_type_all")
        file_types = [(f"{txt_desc}", "*.txt"), (f"{json_desc}", "*.json"), (f"{all_desc}", "*.*")]

        try: current_path = self.filepath_entry.get()
        except AttributeError: current_path = ""

        initial_dir = os.path.dirname(current_path) if current_path and os.path.dirname(current_path) else "."
        initial_file = os.path.basename(current_path) if current_path else DEFAULT_TRANSCRIPTION_FILE

        # Ensure initial_dir exists before passing to filedialog
        if not os.path.isdir(initial_dir):
            logger.warning(f"Initial directory for file dialog not found: '{initial_dir}'. Using current directory.")
            initial_dir = "."

        filepath = filedialog.asksaveasfilename(
            title=tr("dialog_select_output_file"),
            initialdir=initial_dir, initialfile=initial_file,
            defaultextension=default_extension, filetypes=file_types
        )
        if filepath:
            try:
                self.filepath_entry.delete(0, "end")
                self.filepath_entry.insert(0, filepath)
                self._update_status("status_output_file_selected", filename=os.path.basename(filepath), is_key=True)
                logger.info(tr("log_gui_output_file_selected", filepath=filepath))
            except AttributeError: logger.error("Filepath entry widget not available for update.")


    def _edit_filter_file(self):
        """Opens the appropriate filter file in the default editor."""
        try:
            current_tab_name = self.tab_view.get()
            current_mode = self._tab_name_to_mode_safe(current_tab_name)
        except Exception as e:
            logger.warning(f"Could not get current tab name for editing filter file: {e}")
            current_mode = "local" # Default to local filter

        target_file = FILTER_FILE_EL if current_mode == "elevenlabs" else FILTER_FILE
        # Ensure the directory exists
        try: os.makedirs(os.path.dirname(target_file), exist_ok=True)
        except OSError as e: logger.error(f"Could not create directory for filter file {target_file}: {e}")

        # Ensure the file exists (create if not)
        if not os.path.exists(target_file):
            try:
                with open(target_file, 'w', encoding='utf-8') as f: f.write("# Filter patterns (one per line)\n")
                logger.info(f"Created filter file: {target_file}")
            except IOError as e:
                logger.error(f"Could not create filter file {target_file}: {e}")
                self._update_status("status_error_filter_create", filename=os.path.basename(target_file), level="error", is_key=True)
                return

        # Open the file
        self._open_file_in_editor(target_file)

    def _edit_replacements_file(self):
        """Opens the replacements file in the default editor."""
        target_file = REPLACEMENTS_FILE
        # Ensure the directory exists
        try: os.makedirs(os.path.dirname(target_file), exist_ok=True)
        except OSError as e: logger.error(f"Could not create directory for replacements file {target_file}: {e}")

        # Ensure the file exists (create if not, with JSON structure)
        if not os.path.exists(target_file):
            try:
                with open(target_file, 'w', encoding='utf-8') as f: json.dump({}, f, indent=4)
                logger.info(f"Created replacements file: {target_file}")
            except IOError as e:
                logger.error(f"Could not create replacements file {target_file}: {e}")
                self._update_status("status_error_replacements_create", level="error", is_key=True)
                return

        # Open the file
        self._open_file_in_editor(target_file)

    def _open_file_in_editor(self, filepath):
        """Attempts to open a file using the system's default application."""
        filename = os.path.basename(filepath)
        if not os.path.exists(filepath):
            self._update_status("status_error_file_not_found", filename=filename, level="error", is_key=True)
            logger.error(tr("log_gui_file_not_found", filepath=filepath))
            return
        try:
            logger.info(tr("log_gui_opening_file", filepath=filepath))
            self._update_status("status_opening_editor", filename=filename, is_key=True)
            if sys.platform == "win32": os.startfile(filepath)
            elif sys.platform == "darwin": subprocess.call(["open", filepath])
            else: subprocess.call(["xdg-open", filepath])
            # Update status after a short delay
            self.after(1000, lambda: self._update_status("status_opened_editor", filename=filename, log=False, is_key=True))
        except FileNotFoundError: # Should be caught by the check above, but for safety
            self._update_status("status_error_file_not_found", filename=filename, level="error", is_key=True)
            logger.error(tr("log_gui_file_not_found", filepath=filepath))
        except OSError as e: # Permissions issues, etc.
            self._update_status("status_error_opening_file", error=e, level="error", is_key=True)
            logger.error(tr("log_gui_os_error_opening_file", filepath=filepath, error=e))
        except Exception as e: # Catch all other errors
            self._update_status("status_error_opening_file", error=e, level="error", is_key=True)
            logger.exception(tr("log_gui_unknown_error_opening_file", filepath=filepath))

    def _clear_textbox(self):
        """Clears the main output textbox."""
        try:
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.configure(state="disabled")
            self._update_status("status_output_cleared", is_key=True)
        except tk.TclError as e: # Handle case where widget might be destroyed
            logger.warning(f"TclError clearing textbox (might be closing): {e}")
        except AttributeError: # Handle case where self.textbox doesn't exist yet
            logger.warning("Textbox widget not available for clearing.")
        except Exception as e:
            logger.exception(tr("log_gui_textbox_clear_error"))
            self._update_status("status_error_clearing_output", level="error", is_key=True)

    def _show_context_menu(self, event):
        """Displays the right-click context menu for the textbox."""
        try:
            menu = tk.Menu(self, tearoff=0) # Use tk.Menu for context menu
            has_selection = False
            try:
                # Check if there's selected text in the textbox
                if self.textbox.tag_ranges("sel"): has_selection = True
            except tk.TclError: pass # No selection exists

            if has_selection:
                menu.add_command(label=tr("context_copy"), command=self._copy_selection_to_clipboard)
                menu.add_separator()
                menu.add_command(label=tr("context_add_filter"), command=self._add_selection_to_filter)
                menu.add_command(label=tr("context_add_replacement"), command=self._add_botname_replacement_from_selection)
            else:
                menu.add_command(label=tr("context_copy_all"), command=self._copy_all_to_clipboard)

            menu.add_separator()
            menu.add_command(label=tr("context_clear_output"), command=self._clear_textbox)

            # Display the menu at the cursor position
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            # Ensure the menu doesn't linger
            menu.grab_release()

    def _copy_selection_to_clipboard(self):
        """Copies selected text from the textbox to the clipboard."""
        try:
            selected_text = self.textbox.get("sel.first", "sel.last")
            if selected_text:
                self.clipboard_clear()
                self.clipboard_append(selected_text)
                self._update_status("status_selection_copied", log=False, is_key=True)
        except tk.TclError: # This happens if there's no selection
            self._update_status("status_no_selection", level="info", log=False, is_key=True)
        except Exception as e:
            logger.error(tr("log_gui_copy_selection_error", error=e))
            self._update_status("status_error_copy", level="error", is_key=True)

    def _copy_all_to_clipboard(self):
        """Copies all text from the textbox to the clipboard."""
        try:
            # Get text from the beginning (1.0) to the end, minus the trailing newline (-1c)
            all_text = self.textbox.get("1.0", "end-1c")
            if all_text:
                self.clipboard_clear()
                self.clipboard_append(all_text)
                self._update_status("status_all_copied", log=False, is_key=True)
        except Exception as e:
            logger.error(tr("log_gui_copy_all_error", error=e))
            self._update_status("status_error_copy", level="error", is_key=True)

    def _add_selection_to_filter(self):
        """Adds the selected text to the appropriate filter file."""
        try:
            selected_text = self.textbox.get("sel.first", "sel.last").strip()
        except tk.TclError:
            self._update_status("status_no_selection", level="info", is_key=True)
            return
        if not selected_text:
            self._update_status("status_empty_selection", level="info", is_key=True)
            return

        # Determine target filter file based on current mode
        try:
            current_mode = self._tab_name_to_mode_safe(self.tab_view.get())
        except Exception as e:
            logger.warning(f"Could not get current tab mode for adding filter: {e}")
            current_mode = "local" # Default

        target_file = FILTER_FILE_EL if current_mode == "elevenlabs" else FILTER_FILE
        filename = os.path.basename(target_file)

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            # Append the selected text on a new line
            with open(target_file, "a+", encoding="utf-8") as f:
                # Check if file needs a newline before adding text
                f.seek(0, os.SEEK_END) # Go to end of file
                if f.tell() > 0: # If file is not empty
                    f.seek(f.tell() - 1, os.SEEK_SET) # Go to last character
                    if f.read(1) != '\n': # Add newline if last char isn't one
                        f.write("\n")
                f.write(selected_text)

            self._update_status("status_filter_added", text=selected_text[:30], filename=filename, is_key=True)
            logger.info(tr("log_gui_filter_added_context", text=selected_text, target_file=target_file))
            # Reload the filter patterns into memory
            if target_file == FILTER_FILE: self.loaded_filter_patterns = load_filter_patterns(FILTER_FILE)
            else: self.loaded_filter_patterns_el = load_filter_patterns(FILTER_FILE_EL)
        except IOError as e:
            logger.error(tr("log_gui_filter_write_error", target_file=target_file, error=e))
            self._update_status("status_error_saving_filter", error=e, level="error", is_key=True)
        except Exception as e:
            logger.exception(tr("log_gui_filter_add_error"))
            self._update_status("status_error_saving_filter", error=e, level="error", is_key=True)

    # IMPORTANT: Ensure this method is indented correctly inside the WhisperGUI class
    def _add_botname_replacement_from_selection(self):
        """Adds the selected text as a key to the replacements JSON
        using the Botname defined in the GUI entry field."""
        try:
            # Get selected text from the main textbox
            selected_text = self.textbox.get("sel.first", "sel.last").strip()
        except tk.TclError:
            # No text selected
            self._update_status("status_no_selection", level="info", is_key=True)
            return
        if not selected_text:
            # Selection was empty (e.g., just whitespace)
            self._update_status("status_empty_selection", level="info", is_key=True)
            return

        # Use selected text directly as the key (case-sensitive for JSON keys)
        pattern_key = selected_text

        # Read Botname from the GUI entry field added previously
        try:
            # Get value from the entry widget (ensure self.replacement_botname_entry exists)
            correct_name = self.replacement_botname_entry.get().strip()
            if not correct_name: # Fallback if user cleared the field
                correct_name = DEFAULT_REPLACEMENT_BOTNAME # Use default from constants
                # Log this fallback
                logger.warning(f"Replacement Botname field is empty, using default: {correct_name}")
        except AttributeError: # Handle case where entry widget might not exist yet
            logger.error("Replacement Botname entry widget not found! Using default.")
            correct_name = DEFAULT_REPLACEMENT_BOTNAME # Fallback

        # Check if the exact key already exists with the same value
        # Use self.loaded_replacements which should be kept up-to-date
        if pattern_key in self.loaded_replacements and self.loaded_replacements[pattern_key] == correct_name:
            self._update_status("status_replacement_exists", text=selected_text[:20], level="info", is_key=True)
            return

        # Add or update the replacement in the in-memory dictionary
        self.loaded_replacements[pattern_key] = correct_name
        # Use tr() for logging (key should exist in language files)
        logger.info(tr("log_gui_replacement_added_context", pattern=pattern_key, replacement=correct_name))

        # Save the updated replacements back to the file using the function from text_processing
        # Make sure REPLACEMENTS_FILE is imported from constants
        if save_replacements(self.loaded_replacements, REPLACEMENTS_FILE):
            # Success
            self._update_status("status_replacement_added", text=selected_text[:20], level="success", is_key=True)
        else:
            # Save failed, reload from file to revert in-memory change
            # This prevents the UI state from diverging from the file state on error
            logger.warning("Failed to save replacements file. Reverting in-memory changes by reloading.")
            self.loaded_replacements = load_replacements(REPLACEMENTS_FILE) # Revert in-memory change by reloading
            # Notify user of the error
            self._update_status("status_error_saving_replacements", text=selected_text[:20], level="error", is_key=True)

    def populate_mic_dropdown(self):
        """Initiates the microphone discovery in a separate thread."""
        # Update GUI immediately to show loading state
        self._update_status("status_mic_search", level="info", is_key=True)
        try:
            self.mic_combobox.configure(values=[tr("combobox_mic_loading")], state="disabled")
            self.update_idletasks() # Ensure GUI updates before starting thread
        except tk.TclError: logger.warning("Mic combobox TclError on configure (populate).")
        except AttributeError: logger.warning("Mic combobox not ready for populate.")

        # Start the thread to list devices
        threading.Thread(target=self._populate_mic_thread_target, args=(self.gui_q,), daemon=True, name="MicScanThread").start()

    def _populate_mic_thread_target(self, gui_q):
        """Worker thread function to list audio devices."""
        try:
            # This function should put messages like ('status', 'key') or ('error', 'key') on gui_q
            self.available_mics = list_audio_devices_for_gui(gui_q) # Pass the queue
            mic_names = list(self.available_mics.keys())
            saved_mic_name = self.config.get("mic_name") # Get the full name saved previously

            def update_gui():
                """Safely updates the GUI from the main thread."""
                no_mics_text = tr("combobox_mic_nodata")
                error_text = tr("combobox_mic_error")
                try:
                    self.mic_combobox.configure(values=mic_names if mic_names else [no_mics_text], state="readonly" if mic_names else "disabled")
                    if mic_names:
                        selected_mic = None
                        # Try to restore previously selected mic
                        if saved_mic_name and saved_mic_name in mic_names:
                            selected_mic = saved_mic_name
                            logger.debug(f"Restoring saved microphone: {selected_mic}")
                        else:
                            # Try finding the system default
                            default_mic_name = next((name for name in mic_names if "(Default)" in name or "(Standard)" in name), None) # More robust default check
                            if default_mic_name:
                                selected_mic = default_mic_name
                                logger.debug(f"Using system default microphone: {selected_mic}")
                            else:
                                selected_mic = mic_names[0] # Fallback to first mic
                                logger.debug(f"No default found, using first microphone: {selected_mic}")

                        if selected_mic:
                            self.mic_combobox.set(selected_mic)
                            # Update status only if selection changed or was set
                            self._on_mic_change(selected_mic) # Trigger status update via callback
                            # self._update_status("status_mics_loaded_selected", is_key=True) # Generic status
                        else: # Should not happen if mic_names is not empty
                            self.mic_combobox.set(error_text)
                            self._update_status("status_mics_loaded_error", level="warning", is_key=True)
                    else:
                        self.mic_combobox.set(no_mics_text)
                        self._update_status("status_mics_loaded_none", level="warning", is_key=True)

                except tk.TclError: logger.warning("Mic combobox TclError on update.")
                except AttributeError: logger.warning("Mic combobox not ready for update.")

            # Schedule the GUI update to run in the main thread
            self.after(0, update_gui)

        except Exception as e:
            logger.exception(tr("log_gui_mic_thread_error"))
            # Schedule error updates in the main thread
            self.after(0, lambda: self._update_status("status_mics_error", level="error", is_key=True))
            # Use lambda to ensure tr() is called in main thread context if possible
            self.after(0, lambda: self.mic_combobox.configure(values=[tr("combobox_mic_error")], state="disabled"))


    def _check_record_button_state(self):
        """Periodically checks recording state and updates button/indicator."""
        try:
            # Get current mode from the selected tab name
            current_tab_name = self.tab_view.get()
            current_mode = self._tab_name_to_mode_safe(current_tab_name)

            # Determine if button should be disabled based on mode
            is_mode_disabling_button = current_mode in ["websocket", "integration", "info"]

            if self.is_recording:
                self.indicator_light.configure(fg_color="red") # Recording indicator ON
                stop_text = tr("button_stop_recording")
                # Disable button if recording AND in a disabling mode, otherwise enable
                button_state = "disabled" if is_mode_disabling_button else "normal"
                # Don't change text if it's already "Stopping..."
                current_text = self.start_stop_button.cget("text")
                if current_text != tr("button_stopping_recording"):
                    self.start_stop_button.configure(state=button_state, text=stop_text)
                else: # Keep disabled if "Stopping..."
                    self.start_stop_button.configure(state="disabled")
            else:
                self.indicator_light.configure(fg_color="grey") # Recording indicator OFF
                start_text = tr("button_start_recording")
                # Disable button if NOT recording AND in a disabling mode, otherwise enable
                button_state = "disabled" if is_mode_disabling_button else "normal"
                self.start_stop_button.configure(state=button_state, text=start_text)

        except tk.TclError as e: # Handle cases where widgets might be destroyed during close
            if "invalid command name" in str(e): logger.debug(tr("log_gui_tkerror_check_button"))
            else: logger.warning(f"TclError checking button state: {e}")
        except AttributeError as e: # Handle cases where widgets aren't created yet
            logger.debug(f"AttributeError checking button state (likely init): {e}")
        except Exception as e:
            logger.warning(tr("log_gui_check_button_error", error=e))
        finally:
            # Schedule the next check only if the window still exists
            try:
                self.after(500, self._check_record_button_state)
            except tk.TclError: # Handle case where root window is destroyed
                logger.debug("Window destroyed, stopping record button check.")


    def toggle_recording(self):
        """ Toggles the recording state. """
        logger.debug(tr("log_gui_toggle_recording_called", status=tr("log_gui_recording_active" if self.is_recording else "log_gui_recording_inactive")))

        if self.is_recording:
            # --- Stop Recording ---
            logger.info(tr("log_gui_stopping_recording"))
            self._update_status("status_stopping_recording", level="info", is_key=True)
            self.flags['stop_recording'].set() # Signal the worker thread
            # Update button text immediately to "Stopping..." and disable it
            self.start_stop_button.configure(text=tr("button_stopping_recording"), state="disabled")
            logger.debug(tr("log_gui_stop_requested"))
            # The actual state change (is_recording=False) happens when the 'finished' message is received
        else:
            # --- Start Recording ---
            logger.info(tr("log_gui_starting_recording"))
            logger.debug(tr("log_gui_validating_start_conditions"))
            if not self._validate_start_conditions():
                logger.warning(tr("log_gui_start_conditions_failed"))
                # Ensure button is re-enabled if validation fails
                # self._check_record_button_state() # Already called periodically
                return # Don't proceed

            logger.debug(tr("log_gui_gathering_runtime_config"))
            current_config = self._gather_runtime_config_dict()
            if not current_config: # Check if config gathering failed
                logger.error(tr("log_gui_config_gathering_failed"))
                # self._check_record_button_state() # Already called periodically
                return

            try:
                logger.debug(tr("log_gui_preparing_worker_args"))
                worker_args = self._prepare_worker_args(current_config)
            except ValueError as e: # Catch specific errors from arg prep
                logger.error(tr("log_gui_worker_args_error", error=e))
                self._update_status("status_error_invalid_input", error=e, level="error", is_key=True)
                # self._check_record_button_state() # Already called periodically
                return
            except Exception as e: # Catch unexpected errors during prep
                logger.exception(f"Unexpected error preparing worker args: {e}")
                self._update_status("status_error_generic", error=str(e), level="error", is_key=True)
                # self._check_record_button_state() # Already called periodically
                return


            logger.debug(tr("log_gui_clearing_stop_flag"))
            self.flags['stop_recording'].clear() # Clear flag before starting
            self.is_recording = True # Set state *before* starting thread
            self._check_record_button_state() # Update button to "Stop Recording" / red light
            self._update_status("status_starting_recording", level="info", is_key=True)

            # Clear log file if requested
            if current_config.get("clear_log_on_start", False):
                log_filepath = current_config.get("output_filepath")
                if log_filepath: # Only clear if a path is actually set
                    try:
                        # Ensure directory exists before clearing file
                        log_dir = os.path.dirname(log_filepath) or '.'
                        os.makedirs(log_dir, exist_ok=True)
                        # Clear the file content
                        with open(log_filepath, 'w') as f: f.truncate(0)
                        logger.info(tr("log_gui_output_file_cleared", filepath=log_filepath))
                    except IOError as e:
                        logger.error(tr("log_gui_output_file_clear_error", filepath=log_filepath, error=e))
                        self._update_status("status_error_clearing_output_file", error=e, level="error", is_key=True)
                    except Exception as e: # Catch other potential errors like permissions
                        logger.error(f"Unexpected error clearing output file {log_filepath}: {e}")
                        self._update_status("status_error_clearing_output_file", error=e, level="error", is_key=True)
                else:
                    logger.warning("Clear log on start checked, but no output file path is set.")


            logger.debug(tr("log_gui_starting_worker_thread", mode=worker_args['processing_mode']))
            try:
                self.recording_thread = threading.Thread(
                    target=recording_worker, kwargs=worker_args, daemon=True, name="RecordingWorkerThread"
                )
                self.recording_thread.start()
                logger.info(tr("log_gui_worker_thread_started"))
            except Exception as e:
                logger.exception("Failed to start recording worker thread.")
                self.is_recording = False # Revert state
                self._check_record_button_state() # Update button/indicator
                self._update_status("status_error_starting_thread", error=e, level="error", is_key=True)

        # Update button state after action (handled by _check_record_button_state call)


    def _validate_start_conditions(self):
        """Checks if all necessary conditions to start recording are met."""
        # Check Microphone Selection
        try: mic_name = self.mic_combobox.get()
        except AttributeError: self._update_status("status_error_mic_select_fail", level="error", is_key=True); return False
        if not mic_name or mic_name == tr("combobox_mic_loading") or mic_name == tr("combobox_mic_nodata") or mic_name not in self.available_mics:
            self._update_status("status_error_mic_select_fail", level="error", is_key=True); return False

        # Check Output File Path and Directory Permissions
        try: output_file = self.filepath_entry.get().strip()
        except AttributeError: output_file = ""
        if output_file:
            output_dir = os.path.dirname(output_file) or "."
            # Try creating the directory if it doesn't exist
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    logger.info(tr("log_gui_output_dir_created", output_dir=output_dir))
                except OSError as e:
                    self._update_status("status_error_output_dir_create", error=e, level="error", is_key=True)
                    logger.error(f"Failed to create output directory '{output_dir}': {e}")
                    return False
            # Check write permissions for the directory
            if not os.access(output_dir, os.W_OK):
                self._update_status("status_error_output_dir_write", level="error", is_key=True)
                logger.error(f"No write permission for output directory: '{output_dir}'")
                return False
        # else: Output file is optional, maybe log a warning?
        #    logger.warning("No output file specified.")

        # Check Mode-Specific Requirements
        try:
            current_mode = self._tab_name_to_mode_safe(self.tab_view.get())
            if current_mode == "openai" and not self.openai_api_key_entry.get():
                self._update_status("status_error_api_key_openai", level="error", is_key=True); return False
            if current_mode == "elevenlabs":
                if not self.elevenlabs_api_key_entry.get():
                    self._update_status("status_error_api_key_elevenlabs", level="error", is_key=True); return False
                if not self.elevenlabs_model_id_entry.get():
                    self._update_status("status_error_model_id_elevenlabs", level="error", is_key=True); return False
        except AttributeError as e:
            logger.error(f"Error accessing tab widgets during validation: {e}")
            self._update_status("status_error_reading_settings", error=e, level="error", is_key=True)
            return False


        # Check Numeric Inputs
        try:
            float(self.min_buffer_entry.get())
            float(self.silence_threshold_entry.get())
        except (ValueError, AttributeError) as e:
            self._update_status("status_error_numeric_buffer", level="error", is_key=True)
            logger.error(f"Invalid numeric input for buffer/silence: {e}")
            return False

        # All checks passed
        return True

    def _gather_runtime_config_dict(self):
        """ Gathers current settings from GUI elements into a dictionary. """
        try:
            # Create the dictionary
            config_dict = {
                "mode": self._tab_name_to_mode_safe(self.tab_view.get()),
                "openai_api_key": self.openai_api_key_entry.get(),
                "elevenlabs_api_key": self.elevenlabs_api_key_entry.get(),
                "mic_name": self.mic_combobox.get(), # Full name as selected
                "local_model": self.model_combobox.get(),
                "language": self.language_entry.get().strip(),
                "language_ui": self.current_lang_code,
                "log_level": self.config.get("log_level", DEFAULT_LOG_LEVEL), # Get from internal config
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
                "stt_prefix": self.stt_prefix_entry.get(),
                "replacement_botname": self.replacement_botname_entry.get().strip() # Read value from new entry
            }
            # Perform quick sanity checks on numeric conversions again
            # CORRECTED INDENTATION: These lines are now at the same level as config_dict assignment
            float(config_dict["min_buffer_duration"])
            float(config_dict["silence_threshold"])
            int(config_dict["websocket_port"])
            return config_dict
        # CORRECTED INDENTATION: except block is now at the same level as 'try'
        except (tk.TclError, AttributeError, ValueError) as e:
            # Catch errors if widgets don't exist or values are invalid
            logger.error(tr("log_gui_runtime_config_error", error=e))
            self._update_status("status_error_reading_settings", error=e, level="error", is_key=True)
            return None # Indicate failure


    def _prepare_worker_args(self, current_config):
        """Prepares the dictionary of arguments for the recording_worker thread."""
        processing_mode = current_config['mode']

        # Choose filter patterns based on mode
        filter_patterns_to_use = self.loaded_filter_patterns_el if processing_mode == "elevenlabs" else self.loaded_filter_patterns

        # Get the internal device ID from the selected display name
        selected_mic_name = current_config['mic_name']
        device_id = self.available_mics.get(selected_mic_name)
        if device_id is None:
            # This should ideally be caught by _validate_start_conditions, but double-check
            raise ValueError(tr("log_gui_error_mic_id_not_found", mic_name=selected_mic_name))

        args = {
            "processing_mode": processing_mode,
            "openai_api_key": current_config['openai_api_key'],
            "elevenlabs_api_key": current_config['elevenlabs_api_key'],
            "device_id": device_id, # Use the retrieved internal ID
            "samplerate": DEFAULT_SAMPLERATE,
            "channels": DEFAULT_CHANNELS,
            "model_name": current_config['local_model'],
            "language": current_config['language'] or None, # Pass None if empty
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

        logger.debug(tr("log_gui_worker_preparation", output_file=args['output_file']))
        return args

    def _process_gui_queue(self):
        """ Processes messages from other threads placed on the gui_q. """
        try:
            while True:  # Process all available messages in the queue
                msg_type, msg_data = self.queues['gui_q'].get_nowait()

                # Determine if the message data is likely a translation key
                is_key = isinstance(msg_data, str) and msg_data.startswith((
                    "status_", "combobox_", "context_", "dialog_",
                    "log_level_", "button_"
                ))

                if msg_type == "transcription":
                    # Append transcription text to the textbox
                    try:
                        self.textbox.configure(state="normal")
                        self.textbox.insert("end", msg_data + "\n")
                        self.textbox.configure(state="disabled")
                        self.textbox.see("end")  # Auto-scroll to the end
                    except (tk.TclError, AttributeError):
                        pass

                elif msg_type == "status":
                    # Update the status bar label
                    self._update_status(msg_data, level="info", log=False, is_key=is_key)

                elif msg_type == "error":
                    # Update status bar with error style and log the error
                    is_error_key = isinstance(msg_data, str) and msg_data.startswith("status_error_")
                    kwargs = {}
                    key_or_msg = msg_data if is_error_key else "status_error_generic"
                    if not is_error_key:
                        kwargs['error'] = msg_data
                    self._update_status(key_or_msg, level="error", log=True, is_key=True, **kwargs)

                elif msg_type == "warning":
                    # Update status bar with warning style and log the warning
                    is_warn_key = isinstance(msg_data, str) and msg_data.startswith("status_warn_")
                    self._update_status(msg_data, level="warning", log=True, is_key=is_warn_key)

                elif msg_type == "toggle_recording_external":
                    # Handle external command (e.g., from WebSocket) to toggle recording
                    logger.info(tr("log_gui_external_toggle_command"))
                    logger.debug(tr("log_gui_calling_toggle_recording"))
                    self.toggle_recording()
                    logger.debug(tr("log_gui_toggle_recording_call_finished"))

                elif msg_type == "finished":
                    # Handle signal that the recording worker thread has finished
                    logger.info(tr("log_gui_worker_finished"))
                    self.is_recording = False
                    self.recording_thread = None
                    self._check_record_button_state()
                    self._update_initial_status()

                elif msg_type == "ws_state":
                    # payload ∈ {"disabled","enabled","connected"}
                    colors = {
                        "disabled": "grey",
                        "enabled":  "yellow",
                        "connected":"green"
                    }
                    self.ws_indicator_light.configure(fg_color=colors.get(msg_data, "grey"))

                elif msg_type == "sb_state":
                    # payload ∈ {"disabled","connecting","connected"}
                    colors = {
                        "disabled":   "grey",
                        "connecting":"yellow",
                        "connected": "green"
                    }
                    self.sb_indicator_light.configure(fg_color=colors.get(msg_data, "grey"))

                else:
                    # Log unexpected message types
                    logger.warning(tr("log_gui_unknown_message_type", type=msg_type))

                self.queues['gui_q'].task_done()

        except queue.Empty:
            pass  # No messages left in the queue

        except Exception:
            logger.exception(tr("log_gui_queue_processing_error"))

        finally:
            # Schedule the next check of the queue
            try:
                self.after(100, self._process_gui_queue)
            except tk.TclError:
                logger.debug("Window destroyed, stopping GUI queue processing.")



    def _update_status(self, message_or_key, level="info", log=True, is_key=True, **kwargs):
        """Updates the status bar label with appropriate text and color."""
        message = ""
        try:
            # Translate message if it's a key, otherwise format/use as is
            if is_key:
                message = tr(message_or_key, **kwargs)
            else:
                # Try formatting if kwargs are provided, otherwise just convert to string
                try: message = str(message_or_key).format(**kwargs) if kwargs else str(message_or_key)
                except (KeyError, IndexError, TypeError): message = str(message_or_key) # Fallback if format fails

            # Truncate long messages for the status bar
            status_text = message if len(message) < 150 else message[:147] + "..."

            # Update the status label widget
            self.status_label.configure(text=status_text)

            # Set text color based on level
            color_map = {
                "error": ("white", "red"),      # Dark mode, Light mode text color
                "warning": ("black", "#b35900"), # Dark orange for light mode
                "success": ("white", "green")   # Example for success messages
            }
            # Get default text color from theme, provide fallback
            try: default_fg = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
            except: default_fg = ("white", "black") # Basic fallback -> white on dark, black on light

            # Apply the color
            self.status_label.configure(text_color=color_map.get(level, default_fg))

        except tk.TclError:
            # Handle error if the status label widget is already destroyed (e.g., during closing)
            logger.warning(tr("log_gui_status_label_update_error"))
            return # Stop processing if widget gone
        except AttributeError:
            # Handle error if status_label doesn't exist yet (init race condition?)
            logger.warning("Status label not ready for update.")
            return
        except Exception as e:
            logger.error(f"Unexpected error updating status label: {e}")


        # Log the full status message if requested
        if log:
            log_func = getattr(logger, level, logger.info) # Get log function based on level
            log_func(tr("log_gui_status", message=message)) # Log the full, untruncated message

    # --- Management of background tasks ---
    def _start_websocket_server(self):
        """Starts the WebSocket server thread if enabled and not already running."""
        if not self.config.get("websocket_enabled", False): return # Only start if enabled
        if self.websocket_server_thread and self.websocket_server_thread.is_alive():
            logger.debug("WebSocket server thread already running.")
            return

        try: port = int(self.websocket_port_entry.get())
        except (ValueError, tk.TclError, AttributeError):
            logger.warning("Invalid WebSocket port, using default.")
            port = WEBSOCKET_PORT # Use default if GUI value invalid

        self._update_status("status_ws_server_starting", port=port, level="info", is_key=True)
        try:
            # start_websocket_server_thread should return (thread, stop_event)
            self.websocket_server_thread, self.websocket_stop_event = start_websocket_server_thread(port, self.gui_q)
            if self.websocket_server_thread: logger.info(f"WebSocket server thread started on port {port}.")
            else: logger.error("Failed to start WebSocket server thread (returned None).")
        except Exception as e:
            logger.exception(f"Failed to start WebSocket server thread: {e}")
            self._update_status("status_error_starting_ws", error=e, level="error", is_key=True)

        # Update indicator after attempting start
        if hasattr(self, 'ws_indicator_light'): self.ws_indicator_light.configure(fg_color="green" if self.websocket_server_thread and self.websocket_server_thread.is_alive() else "grey")


    def _stop_websocket_server(self):
        """Stops the WebSocket server thread if it's running."""
        stopped = False
        if self.websocket_server_thread and self.websocket_server_thread.is_alive() and self.websocket_stop_event:
            logger.info(tr("log_gui_sending_ws_stop_signal"))
            try:
                # Attempt graceful shutdown via event loop if possible
                loop = getattr(self.websocket_stop_event, '_custom_loop_ref', None)
                if loop and loop.is_running():
                    loop.call_soon_threadsafe(self.websocket_stop_event.set)
                    logger.info(tr("log_gui_ws_stop_event_set_via_loop"))
                else:
                    # Fallback if loop not found or not running
                    logger.warning(tr("log_gui_ws_loop_not_found"))
                    self.websocket_stop_event.set()
                # Give the thread a moment to shut down
                self.websocket_server_thread.join(timeout=1.0)
                if not self.websocket_server_thread.is_alive():
                    logger.info("WebSocket server thread terminated gracefully.")
                    stopped = True
                else:
                    logger.warning("WebSocket server thread did not terminate after stop signal and timeout.")

            except Exception as e:
                logger.error(tr("log_gui_ws_stop_event_error", error=e))
        elif self.websocket_server_thread:
            logger.debug("WebSocket server thread exists but is not alive or stop event missing.")
            stopped = True # Consider it stopped if not alive
        else:
            logger.debug("No WebSocket server thread to stop.")
            stopped = True

        # Clear references regardless of graceful stop success
        self.websocket_server_thread = None
        self.websocket_stop_event = None
        # Update indicator after attempting stop
        if hasattr(self, 'ws_indicator_light'): self.ws_indicator_light.configure(fg_color="grey")
        if stopped: self._update_status("status_ws_server_stopped", level="info", is_key=True)


    def _start_streamerbot_client(self):
        """Starts the Streamer.bot client thread if enabled and not already running."""
        if not self.config.get("streamerbot_ws_enabled", False): return
        if self.streamerbot_client_thread and self.streamerbot_client_thread.is_alive():
            logger.debug("Streamer.bot client thread already running.")
            return

        try: ws_url = self.streamerbot_ws_url_entry.get().strip()
        except AttributeError:
            logger.error("Streamer.bot URL entry widget not available.")
            return

        if not ws_url.startswith(("ws://", "wss://")):
            self._update_status("status_error_sb_url_invalid", url=ws_url, level="error", is_key=True)
            logger.error(f"Invalid Streamer.bot WebSocket URL: {ws_url}")
            return

        self._update_status("status_sb_client_starting", url=ws_url, level="info", is_key=True)
        self.flags['stop_streamerbot'].clear() # Clear stop flag before starting
        try:
            self.streamerbot_client_thread = start_streamerbot_client_thread(
                ws_url, self.queues['streamerbot_q'], self.flags['stop_streamerbot'], self.queues['gui_q']
            )
            if self.streamerbot_client_thread: logger.info(f"Streamer.bot client thread started for {ws_url}.")
            else: logger.error("Failed to start Streamer.bot client thread (returned None).")
        except Exception as e:
            logger.exception(f"Failed to start Streamer.bot client thread: {e}")
            self._update_status("status_error_starting_sb", error=e, level="error", is_key=True)

        # Update indicator after attempting start
        if hasattr(self, 'sb_indicator_light'): self.sb_indicator_light.configure(fg_color="green" if self.streamerbot_client_thread and self.streamerbot_client_thread.is_alive() else "grey")


    def _stop_streamerbot_client(self):
        """Stops the Streamer.bot client thread if it's running."""
        stopped = False
        if self.streamerbot_client_thread and self.streamerbot_client_thread.is_alive():
            logger.info(tr("log_gui_sending_sb_stop_signal"))
            self.flags['stop_streamerbot'].set() # Signal the thread to stop
            # Wait briefly for the thread to potentially exit
            self.streamerbot_client_thread.join(timeout=1.0)
            if not self.streamerbot_client_thread.is_alive():
                logger.info("Streamer.bot client thread terminated.")
                stopped = True
            else:
                logger.warning("Streamer.bot client thread did not terminate after stop signal and timeout.")
        elif self.streamerbot_client_thread:
            logger.debug("Streamer.bot client thread exists but is not alive.")
            stopped = True
        else:
            logger.debug("No Streamer.bot client thread to stop.")
            stopped = True

        self.streamerbot_client_thread = None # Clear reference
        # Update indicator after attempting stop
        if hasattr(self, 'sb_indicator_light'): self.sb_indicator_light.configure(fg_color="grey")
        if stopped: self._update_status("status_sb_client_stopped", level="info", is_key=True)


    # --- Helper methods ---
    def _mode_to_tab_name(self, mode_str):
        """Converts an internal mode string ('local', 'openai') to a translated tab name."""
        key = f"tab_{mode_str}"
        return tr(key) # Return the translated name

    def _tab_name_to_mode_safe(self, tab_name):
        """Converts a (potentially translated) tab name back to an internal mode string."""
        # Use the initial mapping created with the startup language
        mode = self._initial_tab_name_to_mode_map.get(tab_name)
        if mode:
            return mode
        else:
            # Fallback if the current tab name isn't in the initial map
            # (Could happen if language changed and tab names weren't perfectly updated)
            logger.warning(tr("log_gui_tab_mode_not_found", tab_name=tab_name))
            # Try reverse lookup based on current translation (less reliable)
            for key_lookup, mode_lookup in self._initial_tab_keys_to_mode_map.items():
                if tr(key_lookup) == tab_name:
                    logger.debug(f"Tab name '{tab_name}' resolved to mode '{mode_lookup}' via reverse lookup.")
                    return mode_lookup
            # Final fallback
            logger.warning("Falling back to 'local' mode due to tab name mismatch.")
            return "local"

    # --- Close handler ---
    def on_closing(self):
        """Handles the application closing sequence."""
        logger.info(tr("log_gui_closing_initiated"))
        # 0. Disable closing action initially? Maybe not needed if join timeout is short.

        # 1. Stop recording if active
        if self.is_recording:
            self._update_status("status_closing_while_recording", level="info", is_key=True)
            logger.debug(tr("log_gui_setting_stop_flag"))
            self.flags['stop_recording'].set()
            if self.recording_thread and self.recording_thread.is_alive():
                logger.info(tr("log_gui_waiting_for_recording_thread"))
                self.recording_thread.join(timeout=2.0) # Wait max 2 seconds
                if self.recording_thread.is_alive(): logger.warning(tr("log_gui_recording_thread_timeout"))
                else: logger.info(tr("log_gui_recording_thread_terminated"))
            else: logger.debug(tr("log_gui_no_active_recording_thread"))
            self.is_recording = False # Ensure state is updated

        # 2. Stop background services
        logger.debug(tr("log_gui_stopping_background_threads"))
        self._stop_websocket_server()
        self._stop_streamerbot_client()
        # Wait a tiny bit for threads to potentially release resources
        time.sleep(0.1)

        # 3. Save final configuration
        logger.debug(tr("log_gui_saving_final_config"))
        final_config = self._gather_runtime_config_dict()
        if final_config:
            # Ensure config dir exists before saving
            try: os.makedirs(CONFIG_DIR, exist_ok=True)
            except OSError as e: logger.error(f"Could not create config directory {CONFIG_DIR}: {e}")

            if save_config(CONFIG_FILE, final_config, self.encryption_key):
                logger.info(tr("log_gui_final_config_saved"))
            else:
                logger.error(tr("log_gui_final_config_save_error"))
        else:
            logger.error(tr("log_gui_final_config_gather_error"))

        # 4. Destroy the main window
        logger.debug(tr("log_gui_waiting_before_destroy"))
        time.sleep(0.1) # Short pause before destroy
        logger.info(tr("log_gui_destroying_window"))
        try:
            # Stop periodic checks before destroying
            # (This might require tracking the `after_id` but let's try destroy first)
            self.destroy()
        except tk.TclError as e:
            logger.warning(f"TclError during destroy (already closed?): {e}")
        logger.info(tr("log_gui_application_terminated"))
        # Optional: Force exit if threads are hanging? (Use cautiously)
        # sys.exit(0)