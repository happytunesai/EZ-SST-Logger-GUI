# -*- coding: utf-8 -*-
"""
Utility functions for encryption and audio device detection.
"""
import os
import sys
import queue
import logging
import shutil
import platform
import webbrowser

# Import required libraries with fallback
try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    print("CRITICAL ERROR: 'cryptography' not found. Please install: pip install cryptography")
    Fernet = None
    InvalidToken = None

try:
    import sounddevice as sd
except ImportError:
    print("CRITICAL ERROR: 'sounddevice' not found. Please install: pip install sounddevice")
    sd = None

# Import logger 
try:
    from lib.logger_setup import logger
except ImportError:
    import logging
    logger = logging.getLogger("FallbackUtilsLogger")

# Helper function for translation that avoids circular imports
def tr(key, **kwargs):
    """
    Translation function wrapper to avoid circular imports.
    This function will try to use the tr function from language_manager
    but falls back to a simple implementation if that's not available.
    """
    try:
        # Only import tr when needed to avoid circular imports
        from lib.language_manager import tr as lang_tr
        return lang_tr(key, **kwargs)
    except ImportError:
        # Simple fallback implementation
        return key.format(**kwargs) if kwargs else key

# --- PyInstaller Base Path ---
def get_base_path():
    """ 
    Determines the base path for resources.
    Works in both PyInstaller bundled and regular Python environments.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
        logger.debug(f"Running in PyInstaller bundle, base path: {base_path}")
    else:
        try:
            # First try to get path from the main script
            base_path = os.path.abspath(os.path.dirname(sys.modules['__main__'].__file__))
            logger.debug(f"Running from source (main script), base path: {base_path}")
        except:
            # Fallback to this file's directory
            base_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
            logger.debug(f"Running from source (fallback path), base path: {base_path}")
    return base_path

# --- PyInstaller Persistent Base Path ---
def get_persistent_data_path():
    """Returns the directory in which persistent user data is to be saved."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Runs as a packed executable: Use the directory of the exe file
        exe_dir = os.path.dirname(sys.executable)
        logger.debug(f"Path for persistent data (frozen): {exe_dir}")
        return exe_dir
    else:
        # Runs from the source code: Use the project root from get_base_path()
        source_dir = get_base_path() # Use the existing function for the source code case
        logger.debug(f"Path for persistent data (source): {source_dir}")
        return source_dir

