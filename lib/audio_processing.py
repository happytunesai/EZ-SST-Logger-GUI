# -*- coding: utf-8 -*-
"""
Functions and worker thread for audio recording, processing, and transcription.
"""
import threading
import queue
import time
import io
import numpy as np
from datetime import datetime
import os  # Required for os.path.basename

# Import dependent libraries with error handling
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
    # Import specific ElevenLabs elements if available
    from elevenlabs.client import ElevenLabs
    from elevenlabs.core import ApiError as ElevenLabsApiError
    HAS_ELEVENLABS_LIBS = True
except ImportError:
    ElevenLabs = None
    ElevenLabsApiError = None
    HAS_ELEVENLABS_LIBS = False

# Import local modules/objects
from lib.logger_setup import logger
from lib.text_processing import apply_replacements, filter_transcription
from lib.language_manager import tr
from lib.constants import DEFAULT_SAMPLERATE

# Global variables for this module (API clients, loaded model)
# These are managed by initialize_stt_client
local_whisper_model = None
openai_client = None
elevenlabs_client = None
currently_loaded_local_model_name = None

def audio_callback(indata, frames, time_info, status, audio_q):
    """
    This function is called by the sounddevice stream for each new audio buffer.
    Args:
        indata (np.ndarray): The audio data buffer.
        frames (int): Number of frames in the buffer.
        time_info: Time information from the stream.
        status (sd.CallbackFlags): Status flags from the stream.
        audio_q (queue.Queue): The queue to put audio data in.
    """
    if status:
        # Log all status messages from the audio stream (e.g., buffer overflows)
        logger.warning(tr("log_ap_audio_callback_status", status=status))
    # Put a copy of the audio data (numpy array) in the queue for the worker thread
    # Copying is important as the original buffer might be reused by sounddevice
    audio_q.put(indata.copy())

