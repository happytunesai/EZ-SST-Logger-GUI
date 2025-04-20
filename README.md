# EZ STT Logger GUI

**Version:** 1.1.8
**Status:** Release

---
<p align="center">
  <img width="676" alt="EZ_SST_Logger_GUI_v1.1.7_UI" src="https://github.com/user-attachments/assets/3f31ca69-6a11-49ae-9dcd-78b574f19530" />
</p>
*(Note: Screenshot shows v1.1.7 UI; v1.1.8 adds FFmpeg status to Local tab)*

## Overview

The **EZ STT Logger GUI** is a versatile graphical application for real-time speech-to-text (STT) recognition and audio logging. Now available as a **standalone executable** for Windows, making it easier than ever to use without installing Python or dependencies!

The app supports multiple modes – from local Whisper models (with integrated FFmpeg detection) and using the OpenAI and ElevenLabs APIs to WebSocket-based control and integration options.

It was created to provide enhanced STT features for Streamer.bot, often complementing **PNGTuber-GPT** addon setups (like the extended version by [happytunesai](https://github.com/happytunesai/PNGTuber-GPT-WS), based on the original by [RapidRabbit-11485](https://github.com/RapidRabbit-11485/PNGTuber-GPT)).

It features an intuitive interface, extensive configuration options, dynamic language support, theme customization with **included themes**, an integrated update checker, and helpful checks for dependencies like FFmpeg.

---

## Features

-   **Standalone Executable:** Easy to use on Windows without installing Python or required libraries (except [FFmpeg](https://ffmpeg.org/download.html) for *local* Whisper mode).
-   **Multiple Transcription Modes:**
    -   **Local (Whisper):** Use local Whisper models (e.g., *tiny*, *base*, *small*, *medium*, *large*) for transcription directly on your computer. Requires separate FFmpeg installation added to PATH.
    -   **OpenAI API:** Utilize powerful OpenAI speech recognition via your API key.
    -   **ElevenLabs API:** Leverage the ElevenLabs API for STT.
-   **FFmpeg Detector (Local Whisper Mode):**
    -   **Automatic Check:** Automatically checks if FFmpeg is correctly installed and available in the system PATH on startup.
    -   **Status Indicator:** Displays FFmpeg status (Found / Not Found!) with a color indicator directly on the "Local" tab.
    -   **Dynamic Download Button:** If FFmpeg is not found, a button appears offering a direct link to the official FFmpeg download page.
-   **Theme & Appearance Customization:**
    -   **Appearance Manager:** Select Light, Dark, or System appearance mode instantly via the status bar dropdown.
    -   **Theme Switcher:** Choose from various color themes via the status bar dropdown.
    -   **Included Themes:** Comes bundled with a wide selection of themes (e.g., *autumn, breeze, cherry, coffee, lavender, metal, midnight, pink, sky, violet, yellow,* etc.) located in the `themes` folder. Many themes are sourced from the [**CTkThemesPack by a13xe**](https://github.com/a13xe/CTkThemesPack?tab=readme-ov-file).
    -   **Custom Themes:** Supports loading additional custom themes from user-created `.json` files placed in the `themes` folder.
    -   *(Note: Applying a new color theme requires an application restart).*
-   **Real-time Audio Processing:** Input via microphone, segmentation based on buffer/silence thresholds.
-   **Filtering and Replacement:**
    -   Configurable filter rules (per mode type) to remove unwanted phrases.
    -   Dynamic text replacement, including a **configurable Botname** for the context menu replacement action (set in the Integration tab).
-   **Info Tab & Update Checker:** Application info, links, and integrated GitHub release checker with direct download link for updates.
-   **Refined GUI & Dynamic Language Support:**
    -   Modern layout with grouped controls and status indicators (WebSocket, Streamer.bot connection, Recording).
    * **PyInstaller Compatibility:** Path handling refined to ensure configuration, filters, logs, themes, and language files work correctly when run as an executable.
    -   Automatic detection and selection of UI languages (`language/*.json`). Includes English, German, French, Spanish. Easy to add more.
    -   Multi-Tab interface (Local, OpenAI, ElevenLabs, WebSocket, Integration, Info).
    -   Adjustable Console Log Level via GUI.
-   **Security & Configuration:** API key encryption (`secret.key`), settings saved in `config/config.json` next to the executable or script.
-   **Logging & Error Handling:** Comprehensive file logging (`logs/`), GUI status messages.
-   **Interactive Elements:** Context menu in output (copy, add filter, add replacement for Botname), file dialogs.

---

## Dependencies

* **Using the Executable:**
    * **No Python or Python packages needed!** All required libraries are included.
    * **FFmpeg (Conditional):** Required *only* if you intend to use the **Local Whisper** transcription mode. The application will check for FFmpeg and prompt you to download it if missing. Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add its `bin` directory to your Windows PATH environment variable.
* **Running from Source:**
    * Requires **Python 3.10 or higher**.
    * All packages listed in `requirements.txt`. Install using `pip install -r requirements.txt`.
    * **FFmpeg:** Required for Local Whisper mode (install separately, add to PATH). The app will check for it.
    * **`openai-whisper`:** Required for Local Whisper mode (`pip install -U openai-whisper`).

---

## Installation Guide

Choose the method that best suits you:

**Option 1: Using the Executable (Recommended for most users)**

1.  **Download:** Go to the [**GitHub Releases page**](https://github.com/happytunesai/EZ-STT-Logger-GUI/releases/latest) and download the `EZ_STT_Logger_GUI.zip` file for the latest version.
2.  **Extract:** Extract the `.zip` file. This will create a folder named `EZ_STT_Logger_GUI` containing the executable and subfolders like `themes`.
3.  **Place:** Move this extracted `EZ_STT_Logger_GUI` folder to a location of your choice (e.g., Desktop, `C:\Tools\`).
4.  **FFmpeg (For Local Whisper Only):** Follow the steps outlined in the "Dependencies" section if you need Local Whisper mode. The app will guide you via the "Local" tab.
5.  **Run:** Open the `EZ_STT_Logger_GUI` folder and double-click `EZ_STT_Logger_GUI.exe`.
6.  **First Run:** Necessary folders (`config`, `filter`, `logs`, `language`) and the `config/secret.key` are created automatically inside the application folder if they don't already exist alongside the included `themes` folder.

**Option 2: Running from Source (For development or customization)**

1.  **Prerequisites:** Python 3.10+, Git.
2.  **Clone Repository:**
    ```bash
    git clone [https://github.com/happytunesai/EZ-SST-Logger-GUI.git](https://github.com/happytunesai/EZ-SST-Logger-GUI.git)
    cd EZ-SST-Logger-GUI
    ```
3.  **(Recommended) Create Virtual Environment:**
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate  # Windows
    # source .venv/bin/activate # Linux/macOS
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Install Optional Dependencies (If needed):**
    * For **Local Whisper** mode: `pip install -U openai-whisper` AND install FFmpeg + add to PATH.
6.  **Run:**
    ```bash
    python main.py
    ```
7.  **First Run:** Folders (`config`, etc.) and `secret.key` created in the project directory. Ensure the `themes` folder with `.json` files exists for theme selection.

8.  **Verify Directory Structure (Example):**
    ```
    EZ-STT-Logger-GUI/
    ├── config/
    ├── filter/
    ├── language/
    ├── lib/
    │   ├── __init__.py
    │   ├── appearance_manager.py
    │   ├── audio_processing.py
    │   ├── config_manager.py
    │   ├── constants.py
    │   ├── gui.py
    │   ├── gui_layout.py
    │   ├── info.py
    │   ├── language_manager.py
    │   ├── logger_setup.py
    │   ├── text_processing.py
    │   ├── utils.py # Contains FFmpeg check
    │   └── websocket_utils.py
    ├── logs/
    ├── themes/          <-- Included folder with .json themes
    │   ├── autumn.json
    │   ├── breeze.json
    │   └── ... (many more)
    ├── main.py
    ├── README.md
    ├── requirements.txt
    └── logo.ico
    ```
    *(Folders like `config`, `filter`, `logs`, `language` are created automatically if missing. `themes` should be included in the distribution).*
---

## Usage / Operation

### User Interface

* **Tabs:** Select mode/function (Local, OpenAI API, ElevenLabs API, WebSocket, Integration (SB), Info).
* **Local Tab:** Configure local Whisper model. Check the FFmpeg status indicator here.
* **Integration (SB) Tab:** Configure Streamer.bot URL/Prefix/Botname.
* **Info Tab:** View version, access links, check for updates.
* **Common Settings (Below Tabs):** Configure Mic, STT Language, Output Format/File, Buffering/Silence.
* **Control Panel (Right):** Service Indicators (WS, SB), Reload Mics, Start/Stop Rec, Edit Filters/Replacements.
* **Status Bar (Bottom):** Status messages, UI Language, Console Log Level, **Appearance Mode**, **Color Theme**.

-   **Recording:**
    -   Select microphone, configure chosen mode.
    -   Start/Stop via button or WebSocket. Light indicates status.

-   **Customization:**
    -   Use the dropdowns in the status bar to change Appearance Mode (instantly) and Color Theme (requires restart).
    -   The Theme dropdown lists all themes found in the `themes` folder. You can add your own `.json` theme files there too.

-   **Interactive Features:**
    -   **Context Menu:** Right-click in output area to copy, add filter, or add replacement using the **Botname** set in the Integration tab.

### Commands and External Control

-   **WebSocket Control:** Enable on WebSocket tab (check Green indicator). Send `TOGGLE_RECORD` message to the URL (e.g., via Stream Deck).
-   **Streamer.bot / WebSocket Integration (Outgoing):** Enable on Integration (SB) tab (check Green/Yellow indicator). Sends `{"source": "stt", "text": "..."}` JSON string to configured URL.

---

## Configuration

-   Settings managed via GUI, saved in `config/config.json`.
-   Filters/Replacements in `filter/`.
-   UI text in `language/*.json`.
-   Appearance (Mode/Theme) saved in `config/config.json`.
-   Themes are loaded from the included `themes/` folder. Add custom `.json` files here.
-   Visual constants (padding, etc.) in `lib/gui_layout.py`.

---

## Example Command Line Usage

-   **Start the application (from source):**
    ```bash
    python main.py
    ```
---

## Known Issues and TODOs

-   Applying new Color Themes requires an application restart.
-   Audio Buffering Logic Optimization.
-   Extended API Integration possibilities.
-   Error Handling improvements.
-   Streamer.bot Client Robustness enhancements.
-   Indicator Detail enhancements.

---

## License

This project is licensed under the [MIT License](LICENSE). Themes bundled from CTkThemesPack retain their original license if applicable.

---

## Contact 👀

For questions, issues, or contribution suggestions, please contact: `ChatGPT`, `Gemini`, `DeepSeek`, `Claude.ai` 🤖
or try to dump it [here](https://github.com/happytunesai/EZ-STT-Logger-GUI/issues)! ✅

**GitHub:** [github.com/happytunesai/EZ-SST-Logger-GUI](https://github.com/happytunesai/EZ-SST-Logger-GUI)

---

*Created with ❤️ + AI*