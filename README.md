# ![EZ_STT_GUI_LOGO_50](https://github.com/user-attachments/assets/9ccc03b2-6c16-4956-aa49-76c95fdd323a) EZ STT Logger GUI

**Version:** 1.1.9
**Status:** Release

---
![EZ_SST_Logger_GUI_v1.1.9](https://github.com/user-attachments/assets/19c20df4-10fb-4f32-b0db-183f504b5b44)

## Overview

The **EZ STT Logger GUI** is a versatile graphical application for real-time speech-to-text (STT) recognition and audio logging. Now available as a **standalone executable** for Windows, making it easier than ever to use without installing Python or dependencies!

The app supports multiple modes – from local Whisper models (with integrated FFmpeg detection) and using the OpenAI and ElevenLabs APIs to WebSocket-based control and integration options. **Fully integrates an optional Voice Activity Detection (VAD) system** into the audio processing pipeline to improve speech segmentation and adds an **OpenAI model selector**.

It was created to provide enhanced STT features for Streamer.bot, often complementing **PNGTuber-GPT** addon setups (like the extended version by [happytunesai](https://github.com/happytunesai/PNGTuber-GPT-WS), based on the original by [RapidRabbit-11485](https://github.com/RapidRabbit-11485/PNGTuber-GPT)).

It features an intuitive interface, extensive configuration options, dynamic language support, theme customization with **included themes**, an integrated update checker, and helpful checks for dependencies like FFmpeg.

---

## Features

* **Standalone Executable:** Easy to use on Windows without installing Python or required libraries (except [FFmpeg](https://ffmpeg.org/download.html) for *local* Whisper mode). All VAD dependencies are included.
* **Multiple Transcription Modes:**
    * **Local (Whisper):** Use local Whisper models (e.g., *tiny*, *base*, *small*, *medium*, *large*) for transcription directly on your computer. Requires separate FFmpeg installation added to PATH.
    * **OpenAI API:** Utilize powerful OpenAI speech recognition via your API key.
        * **Model Selector:** Choose between different OpenAI STT models directly in the GUI (`whisper-1` (default), `gpt-4o-mini-transcribe`, `gpt-4o-transcribe`). Your selection is saved in the configuration.
    * **ElevenLabs API:** Leverage the ElevenLabs API for STT.
* **Voice Activity Detection (VAD):**
    * **Fully Functional VAD System:** Uses `silero-vad-lite` (with ONNX runtime) for efficient speech detection. When enabled, VAD logic handles audio segmentation in the processing pipeline.
    * **GUI Controls:** Enable/disable VAD via a checkbox in the main settings area. Configure "VAD Threshold" and "VAD Min Silence (ms)" when enabled.
    * **Dynamic UI:** VAD controls enable/disable automatically. When VAD is *enabled*, the traditional "Min. Buffer" / "Silence Detection" settings are disabled. When VAD is *disabled*, the VAD settings are disabled, and the traditional settings become active.
    * **Configuration:** VAD settings (enabled state, threshold, min silence) are saved persistently in `config.json`.
    * **Disclaimer:** While VAD is fully functional and potentially better for varied speech patterns or longer sentences, it's currently considered experimental. Initial tests suggest the legacy silence detection method might still be faster and more reliable for typical use cases in this version. VAD may require careful tuning of Threshold and Min Silence settings to achieve optimal results. We recommend testing both methods to see which works best for your specific environment and use case.
* **FFmpeg Detector (Local Whisper Mode):**
    * **Automatic Check:** Automatically checks if FFmpeg is correctly installed and available in the system PATH on startup when the "Local" tab is selected.
    * **Status Indicator:** Displays FFmpeg status (Found / Not Found!) with a color indicator directly on the "Local" tab.
    * **Dynamic Download Button:** If FFmpeg is not found, a button appears offering a direct link to the official FFmpeg download page.
* **Theme & Appearance Customization:**
    * **Appearance Manager:** Select Light, Dark, or System appearance mode instantly via the status bar dropdown.
    * **Theme Switcher:** Choose from various color themes via the status bar dropdown.
    * **Included Themes:** Comes bundled with a wide selection of themes (e.g., *autumn, breeze, cherry, coffee, lavender, metal, midnight, pink, sky, violet, yellow,* etc.) located in the `themes` folder. Many themes are sourced from the [**CTkThemesPack by a13xe**](https://github.com/a13xe/CTkThemesPack?tab=readme-ov-file).
    * **Custom Themes:** Supports loading additional custom themes from user-created `.json` files placed in the `themes` folder.
    * *(Note: Applying a new color theme requires an application restart).*
* **Real-time Audio Processing:** Input via microphone, segmentation based on the selected method: either **VAD (when enabled)** or the traditional **buffer/silence thresholds (when VAD is disabled)**.
* **Filtering and Replacement:**
    * Configurable filter rules (per mode type) to remove unwanted phrases.
    * Dynamic text replacement, including a **configurable Botname** for the context menu replacement action (set in the Integration tab).
* **Info Tab & Update Checker:** Application info, links, and integrated GitHub release checker with direct download link for updates.
* **Refined GUI & Dynamic Language Support:**
    * Modern layout with grouped controls and status indicators (WebSocket, Streamer.bot connection, Recording).
    * **PyInstaller Compatibility:** Path handling refined to ensure configuration, filters, logs, themes, and language files work correctly when run as an executable.
    * Automatic detection and selection of UI languages (`language/*.json`). Includes English, German, French, Spanish. Easy to add more.
    * Multi-Tab interface (Local, OpenAI, ElevenLabs, WebSocket, Integration, Info).
    * Adjustable Console Log Level via GUI.
* **Security & Configuration:** API key encryption (`secret.key`), settings saved in `config/config.json` next to the executable or script (includes OpenAI model choice and VAD settings).
* **Logging & Error Handling:** Comprehensive file logging (`logs/`), GUI status messages. Includes VAD-specific log messages. Minor bug fixes related to variable handling between modes and VAD implemented.
* **Interactive Elements:** Context menu in output (copy, add filter, add replacement for Botname), file dialogs, "Clear log file on start" checkbox (controls transcription output file clearing).

---

## Dependencies

* **Using the Executable:**
    * **No Python or Python packages needed!** All required libraries (including `silero-vad-lite`, `onnxruntime` for VAD) are bundled.
    * **FFmpeg (Conditional):** Required *only* if you intend to use the **Local Whisper** transcription mode. The application will check for FFmpeg on the Local tab and prompt you to download it if missing. Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add its `bin` directory to your Windows PATH environment variable.
* **Running from Source:**
    * Requires **Python 3.10 or higher**.
    * All packages listed in `requirements.txt`. Install using `pip install -r requirements.txt`.
        * Key additions/updates: `silero-vad-lite>=0.2.1`, `onnxruntime`. Ensure other dependencies are up-to-date.
    * **FFmpeg:** Required for Local Whisper mode (install separately, add to PATH). The app will check for it.
    * **`openai-whisper`:** Required for Local Whisper mode (`pip install -U openai-whisper`).

---

## Installation Guide

Choose the method that best suits you:

**Option 1: Using the Executable (Recommended for most users)**

1.  **Download:** Go to the [**GitHub Releases page**](https://github.com/happytunesai/EZ-STT-Logger-GUI/releases/latest) and download the `EZ_STT_Logger_GUI.zip` file for the latest version (v1.1.9 or newer).
2.  **Extract:** Extract the `.zip` file. This will create a folder named `EZ_STT_Logger_GUI` containing the executable and subfolders like `themes`, `language`.
3.  **Place:** Move this extracted `EZ_STT_Logger_GUI` folder to a location of your choice (e.g., Desktop, `C:\Tools\`).
4.  **FFmpeg (For Local Whisper Only):** Follow the steps outlined in the "Dependencies" section if you need Local Whisper mode. The app will guide you via the "Local" tab.
5.  **Run:** Open the `EZ_STT_Logger_GUI` folder and double-click `EZ_STT_Logger_GUI.exe`.
6.  **First Run:** Necessary folders (`config`, `filter`, `logs`) and the `config/secret.key` are created automatically inside the application folder if they don't already exist alongside the included `themes` and `language` folders.

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
7.  **First Run:** Folders (`config`, `filter`, `logs`) and `secret.key` created in the project directory. Ensure the `themes` and `language` folders with their respective `.json` files exist for theme/language selection.

8.  **Verify Directory Structure (Example):**
    ```
    EZ-STT-Logger-GUI/
    ├── config/
    ├── filter/
    ├── language/         <-- Included folder with .json language files
    │   ├── en.json
    │   ├── de.json
    │   ├── es.json
    │   ├── fr.json
    │   └── ...
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
    │   ├── vad_processor.py   
    │   └── websocket_utils.py
    ├── logs/
    ├── themes/           <-- Included folder with .json themes
    │   ├── autumn.json
    │   ├── breeze.json
    │   └── ... (many more)
    ├── main.py
    ├── README.md
    ├── requirements.txt   
    └── logo.ico
    ```
    *(Folders like `config`, `filter`, `logs` are created automatically if missing. `themes` and `language` should be included).*
---

## Usage / Operation

### User Interface

* **Tabs:** Select mode/function (Local, OpenAI API, ElevenLabs API, WebSocket, Integration (SB), Info).
* **Local Tab:** Configure local Whisper model. Check the FFmpeg status indicator here.
* **OpenAI API Tab:** Configure OpenAI API Key and **select the desired STT model** using the dropdown.
* **Integration (SB) Tab:** Configure Streamer.bot URL/Prefix/Botname.
* **Info Tab:** View version, access links, check for updates.
* **Common Settings (Below Tabs):** Configure Mic, STT Language, Output Format/File.
    * **Segmentation Method:**
        * Use the **"Use VAD Segmentation"** checkbox to toggle between VAD and legacy silence detection.
        * If **checked (VAD active)**: Configure "VAD Threshold" and "VAD Min Silence (ms)". The "Min. Buffer" / "Silence Detection" sliders will be disabled.
        * If **unchecked (Legacy active)**: Configure "Min. Buffer" and "Silence Detection". The VAD settings will be disabled.
* **Control Panel (Right):** Service Indicators (WS, SB), Reload Mics, Start/Stop Rec, Edit Filters/Replacements.
* **Output Area Controls (Below Output):** "Clear Display" button and the repositioned "Clear log file on start" checkbox.
* **Status Bar (Bottom):** Status messages, UI Language, Console Log Level, **Appearance Mode**, **Color Theme**.

* **Recording:**
    * Select microphone, configure chosen mode (including OpenAI model if applicable), and select/configure the desired segmentation method (VAD or traditional).
    * Start/Stop via button or WebSocket. Light indicates status.

* **Customization:**
    * Use the dropdowns in the status bar to change Appearance Mode (instantly) and Color Theme (requires restart).
    * The Theme dropdown lists all themes found in the `themes` folder. You can add your own `.json` theme files there too.

* **Interactive Features:**
    * **Context Menu:** Right-click in output area to copy, add filter, or add replacement using the **Botname** set in the Integration tab.

### Commands and External Control

* **WebSocket Control:** Enable on WebSocket tab (check Green indicator). Send `TOGGLE_RECORD` message to the URL (e.g., via Stream Deck).
* **Streamer.bot / WebSocket Integration (Outgoing):** Enable on Integration (SB) tab (check Green/Yellow indicator). Sends `{"source": "stt", "text": "..."}` JSON string to configured URL.

---

## Configuration

* Settings managed via GUI, saved in `config/config.json`. Includes VAD settings (enabled, threshold, min_silence) and selected OpenAI model.
* Filters/Replacements in `filter/`.
* UI text in `language/*.json` (now includes VAD elements).
* Appearance (Mode/Theme) saved in `config/config.json`.
* Themes are loaded from the included `themes/` folder. Add custom `.json` files here.
* Visual constants (padding, etc.) in `lib/gui_layout.py`.

---

## Example Command Line Usage

* **Start the application (from source):**
    ```bash
    python main.py
    ```
---

## Known Issues and TODOs

* Applying new Color Themes requires an application restart.
* **VAD Performance:** While functional, VAD may require tuning for optimal performance compared to the legacy method in this version (See Features section disclaimer). Further optimization is planned.
* Audio Buffering Logic Optimization.
* Extended API Integration possibilities.
* Error Handling improvements.
* Streamer.bot Client Robustness enhancements.
* Indicator Detail enhancements.

---

## License

This project is licensed under the [MIT License](LICENSE). Themes bundled from CTkThemesPack retain their original license if applicable. VAD model (`silero_vad.onnx`) and library (`silero-vad-lite`) likely have their own license terms; please refer to their respective sources.

---

## Contact 👀

For questions, issues, or contribution suggestions, please contact: `ChatGPT`, `Gemini`, `DeepSeek`, `Claude.ai` 🤖
or try to dump it [here](https://github.com/happytunesai/EZ-STT-Logger-GUI/issues)! ✅

**GitHub:** [github.com/happytunesai/EZ-SST-Logger-GUI](https://github.com/happytunesai/EZ-SST-Logger-GUI)

---

*Created with ❤️ + AI* ![EZ_STT_GUI_LOGO_150](https://github.com/user-attachments/assets/92017d80-a529-49bd-b56f-53ddd3bcabd7)
