# EZ STT Logger GUI

**Version:** 1.1.7
**Status:** Release

---

<img width="676" alt="EZ STT Logger GUI v1.1.7" src="https://github.com/user-attachments/assets/2a8a2860-977d-49fd-b863-13f6c6cc0c50" />
    
## Overview

The **EZ STT Logger GUI** is a versatile graphical application for real-time speech-to-text (STT) recognition and audio logging. Now available as a **standalone executable** for Windows, making it easier than ever to use without installing Python or dependencies!

The app supports multiple modes – from local Whisper models and using the OpenAI and ElevenLabs APIs to WebSocket-based control and integration options.

It was created to provide enhanced STT features for Streamer.bot, often complementing **PNGTuber-GPT** addon setups (like the extended version by [happytunesai](https://github.com/happytunesai/PNGTuber-GPT), based on the original by [RapidRabbit-11485](https://github.com/RapidRabbit-11485/PNGTuber-GPT)).

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
2.  **Extract:** Extract the downloaded `EZ_SST_Logger_GUI.zip` file. This will create a folder named `EZ_SST_Logger_GUI`.
3.  **Place:** Move this extracted `EZ_SST_Logger_GUI` folder to a location of your choice on your computer (e.g., your Desktop or `C:\Tools\`).
4.  **FFmpeg (For Local Whisper Only):** If you plan to use the **Local Whisper** mode:
    * Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) (usually a "release build" zip file).
    * Extract the zip file to a permanent location (e.g., `C:\ffmpeg`).
    * Add the `bin` folder inside the extracted FFmpeg folder (e.g., `C:\ffmpeg\bin`) to your Windows System `PATH` environment variable. (Search Windows for "Edit environment variables for your account"). **Restart your PC** after changing the PATH for it to take effect system-wide.
5.  **Run:** Open the `EZ_SST_Logger_GUI` folder you extracted and placed in Step 3, then double-click the `EZ_SST_Logger_GUI.exe` file inside it to start the application.
6.  **First Run:** On the first run (or when needed), the application will automatically create necessary folders like `config`, `filter`, `logs`, and `language` **inside the `EZ_SST_Logger_GUI` folder where the `.exe` file is located**. A `config/secret.key` for encryption will also be generated in the `config` folder if it doesn't exist.

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

---

## Usage / Operation

### User Interface

* **Tabs:** Select mode/function (Local, OpenAI API, ElevenLabs API, WebSocket, Integration (SB), Info).
* **Integration (SB) Tab:** Configure Streamer.bot URL, Prefix Text, and the **Botname** used for context menu replacements.
* **Common Settings (Below Tabs):** Configure Mic, STT Language, Output Format/File, Buffering/Silence.
* **Control Panel (Right):** Service Indicators (WS, SB), Reload Mics, Start/Stop Rec, Edit Filters/Replacements.
* **Info Tab:** Version, links, update check.
* **Status Bar (Bottom):** Status messages, UI Language, Console Log Level.

*(Rest of Usage section can remain similar to before, maybe update screenshots if desired)*

---

*(Configuration, Example Command Line Usage, Known Issues, License, Contact sections can remain largely the same, just ensure version numbers mentioned match 1.1.7)*

---

*Created with ❤️ + AI*
