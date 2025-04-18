# EZ STT Logger GUI

**Version:** 1.1.7
**Status:** Release

---
![EZ STT Logger GUI v1.1.7](https://github.com/user-attachments/assets/3f31ca69-6a11-49ae-9dcd-78b574f19530)

    
## Overview

The **EZ STT Logger GUI** is a versatile graphical application for real-time speech-to-text (STT) recognition and audio logging. Now available as a **standalone executable** for Windows, making it easier than ever to use without installing Python or dependencies!

The app supports multiple modes – from local Whisper models and using the OpenAI and ElevenLabs APIs to WebSocket-based control and integration options.

It was created to provide enhanced STT features for Streamer.bot, often complementing **PNGTuber-GPT** addon setups (like the extended version by [happytunesai](https://github.com/happytunesai/PNGTuber-GPT-WS), based on the original by [RapidRabbit-11485](https://github.com/RapidRabbit-11485/PNGTuber-GPT)).

It features an intuitive interface, extensive configuration options, dynamic language support, and an integrated update checker.

---

## Features

-   **Standalone Executable:** Easy to use on Windows without installing Python or required libraries (except [FFmpeg](https://ffmpeg.org/download.html) for *local* Whisper mode).
-   **Multiple Transcription Modes:**
    -   **Local (Whisper):** Use local Whisper models (e.g., *tiny*, *base*, *small*, *medium*, *large*) for transcription directly on your computer. Requires separate FFmpeg installation added to PATH.
    -   **OpenAI API:** Utilize powerful OpenAI speech recognition via your API key.
    -   **ElevenLabs API:** Leverage the ElevenLabs API for STT.
-   **Real-time Audio Processing:** Input via microphone, segmentation based on buffer/silence thresholds.
-   **Filtering and Replacement:**
    -   Configurable filter rules (per mode type) to remove unwanted phrases.
    -   Dynamic text replacement, including a **configurable Botname** for the context menu replacement action (set in the Integration tab).
-   **Info Tab & Update Checker:** Application info, links, and integrated GitHub release checker with direct download link for updates.
-   **Refined GUI & Dynamic Language Support:**
    -   Modern layout with grouped controls and status indicators (WebSocket, Streamer.bot connection, Recording).
    * **PyInstaller Compatibility:** Path handling refined to ensure configuration, filters, logs, and language files work correctly when run as an executable.
    -   Automatic detection and selection of UI languages (`language/*.json`). Includes English, German, French, Spanish. Easy to add more.
    -   Multi-Tab interface (Local, OpenAI, ElevenLabs, WebSocket, Integration, Info).
    -   Adjustable Console Log Level via GUI.
-   **Security & Configuration:** API key encryption (`secret.key`), settings saved in `config/config.json` next to the executable or script.
-   **Logging & Error Handling:** Comprehensive file logging (`logs/`), GUI status messages.
-   **Interactive Elements:** Context menu in output (copy, add filter/replacement), file dialogs.

---

## Dependencies

* **Using the Executable:**
    * **No Python or Python packages needed!** All required libraries are included.
    * **FFmpeg (Conditional):** Required *only* if you intend to use the **Local Whisper** transcription mode. Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add its `bin` directory to your Windows PATH environment variable. Other modes (OpenAI API, ElevenLabs API, WebSocket) do **not** require FFmpeg.
* **Running from Source:**
    * Requires **Python 3.10 or higher**.
    * All packages listed in `requirements.txt`[cite: 1, 2, 3]. Install using `pip install -r requirements.txt`.
    * **FFmpeg:** Required for Local Whisper mode (install separately, add to PATH).
    * **`openai-whisper`:** Required for Local Whisper mode (`pip install -U openai-whisper`).

---

## Installation Guide

Choose the method that best suits you:

**Option 1: Using the Executable (Recommended for most users)**

1.  **Download:** Go to the [**GitHub Releases page**](https://github.com/happytunesai/EZ-STT-Logger-GUI/releases/latest) and download the file named `EZ_STT_Logger_GUI.zip` for the latest version.
2.  **Extract:** Extract the downloaded `EZ_STT_Logger_GUI.zip` file. This will create a folder named `EZ_STT_Logger_GUI`.
3.  **Place:** Move this extracted `EZ_STT_Logger_GUI` folder to a location of your choice on your computer (e.g., your Desktop or `C:\Tools\`).
4.  **FFmpeg (For Local Whisper Only):** If you plan to use the **Local Whisper** mode:
    * Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) (usually a "release build" zip file).
    * Extract the zip file to a permanent location (e.g., `C:\ffmpeg`).
    * Add the `bin` folder inside the extracted FFmpeg folder (e.g., `C:\ffmpeg\bin`) to your Windows System `PATH` environment variable. (Search Windows for "Edit environment variables for your account"). **Restart your PC** after changing the PATH for it to take effect system-wide.
5.  **Run:** Open the `EZ_STT_Logger_GUI` folder you extracted and placed in Step 3, then double-click the `EZ_STT_Logger_GUI.exe` file inside it to start the application.
6.  **First Run:** On the first run (or when needed), the application will automatically create necessary folders like `config`, `filter`, `logs`, and `language` **inside the `EZ_STT_Logger_GUI` folder where the `.exe` file is located**. A `config/secret.key` for encryption will also be generated in the `config` folder if it doesn't exist.

**Option 2: Running from Source (For development or customization)**

1.  **Prerequisites:** Ensure you have Python 3.10+ and Git installed.
2.  **Clone Repository:**
    ```bash
    git clone [https://github.com/happytunesai/EZ-STT-Logger-GUI.git](https://github.com/happytunesai/EZ-STT-Logger-GUI.git)
    cd EZ-STT-Logger-GUI
    ```
    Or download and extract the source code ZIP from GitHub.
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
    * For **Local Whisper** mode: `pip install -U openai-whisper` AND install FFmpeg + add to PATH (see step 3 in Option 1).
6.  **Run:**
    ```bash
    python main.py
    ```
7.  **First Run:** Folders (`config`, `filter`...) and the `secret.key` will be created in the project directory.

8.  **Verify Directory Structure:**
    Ensure you have the main script and the `lib` folder containing the core modules:
    ```
    EZ-STT-Logger-GUI/
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
    └── logo.ico
    ```
    *(Folders like `config`, `filter`, `logs`, `language` are created automatically on first run if missing)*.
---

## Usage / Operation

### User Interface

* **Tabs:** Select mode/function (Local, OpenAI API, ElevenLabs API, WebSocket, Integration (SB), Info).
* **Integration (SB) Tab:** Configure Streamer.bot URL, Prefix Text, and the **Botname** used for context menu replacements.
* **Common Settings (Below Tabs):** Configure Mic, STT Language, Output Format/File, Buffering/Silence.
* **Control Panel (Right):** Service Indicators (WS, SB), Reload Mics, Start/Stop Rec, Edit Filters/Replacements.
* **Info Tab:** Version, links, update check.
* **Status Bar (Bottom):** Status messages, UI Language, Console Log Level.
  
-   **Recording:**
    -   Select your preferred microphone from the dropdown menu (use "Reload" if needed).
    -   Set language, output format, and output file path.
    -   Start/Stop recording using the **"Start/Stop Recording"** button or via WebSocket command (`TOGGLE_RECORD`). The button is disabled on WebSocket/Integration tabs, but WebSocket control still works. The indicator light always shows the current recording status.

-   **Interactive Features:**
    -   **Context Menu:** Right-click in the transcription area allows:
        -   Copying selected text or all text.
        -   Adding selected text to the appropriate filter list.
        -   Adding replacement rules (e.g., to automatically insert *BotnameXY*).
        -   Clearing the display.

### Commands and External Control

-   **WebSocket Control (e.g., via Stream Deck):**
    -   Ensure the WebSocket server is enabled in the GUI (WebSocket Tab) and the application is running.
    -   To control recording via a Stream Deck, you can use the **"Web Requests"** plugin by Elgato ([@Adrian Mullings](https://github.com/data-enabler)) ([Marketplace Link](https://marketplace.elgato.com/product/web-requests-d7d46868-f9c8-4fa5-b775-ab3b9a7c8add)).
    -   Configure a Stream Deck button with the following settings within the "Web Requests" plugin:
        -   **Request Type / Method:** `WebSocket Message`
        -   **Title:** Anything you like (e.g., "Toggle STT Rec")
        -   **URL:** The WebSocket server address shown in the GUI (Default: `ws://localhost:8765`)
        -   **Message:** `TOGGLE_RECORD`
    -   Pressing this button on your Stream Deck will now start or stop the recording in the EZ STT Logger GUI.
    - Example configuration:

      ![Stream-Deck: Web Requests](https://github.com/user-attachments/assets/f0411000-91a6-4163-acb8-d8fb84a8dea9)

-   **Streamer.bot / WebSocket Integration (Outgoing):**
    -   Enable sending transcriptions under the "Integration (SB)" tab and configure the correct WebSocket server URL (this doesn't have to be Streamer.bot, any compatible WebSocket server will work).
    -   The application connects as a WebSocket client to the specified URL.
    -   When a transcription is finalized (after filtering and replacements), the application sends a JSON **string** message over the WebSocket connection.
    -   **Message Format:** The JSON string sent follows this structure:
        ```json
        {"source": "stt", "text": "YOUR_PREFIX + transcribed_text"}
        ```
    -   **Example:** If your prefix is `"STREAMER says: "` and the transcribed text is `"Hello world"`, the exact message sent over the WebSocket will be the string:
        ```
        {"source": "stt", "text": "STREAMER says: Hello world"}
        ```
    -   Any application connected to the same WebSocket server (like Streamer.bot using the `WebSocket Client Receive` trigger, or a custom tool) can listen for these messages, parse the JSON string, and use the `"text"` field. This allows integration beyond just Streamer.bot or the PNGTuber-GPT-WS addon.
      
    Link to compatible Addon: [PNGTuber-GPT-WS](https://github.com/happytunesai/PNGTuber-GPT-WS)

---

## Configuration

The application saves all important settings in the `config/config.json` file. Configurable parameters include:

-   Mode, API Keys (encrypted), Microphone, Model selections, STT Language, UI Language, Console Log Level, Output Format/Filepath, Buffering times, WebSocket/SB settings, Prefix text, etc.

Changes to filter and replacement files (`filter/` directory) can be made directly or via the GUI context menu.

Language files (`.json` format) reside in the `language/` directory and control the UI text. New languages can be added by placing correctly formatted files here.

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

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Contact 👀

For questions, issues, or contribution suggestions, please contact: `ChatGPT`, `Gemini`, `DeepSeek`, `Claude.ai` 🤖
or try to dump it [here](https://github.com/happytunesai/EZ-STT-Logger-GUI/issues)! ✅

**GitHub:** [github.com/happytunesai/EZ-STT-Logger-GUI](https://github.com/happytunesai/EZ-STT-Logger-GUI)

---

*Created with ❤️ + AI*
