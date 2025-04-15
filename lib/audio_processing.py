# -*- coding: utf-8 -*-
"""
Funktionen und Worker-Thread für Audioaufnahme, -verarbeitung und Transkription.
"""
import threading
import queue
import time
import io
import numpy as np
from datetime import datetime # FIX: Fehlenden datetime-Import hinzugefügt
import os # Wird für os.path.basename benötigt

# Importiere abhängige Bibliotheken mit Fehlerbehandlung
try:
    import sounddevice as sd
except ImportError:
    sd = None
try:
    import soundfile as sf
except ImportError:
    sf = None
try:
    import whisper
except ImportError:
    whisper = None
try:
    import openai
except ImportError:
    openai = None
try:
    # Importiere spezifische ElevenLabs-Elemente, falls verfügbar
    from elevenlabs.client import ElevenLabs
    from elevenlabs.core import ApiError as ElevenLabsApiError
    HAS_ELEVENLABS_LIBS = True
except ImportError:
    ElevenLabs = None
    ElevenLabsApiError = None
    HAS_ELEVENLABS_LIBS = False

# Importiere lokale Module/Objekte
from lib.logger_setup import logger
from lib.text_processing import apply_replacements, filter_transcription
from lib.constants import DEFAULT_SAMPLERATE # Importiere benötigte Konstanten

# Globale Variablen für dieses Modul (API-Clients, geladenes Modell)
# Diese werden von initialize_stt_client verwaltet
local_whisper_model = None
openai_client = None
elevenlabs_client = None
currently_loaded_local_model_name = None

def audio_callback(indata, frames, time_info, status, audio_q):
    """
    Diese Funktion wird vom Sounddevice-Stream für jeden neuen Audio-Puffer aufgerufen.
    Args:
        indata (np.ndarray): Der Audio-Datenpuffer.
        frames (int): Anzahl der Frames im Puffer.
        time_info: Zeitinformationen vom Stream.
        status (sd.CallbackFlags): Status-Flags vom Stream.
        audio_q (queue.Queue): Die Queue, in die die Audiodaten gelegt werden.
    """
    if status:
        # Logge alle Statusmeldungen vom Audio-Stream (z.B. Pufferüberläufe)
        logger.warning(f"Audio Callback Status: {status}")
    # Lege eine Kopie der Audiodaten (Numpy-Array) in die Queue für den Worker-Thread
    # Kopieren ist wichtig, da der Originalpuffer von Sounddevice wiederverwendet werden könnte
    audio_q.put(indata.copy())