# --- Encryption ---
def load_or_generate_key(key_path, gui_q=None):
    """
    Loads an encryption key from a file or generates a new one.
    Optionally sends error messages to a GUI queue.
    """
    if not Fernet:
        logger.critical(tr("log_utils_crypto_missing"))
        if gui_q:
            gui_q.put(("error", tr("log_utils_crypto_missing_short")))
        return None

    # Convert to absolute path if needed
    absolute_key_path = key_path
    if not os.path.isabs(key_path):
        absolute_key_path = os.path.join(get_base_path(), key_path)
        logger.debug(f"Using absolute key path: {absolute_key_path}")

    if os.path.exists(absolute_key_path):
        try:
            with open(absolute_key_path, 'rb') as f:
                key = f.read()
            if len(key) == 44 and b'=' in key:
                logger.info(tr("log_utils_key_loaded", path=absolute_key_path))
                return key
            else:
                logger.warning(tr("log_utils_key_invalid", path=absolute_key_path))
        except Exception as e:
            logger.warning(tr("log_utils_key_read_error", path=absolute_key_path, error=str(e)))

    logger.info(tr("log_utils_key_generating"))
    key = Fernet.generate_key()
    
    # Ensure directory exists
    key_dir = os.path.dirname(absolute_key_path)
    if key_dir and not os.path.exists(key_dir):
        try:
            os.makedirs(key_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create directory for key file: {e}")
            if gui_q:
                gui_q.put(("error", f"Failed to create key directory: {e}"))
            return key  # Still return the key even if we can't save it

    try:
        with open(absolute_key_path, 'wb') as f:
            f.write(key)
        logger.info(tr("log_utils_key_saved", path=absolute_key_path))
        print("\n" + "=" * 60)
        print(tr("log_utils_key_important_notice", path=absolute_key_path))
        print("=" * 60 + "\n")
    except IOError as e:
        logger.error(tr("log_utils_key_write_error", path=absolute_key_path, error=str(e)))
        if gui_q:
            gui_q.put(("error", tr("log_utils_key_write_error_short", error=str(e))))
    return key

def encrypt_data(data_bytes, key):
    """Encrypts data using the provided Fernet key."""
    if not Fernet:
        logger.error(tr("log_utils_encrypt_failed_crypto"))
        return None
    if not key or not data_bytes:
        logger.debug(tr("log_utils_encrypt_skipped"))
        return None
    try:
        f = Fernet(key)
        return f.encrypt(data_bytes)
    except Exception as e:
        logger.error(tr("log_utils_encrypt_error", error=str(e)))
        return None

def decrypt_data(encrypted_bytes, key):
    """Decrypts data using the provided Fernet key."""
    if not Fernet:
        logger.error(tr("log_utils_decrypt_failed_crypto"))
        return None
    if not key or not encrypted_bytes:
        logger.debug(tr("log_utils_decrypt_skipped"))
        return None
    try:
        f = Fernet(key)
        return f.decrypt(encrypted_bytes)
    except InvalidToken:
        logger.error(tr("log_utils_decrypt_invalid_token"))
        return None
    except Exception as e:
        logger.error(tr("log_utils_decrypt_error", error=str(e)))
        return None

# --- Audio Devices ---
def list_audio_devices_for_gui(gui_q=None):
    """
    Returns a dictionary of available audio input devices.
    Optionally sends status/errors to a GUI queue.
    """
    if not sd:
        logger.critical(tr("log_utils_sounddevice_missing"))
        if gui_q:
            gui_q.put(("status", tr("status_error_sounddevice_missing")))
            gui_q.put(("error", tr("status_error_ws_lib_missing")))
        return {}

    logger.info(tr("log_utils_searching_devices"))
    input_devices_dict = {}
    default_device_index = -1

    try:
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()
    except Exception as e:
        logger.exception(tr("log_utils_audio_query_failed"))
        if gui_q:
            gui_q.put(("status", tr("status_error_audio_query")))
            gui_q.put(("error", tr("log_utils_audio_query_error", error=str(e))))
        return {}

    try:
        default_input_device_info = sd.query_devices(kind='input')
        if default_input_device_info and isinstance(default_input_device_info, dict):
            full_devices_list = sd.query_devices()
            for i, dev in enumerate(full_devices_list):
                if dev['name'] == default_input_device_info['name'] and \
                    dev['hostapi'] == default_input_device_info['hostapi'] and \
                    dev['max_input_channels'] > 0:
                    default_device_index = i
                    logger.debug(tr("log_utils_default_device_found", index=i, name=dev['name']))
                    break
        else:
            logger.info(tr("log_utils_no_default_device"))
    except Exception as e:
        logger.warning(tr("log_utils_default_device_error", error=str(e)))

    logger.debug(tr("log_utils_device_count", count=len(devices)))
    found_input_count = 0
    for i, device in enumerate(devices):
        is_input = device.get('max_input_channels', 0) > 0
        host_api_ok = True

        try:
            hostapi_index = device.get('hostapi', -1)
            if hostapi_index != -1 and hostapi_index < len(host_apis):
                hostapi_name = host_apis[hostapi_index]['name']
                if sys.platform == 'win32' and 'MME' in hostapi_name:
                    logger.debug(tr("log_utils_skipping_mme", index=i, name=device['name']))
                    host_api_ok = False
            else:
                logger.debug(tr("log_utils_invalid_hostapi_info", index=i, name=device['name']))
        except Exception as e_hostapi:
            logger.warning(tr("log_utils_hostapi_check_failed", index=i, error=str(e_hostapi)))

        if is_input and host_api_ok:
            found_input_count += 1
            device_name = f"ID {i}: {device['name']}"
            if i == default_device_index:
                device_name += " (Default)"
            input_devices_dict[device_name] = i
            logger.debug(tr("log_utils_valid_device", name=device_name))
        elif is_input:
            logger.debug(tr("log_utils_skipped_device", index=i, name=device['name']))

    logger.info(tr("log_utils_valid_input_count", count=found_input_count))
    if not input_devices_dict:
        logger.error(tr("log_utils_no_input_devices"))
        if gui_q:
            gui_q.put(("status", tr("status_mics_none")))
            gui_q.put(("error", tr("status_error_mic_select_fail")))

    return input_devices_dict

# --- FFMPEG  Update Checker ---
def check_ffmpeg_path():
    """
    Checks if the ffmpeg executable is available in the system's PATH.

    Returns:
        str or None: The path to the ffmpeg executable if found, otherwise None.
    """
    ffmpeg_executable = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    ffmpeg_path = shutil.which(ffmpeg_executable)
    if ffmpeg_path:
        logger.info(tr("log_utils_ffmpeg_found", path=ffmpeg_path)) # Add new translation key
        return ffmpeg_path
    else:
        logger.warning(tr("log_utils_ffmpeg_not_found")) # Add new translation key
        return None


def _open_link(url):
    """Opens the given URL in the default web browser."""
    try:
        webbrowser.open_new_tab(url)
        logger.info(tr("log_info_link_opened", url=url)) # Keep original key or rename
    except Exception as e:
        logger.error(tr("log_info_link_open_error", url=url, error=e)) # Keep original key or rename
        # Consider if messagebox is appropriate here or just log
        # messagebox.showerror(tr("error_title"), tr("error_opening_link", url=url, error=str(e)))