# -*- coding: utf-8 -*-
"""
GUI-Klasse für die EZ STT Logger Anwendung unter Verwendung von CustomTkinter.
"""
import customtkinter as ctk
from tkinter import filedialog
import tkinter as tk # Für tk.Menu benötigt
import os
import sys
import subprocess
import threading
import queue
import json
import re
import time # Importiert für on_closing

# Importiere lokale Module/Objekte
from lib.logger_setup import logger
from lib.constants import (
    APP_VERSION, ICON_FILE, AVAILABLE_LOCAL_MODELS, DEFAULT_LOCAL_MODEL,
    DEFAULT_OUTPUT_FORMAT, DEFAULT_MIN_BUFFER_SEC, DEFAULT_SILENCE_SEC,
    DEFAULT_ELEVENLABS_MODEL, WEBSOCKET_PORT, DEFAULT_STREAMERBOT_WS_URL,
    DEFAULT_STT_PREFIX, FILTER_FILE, FILTER_FILE_EL, REPLACEMENTS_FILE,
    CONFIG_FILE, DEFAULT_SAMPLERATE, DEFAULT_CHANNELS, DEFAULT_ENERGY_THRESHOLD,
    DEFAULT_TRANSCRIPTION_FILE
)
from lib.utils import list_audio_devices_for_gui
from lib.text_processing import (
    load_filter_patterns, load_replacements, save_replacements
)
# Importiere Startfunktionen für Hintergrund-Threads
from lib.websocket_utils import start_websocket_server_thread, start_streamerbot_client_thread
# Importiere den Worker-Thread selbst, um ihn zu starten
from lib.audio_processing import recording_worker
# Importiere save_config für on_closing
from lib.config_manager import save_config