def initialize_stt_client(mode, gui_q, api_key=None, model_name=None):
    """
    Initialisiert den passenden STT-Client (Lokal, OpenAI, ElevenLabs) basierend auf dem Modus.
    Verwaltet die globalen Client-Referenzen dieses Moduls.
    Args:
        mode (str): Der Verarbeitungsmodus ('local', 'openai', 'elevenlabs').
        gui_q (queue.Queue): Die Queue zum Senden von Status/Fehlern an die GUI.
        api_key (str, optional): Der API-Schlüssel für OpenAI oder ElevenLabs.
        model_name (str, optional): Der Name des lokalen Whisper-Modells.
    Returns:
        bool: True bei Erfolg, False bei Fehler.
    """
    global local_whisper_model, openai_client, elevenlabs_client, currently_loaded_local_model_name

    if mode == "local":
        if not whisper:
             gui_q.put(("status", "Fehler: Whisper-Bibliothek fehlt."))
             gui_q.put(("error", "Lokaler Modus nicht verfügbar. Installiere 'openai-whisper'."))
             return False
        # Lade oder verwende das lokale Whisper-Modell wieder
        if local_whisper_model is None or currently_loaded_local_model_name != model_name:
            gui_q.put(("status", f"Lade lokales Whisper-Modell '{model_name}'... (Kann dauern)"))
            try:
                local_whisper_model = whisper.load_model(model_name)
                currently_loaded_local_model_name = model_name
                gui_q.put(("status", f"Lokales Modell '{model_name}' geladen."))
                logger.info(f"Lokales Whisper-Modell '{model_name}' erfolgreich geladen.")
            except Exception as e:
                logger.exception(f"Fehler beim Laden des lokalen Whisper-Modells {model_name}")
                gui_q.put(("status", f"Fehler Laden lokales Modell {model_name}"))
                gui_q.put(("error", f"Modell-Ladefehler: {e}\nPrüfe Existenz/Speicher/FFmpeg!"))
                currently_loaded_local_model_name = None
                local_whisper_model = None
                return False # Fehler signalisieren
        else:
            gui_q.put(("status", f"Lokales Modell '{model_name}' ist bereits geladen."))
            logger.info(f"Verwende bereits geladenes lokales Modell '{model_name}'.")
        return True # Erfolg signalisieren

    elif mode == "openai":
        if not openai:
             gui_q.put(("status", "Fehler: OpenAI-Bibliothek fehlt."))
             gui_q.put(("error", "OpenAI Modus nicht verfügbar. Installiere 'openai'."))
             return False
        if not api_key:
            gui_q.put(("status", "Fehler: Kein OpenAI API Key."))
            gui_q.put(("error", "Kein OpenAI API-Schlüssel angegeben oder geladen."))
            return False # Fehler signalisieren
        # Initialisiere OpenAI Client
        gui_q.put(("status", "Initialisiere OpenAI API Client..."))
        try:
            # Einfacher Ansatz: Immer neu initialisieren, wenn Modus ausgewählt wird
            openai_client = openai.OpenAI(api_key=api_key)
            # Optional: Testaufruf zur Verifizierung des Schlüssels
            # openai_client.models.list()
            gui_q.put(("status", "OpenAI API Client bereit."))
            logger.info("OpenAI API Client erfolgreich initialisiert.")
            return True # Erfolg signalisieren
        except openai.AuthenticationError:
             logger.error("OpenAI Authentifizierungsfehler. API Key ungültig?")
             gui_q.put(("status", "Fehler: OpenAI API Key ungültig!"))
             gui_q.put(("error", "OpenAI API Key ist ungültig oder abgelaufen."))
             openai_client = None
             return False
        except Exception as e:
            logger.exception("Fehler bei der Initialisierung des OpenAI API Clients")
            gui_q.put(("status", "Fehler OpenAI API Initialisierung!"))
            gui_q.put(("error", f"OpenAI Init Fehler: {e}\nPrüfe Key/Internet."))
            openai_client = None
            return False # Fehler signalisieren

    elif mode == "elevenlabs":
        if not HAS_ELEVENLABS_LIBS:
            gui_q.put(("status", "Fehler: ElevenLabs Lib fehlt."))
            gui_q.put(("error", "ElevenLabs Bibliothek nicht installiert (pip install elevenlabs)."))
            return False # Fehler signalisieren
        if not api_key:
            gui_q.put(("status", "Fehler: Kein ElevenLabs API Key."))
            gui_q.put(("error", "Kein ElevenLabs API-Schlüssel angegeben oder geladen."))
            return False # Fehler signalisieren
        # Initialisiere ElevenLabs Client
        gui_q.put(("status", "Initialisiere ElevenLabs API Client..."))
        try:
            # Einfacher Ansatz: Immer neu initialisieren, wenn Modus ausgewählt wird
            elevenlabs_client = ElevenLabs(api_key=api_key)
            # Optional: Testaufruf, z.B. Benutzerinfo abrufen
            # elevenlabs_client.user.get()
            gui_q.put(("status", "ElevenLabs API Client bereit."))
            logger.info("ElevenLabs API Client erfolgreich initialisiert.")
            return True # Erfolg signalisieren
        except ElevenLabsApiError as e:
             logger.error(f"ElevenLabs API Fehler bei Initialisierung: {e}")
             gui_q.put(("status", f"Fehler: ElevenLabs API Fehler ({e.status_code})!"))
             gui_q.put(("error", f"ElevenLabs API Fehler: {e}\nPrüfe Key/Konto Status."))
             elevenlabs_client = None
             return False
        except Exception as e:
            logger.exception("Fehler bei der Initialisierung des ElevenLabs API Clients")
            gui_q.put(("status", "Fehler ElevenLabs API Initialisierung!"))
            gui_q.put(("error", f"ElevenLabs Init Fehler: {e}\nPrüfe Key/Internet."))
            elevenlabs_client = None
            return False # Fehler signalisieren
    else:
        logger.error(f"Unbekannter Verarbeitungsmodus angefordert: {mode}")
        gui_q.put(("status", f"Fehler: Unbekannter Modus '{mode}'"))
        return False # Fehler signalisieren

