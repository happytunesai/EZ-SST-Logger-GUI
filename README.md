# EZ STT Logger GUI

**Version:** 1.1.3.2
**Status:** Release

---

<img width="639" alt="EZ _SST_Logger_GUI" src="https://github.com/user-attachments/assets/f4952b0a-10aa-49fe-b412-db942b653b2c" />

## Overview


The **EZ STT Logger GUI** is a versatile graphical application for real-time speech-to-text (STT) recognition and audio logging. The app supports multiple modes – from local Whisper models and using the OpenAI and ElevenLabs APIs to WebSocket-based control and integration options.

It was created to provide enhanced STT features for Streamer.bot, often complementing **PNGTuber-GPT** addon setups (like the extended version by [happytunesai](https://github.com/happytunesai/PNGTuber-GPT), based on the original by [RapidRabbit-11485](https://github.com/RapidRabbit-11485/PNGTuber-GPT)).

Thanks to an intuitive interface and extensive configuration options, the application can be flexibly adapted to individual needs.

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

-   **Multi-Tab GUI:**
    -   **Local:** Settings for the local Whisper model.
    -   **OpenAI API:** Configuration for the OpenAI key.
    -   **ElevenLabs API:** API key, model ID, and filter options.
    -   **WebSocket:** Activation of a server for external control (e.g., via Stream Deck, expected command: `TOGGLE_RECORD`).
    -   **Integration (SB):** Sending transcriptions to Streamer.bot via WebSocket, can be used with [PNGTuber-GPT (v1.2)](https://github.com/happytunesai/PNGTuber-GPT) addon.
    -   **Language Selection:** Dropdown menu to switch GUI language (e.g., English, German).
    -   **Log Level Control:** Dropdown menu to set the minimum logging level for console output. 

-   **Security & Configuration:**
    -   Encryption of API keys using [Fernet cryptography](https://cryptography.io/).
    -   Automatic generation and management of an encryption key (`secret.key`).
    -   Configuration file (`config/config.json`) for saving all settings, including UI language and console log level.

-   **Logging & Error Handling:**
    -   Comprehensive logging (including rotating log files in the `logs` directory, always logging at DEBUG level).
    -   Status and error messages are displayed in the GUI (translated) and logs (fixed language).
    -   **Console Log Level:** The GUI allows selecting the *minimum* level for messages shown in the console (DEBUG, INFO, WARNING, ERROR, CRITICAL). Selecting a level (e.g., INFO) will show messages of that level *and all higher levels* (INFO, WARNING, ERROR, CRITICAL). It does not filter for only one specific level.

-   **Interactive Elements:**
    -   Context menu in the transcription window for copying text and adding filter/replacement rules.
    -   File dialogs for selecting the output file (TXT or JSON, defaults to `transcription_log.txt`).

---

## Dependencies

The application uses various libraries. Ensure all the following dependencies are installed, preferably using the `requirements.txt` file:

-   **GUI & File Dialogs:**
    -   [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (`customtkinter`)
    -   `tkinter` (usually included with Python)
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
    ├── language/
    │   ├── de.json
    │   └── en.json
    ├── lib/
    │   ├── __init__.py
    │   ├── constants.py
    │   ├── gui.py
    │   ├── utils.py
    │   ├── ... (other .py files)
    ├── logs/
    ├── main.py
    ├── requirements.txt
    └── (optional: logo.ico)
    ```

3.  **Install Dependencies:**
    (Recommended: Create and activate a virtual environment first)
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration and Encryption:**
    -   On the first run, an encryption key will be automatically generated and saved in `config/secret.key`.
        **Important:** Keep this file safe! Without it, API keys cannot be decrypted. Do NOT commit it to Git.
    -   A default `config/config.json` will be created on the first close or can be adjusted via the GUI. Filter files (`filter/filter_patterns.txt`, etc.), the replacement file (`filter/replacements.json`), and language files will also be created with defaults if they don't exist.

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
    -   **Integration (SB):** Enable sending transcriptions to Streamer.bot (e.g., for use with PNGTuber-GPT actions).
    -   **Common Settings (Below Tabs):** Configure Microphone, STT Language (optional), Output Format, Output File, Buffering/Silence times.
    -   **Language Selector (Top Right):** Choose the GUI language (e.g., English, Deutsch).
    -   **Log Level Selector (Bottom Right):** Choose the minimum log level for console output (DEBUG shows everything, INFO shows INFO and above, etc.).

-   **Recording:**
    -   Select your preferred microphone from the dropdown menu (use "Reload" if needed).
    -   Set language, output format, and output file path.
    -   Start/Stop recording using the **"Start/Stop Recording"** button or via WebSocket command (`TOGGLE_RECORD`). The button is disabled on WebSocket/Integration tabs, but WebSocket control still works. The indicator light always shows the current recording status.

-   **Interactive Features:**
    -   **Context Menu:** Right-click in the transcription area allows:
        -   Copying selected text or all text.
        -   Adding selected text to the appropriate filter list.
        -   Adding replacement rules (e.g., to automatically insert *Tuneingway*).
        -   Clearing the display.

### Commands and External Control

-   **WebSocket Control (e.g., via Stream Deck):**
    -   Ensure the WebSocket server is enabled in the GUI (WebSocket Tab) and the application is running.
    -   To control recording via a Stream Deck, you can use the **"Web Requests"** plugin by Elgato ([Marketplace Link](https://marketplace.elgato.com/product/web-requests-d7d46868-f9c8-4fa5-b775-ab3b9a7c8add)).
    -   Configure a Stream Deck button with the following settings within the "Web Requests" plugin:
        -   **Request Type / Method:** `WebSocket Message`
        -   **Title:** Anything you like (e.g., "Toggle STT Rec")
        -   **URL:** The WebSocket server address shown in the GUI (Default: `ws://localhost:8765`)
        -   **Message:** `TOGGLE_RECORD`
    -   Pressing this button on your Stream Deck will now start or stop the recording in the EZ STT Logger GUI.
    - Example configuration:
      
      ![Stream-Deck: Web Requests](https://github.com/user-attachments/assets/f0411000-91a6-4163-acb8-d8fb84a8dea9)

-   **Streamer.bot Integration:**
    -   Enable sending transcriptions to Streamer.bot under the "Integration (SB)" tab and configure the correct Streamer.bot WebSocket URL.
    -   The application will send transcriptions as JSON messages in the format: `{"source": "stt", "text": "PREFIX + transcribed text"}`.
    -   Your Streamer.bot instance needs corresponding actions set up to listen for WebSocket client messages and process this JSON payload (e.g., using the `websocketClientReceive` trigger and actions available in extended PNGTuber-GPT versions).

    Link: [https://github.com/happytunesai/PNGTuber-GPT](https://github.com/happytunesai/PNGTuber-GPT)

---

## Configuration

The application saves all important settings in the `config/config.json` file. Configurable parameters include:

-   Mode, API Keys (encrypted), Microphone, Model selections, STT Language, UI Language, Console Log Level, Output Format/Filepath, Buffering times, WebSocket/SB settings, Prefix text, etc.

Changes to filter and replacement files (`filter/` directory) can be made directly or via the GUI context menu.

---

## Example Command Line Usage

-   **Start the application:**
    ```bash
    python main.py
    ```

-   **Setting API Keys via Environment Variables (Optional):**
    *(This is often preferred over storing keys in the config file)*
    -   Windows (Command Prompt):
        ```cmd
        set OPENAI_API_KEY=sk-...
        set ELEVENLABS_API_KEY=...
        python main.py
        ```
    -   Windows (PowerShell):
        ```powershell
        $env:OPENAI_API_KEY="sk-..."
        $env:ELEVENLABS_API_KEY="..."
        python main.py
        ```
    -   Linux/macOS:
        ```bash
        export OPENAI_API_KEY="sk-..."
        export ELEVENLABS_API_KEY="..."
        python main.py
        ```

---

## Development & Contributions

If you want to contribute to the development:

-   Fork the repository.
-   Create a new branch (`feature/new_feature`).
-   Ensure all dependencies and functions are integrated into the existing configuration.
-   Submit a pull request – we appreciate your feedback!

---

## Known Issues and TODOs

-   **Audio Buffering Logic Optimization:** Further adjustments for better silence detection are planned.
-   **Extended API Integration:** Support for additional speech recognition services.
-   **Error Handling:** Improvement of error messages and user guidance for API/connection problems.
-   **Streamer.bot Client Robustness:** Improve reconnection logic and error handling for the Streamer.bot client.
-   **GUI Language:** Tab names currently do not update dynamically when the language is changed due to limitations in the GUI library.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Contact 👀

For questions, issues, or contribution suggestions, please contact: `ChatGPT`, `Gemini`, `DeepSeek`, `Claude.ai` 🤖
or try to dump it [here](https://github.com/happytunesai/EZ-SST-Logger-GUI/issues)! ✅

**GitHub:** [github.com/happytunesai/EZ-SST-Logger-GUI](https://github.com/happytunesai/EZ-SST-Logger-GUI)

---

*Created with ❤️ + AI*