def initialize_stt_client(mode, gui_q, api_key=None, model_name=None):
    """
    Initializes the appropriate STT client (Local, OpenAI, ElevenLabs) based on the mode.
    Manages the global client references of this module.
    Args:
        mode (str): The processing mode ('local', 'openai', 'elevenlabs').
        gui_q (queue.Queue): The queue for sending status/errors to the GUI.
        api_key (str, optional): The API key for OpenAI or ElevenLabs.
        model_name (str, optional): The name of the local Whisper model.
    Returns:
        bool: True on success, False on error.
    """
    global local_whisper_model, openai_client, elevenlabs_client, currently_loaded_local_model_name

    if mode == "local":
        if not whisper:
             gui_q.put(("status", tr("log_ap_whisper_missing")))
             gui_q.put(("error", tr("log_ap_whisper_local_unavailable")))
             return False
        # Load or reuse the local Whisper model
        if local_whisper_model is None or currently_loaded_local_model_name != model_name:
            gui_q.put(("status", tr("log_ap_loading_model", model_name=model_name)))
            try:
                local_whisper_model = whisper.load_model(model_name)
                currently_loaded_local_model_name = model_name
                gui_q.put(("status", tr("log_ap_model_loaded", model_name=model_name)))
                logger.info(tr("log_ap_model_loaded", model_name=model_name))
            except Exception as e:
                logger.exception(tr("log_ap_model_load_error", model_name=model_name))
                gui_q.put(("status", tr("log_ap_model_load_error", model_name=model_name)))
                gui_q.put(("error", tr("log_ap_model_load_error_details", error=e)))
                currently_loaded_local_model_name = None
                local_whisper_model = None
                return False  # Signal error
        else:
            gui_q.put(("status", tr("log_ap_model_already_loaded", model_name=model_name)))
            logger.info(tr("log_ap_using_loaded_model", model_name=model_name))
        return True  # Signal success

    elif mode == "openai":
        if not openai:
             gui_q.put(("status", tr("log_ap_openai_missing")))
             gui_q.put(("error", tr("log_ap_openai_unavailable")))
             return False
        if not api_key:
            gui_q.put(("status", tr("log_ap_openai_key_missing")))
            gui_q.put(("error", tr("log_ap_openai_key_invalid")))
            return False  # Signal error
        # Initialize OpenAI Client
        gui_q.put(("status", tr("log_ap_initializing_openai")))
        try:
            # Simple approach: Always reinitialize when mode is selected
            openai_client = openai.OpenAI(api_key=api_key)
            # Optional: Test call to verify the key
            # openai_client.models.list()
            gui_q.put(("status", tr("log_ap_openai_ready")))
            logger.info(tr("log_ap_openai_initialized"))
            return True  # Signal success
        except openai.AuthenticationError:
             logger.error(tr("log_ap_openai_auth_error"))
             gui_q.put(("status", tr("log_ap_openai_key_invalid_status")))
             gui_q.put(("error", tr("log_ap_openai_key_expired")))
             openai_client = None
             return False
        except Exception as e:
            logger.exception(tr("log_ap_openai_init_error"))
            gui_q.put(("status", tr("log_ap_openai_init_error_status")))
            gui_q.put(("error", tr("log_ap_openai_init_error_details", error=e)))
            openai_client = None
            return False  # Signal error

    elif mode == "elevenlabs":
        if not HAS_ELEVENLABS_LIBS:
            gui_q.put(("status", tr("log_ap_elevenlabs_missing")))
            gui_q.put(("error", tr("log_ap_elevenlabs_unavailable")))
            return False  # Signal error
        if not api_key:
            gui_q.put(("status", tr("log_ap_elevenlabs_key_missing")))
            gui_q.put(("error", tr("log_ap_elevenlabs_key_invalid")))
            return False  # Signal error
        # Initialize ElevenLabs Client
        gui_q.put(("status", tr("log_ap_initializing_elevenlabs")))
        try:
            # Simple approach: Always reinitialize when mode is selected
            elevenlabs_client = ElevenLabs(api_key=api_key)
            # Optional: Test call, e.g. get user info
            # elevenlabs_client.user.get()
            gui_q.put(("status", tr("log_ap_elevenlabs_ready")))
            logger.info(tr("log_ap_elevenlabs_initialized"))
            return True  # Signal success
        except ElevenLabsApiError as e:
             logger.error(tr("log_ap_elevenlabs_api_error", error=e))
             gui_q.put(("status", tr("log_ap_elevenlabs_api_error_status", code=e.status_code)))
             gui_q.put(("error", tr("log_ap_elevenlabs_error_details", error=e)))
             elevenlabs_client = None
             return False
        except Exception as e:
            logger.exception(tr("log_ap_elevenlabs_init_error"))
            gui_q.put(("status", tr("log_ap_elevenlabs_init_error_status")))
            gui_q.put(("error", tr("log_ap_elevenlabs_init_error_details", error=e)))
            elevenlabs_client = None
            return False  # Signal error
    else:
        logger.error(tr("log_ap_unknown_mode", mode=mode))
        gui_q.put(("status", tr("log_ap_unknown_mode_status", mode=mode)))
        return False  # Signal error