def transcribe_audio_chunk(audio_data_np, mode, gui_q, lang=None, openai_model="whisper-1", el_model_id=None, api_prompt=None):
    """
    Transkribiert einen NumPy Audio-Chunk mit dem angegebenen Modus und Modell.
    Verwendet die globalen API-Clients dieses Moduls.
    Args:
        audio_data_np (np.ndarray): Der zu transkribierende Audio-Chunk.
        mode (str): Der Verarbeitungsmodus ('local', 'openai', 'elevenlabs').
        gui_q (queue.Queue): Die Queue zum Senden von Status/Fehlern an die GUI.
        lang (str, optional): Der Sprachcode (z.B. 'de', 'en').
        openai_model (str, optional): Das zu verwendende OpenAI-Modell.
        el_model_id (str, optional): Die zu verwendende ElevenLabs Modell-ID.
        api_prompt (str, optional): Ein Prompt für die OpenAI API.
    Returns:
        str: Der rohe Transkriptionstext oder eine Fehlermeldung.
    """
    # Greife auf die globalen Clients dieses Moduls zu
    global local_whisper_model, openai_client, elevenlabs_client

    # Prüfe, ob benötigte Bibliotheken vorhanden sind
    if mode == 'local' and not whisper: return "[Fehler: Whisper Lib fehlt]"
    if mode == 'openai' and not openai: return "[Fehler: OpenAI Lib fehlt]"
    if mode == 'elevenlabs' and not ElevenLabs: return "[Fehler: ElevenLabs Lib fehlt]"
    if (mode == 'openai' or mode == 'elevenlabs') and not sf: return "[Fehler: SoundFile Lib fehlt]"

    text_raw = ""
    try:
        if mode == "local":
            if local_whisper_model is None:
                raise RuntimeError("Lokales Whisper-Modell ist nicht geladen.")
            # Bereite Transkriptionsoptionen vor
            transcription_options = {}
            if lang:
                transcription_options["language"] = lang
            # Stelle sicher, dass Audio float32 ist, wie von Whisper erwartet
            audio_float32 = audio_data_np.astype(np.float32)
            logger.debug(f"Starte lokale Transkription (Länge: {len(audio_float32)/DEFAULT_SAMPLERATE:.2f}s, Optionen: {transcription_options})")
            result = local_whisper_model.transcribe(audio_float32, **transcription_options)
            text_raw = result["text"].strip()
            logger.debug(f"Lokale Transkription Ergebnis: '{text_raw[:100]}...'")

        elif mode == "openai":
            if openai_client is None:
                raise RuntimeError("OpenAI API Client ist nicht initialisiert.")
            # Konvertiere Numpy-Array zu WAV im Speicher
            audio_buffer_bytes = io.BytesIO()
            sf.write(audio_buffer_bytes, audio_data_np, DEFAULT_SAMPLERATE, format='WAV', subtype='PCM_16')
            audio_buffer_bytes.seek(0)
            # Bereite Datei-Tupel für API-Anfrage vor
            files_tuple = ('audio.wav', audio_buffer_bytes, 'audio/wav')
            api_language = lang if lang else None # API erwartet None für Auto-Detect
            logger.debug(f"Sende an OpenAI API (Modell: {openai_model}, Sprache: {api_language}, Prompt: {api_prompt is not None}, Länge: {len(audio_data_np)/DEFAULT_SAMPLERATE:.2f}s)")
            response = openai_client.audio.transcriptions.create(
                model=openai_model,
                file=files_tuple,
                language=api_language,
                prompt=api_prompt, # Sende Prompt, falls vorhanden
                temperature=0.0 # Niedrigere Temperatur für deterministischere Ergebnisse
            )
            text_raw = response.text.strip()
            audio_buffer_bytes.close()
            logger.debug(f"OpenAI API Antwort: '{text_raw[:100]}...'")

        elif mode == "elevenlabs":
            if elevenlabs_client is None:
                raise RuntimeError("ElevenLabs API Client ist nicht initialisiert.")
            if el_model_id is None:
                 raise ValueError("ElevenLabs Modell ID nicht angegeben.")
            # Konvertiere Numpy-Array zu MP3 im Speicher (ElevenLabs bevorzugt MP3)
            audio_buffer_bytes = io.BytesIO()
            sf.write(audio_buffer_bytes, audio_data_np, DEFAULT_SAMPLERATE, format='MP3') # Verwende MP3
            audio_buffer_bytes.seek(0)
            logger.debug(f"Sende an ElevenLabs API (Modell: {el_model_id}, Länge: {len(audio_data_np)/DEFAULT_SAMPLERATE:.2f}s)")
            # Rufe die Speech-to-Text Konvertierungsmethode auf
            response = elevenlabs_client.speech_to_text.convert(
                file=audio_buffer_bytes,
                model_id=el_model_id
            )
            # Prüfe, ob die Antwort ein 'text'-Attribut hat
            if hasattr(response, 'text'):
                text_raw = response.text.strip()
            else:
                # Logge unerwartete Antwortstruktur und konvertiere zu String als Fallback
                logger.warning(f"Unerwartete Antwortstruktur von ElevenLabs STT: {response}")
                text_raw = str(response)
            audio_buffer_bytes.close()
            logger.debug(f"ElevenLabs API Antwort: '{text_raw[:100]}...'")

        return text_raw # Gebe den rohen Transkriptionstext zurück

    # --- Fehlerbehandlung spezifisch für APIs ---
    except openai.APIError as e:
         logger.error(f"OpenAI API Fehler: {e}")
         gui_q.put(("status", f"OpenAI API Fehler Seg!"))
         return f"[OpenAI-API-Fehler: {e.code}]"
    except openai.AuthenticationError:
         logger.error("OpenAI Authentifizierungsfehler während Transkription.")
         gui_q.put(("status", f"OpenAI Auth Fehler Seg!"))
         return "[OpenAI-Auth-Fehler]"
    except ElevenLabsApiError as e:
         logger.error(f"ElevenLabs API Fehler: {e}")
         gui_q.put(("status", f"ElevenLabs API Fehler Seg ({e.status_code})!"))
         return f"[ElevenLabs-API-Fehler: {e.status_code}]"
    # --- Allgemeine Fehlerbehandlung ---
    except sd.PortAudioError as e:
         # Dieser Fehler sollte eigentlich im Stream-Handling auftreten, aber sicherheitshalber hier fangen
         logger.exception("PortAudio Fehler während Transkription")
         gui_q.put(("status", "Audio Fehler Seg!"))
         return "[Audio-Fehler]"
    except RuntimeError as e:
         logger.error(f"Laufzeitfehler während Transkription: {e}")
         gui_q.put(("status", f"Laufzeitfehler Seg! ({e})"))
         return f"[Laufzeitfehler]"
    except Exception as e:
        logger.exception(f"Generischer Transkriptionsfehler im Modus {mode}")
        api_name = mode.capitalize()
        gui_q.put(("status", f"{api_name} Transkriptionsfehler Seg!"))
        return f"[{api_name}-Transkriptionsfehler]"


