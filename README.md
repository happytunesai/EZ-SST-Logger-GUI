# EZ STT Logger GUI

**Version:** 1.1.5
**Status:** Release
---

<img width="676" alt="EZ_SST_Logger_GUI_v1.1.5" src="https://github.com/user-attachments/assets/b0748887-594d-46a0-89e9-5fb61eeba480" />

## Overview


The **EZ STT Logger GUI** is a versatile graphical application for real-time speech-to-text (STT) recognition and audio logging. The app supports multiple modes – from local Whisper models and using the OpenAI and ElevenLabs APIs to WebSocket-based control and integration options.

It was created to provide enhanced STT features for Streamer.bot, often complementing **PNGTuber-GPT** addon setups (like the extended version by [happytunesai](https://github.com/happytunesai/PNGTuber-GPT), based on the original by [RapidRabbit-11485](https://github.com/RapidRabbit-11485/PNGTuber-GPT)).

This version features a significant UI overhaul for improved clarity, compactness, and usability, separates layout constants for easier customization, and includes important bug fixes.

---

## Features

-   **Multiple Transcription Modes:**
    -   **Local (Whisper):** Use pre-installed Whisper models (e.g., *tiny*, *base*, *small*, *medium*, *large*) for transcription directly on your computer.
    -   **OpenAI API:** Utilize the powerful OpenAI speech recognition by providing your OpenAI API key.
    -   **ElevenLabs API:** Leverage the ElevenLabs API for an alternative STT solution.

-   **Real-time Audio Processing:**
    -   Audio input via connected microphones.
    -   Segmentation of voice recordings based on defined buffer and silence thresholds.
    -   Dynamic adjustment of transcription segments based on acoustic values.

-   **Filtering and Replacement Mechanisms:**
    -   Filter rules to clean up unwanted phrases (configurable per mode type).
    -   Dynamic replacement of text fragments for standardization (e.g., automatic spelling correction).

-   **Refined GUI & Dynamic Language Support:**
    -   **Updated Layout:** Reworked interface for a more compact and intuitive feel. Main configuration options and controls are grouped below the tabs, maximizing space for the transcription output.
    -   **Separated Layout Constants:** Basic UI values like fonts, colors, and sizes are now defined in `lib/gui_layout.py`, allowing easier visual customization without modifying the core `gui.py` logic.
    -   **Service Status Indicators:** Visual indicators added to the right control panel show the status of the WebSocket server and Streamer.bot integration.
        -   **WebSocket Indicator:** Gray = Server disabled/not running; Green = Server enabled and listening for `TOGGLE_RECORD` command.
        -   **Streamer.bot Indicator:** Gray = Integration disabled; Yellow = Integration enabled but not connected to Streamer.bot; Green = Integration enabled and connected.
    -   **Dynamic Language Loading:** The application automatically detects available UI languages by scanning `.json` files in the `language/` directory at startup.
        -   Each language file requires `"language_name"` (e.g., "Français") and `"language_code"` (e.g., "fr") metadata for detection.
        -   Valid language files (containing all keys from the reference `en.json`) automatically appear in the language selection dropdown.
    -   **Easy Language Addition:** Users and contributors can add new UI languages simply by creating a valid `.json` file (e.g., `it.json` for Italian) with the required metadata and all necessary translation keys, placing it in the `language/` folder, and restarting the application.
    -   **Included Languages:** Comes with English (`en.json`), German (`de.json`), French (`fr.json`), and Spanish (`es.json`).
    -   **Multi-Tab GUI:**
        -   **Local:** Settings for the local Whisper model.
        -   **OpenAI API:** Configuration for the OpenAI key.
        -   **ElevenLabs API:** API key, model ID, and filter options.
        -   **WebSocket:** Activation of a server for external control.
        -   **Integration (SB):** Sending transcriptions to Streamer.bot via WebSocket.
        -   **Language Selection:** Dropdown menu (bottom right) dynamically populated with detected languages (e.g., English, Deutsch, Français, Español) to switch the GUI language. Tab titles now update correctly upon language change.
        -   **Log Level Control:** Dropdown menu (bottom right) to set the minimum logging level for console output.
    -   **Enhanced Visuals:** Uses the "Montserrat" font and bold headings for better readability.

-   **Security & Configuration:**
    -   Encryption of API keys using [Fernet cryptography](https://cryptography.io/).
    -   Automatic generation and management of an encryption key (`secret.key`).
    -   Configuration file (`config/config.json`) for saving all settings, including UI language and console log level. Settings are now saved automatically when changing language to prevent data loss.
    -   Language files (`language/*.json`) defining UI text.

-   **Logging & Error Handling:**
    -   Comprehensive logging (including rotating log files in the `logs` directory, always logging at DEBUG level).
    -   Status and error messages are displayed in the GUI (translated) and logs (fixed language).
    -   **Console Log Level:** The GUI allows selecting the *minimum* level for messages shown in the console (DEBUG, INFO, WARNING, ERROR, CRITICAL).

-   **Interactive Elements:**
    -   Context menu in the transcription window for copying text and adding filter/replacement rules.
    -   File dialogs for selecting the output file (TXT or JSON, defaults to `transcription_log.txt`).

---

## Dependencies

The application uses various libraries. Ensure all the following dependencies are installed, preferably using the `requirements.txt` file:

-   **GUI & File Dialogs:**
    -   [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (`customtkinter`)
    -   `tkinter` (usually included with Python)
    -   *(Uses the Montserrat font for UI text.)*
-   **Audio & Signal Processing:**
    -   `sounddevice`
    -   `numpy`
    -   `soundfile`
-   **Speech Recognition & APIs:**
    -   [OpenAI Whisper](https://github.com/openai/whisper) (`openai-whisper`) (optional, if local mode is used)
    -   `openai` (for the OpenAI API)
    -   [ElevenLabs Python Library](https://github.com/elevenlabs) (`elevenlabs`) (optional for ElevenLabs API)
-   **Encryption:**
    -   `cryptography`
-   **WebSocket Communication:**
    -   `websockets`

Standard modules like `logging`, `json`, `datetime`, `queue`, `threading`, `asyncio`, `subprocess`, `os`, and `re` are also required.

> **Installation:**
> Requires **Python 3.10 or higher**.
> To install all required packages, use the provided `requirements.txt` file:
> ```bash
> pip install -r requirements.txt
> ```
> *(Optional: For using the local Whisper mode, you also need to install `ffmpeg` on your system and run `pip install -U openai-whisper`. For GPU support, install PyTorch with CUDA. For ElevenLabs, run `pip install elevenlabs`)*

---

## Installation Guide

1.  **Clone or Download the Repository:**
    ```bash
    git clone [https://github.com/happytunesai/EZ-SST-Logger-GUI.git](https://github.com/happytunesai/EZ-SST-Logger-GUI.git)
    cd EZ-SST-Logger-GUI
    ```
    Or simply download and extract the project files (`main.py`, `requirements.txt`, the `lib` folder, etc.).

2.  **Create Directory Structure (if not present):**
    Ensure you have the following structure (the application will try to create `config`, `filter`, `logs`, `language` on first run if they don't exist):
    ```
    EZ-SST-Logger-GUI/
    ├── config/
    ├── filter/
    ├── language/        <-- Folder for language files
    │   ├── de.json      <-- German language file
    │   ├── en.json      <-- English language file (Reference)
    │   ├── es.json      <-- Spanish language file
    │   └── fr.json      <-- French language file
    ├── lib/             <-- Core library files
    │   ├── __init__.py
    │   ├── audio_processing.py
    │   ├── config_manager.py
    │   ├── constants.py
    │   ├── gui.py
    │   ├── gui_layout.py  <-- UI layout constants
    │   ├── language_manager.py
    │   ├── logger_setup.py
    │   ├── text_processing.py
    │   ├── utils.py
    │   └── websocket_utils.py
    ├── logs/
    ├── main.py
    ├── README.md
    ├── requirements.txt
    └── (optional: logo.ico)
    ```

3.  **Install Dependencies:**
    (Recommended: Create and activate a virtual environment first)
    ```bash
    pip install -r requirements.txt
    ```
    *Ensure you have Python 3.10 or newer.*

4.  **Configuration and Encryption:**
    -   On the first run, an encryption key will be automatically generated and saved in `config/secret.key`.
        **Important:** Keep this file safe! Without it, API keys cannot be decrypted. Do NOT commit it to Git.
    -   A default `config/config.json` will be created on the first close or can be adjusted via the GUI. Filter files (`filter/filter_patterns.txt`, etc.), the replacement file (`filter/replacements.json`), and language files (`language/en.json`, `de.json`, `fr.json`, `es.json`) will also be created with defaults if they don't exist.
    -   **Adding Languages:** To add a new language, place a valid `.json` file (containing `"language_name"`, `"language_code"` metadata and all keys from `en.json`) into the `language/` folder. It will be detected on the next application start.

5.  **Start the Application:**
    ```bash
    python main.py
    ```

---

## Usage / Operation

### User Interface

-   **Tabs and Settings:**
    -   **Local:** Select your desired Whisper model.
    -   **OpenAI API:** Enter your OpenAI API key.
    -   **ElevenLabs API:** Configure your ElevenLabs API key and Model ID. Option to filter content in parentheses/brackets.
    -   **WebSocket:** Enable the WebSocket server for external control.
    -   **Integration (SB):** Enable sending transcriptions to Streamer.bot.
    -   **Common Settings (Below Tabs):** Configure Microphone, STT Language (optional), Output Format, Output File, Buffering/Silence times.
    -   **Control Panel (Right Side):**
        -   **Service Indicators:**
            -   **WebSocket:** Shows WebSocket server status. Gray = Server Disabled, Green = Server Enabled & Listening.
            -   **Integration (SB):** Shows Streamer.bot connection status. Gray = Integration Disabled, Yellow = Enabled but Not Connected, Green = Enabled & Connected.
        -   Reload Microphone List button.
        -   Start/Stop Recording button.
        -   Edit Filters / Edit Replacements buttons.
    -   **Status Bar (Bottom):**
        -   **Status Messages:** Displays current status and errors on the left.
        -   **Language Selector:** Choose the GUI language on the right.
        -   **Log Level Selector:** Choose the minimum console log level on the right.

-   **Recording:**
    -   Select your preferred microphone from the dropdown menu (use "Reload" if needed).
    -   Set language, output format, and output file path.
    -   Start/Stop recording using the **"Start/Stop Recording"** button or via WebSocket command (`TOGGLE_RECORD`). The indicator light next to the button shows the current recording status (active/inactive).

-   **Interactive Features:**
    -   **Context Menu:** Right-click in the transcription area allows:
        -   Copying selected text or all text.
        -   Adding selected text to the appropriate filter list.
        -   Adding replacement rules (e.g., to automatically insert *BotnameXY*).
        -   Clearing the display.

### Commands and External Control

-   **WebSocket Control (e.g., via Stream Deck):**
    -   Ensure the WebSocket server is enabled in the GUI (WebSocket Tab) and the application is running (check the 'WebSocket' indicator in the right panel is Green).
    -   Use a tool like the Elgato Stream Deck "Web Requests" plugin to send a `WebSocket Message` with the content `TOGGLE_RECORD` to the server URL (Default: `ws://localhost:8765`).
    - Example configuration:

      ![Stream-Deck: Web Requests](https://github.com/user-attachments/assets/f0411000-91a6-4163-acb8-d8fb84a8dea9)

-   **Streamer.bot Integration:**
    -   Enable sending transcriptions under the "Integration (SB)" tab and configure the correct Streamer.bot WebSocket URL (check the 'Integration (SB)' indicator is Green or Yellow - Yellow means it's trying to connect).
    -   The application sends transcriptions as JSON: `{"source": "stt", "text": "PREFIX + transcribed text"}`.
    -   Set up Streamer.bot actions to listen for WebSocket client messages and process this payload.

    Link: [https://github.com/happytunesai/PNGTuber-GPT](https://github.com/happytunesai/PNGTuber-GPT)

---

## Configuration

The application saves all important settings in the `config/config.json` file. Configurable parameters include:

-   Mode, API Keys (encrypted), Microphone, Model selections, STT Language, UI Language, Console Log Level, Output Format/Filepath, Buffering times, WebSocket/SB settings, Prefix text, etc.

Changes to filter and replacement files (`filter/` directory) can be made directly or via the GUI context menu.

Language files (`.json` format) reside in the `language/` directory and control the UI text. New languages can be added by placing correctly formatted files here.

For minor visual adjustments (fonts, colors, padding), constants are defined in `lib/gui_layout.py`, potentially allowing customization without editing the main GUI logic in `lib/gui.py`.

---

## Example Command Line Usage

-   **Start the application:**
    ```bash
    python main.py
    ```
---

## Known Issues and TODOs

-   **Audio Buffering Logic Optimization:** Further adjustments for better silence detection are planned.
-   **Extended API Integration:** Support for additional speech recognition services.
-   **Error Handling:** Improvement of error messages and user guidance for API/connection problems.
-   **Streamer.bot Client Robustness:** Improve reconnection logic and error handling for the Streamer.bot client.
-   **Indicator Detail:** Enhance indicators to show more states (e.g., connecting error state for SB).

---

## License

-   This project is licensed under the [MIT License](LICENSE).
---

## Contact 👀

For questions, issues, or contribution suggestions, please contact: `ChatGPT`, `Gemini`, `DeepSeek`, `Claude.ai` 🤖
or try to dump it [here](https://github.com/happytunesai/EZ-STT-Logger-GUI/issues)! ✅

**GitHub:** [github.com/happytunesai/EZ-SST-Logger-GUI](https://github.com/happytunesai/EZ-SST-Logger-GUI)

---

*Created with ❤️ + AI*