def transcribe_audio_chunk(audio_data_np, mode, gui_q, lang=None, openai_model="whisper-1", el_model_id=None, api_prompt=None):
    """
    Transcribes a NumPy audio chunk with the specified mode and model.
    Uses the global API clients of this module.
    Args:
        audio_data_np (np.ndarray): The audio chunk to transcribe.
        mode (str): The processing mode ('local', 'openai', 'elevenlabs').
        gui_q (queue.Queue): The queue for sending status/errors to the GUI.
        lang (str, optional): The language code (e.g., 'de', 'en').
        openai_model (str, optional): The OpenAI model to use.
        el_model_id (str, optional): The ElevenLabs model ID to use.
        api_prompt (str, optional): A prompt for the OpenAI API.
    Returns:
        str: The raw transcription text or an error message.
    """
    # Access the global clients of this module
    global local_whisper_model, openai_client, elevenlabs_client

    # Check if required libraries are available
    if mode == 'local' and not whisper: return "[Error: Whisper Lib missing]"
    if mode == 'openai' and not openai: return "[Error: OpenAI Lib missing]"
    if mode == 'elevenlabs' and not ElevenLabs: return "[Error: ElevenLabs Lib missing]"
    if (mode == 'openai' or mode == 'elevenlabs') and not sf: return "[Error: SoundFile Lib missing]"

    text_raw = ""
    try:
        if mode == "local":
            if local_whisper_model is None:
                raise RuntimeError("Local Whisper model is not loaded.")
            # Prepare transcription options
            transcription_options = {}
            if lang:
                transcription_options["language"] = lang
            # Ensure audio is float32 as expected by Whisper
            audio_float32 = audio_data_np.astype(np.float32)
            logger.debug(tr("log_ap_local_transcription_start", 
                           length=f"{len(audio_float32)/DEFAULT_SAMPLERATE:.2f}", 
                           options=transcription_options))
            result = local_whisper_model.transcribe(audio_float32, **transcription_options)
            text_raw = result["text"].strip()
            logger.debug(tr("log_ap_local_transcription_result", 
                           text=f"{text_raw[:100]}..." if len(text_raw) > 100 else text_raw))

        elif mode == "openai":
            if openai_client is None:
                raise RuntimeError("OpenAI API Client is not initialized.")
            # Convert numpy array to WAV in memory
            audio_buffer_bytes = io.BytesIO()
            sf.write(audio_buffer_bytes, audio_data_np, DEFAULT_SAMPLERATE, format='WAV', subtype='PCM_16')
            audio_buffer_bytes.seek(0)
            # Prepare file tuple for API request
            files_tuple = ('audio.wav', audio_buffer_bytes, 'audio/wav')
            api_language = lang if lang else None  # API expects None for auto-detect
            logger.debug(tr("log_ap_openai_transcription_start", 
                           model=openai_model, 
                           language=api_language, 
                           has_prompt=api_prompt is not None, 
                           length=f"{len(audio_data_np)/DEFAULT_SAMPLERATE:.2f}"))
            response = openai_client.audio.transcriptions.create(
                model=openai_model,
                file=files_tuple,
                language=api_language,
                prompt=api_prompt,  # Send prompt if available
                temperature=0.0  # Lower temperature for more deterministic results
            )
            text_raw = response.text.strip()
            audio_buffer_bytes.close()
            logger.debug(tr("log_ap_openai_transcription_result", 
                           text=f"{text_raw[:100]}..." if len(text_raw) > 100 else text_raw))

        elif mode == "elevenlabs":
            if elevenlabs_client is None:
                raise RuntimeError("ElevenLabs API Client is not initialized.")
            if el_model_id is None:
                 raise ValueError("ElevenLabs Model ID not specified.")
            # Convert numpy array to MP3 in memory (ElevenLabs prefers MP3)
            audio_buffer_bytes = io.BytesIO()
            sf.write(audio_buffer_bytes, audio_data_np, DEFAULT_SAMPLERATE, format='MP3')  # Use MP3
            audio_buffer_bytes.seek(0)
            logger.debug(tr("log_ap_elevenlabs_transcription_start", 
                           model=el_model_id, 
                           length=f"{len(audio_data_np)/DEFAULT_SAMPLERATE:.2f}"))
            # Call the speech-to-text conversion method
            response = elevenlabs_client.speech_to_text.convert(
                file=audio_buffer_bytes,
                model_id=el_model_id
            )
            # Check if the response has a 'text' attribute
            if hasattr(response, 'text'):
                text_raw = response.text.strip()
            else:
                # Log unexpected response structure and convert to string as fallback
                logger.warning(tr("log_ap_elevenlabs_unexpected_response", response=response))
                text_raw = str(response)
            audio_buffer_bytes.close()
            logger.debug(tr("log_ap_elevenlabs_transcription_result", 
                           text=f"{text_raw[:100]}..." if len(text_raw) > 100 else text_raw))

        return text_raw  # Return the raw transcription text

    # --- Error handling specific to APIs ---
    except openai.APIError as e:
         logger.error(tr("log_ap_openai_api_error", error=e))
         gui_q.put(("status", tr("log_ap_openai_api_error_status")))
         return f"[OpenAI-API-Error: {e.code}]"
    except openai.AuthenticationError:
         logger.error(tr("log_ap_openai_auth_error_during_transcription"))
         gui_q.put(("status", tr("log_ap_openai_auth_error_status")))
         return "[OpenAI-Auth-Error]"
    except ElevenLabsApiError as e:
         logger.error(tr("log_ap_elevenlabs_api_error_transcription", error=e))
         gui_q.put(("status", tr("log_ap_elevenlabs_api_error_status", code=e.status_code)))
         return f"[ElevenLabs-API-Error: {e.status_code}]"
    # --- General error handling ---
    except sd.PortAudioError as e:
         # This error should actually occur in stream handling, but catch it here to be safe
         logger.exception(tr("log_ap_portaudio_error"))
         gui_q.put(("status", tr("log_ap_audio_error_status")))
         return "[Audio-Error]"
    except RuntimeError as e:
         logger.error(tr("log_ap_runtime_error", error=e))
         gui_q.put(("status", tr("log_ap_runtime_error_status", error=e)))
         return f"[Runtime-Error]"
    except Exception as e:
        logger.exception(tr("log_ap_transcription_error", mode=mode))
        api_name = mode.capitalize()
        gui_q.put(("status", tr("log_ap_transcription_error_status", api_name=api_name)))
        return f"[{api_name}-Transcription-Error]"

