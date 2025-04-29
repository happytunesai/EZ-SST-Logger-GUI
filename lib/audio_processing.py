# -*- coding: utf-8 -*-
# lib/audio_processing.py
"""
Functions and worker thread for audio recording, processing, and transcription.
Enhanced with improved VAD (Voice Activity Detection) handling for better
transcription accuracy with the ElevenLabs Scribe API.
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
from lib.constants import DEFAULT_SAMPLERATE,DEFAULT_OPENAI_MODEL
# --- VAD Import ---
try:
    # We still need VadProcessor, but SegmentBuffer might be unused now
    from lib.vad_processor import VadProcessor
    HAS_VAD_PROCESSOR = True
except ImportError:
    VadProcessor = None  # Define as None if import fails
    HAS_VAD_PROCESSOR = False
    logger.warning(tr("log_ap_vad_import_warning"))


# Global variables for this module (API clients, loaded model)
# These are managed by initialize_stt_client
local_whisper_model = None
openai_client = None
elevenlabs_client = None
currently_loaded_local_model_name = None
openai_model = None  # Added for clarity


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
        logger.warning(tr("log_ap_audio_callback_status", status=status))
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


def transcribe_audio_chunk(audio_data_np, mode, gui_q, lang=None, openai_model=DEFAULT_OPENAI_MODEL, el_model_id=None, api_prompt=None):
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


def process_vad_segment(segment_data, processing_mode, gui_q, segment_id, **kwargs):
    """
    Enhanced processing of VAD-detected speech segments with better error handling
    and segment quality checks.
    MODIFIED: This function is now primarily called by process_and_output_vad_buffer.
    """
    # Get parameters from kwargs
    language = kwargs.get('language')
    openai_model = kwargs.get(DEFAULT_OPENAI_MODEL)
    elevenlabs_model_id = kwargs.get('elevenlabs_model_id')
    api_prompt = kwargs.get('api_prompt')
    loaded_replacements = kwargs.get('loaded_replacements', {})
    filter_patterns = kwargs.get('filter_patterns', [])
    filter_parentheses = kwargs.get('filter_parentheses', False)

    # Check segment duration
    segment_duration = len(segment_data) / DEFAULT_SAMPLERATE

    # Skip extremely short segments (Check might be redundant if buffer ensures min length)
    MIN_SEGMENT_DURATION = 0.25  # Increased slightly
    if segment_duration < MIN_SEGMENT_DURATION:
        logger.warning(tr("log_ap_vad_segment_too_short",
                    segment_id=segment_id,
                    length=f"{segment_duration:.2f}"))
        return None  # Skip processing

    # Skip low energy segments (likely silence) - Apply to combined segment
    rms = np.sqrt(np.mean(segment_data**2))
    if rms < 0.005:  # Very low energy threshold
        logger.warning(tr("log_ap_vad_segment_low_energy",
                    segment_id=segment_id,
                    rms=f"{rms:.5f}"))
        return None  # Skip processing

    # Log detailed segment info
    logger.info(tr("log_ap_vad_segment_process",
            segment_id=segment_id,
            length=f"{segment_duration:.2f}",
            rms=f"{rms:.5f}",
            peak=f"{np.max(np.abs(segment_data)):.5f}"))

    # --- Perform transcription ---
    text_raw = transcribe_audio_chunk(
        segment_data,
        processing_mode,
        gui_q,
        lang=language,
        openai_model=DEFAULT_OPENAI_MODEL,
        el_model_id=elevenlabs_model_id,
        api_prompt=api_prompt
    )

    # Check for API errors related to short audio
    if text_raw and "audio_too_short" in text_raw:
        logger.warning(tr("log_ap_vad_segment_too_short_api",
                    segment_id=segment_id))
        return None

    # Check for any other errors
    if text_raw and (text_raw.startswith("[Error") or text_raw.startswith("[OpenAI-API-Error") or text_raw.startswith("[ElevenLabs-API-Error")):
        logger.error(tr("log_ap_vad_segment_api_error",
                    segment_id=segment_id,
                    error=text_raw))
        return None  # Return None on error

    # --- Post-processing ---
    # Ensure text_raw is not None before processing
    text_replaced = apply_replacements(text_raw or "", loaded_replacements)
    text_filtered = filter_transcription(text_replaced, filter_patterns, filter_parentheses)

    # Skip empty results
    if not text_filtered or text_filtered.isspace():
        logger.warning(tr("log_ap_vad_segment_empty_result", segment_id=segment_id))
        return None

    # Log success with details
    logger.info(tr("log_ap_vad_segment_result",
            segment_id=segment_id,
            text=f"{text_filtered[:100]}..." if len(text_filtered) > 100 else text_filtered))

    return text_filtered


def process_and_output_vad_buffer(
    vad_segment_buffer_list,
    segment_counter_ref,
    processing_mode,
    gui_q, output_file, file_format,
    send_to_streamerbot_flag, streamerbot_queue, stt_prefix,
    **kwargs
):
    """
    Concatenates buffered VAD segments, processes them, and handles output.
    Resets the buffer list after processing.
    """
    if not vad_segment_buffer_list:
        return

    # Combine buffered segments
    try:
        combined_audio = np.concatenate(vad_segment_buffer_list)
    except ValueError:
        logger.error("Error concatenating VAD buffer segments - buffer likely empty or corrupted.")
        vad_segment_buffer_list.clear()  # Clear the potentially problematic buffer
        return

    segment_counter_ref[0] += 1
    current_segment_id = segment_counter_ref[0]

    # Process the combined segment
    text_filtered = process_vad_segment(
        combined_audio,
        processing_mode,
        gui_q,
        current_segment_id,
        language=kwargs.get('language'),
        openai_model=kwargs.get('openai_model', DEFAULT_OPENAI_MODEL),
        elevenlabs_model_id=kwargs.get('elevenlabs_model_id'),
        api_prompt=kwargs.get('api_prompt'),
        loaded_replacements=kwargs.get('loaded_replacements', {}),
        filter_patterns=kwargs.get('filter_patterns', []),
        filter_parentheses=kwargs.get('filter_parentheses', False)
    )

    # --- Output handling ---
    if text_filtered:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        gui_q.put(("transcription", f"{timestamp} - {text_filtered}"))

        # File output
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
                logger.error(tr("log_ap_file_write_error", filename=output_file, error=e_io))
                gui_q.put(("error", tr("log_ap_file_write_error", filename=os.path.basename(output_file), error=e_io)))
            except Exception as e_file:
                logger.exception(tr("log_ap_file_unexpected_error", filename=output_file))
                gui_q.put(("error", tr("log_ap_file_unexpected_error", filename=os.path.basename(output_file), error=e_file)))

        # Streamer bot integration
        if send_to_streamerbot_flag:
            try:
                payload = {"source": "stt", "text": stt_prefix + text_filtered}
                import json
                payload_json = json.dumps(payload)
                streamerbot_queue.put(payload_json)
                logger.debug(tr("log_ap_sb_message_sent", message=f"{payload_json[:100]}..." if len(payload_json) > 100 else payload_json))
            except queue.Full:
                logger.warning(tr("log_ap_sb_queue_full"))
                gui_q.put(("warning", tr("status_ap_sb_queue_full")))
            except Exception as e_q:
                logger.error(tr("log_ap_sb_queue_error", error=e_q))
                gui_q.put(("warning", tr("status_ap_sb_queue_error", error=e_q)))

    # --- IMPORTANT: Clear the buffer after processing ---
    vad_segment_buffer_list.clear()


def recording_worker(**kwargs):
    """
    Worker thread that handles audio recording, buffering, silence detection (or VAD), and transcription.
    Takes all required parameters as keyword arguments.
    ENHANCED: Implements improved VAD segment buffering with linguistic context preservation.
    """
    # --- Unpack arguments ---
    processing_mode = kwargs['processing_mode']
    openai_api_key = kwargs['openai_api_key']
    elevenlabs_api_key = kwargs['elevenlabs_api_key']
    device_id = kwargs['device_id']
    samplerate = kwargs['samplerate']
    channels = kwargs['channels']
    model_name = kwargs['model_name']
    openai_model_selected = kwargs['openai_model_selected'] 
    language = kwargs['language']
    output_file = kwargs['output_file']
    file_format = kwargs['file_format']
    energy_threshold = kwargs['energy_threshold']
    min_buffer_sec = kwargs['min_buffer_sec']
    silence_sec = kwargs['silence_sec']
    elevenlabs_model_id = kwargs['elevenlabs_model_id']
    filter_parentheses = kwargs['filter_parentheses']
    send_to_streamerbot_flag = kwargs['send_to_streamerbot_flag']
    stt_prefix = kwargs['stt_prefix']
    audio_q = kwargs['audio_q']
    gui_q = kwargs['gui_q']
    streamerbot_queue = kwargs['streamerbot_queue']
    stop_recording_flag = kwargs['stop_recording_flag']
    loaded_replacements = kwargs['loaded_replacements']
    filter_patterns = kwargs['filter_patterns']
    openai_model_to_use = None
    if processing_mode == "openai":
        openai_model_to_use = openai_model_selected
    # --- VAD Parameters ---
    use_vad = kwargs.get('use_vad', False)
    vad_threshold = kwargs.get('vad_threshold', 0.5)  # Default threshold
    vad_min_speech_ms = kwargs.get('vad_min_speech_ms', 200)  # Keep default

    # Check if Sounddevice is available
    if not sd or not sf:
        logger.critical(tr("log_ap_libs_missing"))
        gui_q.put(("error", tr("status_ap_libs_missing")))
        stop_recording_flag.set()
        gui_q.put(("finished", None))
        return

    # --- Initialization ---
    logger.info(tr("log_ap_worker_start", mode=processing_mode, device=device_id, model=model_name or elevenlabs_model_id))
    if not initialize_stt_client(processing_mode, gui_q,
                                api_key=openai_api_key if processing_mode == "openai" else elevenlabs_api_key,
                                model_name=model_name if processing_mode == "local" else None):
        logger.error(tr("log_ap_client_init_failed"))
        stop_recording_flag.set()
        gui_q.put(("finished", None))
        return

    # --- VAD Initialization with Enhanced Parameters ---
    vad_processor = None
    if use_vad:
        if not HAS_VAD_PROCESSOR or VadProcessor is None:
            logger.error(tr("log_ap_vad_error_processor_unavailable"))
            gui_q.put(("error", tr("status_ap_vad_error_processor_unavailable")))
            use_vad = False
            logger.warning(tr("log_ap_vad_fallback_to_traditional"))
            gui_q.put(("status", tr("status_ap_vad_fallback_to_traditional")))
        else:
            try:
                # Set a more balanced initial silence duration (2000ms)
                # Higher than default but not too high to maximize ElevenLabs API accuracy
                vad_processor = VadProcessor(
                    threshold=vad_threshold,
                    min_silence_duration_ms=2000,  # 2 seconds - better balance for ElevenLabs
                    min_speech_duration_ms=vad_min_speech_ms,
                    sample_rate=samplerate,
                    enable_adaptive_threshold=True,
                    add_padding=True,
                    padding_ms=300,  # More padding helps with context
                    debug_mode=False
                )
                logger.info(tr("log_vad_initialized_with_config",
                        threshold=vad_threshold,
                        silence=2000,  # Use actual value for clarity
                        speech=vad_min_speech_ms))
                gui_q.put(("status", tr("status_vad_mode_active")))
            except Exception as e:
                logger.error(tr("log_ap_vad_init_error", error=e))
                gui_q.put(("error", tr("status_ap_vad_init_error", error=e)))
                use_vad = False
                logger.warning(tr("log_ap_vad_fallback_to_traditional"))
                gui_q.put(("status", tr("status_ap_vad_fallback_to_traditional")))

    # --- State variables ---
    # Legacy state variables (used only if use_vad is False)
    audio_buffer = np.array([], dtype=np.float32)
    min_buffer_samples = int(min_buffer_sec * samplerate)
    silence_samples = int(silence_sec * samplerate)
    last_sound_time = time.time()
    is_silent = True
    samples_since_last_sound = 0

    # Enhanced VAD path state variables (used only if use_vad is True)
    vad_segment_buffer_list = []  # List to hold numpy arrays of VAD segments
    vad_buffer_duration_samples = 0  # Track total samples in buffer
    last_vad_segment_time = None  # Timestamp of last segment
    last_speech_end_time = None  # Track when speech ends for intelligent merging
    vad_error_count = 0
    speech_in_progress = False  # Track if we're currently in a speech segment

    # --- Enhanced VAD Buffering Parameters ---
    MIN_TRANSCRIPTION_DURATION_SEC = 2.5  # Minimum combined audio to transcribe (reduced slightly)
    MAX_BUFFER_DURATION_SEC = 4.5  # Force transcription at this duration
    BUFFER_TIMEOUT_SEC = 2.0  # Force transcription if no segment for this long
    SPEECH_CONTINUATION_THRESHOLD_SEC = 1.5  # Continue same speech segment if pause is shorter
    INTER_SEGMENT_GROUPING_THRESHOLD_SEC = 1.0  # Group segments that occur close together
    MAX_SILENCE_ACCUMULATION_SEC = 2.0  # Maximum silence to accumulate between words

    # Segment counter (needs to be mutable to be updated by helper function)
    segment_counter_ref = [0]

    # --- OpenAI Specific prompt ---
    api_prompt = None
    if processing_mode == "openai" and language:
        lang_map = {"de": "Deutsch", "en": "English", "fr": "French", "es": "Spanish"}
        lang_name = lang_map.get(language.lower(), language)
        api_prompt = f"The following transcription is in {lang_name}."
        logger.info(tr("log_ap_using_openai_prompt", prompt=api_prompt))

    # --- Audio Stream ---
    stream = None
    try:
        gui_q.put(("status", tr("log_ap_open_audio_stream", device_id=device_id)))
        stream = sd.InputStream(
            samplerate=samplerate,
            device=device_id,
            channels=channels,
            callback=lambda indata, frames, time_info, status: audio_callback(indata, frames, time_info, status, audio_q),
            dtype='float32',
            blocksize=int(samplerate * 0.1)
        )
        logger.info(tr("log_ap_audio_stream_configured", rate=samplerate, channels=channels, blocksize=stream.blocksize))

        with stream:
            gui_q.put(("status", tr("log_ap_recording_running", mode=processing_mode.upper())))
            logger.info(tr("log_ap_audio_stream_started"))

            # --- Main recording loop ---
            while not stop_recording_flag.is_set():
                try:
                    audio_chunk = audio_q.get(timeout=0.1)

                    # ==================================================
                    # === Enhanced VAD Processing Path ===
                    # ==================================================
                    if use_vad and vad_processor:
                        # Process chunk through VAD
                        status, segment_data = vad_processor.process_chunk(audio_chunk.flatten())

                        # Handle VAD errors
                        if status == 'ERROR':
                            logger.error(tr("log_ap_vad_chunk_error"))
                            vad_error_count += 1
                            if vad_error_count >= 5:  # Fallback if too many errors
                                logger.warning(tr("log_ap_vad_too_many_errors"))
                                gui_q.put(("warning", tr("status_ap_vad_too_many_errors")))
                                use_vad = False  # Switch to legacy
                                # Initialize legacy variables
                                audio_buffer = np.array([], dtype=np.float32)
                                last_sound_time = time.time()
                                is_silent = True
                                samples_since_last_sound = 0
                                logger.info(tr("log_ap_switched_to_traditional"))
                                gui_q.put(("status", tr("status_traditional_mode_active")))
                            continue

                        current_time = time.time()

                        # If VAD detected end of speech segment
                        if status == 'SPEECH_ENDED' and segment_data is not None:
                            speech_duration = len(segment_data) / samplerate
                            
                            # Skip extremely short segments that are likely noise
                            if speech_duration < 0.3:  # 300ms minimum for useful speech
                                logger.debug(f"Skipping very short segment ({speech_duration:.2f}s)")
                                continue
                                
                            # Log segment details
                            logger.debug(f"VAD segment ended. Length: {speech_duration:.2f}s")
                            
                            # Track when speech ended
                            last_speech_end_time = current_time
                            
                            # Calculate continuity with previous segment
                            is_continuation = False
                            if last_vad_segment_time and (current_time - last_vad_segment_time) < SPEECH_CONTINUATION_THRESHOLD_SEC:
                                is_continuation = True
                                logger.debug(f"Treating as continuation of previous speech (gap: {current_time - last_vad_segment_time:.2f}s)")
                            
                            # Add to buffer
                            vad_segment_buffer_list.append(segment_data)
                            vad_buffer_duration_samples += len(segment_data)
                            last_vad_segment_time = current_time
                            
                            # Update buffer duration
                            current_buffer_duration_sec = vad_buffer_duration_samples / samplerate
                            logger.debug(f"Buffer now contains {len(vad_segment_buffer_list)} segments, {current_buffer_duration_sec:.2f}s total")
                            
                            # DECISION LOGIC: When to process the buffer
                            should_process = False
                            process_reason = ""
                            
                            # 1. Process if max duration reached
                            if current_buffer_duration_sec >= MAX_BUFFER_DURATION_SEC:
                                should_process = True
                                process_reason = f"Max duration reached ({current_buffer_duration_sec:.2f}s)"
                            
                            # 2. Process if we have enough audio AND this isn't a continuation
                            elif current_buffer_duration_sec >= MIN_TRANSCRIPTION_DURATION_SEC and not is_continuation:
                                # Check if this segment is grouped with previous ones
                                if len(vad_segment_buffer_list) > 1:
                                    # Check average gap between segments
                                    should_process = True
                                    process_reason = f"Sufficient audio collected ({current_buffer_duration_sec:.2f}s) and logical break detected"
                                
                            if should_process:
                                logger.info(f"Processing VAD buffer: {process_reason}")
                                
                                # Process buffer (construct kwargs for helper)
                                vad_processing_kwargs = {
                                    'language': language, 
                                    'openai_model': openai_model_to_use, 
                                    'elevenlabs_model_id': elevenlabs_model_id,
                                    'api_prompt': api_prompt, 
                                    'loaded_replacements': loaded_replacements,
                                    'filter_patterns': filter_patterns, 
                                    'filter_parentheses': filter_parentheses
                                }
                                
                                process_and_output_vad_buffer(
                                    vad_segment_buffer_list, 
                                    segment_counter_ref,
                                    processing_mode, 
                                    gui_q, 
                                    output_file, 
                                    file_format,
                                    send_to_streamerbot_flag, 
                                    streamerbot_queue, 
                                    stt_prefix,
                                    **vad_processing_kwargs
                                )
                                
                                # Reset buffer
                                vad_segment_buffer_list = []
                                vad_buffer_duration_samples = 0
                                
                                # Don't reset last_vad_segment_time completely as we might need it for continuation logic
                                # but do track that we've processed
                                last_processed_time = current_time
                        
                        # Reset VAD error count if processing was successful
                        if status != 'ERROR':
                            vad_error_count = 0
                            
                    # ==================================================
                    # === Traditional RMS/Silence Path ===
                    # ==================================================
                    else:
                        # Add new chunk to main buffer
                        audio_buffer = np.concatenate((audio_buffer, audio_chunk.flatten()))

                        # --- Silence detection ---
                        rms = np.sqrt(np.mean(audio_chunk**2))
                        if rms > energy_threshold / 1000.0:
                            last_sound_time = time.time()
                            samples_since_last_sound = 0
                            if is_silent:
                                logger.debug(tr("log_ap_speech_detected"))
                                is_silent = False
                        else:
                            if not is_silent:
                                samples_since_last_sound += len(audio_chunk)
                                if samples_since_last_sound >= silence_samples:
                                    logger.debug(tr("log_ap_silence_detected", seconds=silence_sec))
                                    is_silent = True
                                    should_transcribe = True  # Trigger transcription on silence
                                else:
                                    should_transcribe = False
                            else:
                                should_transcribe = False

                        # --- Transcription triggers ---
                        buffer_duration_samples = len(audio_buffer)
                        # Trigger if buffer is long enough OR if silence was just detected
                        if not should_transcribe:
                            should_transcribe = buffer_duration_samples >= min_buffer_samples

                        # Don't transcribe very short silent buffers
                        if is_silent and buffer_duration_samples < int(0.5 * samplerate):
                            should_transcribe = False

                        # --- Process buffer ---
                        if should_transcribe and buffer_duration_samples > 0:
                            segment_counter_ref[0] += 1  # Use the mutable counter
                            current_segment_id = segment_counter_ref[0]
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
                                gui_q,
                                lang=language,
                                openai_model=openai_model_to_use,
                                el_model_id=elevenlabs_model_id,
                                api_prompt=api_prompt
                            )

                            # --- Post-processing ---
                            text_replaced = apply_replacements(text_raw or "", loaded_replacements)  # Handle None
                            text_filtered = filter_transcription(text_replaced, filter_patterns, filter_parentheses)

                            logger.info(tr("log_ap_segment_result",
                                        segment_id=current_segment_id,
                                        text=f"{text_filtered[:100]}..." if len(text_filtered) > 100 else text_filtered))

                            # --- Output ---
                            if text_filtered and not text_filtered.startswith("[Error") and not text_filtered.startswith("[OpenAI-API-Error") and not text_filtered.startswith("[ElevenLabs-API-Error"):
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
                                        logger.error(tr("log_ap_file_write_error", filename=output_file, error=e_io))
                                        gui_q.put(("error", tr("log_ap_file_write_error", filename=os.path.basename(output_file), error=e_io)))
                                    except Exception as e_file:
                                        logger.exception(tr("log_ap_file_unexpected_error", filename=output_file))
                                        gui_q.put(("error", tr("log_ap_file_unexpected_error", filename=os.path.basename(output_file), error=e_file)))
                                if send_to_streamerbot_flag:
                                    try:
                                        payload = {"source": "stt", "text": stt_prefix + text_filtered}
                                        import json
                                        payload_json = json.dumps(payload)
                                        streamerbot_queue.put(payload_json)
                                        logger.debug(tr("log_ap_sb_message_sent", message=f"{payload_json[:100]}..." if len(payload_json) > 100 else payload_json))
                                    except queue.Full:
                                        logger.warning(tr("log_ap_sb_queue_full"))
                                        gui_q.put(("warning", tr("status_ap_sb_queue_full")))
                                    except Exception as e_q:
                                        logger.error(tr("log_ap_sb_queue_error", error=e_q))
                                        gui_q.put(("warning", tr("status_ap_sb_queue_error", error=e_q)))

                    # Small pause to yield control
                    time.sleep(0.01)

                except queue.Empty:
                    # --- Timeout checks ---

                    # Enhanced VAD Timeout Check
                    if use_vad and vad_processor and vad_segment_buffer_list:
                        # Check if we have content and haven't received new segments for a while
                        if last_vad_segment_time and (time.time() - last_vad_segment_time) > BUFFER_TIMEOUT_SEC:
                            buffer_duration_sec = vad_buffer_duration_samples / samplerate
                            
                            # Only process if we have meaningful content
                            if buffer_duration_sec >= 0.5:  # At least half a second of speech
                                logger.info(f"Buffer timeout ({BUFFER_TIMEOUT_SEC:.1f}s) reached, processing buffered segments ({buffer_duration_sec:.2f}s)")
                                
                                # Process buffer with helper function
                                vad_processing_kwargs = {
                                    'language': language, 
                                    'openai_model': openai_model_to_use,
                                    'elevenlabs_model_id': elevenlabs_model_id,
                                    'api_prompt': api_prompt, 
                                    'loaded_replacements': loaded_replacements,
                                    'filter_patterns': filter_patterns, 
                                    'filter_parentheses': filter_parentheses
                                }
                                
                                process_and_output_vad_buffer(
                                    vad_segment_buffer_list, 
                                    segment_counter_ref,
                                    processing_mode, 
                                    gui_q, 
                                    output_file, 
                                    file_format,
                                    send_to_streamerbot_flag, 
                                    streamerbot_queue, 
                                    stt_prefix,
                                    **vad_processing_kwargs
                                )
                                
                                # Reset buffer state
                                vad_segment_buffer_list = []
                                vad_buffer_duration_samples = 0
                                last_vad_segment_time = None
                            else:
                                # Clear very short content without processing
                                logger.debug(f"Discarding short content on timeout ({buffer_duration_sec:.2f}s)")
                                vad_segment_buffer_list = []
                                vad_buffer_duration_samples = 0
                                last_vad_segment_time = None

                    # Traditional Mode Timeout Check
                    elif not use_vad:
                        if not is_silent and (time.time() - last_sound_time) > silence_sec:
                            logger.debug(tr("log_ap_silence_detected", seconds=silence_sec))
                            is_silent = True
                            # Process any remaining buffer content in traditional mode
                            if len(audio_buffer) > int(0.5 * samplerate):  # Check buffer has meaningful audio
                                segment_counter_ref[0] += 1  # Use mutable counter
                                current_segment_id = segment_counter_ref[0]
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
                                    openai_model=openai_model_to_use,
                                    el_model_id=elevenlabs_model_id,
                                    api_prompt=api_prompt
                                )
                                text_replaced = apply_replacements(text_raw or "", loaded_replacements)  # Handle None
                                text_filtered = filter_transcription(text_replaced, filter_patterns, filter_parentheses)

                                logger.info(tr("log_ap_remainder_result",
                                            segment_id=current_segment_id,
                                            text=f"{text_filtered[:100]}..." if len(text_filtered) > 100 else text_filtered))

                                # --- Output (repeat logic) ---
                                if text_filtered and not text_filtered.startswith("[Error") and not text_filtered.startswith("[OpenAI-API-Error") and not text_filtered.startswith("[ElevenLabs-API-Error"):
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
                                            logger.debug(tr("log_ap_sb_message_sent_remainder", message=f"{payload_json[:100]}..." if len(payload_json) > 100 else payload_json))
                                        except queue.Full:
                                            logger.warning(tr("log_ap_sb_queue_full_remainder"))
                                            gui_q.put(("warning", tr("status_ap_sb_queue_full")))
                                        except Exception as e_q:
                                            logger.error(tr("log_ap_sb_queue_error_remainder", error=e_q))
                                            gui_q.put(("warning", tr("status_ap_sb_queue_error", error=e_q)))
                            else:
                                # If buffer is too short even after silence, just clear it
                                audio_buffer = np.array([], dtype=np.float32)
                                samples_since_last_sound = 0

                    continue  # Continue loop after handling empty queue

    except sd.PortAudioError as e:
        logger.exception(tr("log_ap_portaudio_stream_error"))
        gui_q.put(("status", tr("status_ap_portaudio_stream_error")))
        gui_q.put(("error", tr("log_ap_portaudio_error_details", error=e)))
        stop_recording_flag.set()
    except Exception as e:
        logger.exception(tr("log_ap_worker_unexpected_error"))
        gui_q.put(("status", tr("status_ap_worker_unexpected_error")))
        gui_q.put(("error", tr("status_ap_worker_unexpected_error_details", error=e)))
        stop_recording_flag.set()
    finally:
        # --- Cleanup ---
        logger.info(tr("log_ap_worker_ending"))

        # --- Process any remaining buffered VAD segments ---
        if use_vad and vad_processor and vad_segment_buffer_list:
            logger.info("Processing remaining VAD buffer on exit.")
            # Construct kwargs for helper
            vad_processing_kwargs = {
                'language': language, 
                'openai_model': openai_model_to_use, 
                'elevenlabs_model_id': elevenlabs_model_id,
                'api_prompt': api_prompt, 
                'loaded_replacements': loaded_replacements,
                'filter_patterns': filter_patterns, 
                'filter_parentheses': filter_parentheses
            }
            process_and_output_vad_buffer(
                vad_segment_buffer_list, 
                segment_counter_ref,
                processing_mode, 
                gui_q, 
                output_file, 
                file_format,
                send_to_streamerbot_flag, 
                streamerbot_queue, 
                stt_prefix,
                **vad_processing_kwargs
            )

        # --- Process any remaining legacy buffer ---
        elif not use_vad and len(audio_buffer) > int(0.2 * samplerate):  # Check buffer has *some* audio
            segment_counter_ref[0] += 1
            current_segment_id = segment_counter_ref[0]
            logger.info(f"Processing final legacy buffer remainder {current_segment_id} (Length: {len(audio_buffer)/samplerate:.2f}s)")
            text_raw = transcribe_audio_chunk(
                audio_buffer, 
                processing_mode, 
                gui_q, 
                lang=language,
                openai_model=openai_model_to_use, 
                el_model_id=elevenlabs_model_id, 
                api_prompt=api_prompt
            )
            text_replaced = apply_replacements(text_raw or "", loaded_replacements)  # Handle None
            text_filtered = filter_transcription(text_replaced, filter_patterns, filter_parentheses)
            if text_filtered and not text_filtered.startswith("[Error") and not text_filtered.startswith("[OpenAI-API-Error") and not text_filtered.startswith("[ElevenLabs-API-Error"):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                gui_q.put(("transcription", f"{timestamp} - {text_filtered}"))
                # --- Output (repeat logic for final legacy chunk) ---
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
                        logger.error(tr("log_ap_file_write_error_final", filename=output_file, error=e_io))
                        gui_q.put(("error", tr("log_ap_file_write_error_final", filename=os.path.basename(output_file), error=e_io)))
                    except Exception as e_file:
                        logger.exception(tr("log_ap_file_unexpected_error_final", filename=output_file))
                        gui_q.put(("error", tr("log_ap_file_unexpected_error_final", filename=os.path.basename(output_file), error=e_file)))
                if send_to_streamerbot_flag:
                    try:
                        payload = {"source": "stt", "text": stt_prefix + text_filtered}
                        import json
                        payload_json = json.dumps(payload)
                        streamerbot_queue.put(payload_json)
                        logger.debug(tr("log_ap_sb_message_sent_final", message=f"{payload_json[:100]}..." if len(payload_json) > 100 else payload_json))
                    except queue.Full:
                        logger.warning(tr("log_ap_sb_queue_full_final"))
                        gui_q.put(("warning", tr("status_ap_sb_queue_full")))
                    except Exception as e_q:
                        logger.error(tr("log_ap_sb_queue_error_final", error=e_q))
                        gui_q.put(("warning", tr("status_ap_sb_queue_error", error=e_q)))

        # --- Stop stream and cleanup queue ---
        if stream and stream.active:
            try:
                stream.stop()
                stream.close()
                logger.info(tr("log_ap_stream_stopped"))
            except Exception as e_close:
                logger.error(tr("log_ap_stream_close_error", error=e_close))

        while not audio_q.empty():
            try:
                audio_q.get_nowait()
            except queue.Empty:
                break
        logger.debug(tr("log_ap_audio_queue_cleared"))

        # Notify GUI
        gui_q.put(("finished", None))
        status_msg = tr("status_ap_recording_finished") if stop_recording_flag.is_set() else tr("status_ap_worker_unexpected_end")
        logger.info(tr("log_ap_worker_thread_ended", status=status_msg))
        
        