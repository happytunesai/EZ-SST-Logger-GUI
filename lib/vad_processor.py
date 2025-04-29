# lib/vad_processor.py

import numpy as np
from silero_vad_lite import SileroVAD
import collections
import logging
import time
import os
# Import the translation function
from lib.language_manager import tr
from lib.constants import (
    DEFAULT_VAD_THRESHOLD,
    DEFAULT_VAD_MIN_SILENCE_MS,
    DEFAULT_VAD_MIN_SPEECH_MS,
    DEFAULT_SAMPLERATE
)

logger = logging.getLogger(__name__)

class VadProcessor:
    """
    Handles voice activity detection using Silero VAD Lite for streaming audio data.
    Uses tr() for internationalized log messages.
    """
    def __init__(self,
                threshold: float = DEFAULT_VAD_THRESHOLD,
                min_silence_duration_ms: int = DEFAULT_VAD_MIN_SILENCE_MS,
                min_speech_duration_ms: int = DEFAULT_VAD_MIN_SPEECH_MS,
                sample_rate: int = DEFAULT_SAMPLERATE,
                enable_adaptive_threshold: bool = True,
                add_padding: bool = True,
                padding_ms: int = 200,
                debug_mode: bool = False):
        """
        Initializes the VAD processor.

        Args:
            threshold: Speech probability threshold (0.0 to 1.0).
            min_silence_duration_ms: Minimum silence duration (ms) after speech to trigger endpoint.
            min_speech_duration_ms: Minimum speech duration (ms) to trigger start of speech segment.
            sample_rate: Audio sample rate (only 8000 or 16000 supported by Silero VAD).
            enable_adaptive_threshold: Enable dynamic threshold adjustment.
            add_padding: Add silence padding to detected segments.
            padding_ms: Amount of padding in ms to add before/after speech.
            debug_mode: Enable detailed debug logging.
        """
        if sample_rate not in [8000, 16000]:
            raise ValueError(tr("error_vad_sample_rate", rate=sample_rate))

        self.threshold = threshold
        self.initial_threshold = threshold  # Store initial value for reference
        self.min_silence_duration_ms = min_silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.sample_rate = sample_rate
        
        # Enhanced features
        self.enable_adaptive_threshold = enable_adaptive_threshold
        self.add_padding = add_padding
        self.padding_ms = padding_ms
        self.debug_mode = debug_mode
        
        # Adaptive threshold parameters
        self.background_noise_level = None
        self.snr_history = collections.deque(maxlen=10)
        self.last_threshold_update = time.time()

        # Load the Silero VAD model
        try:
            self._vad_model = SileroVAD(sample_rate)
            logger.info(tr("log_vad_initialized"))
        except Exception as e:
            logger.error(tr("log_vad_init_failed", error=e))
            self._vad_model = None
            raise RuntimeError(tr("error_vad_init_failed_runtime", error=e)) from e

        # Calculate window size
        self._window_size_samples = 512 if sample_rate == 16000 else 256
        self._window_size_ms = (self._window_size_samples / sample_rate) * 1000

        # Calculate frame counts
        self._min_silence_frames = int(np.ceil(min_silence_duration_ms / self._window_size_ms))
        self._min_speech_frames = int(np.ceil(min_speech_duration_ms / self._window_size_ms))

        # State variables
        self._triggered = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._current_speech_segment = []
        self._internal_buffer = np.array([], dtype=np.float32)
        
        # Energy history for dynamic adjustments
        self._energy_history = collections.deque(maxlen=100)  # Last ~5 seconds at 20 frames/sec

        logger.debug(tr("log_vad_init_details",
                    sr=sample_rate,
                    chunk_size=self._window_size_samples,
                    threshold=threshold,
                    min_silence_frames=self._min_silence_frames,
                    min_speech_frames=self._min_speech_frames))

    def reset_state(self):
        """Resets the internal state of the VAD processor."""
        logger.debug(tr("log_vad_resetting"))
        self._triggered = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._current_speech_segment = []
        self._internal_buffer = np.array([], dtype=np.float32)

    def update_threshold(self, audio_window):
        """
        Dynamically adjust threshold based on signal-to-noise ratio
        and environment conditions.
        """
        if not self.enable_adaptive_threshold:
            return
            
        # Calculate energy of current window
        rms = np.sqrt(np.mean(audio_window**2))
        self._energy_history.append(rms)
        
        # Only update every ~2 seconds to avoid rapid fluctuations
        if time.time() - self.last_threshold_update < 2.0:
            return
            
        # Update background noise during likely silence periods
        # (when RMS is in the bottom 20% of recent history)
        if len(self._energy_history) > 10:
            sorted_energy = sorted(self._energy_history)
            noise_threshold = sorted_energy[int(len(sorted_energy) * 0.2)]
            
            if rms <= noise_threshold:
                if self.background_noise_level is None:
                    self.background_noise_level = rms
                else:
                    # Slowly adapt to environment (more weight to historical values)
                    self.background_noise_level = 0.95 * self.background_noise_level + 0.05 * rms
        
        # Calculate SNR and adjust threshold if we have background noise data
        if self.background_noise_level and self.background_noise_level > 0:
            if rms > 0:
                # Calculate signal-to-noise ratio in dB
                snr = 20 * np.log10(max(rms, 0.0000001) / max(self.background_noise_level, 0.0000001))
                self.snr_history.append(snr)
                
                if len(self.snr_history) >= 3:
                    avg_snr = sum(self.snr_history) / len(self.snr_history)
                    
                    # Adjust threshold based on SNR
                    old_threshold = self.threshold
                    
                    if avg_snr > 15:  # High SNR (clear voice)
                        # Can be more strict to reject noise
                        self.threshold = min(0.7, self.threshold + 0.02)
                    elif avg_snr < 5:  # Low SNR (noisy environment)
                        # Need to be more lenient to catch speech
                        self.threshold = max(0.3, self.threshold - 0.02)
                    else:
                        # Gradually return to initial settings in moderate conditions
                        if self.threshold < self.initial_threshold:
                            self.threshold = min(self.initial_threshold, self.threshold + 0.01)
                        elif self.threshold > self.initial_threshold:
                            self.threshold = max(self.initial_threshold, self.threshold - 0.01)
                    
                    # Log threshold change if significant
                    if abs(old_threshold - self.threshold) > 0.01:
                        logger.debug(tr("log_vad_threshold_adjusted", 
                                    old=f"{old_threshold:.2f}", 
                                    new=f"{self.threshold:.2f}", 
                                    snr=f"{avg_snr:.1f}"))
                        
                    self.last_threshold_update = time.time()

    def add_padding_to_segment(self, segment):
        """
        Add silence padding before and after speech segment 
        for better recognition and more natural boundaries.
        """
        if not self.add_padding:
            return segment
            
        padding_samples = int((self.padding_ms / 1000) * self.sample_rate)
        padding = np.zeros(padding_samples, dtype=np.float32)
        padded_segment = np.concatenate([padding, segment, padding])
        
        logger.debug(tr("log_vad_padding_added", 
                    original=f"{len(segment)/self.sample_rate:.2f}s", 
                    padded=f"{len(padded_segment)/self.sample_rate:.2f}s"))
                    
        return padded_segment

    def process_chunk(self, audio_chunk: np.ndarray):
        """
        Process an audio chunk for speech detection.
        
        Simplified version to avoid issues with duplicate segments.

        Args:
            audio_chunk: A numpy array containing the audio data (float32, mono).

        Returns:
            A tuple: (status: str, segment_data: np.ndarray | None)
            Possible statuses:
                'PROCESSING': Still processing, no complete segment yet.
                'SPEECH_ENDED': Detected end of speech, segment_data contains the utterance.
                'ERROR': VAD model not initialized or error occurred.
        """
        if not self._vad_model:
            logger.error(tr("log_vad_process_error_not_init"))
            return 'ERROR', None

        self._internal_buffer = np.concatenate((self._internal_buffer, audio_chunk))
        segment_to_return = None
        status = 'PROCESSING'

        # Main processing loop
        while len(self._internal_buffer) >= self._window_size_samples:
            window = self._internal_buffer[:self._window_size_samples]
            self._internal_buffer = self._internal_buffer[self._window_size_samples:]

            if window.dtype != np.float32:
                window = window.astype(np.float32)

            # Update threshold if adaptive mode is enabled
            self.update_threshold(window)

            try:
                speech_prob = self._vad_model.process(window)
            except Exception as e:
                logger.error(tr("log_vad_processing_error", error=e))
                continue  # Skip this chunk

            is_speech = speech_prob >= self.threshold

            if is_speech:
                self._silence_frames = 0
                if not self._triggered:
                    self._speech_frames += 1
                    if self._speech_frames >= self._min_speech_frames:
                        logger.debug(tr("log_vad_speech_started", 
                                    prob=f"{speech_prob:.2f}", 
                                    threshold=f"{self.threshold:.2f}"))
                        self._triggered = True
                        # Don't return 'SPEECH_STARTED' status to avoid duplicate processing
                        status = 'PROCESSING'
                        self._current_speech_segment = [window]
                else:
                    self._current_speech_segment.append(window)
            else:  # Not speech
                self._speech_frames = 0
                if self._triggered:
                    self._silence_frames += 1
                    # Still append a few silence frames within segment to capture trailing sounds
                    if self._silence_frames <= min(3, self._min_silence_frames // 2):
                        self._current_speech_segment.append(window)
                        
                    if self._silence_frames >= self._min_silence_frames:
                        logger.debug(tr("log_vad_speech_ended",
                                    silence_frames=self._silence_frames,
                                    min_silence=self._min_silence_frames))
                        
                        # Compile raw segment
                        raw_segment = np.concatenate(self._current_speech_segment)
                        
                        # Check if segment is long enough
                        segment_duration = len(raw_segment) / self.sample_rate
                        
                        # Skip very short segments
                        if segment_duration < 0.2:  # Less than 200ms is too short for useful transcription
                            logger.debug(f"Segment too short ({segment_duration:.3f}s), skipping")
                            self.reset_state()
                            status = 'PROCESSING'
                            continue
                            
                        # Add padding for better transcription
                        processed_segment = self.add_padding_to_segment(raw_segment)
                        
                        # Prepare to return segment
                        segment_to_return = processed_segment
                        self.reset_state()
                        status = 'SPEECH_ENDED'
                        break
                    
                else:
                    self._silence_frames += 1

        return status, segment_to_return


class SegmentBuffer:
    """
    Simple buffer for merging short speech segments.
    This version focuses on reliability over complexity.
    """
    
    def __init__(self, max_gap_sec=1.5, min_merged_duration_sec=0.5, sample_rate=16000):
        """
        Initialize the segment buffer.
        
        Args:
            max_gap_sec: Maximum time gap between segments to consider for merging (seconds)
            min_merged_duration_sec: Minimum duration required for processing a segment (seconds)
            sample_rate: Audio sample rate (Hz)
        """
        self.segments = []
        self.timestamps = []
        self.last_segment_time = None
        self.max_gap_sec = max_gap_sec
        self.min_merged_duration_sec = min_merged_duration_sec
        self.sample_rate = sample_rate
        
        # For tracking last processed segment to avoid duplicates
        self.last_processed_time = None
    
    def add_segment(self, segment_data):
        """
        Add a segment to the buffer, potentially triggering a merge.
        Simple version focused on reliability.
        
        Args:
            segment_data: Audio segment data (numpy array)
            
        Returns:
            (segment_to_process, should_process) - segment and boolean indicating if it should be processed.
        """
        current_time = time.time()
        
        # Skip processing if this segment comes too quickly after the last one
        # This helps avoid duplicate segments
        if self.last_processed_time and current_time - self.last_processed_time < 0.5:
            logger.debug("Skipping segment - too soon after previous one")
            return None, False
        
        # If segment is already long enough, process it directly
        segment_duration = len(segment_data) / self.sample_rate
        if segment_duration >= 1.0:  # 1 second or longer is substantial on its own
            logger.debug(f"Processing substantial segment: {segment_duration:.2f}s")
            self.last_processed_time = current_time
            return segment_data, True
        
        # Initialize if first segment
        if self.last_segment_time is None:
            self.segments = [segment_data]
            self.timestamps = [current_time]
            self.last_segment_time = current_time
            return None, False
        
        # Check if segment is within merge window of previous segment
        if current_time - self.last_segment_time < self.max_gap_sec:
            # Add to buffer
            self.segments.append(segment_data)
            self.timestamps.append(current_time)
            self.last_segment_time = current_time
            
            # Check combined duration
            total_samples = sum(len(s) for s in self.segments)
            total_duration = total_samples / self.sample_rate
            
            # If we have enough audio, merge and return
            if total_duration >= self.min_merged_duration_sec:
                merged_segment = np.concatenate(self.segments)
                logger.debug(f"Merged {len(self.segments)} segments: {total_duration:.2f}s")
                
                # Reset buffer
                self.segments = []
                self.timestamps = []
                self.last_segment_time = None
                self.last_processed_time = current_time
                
                return merged_segment, True
                
            # Not enough data yet
            return None, False
            
        else:
            # Too much time elapsed, process any pending segments
            if len(self.segments) > 0:
                # Check if we have multiple segments to merge
                if len(self.segments) > 1:
                    merged_segment = np.concatenate(self.segments)
                    total_duration = len(merged_segment) / self.sample_rate
                    
                    logger.debug(f"Merging {len(self.segments)} segments after timeout: {total_duration:.2f}s")
                    
                    # Reset buffer with new segment
                    self.segments = [segment_data]
                    self.timestamps = [current_time]
                    self.last_segment_time = current_time
                    self.last_processed_time = current_time
                    
                    # Only process if long enough
                    if total_duration >= self.min_merged_duration_sec:
                        return merged_segment, True
                    
                    # Otherwise discard (too short and too old)
                    return None, False
                    
                else:
                    # Just one segment in buffer
                    existing_segment = self.segments[0]
                    existing_duration = len(existing_segment) / self.sample_rate
                    
                    # Reset buffer with new segment
                    self.segments = [segment_data]
                    self.timestamps = [current_time]
                    self.last_segment_time = current_time
                    
                    # Only process if long enough
                    if existing_duration >= self.min_merged_duration_sec:
                        self.last_processed_time = current_time
                        return existing_segment, True
                    
                    # Otherwise discard (too short and too old)
                    logger.debug(f"Discarded segment (too short): {existing_duration:.2f}s")
                    return None, False
            else:
                # No pending segments
                self.segments = [segment_data]
                self.timestamps = [current_time]
                self.last_segment_time = current_time
                return None, False
    
    def flush(self):
        """
        Flush any pending segments in the buffer.
        
        Returns:
            (segment_to_process, should_process) - segment and boolean indicating if it should be processed.
        """
        if not self.segments:
            return None, False
            
        current_time = time.time()
        
        if len(self.segments) > 1:
            merged_segment = np.concatenate(self.segments)
            total_duration = len(merged_segment) / self.sample_rate
            
            logger.debug(f"Flushing {len(self.segments)} segments: {total_duration:.2f}s")
            
            # Reset buffer
            self.segments = []
            self.timestamps = []
            self.last_segment_time = None
            self.last_processed_time = current_time
            
            # Only process if long enough
            if total_duration >= self.min_merged_duration_sec:
                return merged_segment, True
        
        elif len(self.segments) == 1:
            segment = self.segments[0]
            duration = len(segment) / self.sample_rate
            
            # Reset buffer
            self.segments = []
            self.timestamps = []
            self.last_segment_time = None
            self.last_processed_time = current_time
            
            # Only process if long enough
            if duration >= self.min_merged_duration_sec:
                return segment, True
        
        # Nothing to process
        return None, False