class WhisperGUI(ctk.CTk):
    """Haupt-GUI-Anwendungsklasse."""

    def __init__(self, app_config, key, queues, flags):
        """
        Initialisiert die GUI.
        Args:
            app_config (dict): Das geladene Konfigurations-Dictionary.
            key (bytes): Der Verschlüsselungsschlüssel.
            queues (dict): Ein Dictionary mit den Queues ('audio_q', 'gui_q', 'streamerbot_q').
            flags (dict): Ein Dictionary mit den Thread-Steuerungs-Flags ('stop_recording', 'stop_streamerbot').
        """
        super().__init__()
        self.config = app_config
        self.encryption_key = key

        # Übernehme Queues und Flags
        self.audio_q = queues['audio_q']
        self.gui_q = queues['gui_q']
        self.streamerbot_queue = queues['streamerbot_q']
        self.stop_recording_flag = flags['stop_recording']
        self.streamerbot_client_stop_event = flags['stop_streamerbot']

        # Interner GUI-Zustand
        self.is_recording = False
        self.available_mics = {} # Wird später gefüllt
        self.loaded_filter_patterns = [] # Wird später gefüllt
        self.loaded_filter_patterns_el = [] # Wird später gefüllt
        self.loaded_replacements = {} # Wird später gefüllt

        # Referenzen auf Hintergrund-Threads und Events
        self.websocket_server_thread = None
        self.websocket_stop_event = None # Wird von start_websocket_server_thread zurückgegeben
        self.streamerbot_client_thread = None
        self.recording_thread = None # Referenz auf den Worker-Thread

        # --- GUI Aufbau ---
        self._setup_window()
        self._create_widgets()
        self._load_initial_gui_data() # Lädt Mikrofone, Filter, Ersetzungen für die GUI
        self._start_background_tasks() # Startet WS-Server/Client basierend auf Config
        self._update_status("Bereit.", log=False) # Initialer Status

        # Starte die Verarbeitung der GUI-Queue
        self.after(100, self._process_gui_queue)
        # Starte periodische Prüfung für Aufnahme-Button-Status
        self.after(500, self._check_record_button_state)


    def _setup_window(self):
        """Konfiguriert das Hauptfenster der Anwendung."""
        logger.debug("Richte Hauptfenster ein...")
        try:
            if os.path.exists(ICON_FILE):
                 self.iconbitmap(ICON_FILE)
            else:
                 logger.warning(f"Icon-Datei '{ICON_FILE}' nicht gefunden.")
        except Exception as e:
            logger.warning(f"Fehler beim Setzen des Icons: {e}")

        self.title(f"EZ STT Logger GUI v.{APP_VERSION} (Tuneingeway)")
        self.geometry("800x780") # Anfangsgröße
        self.minsize(600, 500) # Mindestgröße

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Hauptframe soll expandieren

        self.protocol("WM_DELETE_WINDOW", self.on_closing) # Handler für Schließen-Button
        logger.debug("Hauptfenster eingerichtet.")


    def _create_widgets(self):
        """Erstellt und arrangiert alle Widgets in der GUI."""
        logger.debug("Erstelle Widgets...")

        # --- Haupt-Frame ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.main_frame.columnconfigure(0, weight=1) # Config-Spalte expandiert
        self.main_frame.rowconfigure(1, weight=1)    # Ausgabebereich expandiert

        # --- Oberer Konfigurations-Frame (hält Tabs und gemeinsame Einstellungen) ---
        self.top_config_frame = ctk.CTkFrame(self.main_frame)
        self.top_config_frame.grid(row=0, column=0, pady=(0,10), padx=0, sticky="ew")
        self.top_config_frame.columnconfigure(1, weight=1) # Erlaube Widgets in Spalte 1 zu expandieren

        # --- Tab-Ansicht ---
        self._create_tab_view()

        # --- Gemeinsame Konfigurations-Widgets (Mic, Lang, Format, Datei, Puffer) ---
        self._create_common_config_widgets()

        # --- Rechter Button-Frame (Aufnahme, Filter bearbeiten) ---
        self._create_right_button_frame()

        # --- Ausgabe-Frame (Textbox, Leeren-Button) ---
        self._create_output_frame()

        # --- Statusleisten-Frame ---
        self.status_frame = ctk.CTkFrame(self.main_frame, height=30)
        self.status_frame.grid(row=2, column=0, pady=(5,0), padx=0, sticky="ew")
        self.status_label = ctk.CTkLabel(self.status_frame, text="Initialisiere...", anchor="w")
        self.status_label.pack(side="left", padx=5, pady=2, fill="x", expand=True)

        logger.debug("Widgets erstellt.")

    # --- Methoden zum Erstellen von Widget-Gruppen (_create_... ) ---

    def _create_tab_view(self):
        """Erstellt die Tab-Ansicht und ihren Inhalt."""
        # Initialisiere CTkTabview OHNE command
        self.tab_view = ctk.CTkTabview(self.top_config_frame)
        self.tab_view.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        # Füge Tabs hinzu
        self.tab_view.add("Lokal")
        self.tab_view.add("OpenAI API")
        self.tab_view.add("ElevenLabs API")
        self.tab_view.add("WebSocket")
        self.tab_view.add("Integration (SB)")

        # Erstelle Widgets innerhalb jedes Tabs
        self._create_local_tab(self.tab_view.tab("Lokal"))
        self._create_openai_tab(self.tab_view.tab("OpenAI API"))
        self._create_elevenlabs_tab(self.tab_view.tab("ElevenLabs API"))
        self._create_websocket_tab(self.tab_view.tab("WebSocket"))
        self._create_integration_tab(self.tab_view.tab("Integration (SB)"))

        # Setze initialen Tab basierend auf geladener Config
        initial_mode = self.config.get("mode", "local")
        initial_tab_name = self._mode_to_tab_name(initial_mode)
        try:
            self.tab_view.set(initial_tab_name)
            logger.debug(f"Initialer Tab gesetzt auf: {initial_tab_name}")
        except Exception as e:
             logger.warning(f"Konnte initialen Tab '{initial_tab_name}' nicht setzen: {e}. Fallback auf 'Lokal'.")
             try:
                 self.tab_view.set("Lokal") # Fallback versuchen
             except Exception as e_fallback:
                  logger.error(f"Fallback-Setzen des Tabs 'Lokal' fehlgeschlagen: {e_fallback}")

        # Konfiguriere den command erst NACHDEM der initiale Tab gesetzt wurde
        self.tab_view.configure(command=self._on_tab_change)
        logger.debug("Tab-Command konfiguriert.")


    def _create_local_tab(self, tab):
        """Erstellt Widgets für den 'Lokal' Tab."""
        tab.columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="Whisper Modell:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.model_combobox = ctk.CTkComboBox(tab, values=AVAILABLE_LOCAL_MODELS, width=150)
        self.model_combobox.set(self.config.get("local_model", DEFAULT_LOCAL_MODEL))
        self.model_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    def _create_openai_tab(self, tab):
        """Erstellt Widgets für den 'OpenAI API' Tab."""
        tab.columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="OpenAI API Key:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.openai_api_key_entry = ctk.CTkEntry(tab, placeholder_text="sk-...", width=400, show="*")
        self.openai_api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        openai_key = self.config.get("openai_api_key", "") or os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            self.openai_api_key_entry.insert(0, openai_key)

    def _create_elevenlabs_tab(self, tab):
        """Erstellt Widgets für den 'ElevenLabs API' Tab."""
        tab.columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="ElevenLabs API Key:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.elevenlabs_api_key_entry = ctk.CTkEntry(tab, placeholder_text="ElevenLabs Key...", width=400, show="*")
        self.elevenlabs_api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        el_key = self.config.get("elevenlabs_api_key", "") or os.getenv("ELEVENLABS_API_KEY", "")
        if el_key:
            self.elevenlabs_api_key_entry.insert(0, el_key)

        ctk.CTkLabel(tab, text="ElevenLabs Modell ID:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.elevenlabs_model_id_entry = ctk.CTkEntry(tab, placeholder_text=f"z.B. {DEFAULT_ELEVENLABS_MODEL}", width=200)
        self.elevenlabs_model_id_entry.insert(0, self.config.get("elevenlabs_model_id", DEFAULT_ELEVENLABS_MODEL))
        self.elevenlabs_model_id_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.filter_parentheses_checkbox = ctk.CTkCheckBox(tab, text="Inhalte in (...) und [...] filtern")
        if self.config.get("filter_parentheses", False):
            self.filter_parentheses_checkbox.select()
        self.filter_parentheses_checkbox.grid(row=2, column=0, columnspan=2, padx=5, pady=(10,5), sticky="w")

    def _create_websocket_tab(self, tab):
        """Erstellt Widgets für den 'WebSocket' (Server) Tab."""
        tab.columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="Eingehend (Steuerung via WebSocket):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, padx=5, pady=(10,0), sticky="w")
        self.websocket_enable_checkbox = ctk.CTkCheckBox(tab, text="WebSocket Server aktivieren")
        if self.config.get("websocket_enabled", False):
            self.websocket_enable_checkbox.select()
        self.websocket_enable_checkbox.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(tab, text="Server Port:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.websocket_port_entry = ctk.CTkEntry(tab, width=80)
        self.websocket_port_entry.insert(0, str(self.config.get("websocket_port", WEBSOCKET_PORT)))
        self.websocket_port_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(tab, text=f"(Standard: {WEBSOCKET_PORT}, Neustart der App nötig bei Änderung)").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(tab, text="Erwarteter Befehl für Aufnahme-Umschaltung: TOGGLE_RECORD").grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="w")

    def _create_integration_tab(self, tab):
        """Erstellt Widgets für den 'Integration (SB)' (Streamer.bot Client) Tab."""
        tab.columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="Ausgehend (Senden an Streamer.bot):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, padx=5, pady=(10,0), sticky="w")
        self.streamerbot_ws_enable_checkbox = ctk.CTkCheckBox(tab, text="Transkriptionen an Streamer.bot senden")
        if self.config.get("streamerbot_ws_enabled", False):
            self.streamerbot_ws_enable_checkbox.select()
        self.streamerbot_ws_enable_checkbox.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(tab, text="Streamer.bot URL:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.streamerbot_ws_url_entry = ctk.CTkEntry(tab, placeholder_text=DEFAULT_STREAMERBOT_WS_URL, width=300)
        self.streamerbot_ws_url_entry.insert(0, self.config.get("streamerbot_ws_url", DEFAULT_STREAMERBOT_WS_URL))
        self.streamerbot_ws_url_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(tab, text="(Neustart der App nötig bei Änderung)").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(tab, text="Vorangestellter Text:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.stt_prefix_entry = ctk.CTkEntry(tab, width=400)
        self.stt_prefix_entry.insert(0, self.config.get("stt_prefix", DEFAULT_STT_PREFIX))
        self.stt_prefix_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="w")

    def _create_common_config_widgets(self):
        """Erstellt Widgets, die unterhalb der Tabs gemeinsam genutzt werden."""
        common_grid_row = 1
        ctk.CTkLabel(self.top_config_frame, text="Mikrofon:").grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.mic_combobox = ctk.CTkComboBox(self.top_config_frame, values=["Lade..."], command=self._on_mic_change, width=300, state="readonly")
        self.mic_combobox.grid(row=common_grid_row, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.refresh_button = ctk.CTkButton(self.top_config_frame, text="Neu laden", width=100, command=self.populate_mic_dropdown)
        self.refresh_button.grid(row=common_grid_row, column=3, padx=(5,15), pady=5, sticky="e")
        common_grid_row += 1
        ctk.CTkLabel(self.top_config_frame, text="Sprache (leer=Auto):").grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.language_entry = ctk.CTkEntry(self.top_config_frame, placeholder_text="z.B. de, en, fr (ISO-Code)", width=150)
        self.language_entry.insert(0, self.config.get("language", ""))
        self.language_entry.grid(row=common_grid_row, column=1, padx=5, pady=5, sticky="w")
        common_grid_row += 1
        ctk.CTkLabel(self.top_config_frame, text="Format:").grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        format_frame = ctk.CTkFrame(self.top_config_frame, fg_color="transparent")
        format_frame.grid(row=common_grid_row, column=1, columnspan=2, padx=0, pady=0, sticky="w")
        self.format_var = ctk.StringVar(value=self.config.get("output_format", DEFAULT_OUTPUT_FORMAT))
        self.txt_radio = ctk.CTkRadioButton(format_frame, text="TXT", variable=self.format_var, value="txt")
        self.txt_radio.pack(side="left", padx=(0, 10), pady=5)
        self.json_radio = ctk.CTkRadioButton(format_frame, text="JSON", variable=self.format_var, value="json")
        self.json_radio.pack(side="left", padx=5, pady=5)
        common_grid_row += 1
        ctk.CTkLabel(self.top_config_frame, text="Ausgabedatei:").grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.filepath_entry = ctk.CTkEntry(self.top_config_frame, placeholder_text="Standard: "+DEFAULT_TRANSCRIPTION_FILE, width=250) # Placeholder geändert
        saved_path = self.config.get("output_filepath", "")
        # FIX: Setze Default-Wert, wenn kein Pfad geladen wurde
        if saved_path:
            self.filepath_entry.insert(0, saved_path)
        else:
            self.filepath_entry.insert(0, DEFAULT_TRANSCRIPTION_FILE)
            logger.info(f"Kein Ausgabepfad in Config gefunden, verwende Standard: {DEFAULT_TRANSCRIPTION_FILE}")

        self.filepath_entry.grid(row=common_grid_row, column=1, padx=5, pady=5, sticky="ew")
        self.browse_button = ctk.CTkButton(self.top_config_frame, text="Wählen...", width=80, command=self._browse_output_file)
        self.browse_button.grid(row=common_grid_row, column=2, padx=(5,0), pady=5, sticky="w")
        common_grid_row += 1
        ctk.CTkLabel(self.top_config_frame, text="Min. Puffer (s):").grid(row=common_grid_row, column=0, padx=5, pady=5, sticky="w")
        self.min_buffer_entry = ctk.CTkEntry(self.top_config_frame, width=60)
        self.min_buffer_entry.insert(0, str(self.config.get("min_buffer_duration", DEFAULT_MIN_BUFFER_SEC)))
        self.min_buffer_entry.grid(row=common_grid_row, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.top_config_frame, text="Stille-Erkennung (s):").grid(row=common_grid_row, column=2, padx=(15, 5), pady=5, sticky="w")
        self.silence_threshold_entry = ctk.CTkEntry(self.top_config_frame, width=60)
        self.silence_threshold_entry.insert(0, str(self.config.get("silence_threshold", DEFAULT_SILENCE_SEC)))
        self.silence_threshold_entry.grid(row=common_grid_row, column=3, padx=5, pady=5, sticky="w")
        common_grid_row += 1
        self.clear_log_checkbox = ctk.CTkCheckBox(self.top_config_frame, text="Logdatei bei Start leeren")
        if self.config.get("clear_log_on_start", False): self.clear_log_checkbox.select()
        self.clear_log_checkbox.grid(row=common_grid_row, column=1, columnspan=3, padx=5, pady=(10,5), sticky="w")

    def _create_right_button_frame(self):
        """Erstellt den Frame rechts mit Aufnahme- und Bearbeiten-Buttons."""
        right_button_frame = ctk.CTkFrame(self.top_config_frame, fg_color="transparent")
        right_button_frame.grid(row=1, column=4, rowspan=6, padx=(15,5), pady=5, sticky="ns")
        self.record_button_frame = ctk.CTkFrame(right_button_frame, fg_color="transparent")
        self.record_button_frame.pack(pady=(0,10), fill="x")
        self.start_stop_button = ctk.CTkButton(self.record_button_frame, text="Aufnahme starten", command=self.toggle_recording, width=140, height=35)
        self.start_stop_button.pack(pady=(0,5))
        self.indicator_light = ctk.CTkFrame(self.record_button_frame, width=20, height=20, fg_color="grey", corner_radius=10)
        self.indicator_light.pack(pady=5)
        self.edit_filter_button = ctk.CTkButton(right_button_frame, text="Filter bearbeiten...", width=140, command=self._edit_filter_file)
        self.edit_filter_button.pack(pady=5, fill="x")
        self.edit_replacements_button = ctk.CTkButton(right_button_frame, text="Ersetzungen bearb...", width=140, command=self._edit_replacements_file)
        self.edit_replacements_button.pack(pady=5, fill="x")

    def _create_output_frame(self):
        """Erstellt den Ausgabebereich (Textbox) und den Leeren-Button."""
        self.output_frame = ctk.CTkFrame(self.main_frame)
        self.output_frame.grid(row=1, column=0, pady=0, padx=0, sticky="nsew")
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.rowconfigure(0, weight=1)
        self.textbox = ctk.CTkTextbox(self.output_frame, wrap="word", state="disabled", font=("Segoe UI", 12))
        self.textbox.grid(row=0, column=0, padx=5, pady=(0,5), sticky="nsew")
        self.textbox.tag_config("error_tag", foreground="red")
        self.textbox.tag_config("warning_tag", foreground="orange")
        self.textbox.tag_config("info_tag", foreground="gray")
        self.textbox.bind("<Button-3>", self._show_context_menu)
        self.clear_log_button = ctk.CTkButton(self.output_frame, text="Anzeige leeren", command=self._clear_textbox, width=120)
        self.clear_log_button.grid(row=1, column=0, pady=(0,5))


    # --- Initialisierung und Hintergrund-Tasks ---

    def _load_initial_gui_data(self):
        """Lädt initiale Daten für die GUI (Mikrofone, Filter, Ersetzungen)."""
        logger.debug("Lade initiale GUI-Daten...")
        self.populate_mic_dropdown() # Lade Mikrofone
        # Lade Filter/Ersetzungen und speichere sie in Instanzvariablen
        self.loaded_filter_patterns = load_filter_patterns(FILTER_FILE)
        self.loaded_filter_patterns_el = load_filter_patterns(FILTER_FILE_EL)
        self.loaded_replacements = load_replacements(REPLACEMENTS_FILE)
        logger.debug("Initiale GUI-Daten geladen.")

    def _start_background_tasks(self):
        """Startet Hintergrund-Threads/Tasks (WebSocket-Server/Client)."""
        logger.debug("Starte Hintergrund-Tasks...")
        # Starte WebSocket-Server, wenn aktiviert
        if self.config.get("websocket_enabled", False):
            self._start_websocket_server()
        else:
            self._update_status("Bereit (WS Server deaktiviert).", log=False)

        # Starte Streamer.bot-Client, wenn aktiviert
        if self.config.get("streamerbot_ws_enabled", False):
            self._start_streamerbot_client()
        else:
             current_text = self.status_label.cget("text") # Hole aktuellen Text
             if "SB Senden deaktiviert" not in current_text:
                 # Füge Hinweis hinzu, wenn nicht schon vorhanden
                 self._update_status(current_text + " (SB Senden deaktiviert)", log=False)

    # --- Widget Interaktions-Callbacks ---

    def _on_tab_change(self):
        """Wird aufgerufen, wenn der ausgewählte Tab wechselt."""
        self._check_record_button_state()
        current_tab = self.tab_view.get()
        logger.debug(f"Tab gewechselt zu: {current_tab}")

    def _on_mic_change(self, choice):
        """Wird aufgerufen, wenn die Mikrofonauswahl wechselt."""
        if choice in self.available_mics:
            # Extrahiere nur den Namen ohne ID für die Statusmeldung
            mic_display_name = choice.split(":", 1)[-1].strip()
            self._update_status(f"Mikrofon '{mic_display_name}' ausgewählt.")
        else:
            self._update_status("Ungültige Mikrofon-Auswahl.", level="warning")

    def _browse_output_file(self):
        """Öffnet einen Dateidialog zur Auswahl der Ausgabedatei."""
        file_format = self.format_var.get()
        default_extension = f".{file_format}"
        file_types = [(f"{file_format.upper()}-Datei", f"*{default_extension}"), ("Alle Dateien", "*.*")]
        current_path = self.filepath_entry.get()
        initial_dir = os.path.dirname(current_path) if current_path else "."
        # FIX: Verwende DEFAULT_TRANSCRIPTION_FILE als Fallback für initialfile
        initial_file = os.path.basename(current_path) if current_path else DEFAULT_TRANSCRIPTION_FILE
        if not os.path.isdir(initial_dir): initial_dir = "."

        filepath = filedialog.asksaveasfilename(
            title="Ausgabedatei wählen", initialdir=initial_dir, initialfile=initial_file,
            defaultextension=default_extension, filetypes=file_types
        )
        if filepath:
            self.filepath_entry.delete(0, "end")
            self.filepath_entry.insert(0, filepath)
            self._update_status(f"Ausgabedatei: {os.path.basename(filepath)}")
            logger.info(f"Ausgabedatei ausgewählt: {filepath}")

    def _edit_filter_file(self):
        """Öffnet die passende Filterdatei im Standard-Texteditor."""
        current_mode = self._tab_name_to_mode(self.tab_view.get())
        target_file = FILTER_FILE_EL if current_mode == "elevenlabs" else FILTER_FILE
        # Stelle sicher, dass die Datei existiert (erstelle sie, wenn nicht)
        if not os.path.exists(target_file):
            load_filter_patterns(target_file) # Diese Funktion erstellt die Datei bei Bedarf
        if not os.path.exists(target_file):
            self._update_status(f"Fehler: Filterdatei '{os.path.basename(target_file)}' konnte nicht erstellt/gefunden werden.", level="error")
            return
        self._open_file_in_editor(target_file)

    def _edit_replacements_file(self):
        """Öffnet die Ersetzungs-JSON-Datei im Standard-Texteditor."""
        target_file = REPLACEMENTS_FILE
        if not os.path.exists(target_file):
            load_replacements(target_file) # Erstellt Datei bei Bedarf
        if not os.path.exists(target_file):
            self._update_status("Fehler: Ersetzungsdatei konnte nicht erstellt/gefunden werden.", level="error")
            return
        self._open_file_in_editor(target_file)

    def _open_file_in_editor(self, filepath):
        """Versucht, eine Datei im Standardeditor des Systems zu öffnen."""
        try:
            logger.info(f"Versuche Datei '{filepath}' im Standardeditor zu öffnen...")
            self._update_status(f"Öffne '{os.path.basename(filepath)}' im Editor...")
            if sys.platform == "win32": os.startfile(filepath)
            elif sys.platform == "darwin": subprocess.call(["open", filepath])
            else: subprocess.call(["xdg-open", filepath])
            self.after(1000, lambda: self._update_status(f"'{os.path.basename(filepath)}' zum Bearbeiten geöffnet.", log=False))
        except FileNotFoundError:
            self._update_status(f"Fehler: Datei '{os.path.basename(filepath)}' nicht gefunden.", level="error")
            logger.error(f"Datei nicht gefunden beim Versuch zu öffnen: {filepath}")
        except OSError as e:
            self._update_status(f"Fehler beim Öffnen der Datei: {e}", level="error")
            logger.error(f"OS-Fehler beim Öffnen von '{filepath}': {e}")
        except Exception as e:
            self._update_status(f"Unbekannter Fehler beim Öffnen: {e}", level="error")
            logger.exception(f"Unbekannter Fehler beim Öffnen von '{filepath}'")

    def _clear_textbox(self):
        """Leert den Inhalt der Haupt-Ausgabe-Textbox."""
        try:
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.configure(state="disabled")
            self._update_status("Anzeige geleert.")
        except Exception as e:
            logger.exception("Fehler beim Leeren der Textbox")
            self._update_status("Fehler beim Leeren der Anzeige.", level="error")

    # --- Kontextmenü-Logik ---

    def _show_context_menu(self, event):
        """Zeigt ein Kontextmenü bei Rechtsklick in der Textbox an."""
        try:
            menu = tk.Menu(self, tearoff=0)
            has_selection = False
            try:
                if self.textbox.tag_ranges("sel"): has_selection = True
            except tk.TclError: pass

            if has_selection:
                menu.add_command(label="Kopieren", command=self._copy_selection_to_clipboard)
                menu.add_separator()
                menu.add_command(label="Zur Filterliste hinzufügen", command=self._add_selection_to_filter)
                menu.add_command(label="Als 'Tuneingway'-Ersetzung hinzufügen", command=self._add_tuneingway_replacement_from_selection)
            else:
                menu.add_command(label="Alles kopieren", command=self._copy_all_to_clipboard)

            menu.add_separator()
            menu.add_command(label="Anzeige leeren", command=self._clear_textbox)
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_selection_to_clipboard(self):
        """Kopiert den ausgewählten Text aus der Textbox in die Zwischenablage."""
        try:
            selected_text = self.textbox.get("sel.first", "sel.last")
            if selected_text:
                self.clipboard_clear()
                self.clipboard_append(selected_text)
                self._update_status("Auswahl kopiert.", log=False)
        except tk.TclError: self._update_status("Keine Auswahl zum Kopieren.", level="info", log=False)
        except Exception as e: logger.error(f"Fehler beim Kopieren der Auswahl: {e}"); self._update_status("Fehler beim Kopieren.", level="error")

    def _copy_all_to_clipboard(self):
        """Kopiert den gesamten Text aus der Textbox in die Zwischenablage."""
        try:
            all_text = self.textbox.get("1.0", "end-1c")
            if all_text:
                self.clipboard_clear()
                self.clipboard_append(all_text)
                self._update_status("Gesamter Text kopiert.", log=False)
        except Exception as e: logger.error(f"Fehler beim Kopieren des gesamten Textes: {e}"); self._update_status("Fehler beim Kopieren.", level="error")

    def _add_selection_to_filter(self):
        """Fügt den ausgewählten Text zur passenden Filterdatei hinzu."""
        try:
            selected_text = self.textbox.get("sel.first", "sel.last").strip()
            if not selected_text: self._update_status("Keine Textauswahl zum Filtern vorhanden!", level="info"); return

            current_mode = self._tab_name_to_mode(self.tab_view.get())
            target_file = FILTER_FILE_EL if current_mode == "elevenlabs" else FILTER_FILE

            # Füge den ausgewählten Text als neue Zeile hinzu
            with open(target_file, "a", encoding="utf-8") as f: f.write("\n" + selected_text)

            self._update_status(f"'{selected_text[:30]}...' zur Filterliste ({os.path.basename(target_file)}) hinzugefügt.")
            logger.info(f"Filter hinzugefügt via Kontextmenü: '{selected_text}' zu {target_file}")

            # Lade die entsprechenden Filter-Patterns sofort neu
            if target_file == FILTER_FILE: self.loaded_filter_patterns = load_filter_patterns(FILTER_FILE)
            else: self.loaded_filter_patterns_el = load_filter_patterns(FILTER_FILE_EL)

        except tk.TclError: self._update_status("Keine Auswahl getroffen.", level="info")
        except IOError as e: logger.error(f"Fehler beim Schreiben in die Filterdatei '{target_file}': {e}"); self._update_status(f"Fehler beim Speichern des Filters: {e}", level="error")
        except Exception as e: logger.exception("Fehler beim Hinzufügen zur Filterliste via Kontextmenü"); self._update_status(f"Fehler Hinzufügen Filter: {e}", level="error")

    def _add_tuneingway_replacement_from_selection(self):
        """Fügt eine Ersetzungsregel für den ausgewählten Text -> 'Tuneingway' hinzu."""
        try:
            selected_text = self.textbox.get("sel.first", "sel.last").strip()
        except tk.TclError: self._update_status("Keine Auswahl getroffen.", level="info"); return
        if not selected_text: self._update_status("Leere Auswahl ignoriert.", level="info"); return

        # Verwende das Instanz-Dictionary
        pattern = f"(?i)\\b{re.escape(selected_text)}\\b"
        correct_name = "Tuneingway"
        if pattern in self.loaded_replacements and self.loaded_replacements[pattern] == correct_name:
            self._update_status(f"Info: Ersetzung für '{selected_text[:20]}...' existiert bereits.", level="info")
            return

        self.loaded_replacements[pattern] = correct_name
        logger.info(f"Neue Ersetzung via Kontextmenü hinzugefügt: '{pattern}' -> '{correct_name}'")

        # Speichere das aktualisierte Dictionary (Instanzvariable)
        if save_replacements(self.loaded_replacements, REPLACEMENTS_FILE):
            self._update_status(f"Ersetzung für '{selected_text[:20]}...' gespeichert.", level="success")
        else:
            self._update_status(f"Fehler beim Speichern der Ersetzung für '{selected_text[:20]}...'.", level="error")


    # --- Kernlogik ---

    def populate_mic_dropdown(self):
        """Holt verfügbare Mikrofone und aktualisiert die Dropdown-Liste."""
        self._update_status("Suche Mikrofone...", level="info")
        self.mic_combobox.configure(values=["Lade..."], state="disabled")
        self.update_idletasks()
        # Führe Geräteauflistung in separatem Thread aus, um GUI nicht zu blockieren
        # Übergib die gui_q an die Funktion
        threading.Thread(target=self._populate_mic_thread_target, args=(self.gui_q,), daemon=True).start()

    def _populate_mic_thread_target(self, gui_q):
        """Zielfunktion für den Mikrofon-Auflistungs-Thread."""
        try:
            # Rufe list_audio_devices_for_gui aus utils auf und übergebe die gui_q
            self.available_mics = list_audio_devices_for_gui(gui_q)
            mic_names = list(self.available_mics.keys())
            saved_mic_name = self.config.get("mic_name")

            def update_gui():
                """Interne Funktion zum Aktualisieren der GUI im Hauptthread."""
                self.mic_combobox.configure(values=mic_names if mic_names else ["Keine Mikrofone!"], state="readonly" if mic_names else "disabled")
                if mic_names:
                    selected_mic = None
                    if saved_mic_name and saved_mic_name in mic_names: selected_mic = saved_mic_name
                    else:
                        default_mic_name = next((name for name in mic_names if "(Standard)" in name), None)
                        if default_mic_name: selected_mic = default_mic_name
                        else: selected_mic = mic_names[0] # Fallback

                    if selected_mic:
                        self.mic_combobox.set(selected_mic)
                        self._update_status("Mikrofone geladen. Mikrofon ausgewählt.")
                    else:
                        self.mic_combobox.set("Fehler Auswahl")
                        self._update_status("Mikrofone geladen, aber Auswahlfehler.", level="warning")
                else:
                    self.mic_combobox.set("Keine Mikrofone!")
                    # Status wurde bereits von list_audio_devices_for_gui gesetzt

            self.after(0, update_gui) # Plane GUI-Update im Hauptthread
        except Exception as e:
             logger.exception("Fehler im Mikrofon-Lade-Thread")
             self.after(0, lambda: self._update_status("Fehler beim Laden der Mikrofone!", level="error"))
             self.after(0, lambda: self.mic_combobox.configure(values=["Fehler!"], state="disabled"))

    def _check_record_button_state(self):
        """Aktiviert/Deaktiviert den Aufnahme-Button basierend auf Tab und Aufnahmestatus."""
        try:
            # FIX: Logik für Indikatorlicht von Button-Status getrennt
            # Indikatorlicht SOLLTE IMMER den Aufnahmestatus widerspiegeln
            if self.is_recording:
                self.indicator_light.configure(fg_color="red")
                # Der Button-Text und -Status hängt vom Tab ab
                current_tab = self.tab_view.get()
                if current_tab in ["WebSocket", "Integration (SB)"]:
                    # Button bleibt deaktiviert, aber Text zeigt Stopp an (falls man zurückwechselt)
                    self.start_stop_button.configure(state="disabled", text="Aufnahme stoppen")
                else:
                    # Button ist aktiv und zeigt Stopp an
                    self.start_stop_button.configure(state="normal", text="Aufnahme stoppen")
            else:
                # Nicht aufnehmen: Indikator grau
                self.indicator_light.configure(fg_color="grey")
                # Button-Status hängt vom Tab ab
                current_tab = self.tab_view.get()
                if current_tab in ["WebSocket", "Integration (SB)"]:
                    self.start_stop_button.configure(state="disabled", text="Aufnahme starten")
                else:
                    self.start_stop_button.configure(state="normal", text="Aufnahme starten")

            # Erneut planen
            self.after(500, self._check_record_button_state)
        except Exception as e:
             if isinstance(e, tk.TclError) and "invalid command name" in str(e): logger.debug("TclError in _check_record_button_state (Shutdown?).")
             else: logger.warning(f"Fehler in _check_record_button_state: {e}")


    def toggle_recording(self):
        """Startet oder stoppt den Audioaufnahme- und Verarbeitungs-Worker-Thread."""
        # DEBUG: Logge den Start der Funktion
        logger.debug(f"toggle_recording aufgerufen. Aktueller Status: {'Aufnahme läuft' if self.is_recording else 'Nicht aufnehmen'}")

        # FIX: Entferne die Prüfung, die den Start auf WS/Integration Tabs verhindert hat
        # current_tab = self.tab_view.get()
        # if not self.is_recording and current_tab in ["WebSocket", "Integration (SB)"]:
        #     self._update_status("Aufnahme nicht verfügbar in diesem Modus!", level="warning")
        #     logger.warning(f"toggle_recording: Start auf Tab '{current_tab}' verhindert.")
        #     return

        if self.is_recording:
            # --- Aufnahme stoppen ---
            logger.info("Stoppe Aufnahme...")
            self._update_status("Stoppe Aufnahme...", level="info")
            logger.debug("toggle_recording: Setze stop_recording_flag...")
            self.stop_recording_flag.set() # Signalisiere Worker-Thread
            # Aktualisiere Button und Indikator sofort (wird ggf. durch _check_record_button_state korrigiert)
            self.start_stop_button.configure(text="Stoppe...", state="disabled")
            # self.indicator_light.configure(fg_color="grey") # Wird von _check_record_button_state übernommen
            logger.debug("toggle_recording: Stopp angefordert.")
        else:
            # --- Aufnahme starten ---
            logger.info("Starte Aufnahme...")
            logger.debug("toggle_recording: Validiere Startbedingungen...")
            if not self._validate_start_conditions():
                logger.warning("toggle_recording: Startbedingungen nicht erfüllt.")
                return # Eingaben prüfen

            logger.debug("toggle_recording: Sammle Laufzeit-Konfiguration...")
            current_config = self._gather_runtime_config_dict() # Aktuelle Einstellungen sammeln
            if not current_config:
                logger.error("toggle_recording: Sammeln der Konfiguration fehlgeschlagen.")
                return # Sammeln fehlgeschlagen

            # Bereite Argumente für den Worker vor
            try:
                logger.debug("toggle_recording: Bereite Worker-Argumente vor...")
                worker_args = self._prepare_worker_args(current_config)
                logger.debug(f"Vorbereitung für Worker: output_file='{worker_args['output_file']}'")
            except ValueError as e:
                 logger.error(f"toggle_recording: Fehler bei Worker-Argumenten: {e}")
                 self._update_status(f"Ungültige Eingabe: {e}", level="error")
                 return

            # Stopp-Flag löschen und GUI aktualisieren
            logger.debug("toggle_recording: Lösche Stopp-Flag und aktualisiere GUI...")
            self.stop_recording_flag.clear()
            self.is_recording = True
            # Aktualisiere Button und Indikator sofort
            self.start_stop_button.configure(text="Aufnahme stoppen", state="normal") # Wird ggf. von _check korrigiert
            self.indicator_light.configure(fg_color="red")
            self._update_status("Starte Aufnahme...", level="info")

            # Starte Worker-Thread
            logger.debug(f"toggle_recording: Starte recording_worker Thread (Modus: {worker_args['processing_mode']})...")
            self.recording_thread = threading.Thread(
                target=recording_worker, # Importierte Funktion
                kwargs=worker_args,      # Übergebe Argumente als dict
                daemon=True,
                name="RecordingWorkerThread"
            )
            self.recording_thread.start()
            logger.info("recording_worker Thread gestartet.")
        # Stelle sicher, dass der Button/Indikator-Status sofort aktualisiert wird
        self._check_record_button_state()


    def _validate_start_conditions(self):
        """Prüft, ob alle notwendigen Bedingungen zum Starten der Aufnahme erfüllt sind."""
        # Mikrofonprüfung
        mic_name = self.mic_combobox.get()
        if not mic_name or mic_name == "Lade..." or mic_name == "Keine Mikrofone!" or mic_name not in self.available_mics:
            self._update_status("Fehler: Bitte gültiges Mikrofon auswählen!", level="error"); return False
        # Ausgabedateipfadprüfung (Schreibbarkeit)
        output_file = self.filepath_entry.get().strip()
        if output_file:
            output_dir = os.path.dirname(output_file) or "."
            if not os.path.exists(output_dir):
                try: os.makedirs(output_dir, exist_ok=True); logger.info(f"Ausgabeverzeichnis erstellt (Validate): {output_dir}")
                except OSError as e: self._update_status(f"Fehler Erstellen Ausgabeverz. (Validate): {e}", level="error"); return False
            if not os.access(output_dir, os.W_OK):
                 self._update_status(f"Fehler: Kein Schreibzugriff für Ausgabepfad.", level="error"); return False
        # API-Key-Prüfung basierend auf Modus
        processing_mode = self._tab_name_to_mode(self.tab_view.get())
        if processing_mode == "openai" and not self.openai_api_key_entry.get():
            self._update_status("Fehler: OpenAI API Key fehlt!", level="error"); return False
        if processing_mode == "elevenlabs":
             if not self.elevenlabs_api_key_entry.get(): self._update_status("Fehler: ElevenLabs API Key fehlt!", level="error"); return False
             if not self.elevenlabs_model_id_entry.get(): self._update_status("Fehler: ElevenLabs Modell ID fehlt!", level="error"); return False
        # Numerische Eingaben prüfen
        try: float(self.min_buffer_entry.get()); float(self.silence_threshold_entry.get())
        except ValueError: self._update_status("Fehler: Ungültige Zahl bei Puffer/Stille.", level="error"); return False
        return True

    def _gather_runtime_config_dict(self):
         """Sammelt die aktuellen Einstellungen aus der GUI in einem Dictionary."""
         try:
             config_dict = {
                 "mode": self._tab_name_to_mode(self.tab_view.get()),
                 "openai_api_key": self.openai_api_key_entry.get(),
                 "elevenlabs_api_key": self.elevenlabs_api_key_entry.get(),
                 "mic_name": self.mic_combobox.get(),
                 "local_model": self.model_combobox.get(),
                 "language": self.language_entry.get().strip(),
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
             # Erneute Validierung numerischer Werte
             float(config_dict["min_buffer_duration"])
             float(config_dict["silence_threshold"])
             int(config_dict["websocket_port"])
             return config_dict
         except (tk.TclError, AttributeError, ValueError) as e:
              logger.error(f"Fehler beim Sammeln der Laufzeit-Konfiguration: {e}")
              self._update_status(f"Fehler beim Lesen der Einstellungen: {e}", level="error")
              return None


    def _prepare_worker_args(self, current_config):
        """Bereitet das Argument-Dictionary für den recording_worker Thread vor."""
        # Hole die korrekten Filterpatterns basierend auf dem Modus
        processing_mode = current_config['mode']
        filter_patterns_to_use = self.loaded_filter_patterns_el if processing_mode == "elevenlabs" else self.loaded_filter_patterns

        args = {
            "processing_mode": processing_mode,
            "openai_api_key": current_config['openai_api_key'],
            "elevenlabs_api_key": current_config['elevenlabs_api_key'],
            "device_id": self.available_mics.get(current_config['mic_name']), # Hole ID aus Dict
            "samplerate": DEFAULT_SAMPLERATE, # Verwende importierte Konstante
            "channels": DEFAULT_CHANNELS,     # Verwende importierte Konstante
            "model_name": current_config['local_model'],
            "language": current_config['language'] or None,
            "output_file": current_config['output_filepath'],
            "file_format": current_config['output_format'],
            "energy_threshold": DEFAULT_ENERGY_THRESHOLD, # Verwende importierte Konstante
            "min_buffer_sec": current_config['min_buffer_duration'],
            "silence_sec": current_config['silence_threshold'],
            "elevenlabs_model_id": current_config['elevenlabs_model_id'],
            "filter_parentheses": current_config['filter_parentheses'],
            "send_to_streamerbot_flag": current_config['streamerbot_ws_enabled'],
            "stt_prefix": current_config['stt_prefix'],
            # Übergebe Queues und Flags
            "audio_q": self.audio_q,
            "gui_q": self.gui_q,
            "streamerbot_queue": self.streamerbot_queue,
            "stop_recording_flag": self.stop_recording_flag,
            # Übergebe geladene Filter/Ersetzungen
            "loaded_replacements": self.loaded_replacements,
            "filter_patterns": filter_patterns_to_use,
        }
        if args["device_id"] is None: raise ValueError("Mikrofon-ID nicht gefunden.")
        # DEBUG Log hinzugefügt
        logger.debug(f"Vorbereitung für Worker: output_file='{args['output_file']}'")
        return args

    def _process_gui_queue(self):
        """Verarbeitet Nachrichten aus Hintergrund-Threads über die gui_q."""
        try:
            while True:
                msg_type, msg_data = self.gui_q.get_nowait()
                # DEBUG: Logge jede empfangene Nachricht
                # logger.debug(f"GUI Queue: Empfangen: Typ={msg_type}, Daten={str(msg_data)[:100]}")

                if msg_type == "transcription":
                    self.textbox.configure(state="normal")
                    self.textbox.insert("end", msg_data + "\n")
                    self.textbox.configure(state="disabled")
                    self.textbox.see("end")
                elif msg_type == "status":
                    self._update_status(msg_data, level="info", log=False)
                elif msg_type == "error":
                    self._update_status(msg_data, level="error", log=True)
                elif msg_type == "warning":
                    self._update_status(msg_data, level="warning", log=True)
                elif msg_type == "toggle_recording_external":
                    logger.info("Externer Umschaltbefehl für Aufnahme empfangen (via GUI Queue).")
                    logger.debug("Rufe self.toggle_recording() aus _process_gui_queue auf...")
                    self.toggle_recording()
                    logger.debug("Aufruf von self.toggle_recording() aus _process_gui_queue beendet.")
                elif msg_type == "finished":
                    logger.info("Aufnahme-Worker hat 'finished' signalisiert.")
                    self.is_recording = False
                    self.recording_thread = None # Referenz löschen
                    # Button/Indikator werden durch _check_record_button_state aktualisiert
                    self._check_record_button_state() # Stelle Button-Status sicher
                else: logger.warning(f"Unbekannter Nachrichtentyp in GUI Queue: {msg_type}")
                self.gui_q.task_done()
        except queue.Empty: pass
        except Exception as e: logger.exception("Fehler in der GUI Queue Verarbeitungsschleife")
        self.after(100, self._process_gui_queue) # Erneut planen

    def _update_status(self, message, level="info", log=True):
        """Aktualisiert die Statusleiste und loggt optional die Nachricht."""
        status_text = message if len(message) < 150 else message[:147] + "..."
        try:
            self.status_label.configure(text=status_text)
            color_map = {"error": ("black", "red"), "warning": ("black", "#FF8C00")}
            # Hole Standardfarbe sicher, falls ThemeManager nicht verfügbar
            try:
                 default_fg = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
            except:
                 default_fg = ("black", "white") # Fallback
            self.status_label.configure(text_color=color_map.get(level, default_fg))
        except tk.TclError: logger.warning("Status-Label konnte nicht aktualisiert werden (Fenster geschlossen?)."); return
        if log:
            log_func = getattr(logger, level, logger.info) # Finde passende Log-Funktion
            log_func(f"GUI Status: {message}")

    # --- Management von Hintergrund-Tasks ---

    def _start_websocket_server(self):
        """Startet den WebSocket-Server-Thread, falls aktiviert und nicht bereits aktiv."""
        if not self.config.get("websocket_enabled", False): return
        if self.websocket_server_thread and self.websocket_server_thread.is_alive(): return

        try: port = int(self.websocket_port_entry.get())
        except (ValueError, tk.TclError): port = WEBSOCKET_PORT
        self._update_status(f"Starte WebSocket Server auf Port {port}...", level="info")
        # Starte Thread und speichere Referenz und Stop-Event
        self.websocket_server_thread, self.websocket_stop_event = start_websocket_server_thread(port, self.gui_q)

    def _stop_websocket_server(self):
        """Signalisiert dem WebSocket-Server-Thread das Stoppen."""
        if self.websocket_server_thread and self.websocket_server_thread.is_alive() and self.websocket_stop_event:
            logger.info("Sende Stop-Signal an WebSocket Server...")
            try:
                # Das Event gehört zur Loop des WS-Threads, daher call_soon_threadsafe verwenden
                # Prüfe, ob die Loop-Referenz, die wir angehängt haben, existiert
                loop = getattr(self.websocket_stop_event, '_custom_loop_ref', None)
                if loop and loop.is_running():
                     loop.call_soon_threadsafe(self.websocket_stop_event.set)
                     logger.info("Stop-Event für WebSocket Server via call_soon_threadsafe gesetzt.")
                else:
                     logger.warning("Konnte Loop für WebSocket Stop-Event nicht finden oder sie läuft nicht mehr. Versuche direktes Setzen.")
                     self.websocket_stop_event.set() # Fallback (könnte unsicher sein)
            except Exception as e: logger.error(f"Fehler beim Setzen des WebSocket Stop-Events: {e}")
        self.websocket_server_thread = None # Referenz löschen
        self.websocket_stop_event = None

    def _start_streamerbot_client(self):
        """Startet den Streamer.bot-Client-Thread, falls aktiviert und nicht bereits aktiv."""
        if not self.config.get("streamerbot_ws_enabled", False): return
        if self.streamerbot_client_thread and self.streamerbot_client_thread.is_alive(): return

        ws_url = self.streamerbot_ws_url_entry.get()
        if not ws_url.startswith(("ws://", "wss://")):
            self._update_status(f"Ungültige Streamer.bot URL: {ws_url}", level="error"); return

        self._update_status(f"Starte Streamer.bot Client für {ws_url}...", level="info")
        self.streamerbot_client_stop_event.clear() # Stelle sicher, dass Flag gelöscht ist
        # Starte Thread und speichere Referenz
        self.streamerbot_client_thread = start_streamerbot_client_thread(
            ws_url, self.streamerbot_queue, self.streamerbot_client_stop_event, self.gui_q
        )

    def _stop_streamerbot_client(self):
        """Signalisiert dem Streamer.bot-Client-Thread das Stoppen."""
        if self.streamerbot_client_thread and self.streamerbot_client_thread.is_alive():
            logger.info("Sende Stop-Signal an Streamer.bot Client...")
            self.streamerbot_client_stop_event.set()
        self.streamerbot_client_thread = None # Referenz löschen

    # --- Hilfsmethoden ---

    def _mode_to_tab_name(self, mode_str):
        """Konvertiert interne Modus-ID zu GUI-Tab-Namen."""
        mapping = { "local": "Lokal", "openai": "OpenAI API", "elevenlabs": "ElevenLabs API",
                    "websocket": "WebSocket", "integration": "Integration (SB)" }
        return mapping.get(mode_str, "Lokal")

    def _tab_name_to_mode(self, tab_name):
        """Konvertiert GUI-Tab-Namen zu interner Modus-ID."""
        mapping = { "Lokal": "local", "OpenAI API": "openai", "ElevenLabs API": "elevenlabs",
                    "WebSocket": "websocket", "Integration (SB)": "integration" }
        return mapping.get(tab_name, "local")

    # --- Schließen-Handler ---

    def on_closing(self):
        """Behandelt das Schließen des Fensters."""
        logger.info("Schließvorgang eingeleitet...")
        # 1. Aufnahme stoppen, falls aktiv
        if self.is_recording:
            self._update_status("Beende Aufnahme vor dem Schließen...", level="info")
            logger.debug("on_closing: Setze stop_recording_flag...")
            self.stop_recording_flag.set()
            if self.recording_thread and self.recording_thread.is_alive():
                logger.info("Warte auf Beendigung des Aufnahme-Threads (max 2s)...")
                self.recording_thread.join(timeout=2) # Kürzeres Timeout beim Schließen
                if self.recording_thread.is_alive():
                     logger.warning("Aufnahme-Thread hat sich nach 2s nicht beendet.")
                else:
                     logger.info("Aufnahme-Thread erfolgreich beendet.")
            else:
                 logger.debug("on_closing: Kein aktiver Aufnahme-Thread zum Beenden gefunden.")
            self.is_recording = False

        # 2. Hintergrund-Threads stoppen
        logger.debug("on_closing: Stoppe Hintergrund-Threads...")
        self._stop_websocket_server()
        self._stop_streamerbot_client()

        # 3. Finale Konfiguration speichern (aus GUI-Werten)
        logger.debug("on_closing: Speichere finale Konfiguration...")
        final_config = self._gather_runtime_config_dict()
        if final_config:
             # save_config wurde bereits importiert
             if save_config(CONFIG_FILE, final_config, self.encryption_key):
                  logger.info("Finale Konfiguration gespeichert.")
             else:
                  logger.error("Fehler beim Speichern der finalen Konfiguration.")
        else:
             logger.error("Konnte finale Konfiguration nicht sammeln/speichern.")

        # 4. Kurz warten, damit Threads aufräumen können
        logger.debug("on_closing: Warte kurz...")
        time.sleep(0.2)

        # 5. Tkinter-Fenster zerstören
        logger.info("Zerstöre Tkinter-Fenster.")
        self.destroy()
        logger.info("Anwendung beendet.")

