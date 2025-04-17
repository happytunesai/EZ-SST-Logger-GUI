# EZ STT Logger GUI

**Version:** 1.1.6
**Status:** Release

---

<img width="676" alt="EZ _SST_Logger_GUI_v1 1 6" src="https://github.com/user-attachments/assets/2a8a2860-977d-49fd-b863-13f6c6cc0c50" />
    
## Overview


The **EZ STT Logger GUI** is a versatile graphical application for real-time speech-to-text (STT) recognition and audio logging. The app supports multiple modes – from local Whisper models and using the OpenAI and ElevenLabs APIs to WebSocket-based control and integration options.

It was created to provide enhanced STT features for Streamer.bot, often complementing **PNGTuber-GPT** addon setups (like the extended version by [happytunesai](https://github.com/happytunesai/PNGTuber-GPT), based on the original by [RapidRabbit-11485](https://github.com/RapidRabbit-11485/PNGTuber-GPT)).

It features an intuitive interface, extensive configuration options, dynamic language support, and an integrated update checker.

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

-   **Info Tab & Update Checker:**
    -   An **"Info" Tab** provides quick access to application information.
    -   **Version Display:** Shows the currently running application version.
    -   **Helpful Links:** Contains clickable links to the project's GitHub Repository and the related PNGTuber Addon repository.
    -   **Update Check Function:** Includes a button ("Check for Updates") to check for new releases via the GitHub API.
    -   **Background Checking:** The check runs in a separate thread to keep the UI responsive.
    -   **Status Feedback:** A label indicates the status ("Checking...", "Up to date", "Update available!", "Error...").
    -   **Direct Download Link:** A "Download Update" button appears *only* if a newer version is found, linking directly to the GitHub Releases page.

-   **Refined GUI & Dynamic Language Support:**
    -   **Modern Layout:** Features a compact and intuitive interface. Main configuration options and controls are grouped below the tabs, maximizing space for the transcription output.
    -   **Separated UI Logic:** UI constants are defined in `lib/gui_layout.py`, and Info tab logic is modularized in `lib/info.py` for better code structure and easier customization.
    -   **Service Status Indicators:** Visual indicators in the right control panel show the status of the WebSocket server and Streamer.bot integration.
        -   **WebSocket Indicator:** ⚫ Gray = Server disabled/not running; 🟢 Green = Server enabled and listening.
        -   **Streamer.bot Indicator:** ⚫ Gray = Integration disabled; 🟡 Yellow = Enabled but Not Connected; 🟢 Green = Enabled & Connected.
    -   **Dynamic Language Loading:** Automatically detects available UI languages from `.json` files in the `language/` directory.
        -   Language files require `"language_name"` and `"language_code"` metadata.
        -   Valid files appear in the language selection dropdown.
    -   **Easy Language Addition:** Add new UI languages by creating a valid `.json` file in the `language/` folder.
    -   **Included Languages:** Comes with English (`en.json`), German (`de.json`), French (`fr.json`), and Spanish (`es.json`).
    -   **Multi-Tab GUI:**
        -   **Local, OpenAI API, ElevenLabs API, WebSocket, Integration (SB):** Tabs for specific service configurations.
        -   **Info:** Tab with version info, links, and update checker.
        -   **Language Selection:** Dropdown menu (bottom right) for switching GUI language.
        -   **Log Level Control:** Dropdown menu (bottom right) to set the minimum console log level.
    -   **Enhanced Visuals:** Uses the "Montserrat" font and bold headings for better readability.

-   **Security & Configuration:**
    -   Encryption of API keys using Fernet cryptography.
    -   Automatic generation and management of an encryption key (`secret.key`).
    -   Configuration file (`config/config.json`) saves all settings. Settings are saved automatically when changing language.
    -   Language files (`language/*.json`) define UI text.

-   **Logging & Error Handling:**
    -   Comprehensive logging to rotating files in the `logs` directory.
    -   Status and error messages displayed in the GUI and logs.
    -   **Console Log Level:** Select the minimum level for console messages via the GUI.

-   **Interactive Elements:**
    -   Context menu in the transcription window (copy, add filter/replacement, clear).
    -   File dialogs for selecting the output file.

---

## Dependencies

The application uses various libraries. Ensure all dependencies listed in `requirements.txt` are installed.

-   **Key Libraries:** `CustomTkinter`, `sounddevice`, `numpy`, `soundfile`, `openai` (optional), `openai-whisper` (optional), `elevenlabs` (optional), `cryptography`, `websockets`, `requests`.
-   *(Uses the Montserrat font for UI text.)*

> **Installation:**
> Requires **Python 3.10 or higher**.
> To install all required packages, use the provided `requirements.txt` file:
> ```bash
> pip install -r requirements.txt
> ```
> *(Optional dependencies for specific modes are noted in the full requirements file or previous sections).*

---

## Installation Guide

1.  **Clone or Download the Repository:**
    ```bash
    git clone [https://github.com/happytunesai/EZ-SST-Logger-GUI.git](https://github.com/happytunesai/EZ-SST-Logger-GUI.git)
    cd EZ-SST-Logger-GUI
    ```
    Or download and extract the project files.

2.  **Verify Directory Structure:**
    Ensure you have the main script and the `lib` folder containing the core modules:
    ```
    EZ-SST-Logger-GUI/
    ├── config/
    ├── filter/
    ├── language/
    │   ├── de.json
    │   ├── en.json
    │   ├── es.json
    │   └── fr.json
    ├── lib/
    │   ├── __init__.py
    │   ├── audio_processing.py
    │   ├── config_manager.py
    │   ├── constants.py
    │   ├── gui.py
    │   ├── gui_layout.py
    │   ├── info.py
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
    *(Folders like `config`, `filter`, `logs`, `language` are created automatically on first run if missing)*.

3.  **Install Dependencies:**
    (Recommended: Use a virtual environment)
    ```bash
    pip install -r requirements.txt
    ```
    *Requires Python 3.10+.*

4.  **First Run & Configuration:**
    -   An encryption key (`config/secret.key`) is generated on first run. **Keep this safe!**
    -   Default config (`config/config.json`), filter/replacement files (`filter/`), and language files (`language/`) are created if missing. Configure settings via the GUI.

5.  **Start the Application:**
    ```bash
    python main.py
    ```

---

## Usage / Operation

### User Interface

-   **Tabs:** Select the desired mode or function (Local, OpenAI API, ElevenLabs API, WebSocket, Integration (SB), Info).
-   **Common Settings (Below Tabs):** Configure Microphone, STT Language, Output Format/File, Buffering/Silence times.
-   **Control Panel (Right Side):** Access Service Indicators (WS, SB), Reload Mics, Start/Stop Recording, Edit Filters/Replacements.
-   **Info Tab:** View version, access links, check for updates.
-   **Status Bar (Bottom):** View status messages, select UI Language and Console Log Level.

-   **Recording:**
    -   Select a microphone.
    -   Navigate to a recording configuration tab (e.g., Local).
    -   Start/Stop via the button (active on relevant tabs) or WebSocket command. The light next to the button indicates recording status. [not recording : ⚫] [recording : 🔴]

-   **Update Check (Info Tab):**
    -   Click "Check for Updates".
    -   Observe the status label.
    -   Click "Download Update" if it appears.

### Commands and External Control

-   **WebSocket Control:** Enable on the WebSocket tab (check Green indicator). Send `TOGGLE_RECORD` message to the displayed URL (e.g., via Stream Deck Web Requests plugin).
-   **Streamer.bot Integration:** Enable on the Integration (SB) tab (check Green/Yellow indicator). Sends `{"source": "stt", "text": "..."}` JSON to configured SB URL.

---

## Configuration

-   Most settings are managed via the GUI and saved in `config/config.json`.
-   Filters/Replacements are in the `filter/` directory.
-   UI text is defined in `language/*.json`.
-   Visual constants (fonts, colors, padding) can potentially be adjusted in `lib/gui_layout.py`.

---

## Example Command Line Usage

-   **Start the application:**
    ```bash
    python main.py
    ```
---

## Known Issues and TODOs

-   **Audio Buffering Logic Optimization:** Ongoing refinement.
-   **Extended API Integration:** Potential future support for more STT services.
-   **Error Handling:** Continuous improvement.
-   **Streamer.bot Client Robustness:** Improve reconnection logic.
-   **Indicator Detail:** Enhance indicators for more states.

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