def recording_worker(**kwargs):
    """
    Worker-Thread, der Audioaufnahme, Pufferung, Stilleerkennung und Transkription handhabt.
    Nimmt alle benötigten Parameter als Keyword-Argumente entgegen.
    """
    # Entpacke Argumente aus kwargs für bessere Lesbarkeit
    processing_mode = kwargs['processing_mode']
    openai_api_key = kwargs['openai_api_key']
    elevenlabs_api_key = kwargs['elevenlabs_api_key']
    device_id = kwargs['device_id']
    samplerate = kwargs['samplerate']
    channels = kwargs['channels']
    model_name = kwargs['model_name']
    language = kwargs['language']
    output_file = kwargs['output_file']
    file_format = kwargs['file_format']
    energy_threshold = kwargs['energy_threshold']
    min_buffer_sec = kwargs['min_buffer_sec']
    silence_sec = kwargs['silence_sec']
    elevenlabs_model_id = kwargs['elevenlabs_model_id']
    filter_parentheses = kwargs['filter_parentheses']
    send_to_streamerbot_flag = kwargs['send_to_streamerbot_flag']
    # streamerbot_ws_url = kwargs['streamerbot_ws_url'] # Nicht direkt hier benötigt
    stt_prefix = kwargs['stt_prefix']
    # Hole Queues und Flags aus kwargs
    audio_q = kwargs['audio_q']
    gui_q = kwargs['gui_q']
    streamerbot_queue = kwargs['streamerbot_queue']
    stop_recording_flag = kwargs['stop_recording_flag']
    # Hole Filter/Ersetzungen
    loaded_replacements = kwargs['loaded_replacements']
    filter_patterns = kwargs['filter_patterns'] # Liste der kompilierten Patterns

    # Prüfe, ob Sounddevice verfügbar ist
    if not sd or not sf:
        logger.critical("Sounddevice oder Soundfile Bibliothek nicht verfügbar. Aufnahme nicht möglich.")
        gui_q.put(("error", "Sounddevice/Soundfile fehlt!"))
        stop_recording_flag.set()
        gui_q.put(("finished", None))
        return

    # --- Initialisierung ---
    logger.info(f"Starte Aufnahme-Worker. Modus: {processing_mode}, Gerät: {device_id}, Modell: {model_name or elevenlabs_model_id}")
    if not initialize_stt_client(processing_mode, gui_q,
                                 api_key=openai_api_key if processing_mode == "openai" else elevenlabs_api_key,
                                 model_name=model_name if processing_mode == "local" else None):
        logger.error("Initialisierung des STT-Clients fehlgeschlagen. Worker wird beendet.")
        stop_recording_flag.set() # Stelle sicher, dass Flag gesetzt ist, wenn Init fehlschlägt
        gui_q.put(("finished", None)) # Benachrichtige GUI
        return # Beende Thread

    # --- Zustandsvariablen ---
    audio_buffer = np.array([], dtype=np.float32) # Puffer zum Sammeln von Audio-Chunks
    min_buffer_samples = int(min_buffer_sec * samplerate) # Mindestanzahl Samples vor Verarbeitung
    silence_samples = int(silence_sec * samplerate) # Samples der Stille vor Verarbeitung des Puffers
    last_sound_time = time.time() # Zeitstempel des letzten erkannten Geräuschs
    is_silent = True # Flag, das anzeigt, ob gerade eine stille Periode ist
    segment_counter = 0 # Zähler für verarbeitete Audio-Segmente
    samples_since_last_sound = 0 # Zähler für aufeinanderfolgende stille Samples

    # --- OpenAI Spezifisch ---
    api_prompt = None
    if processing_mode == "openai" and language:
        # Einfacher Prompt zur Unterstützung der Spracherkennung des Modells
        lang_map = {"de": "Deutsch", "en": "Englisch", "fr": "Französisch", "es": "Spanisch"} # Bei Bedarf erweitern
        lang_name = lang_map.get(language.lower(), language)
        api_prompt = f"Die folgende Transkription ist auf {lang_name}."
        logger.info(f"Verwende OpenAI API Prompt: '{api_prompt}'")

    # --- Audio Stream ---
    stream = None
    try:
        gui_q.put(("status", f"Öffne Audio Stream von Gerät {device_id}..."))
        # Übergib die audio_q an den Callback
        stream = sd.InputStream(
            samplerate=samplerate,
            device=device_id,
            channels=channels,
            callback=lambda indata, frames, time_info, status: audio_callback(indata, frames, time_info, status, audio_q),
            dtype='float32',
            blocksize=int(samplerate * 0.1) # Verarbeite Audio in 100ms-Chunks (anpassbar)
        )
        logger.info(f"Audio Stream konfiguriert: Rate={samplerate}, Kanäle={channels}, Blocksize={stream.blocksize}")

        with stream:
            gui_q.put(("status", f"Aufnahme läuft ({processing_mode.upper()}) – Sprich jetzt."))
            logger.info("Audio Stream gestartet. Warte auf Audio-Daten...")

            # --- Haupt-Aufnahmeschleife ---
            while not stop_recording_flag.is_set():
                try:
                    # Hole Audio-Chunk aus der Queue (gefüllt durch audio_callback)
                    # Timeout verhindert unendliches Blockieren, wenn kein Audio kommt
                    audio_chunk = audio_q.get(timeout=0.1) # Timeout in Sekunden

                    # Füge neuen Chunk zum Hauptpuffer hinzu
                    # Verwende flatten(), falls audio_chunk mehrere Dimensionen hat (z.B. Stereo)
                    audio_buffer = np.concatenate((audio_buffer, audio_chunk.flatten()))

                    # --- Stilleerkennung ---
                    # Berechne Root Mean Square (RMS) Energie des Chunks
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    # Vergleiche RMS mit dem Energie-Schwellenwert (passend skaliert)
                    if rms > energy_threshold / 1000.0: # Skalierungsfaktor bei Bedarf anpassen
                        last_sound_time = time.time()
                        samples_since_last_sound = 0 # Setze Stillezähler zurück
                        if is_silent:
                            logger.debug("Sprache erkannt.")
                            is_silent = False
                    else:
                        # Erhöhe Stillezähler nur, wenn wir vorher Geräusche gehört haben
                        if not is_silent:
                            samples_since_last_sound += len(audio_chunk)
                            # Prüfe, ob Schwellenwert für Stilledauer erreicht ist
                            if samples_since_last_sound >= silence_samples:
                                logger.debug(f"Stille erkannt ({silence_sec}s).")
                                is_silent = True
                                # Verarbeite Puffer jetzt aufgrund von Stille
                                should_transcribe = True
                            else:
                                # Noch in der Toleranzzeit der Stille
                                should_transcribe = False
                        else:
                             # Bereits still, noch keine Verarbeitung nötig, es sei denn, Puffer ist voll
                             should_transcribe = False

                    # --- Transkriptionsauslöser ---
                    buffer_duration_samples = len(audio_buffer)
                    # Bedingung 1: Puffer überschreitet Mindestdauer ODER
                    # Bedingung 2: Stille erkannt UND Puffer hat Inhalt (>0.5s, um kleine Fragmente zu vermeiden)
                    if not should_transcribe: # Prüfe Pufferlänge nur, wenn Stille nicht ausgelöst hat
                        should_transcribe = buffer_duration_samples >= min_buffer_samples

                    # Füge Bedingung hinzu, um bei Stille nur zu verarbeiten, wenn Puffer nicht leer ist
                    if is_silent and buffer_duration_samples < int(0.5 * samplerate):
                        should_transcribe = False # Verarbeite keine sehr kurzen stillen Puffer

                    # --- Puffer verarbeiten ---
                    if should_transcribe and buffer_duration_samples > 0:
                        segment_counter += 1
                        current_segment_id = segment_counter
                        gui_q.put(("status", f"Verarbeite Segment {current_segment_id} ({processing_mode.upper()})..."))
                        logger.info(f"Verarbeite Segment {current_segment_id} (Länge: {buffer_duration_samples/samplerate:.2f}s)")

                        # Kopiere Pufferinhalt zur Transkription und leere Hauptpuffer
                        audio_to_transcribe = audio_buffer.copy()
                        audio_buffer = np.array([], dtype=np.float32) # Setze Puffer zurück
                        samples_since_last_sound = 0 # Setze Stillezähler nach Verarbeitung zurück

                        # --- Führe Transkription durch ---
                        text_raw = transcribe_audio_chunk(
                            audio_to_transcribe,
                            processing_mode,
                            gui_q, # Übergebe gui_q für Fehlermeldungen
                            lang=language,
                            openai_model="whisper-1", # Hardcodiert, könnte konfigurierbar sein
                            el_model_id=elevenlabs_model_id,
                            api_prompt=api_prompt
                        )

                        # --- Nachbearbeitung ---
                        # Wende Ersetzungen AN, bevor gefiltert wird
                        text_replaced = apply_replacements(text_raw, loaded_replacements)
                        # Wende Filter auf den ersetzten Text an
                        text_filtered = filter_transcription(text_replaced, filter_patterns, filter_parentheses)


                        gui_q.put(("status", f"Segment {current_segment_id} fertig ({processing_mode.upper()}). Warte auf nächste Sprache."))
                        logger.info(f"Segment {current_segment_id} Ergebnis (gefiltert): '{text_filtered[:100]}...'")

                        # --- Ausgabe ---
                        if text_filtered and "[Fehler]" not in text_filtered: # Prüfe auf Fehlermarkierungen
                            # FIX: Verwende das importierte datetime-Objekt
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            # Sende an GUI
                            gui_q.put(("transcription", f"{timestamp} - {text_filtered}"))

                            # Schreibe in Datei
                            if output_file:
                                try:
                                    with open(output_file, "a", encoding="utf-8") as f:
                                        if file_format == "txt":
                                            f.write(f"{timestamp} - {text_filtered}\n")
                                        elif file_format == "json":
                                            # Importiere json nur hier, wenn es nur hier gebraucht wird
                                            import json
                                            json.dump({"timestamp": timestamp, "text": text_filtered}, f, ensure_ascii=False)
                                            f.write("\n")
                                except IOError as e_io:
                                    logger.error(f"Fehler beim Schreiben in die Ausgabedatei '{output_file}': {e_io}")
                                    gui_q.put(("error", f"Fehler Schreiben Datei '{os.path.basename(output_file)}': {e_io}"))
                                except Exception as e_file:
                                     logger.exception(f"Unerwarteter Fehler beim Schreiben der Datei '{output_file}'")
                                     gui_q.put(("error", f"Dateifehler '{os.path.basename(output_file)}': {e_file}"))

                            # Sende an Streamer.bot über Queue
                            if send_to_streamerbot_flag:
                                try:
                                    # Erstelle Payload als Dictionary
                                    payload = {"source": "stt", "text": stt_prefix + text_filtered}
                                    # Konvertiere Dictionary zu JSON-String
                                    # Importiere json nur hier, wenn es nur hier gebraucht wird
                                    import json
                                    payload_json = json.dumps(payload)
                                    streamerbot_queue.put(payload_json)
                                    logger.debug(f"Nachricht an Streamer.bot Queue gesendet: {payload_json[:100]}...")
                                except queue.Full:
                                     logger.warning("Streamer.bot Queue ist voll. Nachricht verworfen.")
                                     gui_q.put(("warning", "SB Queue voll!"))
                                except Exception as e_q:
                                    logger.error(f"Fehler beim Hinzufügen zur Streamer.bot Queue: {e_q}")
                                    gui_q.put(("warning", f"Fehler Senden an SB: {e_q}"))

                        # Kleine Pause, um Kontrolle abzugeben und Busy-Waiting zu verhindern
                        time.sleep(0.01)

                except queue.Empty:
                    # Queue war leer, d.h. kein neuer Audio-Chunk kam innerhalb des Timeouts an.
                    # Prüfe, ob der Stille-Schwellenwert *jetzt* erreicht wurde
                    if not is_silent and (time.time() - last_sound_time) > silence_sec:
                         logger.debug(f"Stille nach Timeout erkannt ({silence_sec}s).")
                         is_silent = True
                         # Verarbeite jeglichen verbleibenden Pufferinhalt, falls vorhanden
                         if len(audio_buffer) > int(0.5 * samplerate): # Schwellenwert, um kleine Fragmente zu vermeiden
                            segment_counter += 1
                            current_segment_id = segment_counter
                            gui_q.put(("status", f"Verarbeite Restpuffer {current_segment_id} nach Stille ({processing_mode.upper()})..."))
                            logger.info(f"Verarbeite Restpuffer {current_segment_id} (Länge: {len(audio_buffer)/samplerate:.2f}s)")

                            audio_to_transcribe = audio_buffer.copy()
                            audio_buffer = np.array([], dtype=np.float32) # Setze Puffer zurück
                            samples_since_last_sound = 0

                            # --- Führe Transkription durch (Logik wiederholen) ---
                            text_raw = transcribe_audio_chunk(
                                audio_to_transcribe,
                                processing_mode,
                                gui_q,
                                lang=language,
                                openai_model="whisper-1",
                                el_model_id=elevenlabs_model_id,
                                api_prompt=api_prompt
                            )
                            text_replaced = apply_replacements(text_raw, loaded_replacements)
                            text_filtered = filter_transcription(text_replaced, filter_patterns, filter_parentheses)


                            gui_q.put(("status", f"Segment {current_segment_id} (Rest) fertig ({processing_mode.upper()}). Warte auf nächste Sprache."))
                            logger.info(f"Segment {current_segment_id} (Rest) Ergebnis: '{text_filtered[:100]}...'")

                            # --- Ausgabe (Logik wiederholen) ---
                            if text_filtered and "[Fehler]" not in text_filtered:
                                # FIX: Verwende das importierte datetime-Objekt
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                gui_q.put(("transcription", f"{timestamp} - {text_filtered}"))
                                if output_file:
                                    try:
                                        with open(output_file, "a", encoding="utf-8") as f:
                                            if file_format == "txt": f.write(f"{timestamp} - {text_filtered}\n")
                                            elif file_format == "json":
                                                import json
                                                json.dump({"timestamp": timestamp, "text": text_filtered}, f, ensure_ascii=False); f.write("\n")
                                    except IOError as e_io:
                                        logger.error(f"Fehler Schreiben (Restpuffer) '{output_file}': {e_io}")
                                        gui_q.put(("error", f"Fehler Schreiben (Rest) '{os.path.basename(output_file)}': {e_io}"))
                                    except Exception as e_file:
                                         logger.exception(f"Unerwarteter Dateifehler (Restpuffer) '{output_file}'")
                                         gui_q.put(("error", f"Dateifehler (Rest) '{os.path.basename(output_file)}': {e_file}"))

                                if send_to_streamerbot_flag:
                                    try:
                                        payload = {"source": "stt", "text": stt_prefix + text_filtered}
                                        import json
                                        payload_json = json.dumps(payload)
                                        streamerbot_queue.put(payload_json)
                                        logger.debug(f"Nachricht (Restpuffer) an SB Queue: {payload_json[:100]}...")
                                    except queue.Full:
                                         logger.warning("Streamer.bot Queue (Restpuffer) ist voll.")
                                         gui_q.put(("warning", "SB Queue voll!"))
                                    except Exception as e_q:
                                        logger.error(f"Fehler Hinzufügen zur SB Queue (Restpuffer): {e_q}")
                                        gui_q.put(("warning", f"Fehler Senden an SB: {e_q}"))
                    continue # Setze Schleife nach Behandlung der leeren Queue fort

    except sd.PortAudioError as e:
        logger.exception("PortAudio Fehler im Audio Stream")
        gui_q.put(("status", "Fehler Audio Stream!"))
        gui_q.put(("error", f"PortAudio Fehler: {e}. Aufnahme gestoppt."))
        stop_recording_flag.set() # Signalisiere Stopp bei kritischem Audiofehler
    except Exception as e:
        logger.exception("Unerwarteter Fehler im Aufnahme-Worker-Thread")
        gui_q.put(("status", "Unerwarteter Fehler im Worker!"))
        gui_q.put(("error", f"Unerwarteter Fehler: {e}\n(Details im Logfile)"))
        stop_recording_flag.set() # Signalisiere Stopp bei unerwartetem Fehler
    finally:
        # --- Aufräumen ---
        logger.info("Aufnahme-Worker wird beendet.")
        if stream and stream.active:
            try:
                stream.stop()
                stream.close()
                logger.info("Audio Stream gestoppt und geschlossen.")
            except Exception as e_close:
                 logger.error(f"Fehler beim Schließen des Audio Streams: {e_close}")

        # Leere die Audio-Queue, falls der Callback während des Herunterfahrens weitere Daten hinzugefügt hat
        while not audio_q.empty():
            try:
                audio_q.get_nowait()
            except queue.Empty:
                break
        logger.debug("Audio Queue geleert.")

        # Benachrichtige den GUI-Thread, dass der Worker beendet ist
        gui_q.put(("finished", None))
        status_msg = "Aufnahme beendet." if stop_recording_flag.is_set() else "Worker unerwartet beendet."
        gui_q.put(("status", status_msg))
        logger.info(f"Aufnahme-Worker-Thread vollständig beendet. Status: {status_msg}")