def recording_worker(**kwargs):
    """
    Worker thread that handles audio recording, buffering, silence detection, and transcription.
    Takes all required parameters as keyword arguments.
    """
    # Unpack arguments from kwargs for better readability
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
    # streamerbot_ws_url = kwargs['streamerbot_ws_url']  # Not directly needed here
    stt_prefix = kwargs['stt_prefix']
    # Get queues and flags from kwargs
    audio_q = kwargs['audio_q']
    gui_q = kwargs['gui_q']
    streamerbot_queue = kwargs['streamerbot_queue']
    stop_recording_flag = kwargs['stop_recording_flag']
    # Get filters/replacements
    loaded_replacements = kwargs['loaded_replacements']
    filter_patterns = kwargs['filter_patterns']  # List of compiled patterns

    # Check if Sounddevice is available
    if not sd or not sf:
        logger.critical(tr("log_ap_libs_missing"))
        gui_q.put(("error", "Sounddevice/Soundfile missing!"))
        stop_recording_flag.set()
        gui_q.put(("finished", None))
        return

    # --- Initialization ---
    logger.info(tr("log_ap_worker_start", mode=processing_mode, device=device_id, model=model_name or elevenlabs_model_id))
    if not initialize_stt_client(processing_mode, gui_q,
                                 api_key=openai_api_key if processing_mode == "openai" else elevenlabs_api_key,
                                 model_name=model_name if processing_mode == "local" else None):
        logger.error(tr("log_ap_client_init_failed"))
        stop_recording_flag.set()  # Ensure flag is set when init fails
        gui_q.put(("finished", None))  # Notify GUI
        return  # End thread

    # --- State variables ---
    audio_buffer = np.array([], dtype=np.float32)  # Buffer for collecting audio chunks
    min_buffer_samples = int(min_buffer_sec * samplerate)  # Minimum samples before processing
    silence_samples = int(silence_sec * samplerate)  # Silence samples before processing buffer
    last_sound_time = time.time()  # Timestamp of last detected sound
    is_silent = True  # Flag indicating if currently in a silent period
    segment_counter = 0  # Counter for processed audio segments
    samples_since_last_sound = 0  # Counter for consecutive silent samples

    # --- OpenAI Specific ---
    api_prompt = None
    if processing_mode == "openai" and language:
        # Simple prompt to assist the model's language recognition
        lang_map = {"de": "Deutsch", "en": "English", "fr": "French", "es": "Spanish"}  # Expand as needed
        lang_name = lang_map.get(language.lower(), language)
        api_prompt = f"The following transcription is in {lang_name}."
        logger.info(tr("log_ap_using_openai_prompt", prompt=api_prompt))

    # --- Audio Stream ---
    stream = None
    try:
        gui_q.put(("status", tr("log_ap_open_audio_stream", device_id=device_id)))
        # Pass the audio_q to the callback
        stream = sd.InputStream(
            samplerate=samplerate,
            device=device_id,
            channels=channels,
            callback=lambda indata, frames, time_info, status: audio_callback(indata, frames, time_info, status, audio_q),
            dtype='float32',
            blocksize=int(samplerate * 0.1)  # Process audio in 100ms chunks (adjustable)
        )
        logger.info(tr("log_ap_audio_stream_configured", rate=samplerate, channels=channels, blocksize=stream.blocksize))

        with stream:
            gui_q.put(("status", tr("log_ap_recording_running", mode=processing_mode.upper())))
            logger.info(tr("log_ap_audio_stream_started"))

            # --- Main recording loop ---
            while not stop_recording_flag.is_set():
                try:
                    # Get audio chunk from the queue (filled by audio_callback)
                    # Timeout prevents infinite blocking if no audio is coming
                    audio_chunk = audio_q.get(timeout=0.1)  # Timeout in seconds

                    # Add new chunk to main buffer
                    # Use flatten() in case audio_chunk has multiple dimensions (e.g., stereo)
                    audio_buffer = np.concatenate((audio_buffer, audio_chunk.flatten()))

                    # --- Silence detection ---
                    # Calculate Root Mean Square (RMS) energy of the chunk
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    # Compare RMS with the energy threshold (suitably scaled)
                    if rms > energy_threshold / 1000.0:  # Scaling factor, adjust as needed
                        last_sound_time = time.time()
                        samples_since_last_sound = 0  # Reset silence counter
                        if is_silent:
                            logger.debug(tr("log_ap_speech_detected"))
                            is_silent = False
                    else:
                        # Increase silence counter only if we previously heard sounds
                        if not is_silent:
                            samples_since_last_sound += len(audio_chunk)
                            # Check if silence duration threshold has been reached
                            if samples_since_last_sound >= silence_samples:
                                logger.debug(tr("log_ap_silence_detected", seconds=silence_sec))
                                is_silent = True
                                # Process buffer now due to silence
                                should_transcribe = True
                            else:
                                # Still within silence tolerance time
                                should_transcribe = False
                        else:
                             # Already silent, no processing needed unless buffer is full
                             should_transcribe = False

                    # --- Transcription triggers ---
                    buffer_duration_samples = len(audio_buffer)
                    # Condition 1: Buffer exceeds minimum duration OR
                    # Condition 2: Silence detected AND buffer has content (>0.5s, to avoid small fragments)
                    if not should_transcribe:  # Only check buffer length if silence hasn't triggered
                        should_transcribe = buffer_duration_samples >= min_buffer_samples

                    # Add condition to only process on silence if buffer is not empty
                    if is_silent and buffer_duration_samples < int(0.5 * samplerate):
                        should_transcribe = False  # Don't process very short silent buffers

                    # --- Process buffer ---
                    if should_transcribe and buffer_duration_samples > 0:
                        segment_counter += 1
                        current_segment_id = segment_counter
                        gui_q.put(("status", tr("log_ap_processing_segment", segment_id=current_segment_id, mode=processing_mode.upper())))
                        logger.info(tr("log_ap_segment_length", segment_id=current_segment_id, length=f"{buffer_duration_samples/samplerate:.2f}"))

                        # Copy buffer content for transcription and clear main buffer
                        audio_to_transcribe = audio_buffer.copy()
                        audio_buffer = np.array([], dtype=np.float32)  # Reset buffer
                        samples_since_last_sound = 0  # Reset silence counter after processing

                        # --- Perform transcription ---
                        text_raw = transcribe_audio_chunk(
                            audio_to_transcribe,
                            processing_mode,
                            gui_q,  # Pass gui_q for error messages
                            lang=language,
                            openai_model="whisper-1",  # Hardcoded, could be configurable
                            el_model_id=elevenlabs_model_id,
                            api_prompt=api_prompt
                        )

                        # --- Post-processing ---
                        # Apply replacements BEFORE filtering
                        text_replaced = apply_replacements(text_raw, loaded_replacements)
                        # Apply filters to the replaced text
                        text_filtered = filter_transcription(text_replaced, filter_patterns, filter_parentheses)

                        gui_q.put(("status", tr("log_ap_segment_finished", segment_id=current_segment_id, mode=processing_mode.upper())))
                        logger.info(tr("log_ap_segment_result", 
                                      segment_id=current_segment_id, 
                                      text=f"{text_filtered[:100]}..." if len(text_filtered) > 100 else text_filtered))

                        # --- Output ---
                        if text_filtered and "[Error]" not in text_filtered:  # Check for error markers
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            # Send to GUI
                            gui_q.put(("transcription", f"{timestamp} - {text_filtered}"))

                            # Write to file
                            if output_file:
                                try:
                                    with open(output_file, "a", encoding="utf-8") as f:
                                        if file_format == "txt":
                                            f.write(f"{timestamp} - {text_filtered}\n")
                                        elif file_format == "json":
                                            # Import json only here if only needed here
                                            import json
                                            json.dump({"timestamp": timestamp, "text": text_filtered}, f, ensure_ascii=False)
                                            f.write("\n")
                                except IOError as e_io:
                                    logger.error(tr("log_ap_file_write_error", filename=output_file, error=e_io))
                                    gui_q.put(("error", tr("log_ap_file_write_error", filename=os.path.basename(output_file), error=e_io)))
                                except Exception as e_file:
                                     logger.exception(tr("log_ap_file_unexpected_error", filename=output_file))
                                     gui_q.put(("error", tr("log_ap_file_unexpected_error", filename=os.path.basename(output_file), error=e_file)))

                            # Send to Streamer.bot via queue
                            if send_to_streamerbot_flag:
                                try:
                                    # Create payload as dictionary
                                    payload = {"source": "stt", "text": stt_prefix + text_filtered}
                                    # Convert dictionary to JSON string
                                    # Import json only here if only needed here
                                    import json
                                    payload_json = json.dumps(payload)
                                    streamerbot_queue.put(payload_json)
                                    logger.debug(tr("log_ap_sb_message_sent", 
                                                   message=f"{payload_json[:100]}..." if len(payload_json) > 100 else payload_json))
                                except queue.Full:
                                     logger.warning(tr("log_ap_sb_queue_full"))
                                     gui_q.put(("warning", "SB Queue full!"))
                                except Exception as e_q:
                                    logger.error(tr("log_ap_sb_queue_error", error=e_q))
                                    gui_q.put(("warning", tr("log_ap_sb_queue_error", error=e_q)))

                        # Small pause to yield control and prevent busy-waiting
                        time.sleep(0.01)

                except queue.Empty:
                    # Queue was empty, i.e., no new audio chunk arrived within the timeout.
                    # Check if the silence threshold has been reached *now*
                    if not is_silent and (time.time() - last_sound_time) > silence_sec:
                         logger.debug(tr("log_ap_silence_detected", seconds=silence_sec))
                         is_silent = True
                         # Process any remaining buffer content, if present
                         if len(audio_buffer) > int(0.5 * samplerate):  # Threshold to avoid small fragments
                            segment_counter += 1
                            current_segment_id = segment_counter
                            gui_q.put(("status", tr("log_ap_processing_remainder", segment_id=current_segment_id, mode=processing_mode.upper())))
                            logger.info(tr("log_ap_processing_remainder_length", segment_id=current_segment_id, length=f"{len(audio_buffer)/samplerate:.2f}"))

                            audio_to_transcribe = audio_buffer.copy()
                            audio_buffer = np.array([], dtype=np.float32)  # Reset buffer
                            samples_since_last_sound = 0

                            # --- Perform transcription (repeat logic) ---
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

                            gui_q.put(("status", tr("log_ap_remainder_finished", segment_id=current_segment_id, mode=processing_mode.upper())))
                            logger.info(tr("log_ap_remainder_result", 
                                          segment_id=current_segment_id, 
                                          text=f"{text_filtered[:100]}..." if len(text_filtered) > 100 else text_filtered))

                            # --- Output (repeat logic) ---
                            if text_filtered and "[Error]" not in text_filtered:
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                gui_q.put(("transcription", f"{timestamp} - {text_filtered}"))
                                if output_file:
                                    try:
                                        with open(output_file, "a", encoding="utf-8") as f:
                                            if file_format == "txt": 
                                                f.write(f"{timestamp} - {text_filtered}\n")
                                            elif file_format == "json":
                                                import json
                                                json.dump({"timestamp": timestamp, "text": text_filtered}, f, ensure_ascii=False)
                                                f.write("\n")
                                    except IOError as e_io:
                                        logger.error(tr("log_ap_file_write_error_remainder", filename=output_file, error=e_io))
                                        gui_q.put(("error", tr("log_ap_file_write_error_remainder", filename=os.path.basename(output_file), error=e_io)))
                                    except Exception as e_file:
                                         logger.exception(tr("log_ap_file_unexpected_error_remainder", filename=output_file))
                                         gui_q.put(("error", tr("log_ap_file_unexpected_error_remainder", filename=os.path.basename(output_file), error=e_file)))

                                if send_to_streamerbot_flag:
                                    try:
                                        payload = {"source": "stt", "text": stt_prefix + text_filtered}
                                        import json
                                        payload_json = json.dumps(payload)
                                        streamerbot_queue.put(payload_json)
                                        logger.debug(tr("log_ap_sb_message_sent_remainder", 
                                                       message=f"{payload_json[:100]}..." if len(payload_json) > 100 else payload_json))
                                    except queue.Full:
                                         logger.warning(tr("log_ap_sb_queue_full_remainder"))
                                         gui_q.put(("warning", "SB Queue full!"))
                                    except Exception as e_q:
                                        logger.error(tr("log_ap_sb_queue_error_remainder", error=e_q))
                                        gui_q.put(("warning", tr("log_ap_sb_queue_error", error=e_q)))
                    continue  # Continue loop after handling empty queue

    except sd.PortAudioError as e:
        logger.exception(tr("log_ap_portaudio_stream_error"))
        gui_q.put(("status", "Error Audio Stream!"))
        gui_q.put(("error", tr("log_ap_portaudio_error_details", error=e)))
        stop_recording_flag.set()  # Signal stop on critical audio error
    except Exception as e:
        logger.exception(tr("log_ap_worker_unexpected_error"))
        gui_q.put(("status", "Unexpected error in worker!"))
        gui_q.put(("error", f"Unexpected error: {e}\n(Details in logfile)"))
        stop_recording_flag.set()  # Signal stop on unexpected error
    finally:
        # --- Cleanup ---
        logger.info(tr("log_ap_worker_ending"))
        if stream and stream.active:
            try:
                stream.stop()
                stream.close()
                logger.info(tr("log_ap_stream_stopped"))
            except Exception as e_close:
                 logger.error(tr("log_ap_stream_close_error", error=e_close))

        # Empty the audio queue if the callback added more data during shutdown
        while not audio_q.empty():
            try:
                audio_q.get_nowait()
            except queue.Empty:
                break
        logger.debug(tr("log_ap_audio_queue_cleared"))

        # Notify the GUI thread that the worker has ended
        gui_q.put(("finished", None))
        status_msg = "Recording finished." if stop_recording_flag.is_set() else "Worker unexpectedly ended."
        gui_q.put(("status", status_msg))
        logger.info(tr("log_ap_worker_thread_ended", status=status_msg))
        