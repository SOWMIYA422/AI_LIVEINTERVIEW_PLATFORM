# backend/live_transcriber.py - REAL-TIME VOICE-TO-TEXT WITH VOSK
import json
import logging
import queue
import threading
import time
from typing import Optional
import wave
import io
import base64
import numpy as np
import os
from vosk import Model, KaldiRecognizer
from config import VOSK_MODEL_PATH, SAMPLE_RATE

logger = logging.getLogger(__name__)


class LiveTranscriber:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.model = None
        self.recognizer = None
        self.is_listening = False
        self.audio_queue = queue.Queue()
        self.transcription_queue = queue.Queue()
        self.last_transcription = ""
        self.processing_thread = None

        # Initialize VOSK model
        self._initialize_vosk()

        logger.info(f"LiveTranscriber initialized for session: {session_id}")

    def _initialize_vosk(self):
        """Initialize VOSK model for speech recognition"""
        try:
            if not VOSK_MODEL_PATH or not os.path.exists(VOSK_MODEL_PATH):
                logger.error(f"VOSK model path not found: {VOSK_MODEL_PATH}")
                raise FileNotFoundError(f"VOSK model not found at {VOSK_MODEL_PATH}")

            logger.info(f"Loading VOSK model from: {VOSK_MODEL_PATH}")
            self.model = Model(VOSK_MODEL_PATH)
            self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
            self.recognizer.SetWords(True)
            logger.info("VOSK model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize VOSK model: {e}")
            raise

    def start_listening(self):
        """Start listening for audio chunks"""
        if self.is_listening:
            return

        self.is_listening = True
        self.processing_thread = threading.Thread(target=self._process_audio_queue)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("Live transcription started")

    def stop_listening(self):
        """Stop listening"""
        self.is_listening = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2)
        logger.info("Live transcription stopped")

    def add_audio_chunk(self, audio_data: bytes, is_base64: bool = True):
        """Add audio chunk for processing"""
        try:
            if not audio_data:
                return

            # Decode base64 if needed
            if is_base64:
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = audio_data

            # Ensure it's in correct format (16-bit PCM, mono, 16kHz)
            if len(audio_bytes) > 0:
                self.audio_queue.put(audio_bytes)

        except Exception as e:
            logger.error(f"Error adding audio chunk: {e}")

    def _process_audio_queue(self):
        """Process audio queue in background thread"""
        while self.is_listening:
            try:
                # Get audio chunk from queue
                audio_chunk = self.audio_queue.get(timeout=1)

                if audio_chunk and self.recognizer:
                    # Process with VOSK
                    if self.recognizer.AcceptWaveform(audio_chunk):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()
                        if text and text != self.last_transcription:
                            self.last_transcription = text
                            self.transcription_queue.put(
                                {
                                    "type": "final",
                                    "text": text,
                                    "timestamp": time.time(),
                                }
                            )
                            logger.info(f"Final transcription: {text}")
                    else:
                        # Partial result
                        partial_result = json.loads(self.recognizer.PartialResult())
                        partial_text = partial_result.get("partial", "").strip()
                        if partial_text:
                            self.transcription_queue.put(
                                {
                                    "type": "partial",
                                    "text": partial_text,
                                    "timestamp": time.time(),
                                }
                            )

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio chunk: {e}")

    def get_transcription(self, timeout: float = 1.0) -> Optional[dict]:
        """Get latest transcription from queue"""
        try:
            return self.transcription_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def transcribe_full_audio(self, audio_base64: str) -> str:
        """Transcribe complete audio file"""
        try:
            # Decode base64
            audio_bytes = base64.b64decode(audio_base64)

            # Reset recognizer for fresh transcription
            self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
            self.recognizer.SetWords(True)

            # Process in chunks
            chunk_size = 4000  # Process in 0.25 second chunks
            full_text = []

            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i : i + chunk_size]
                if self.recognizer.AcceptWaveform(chunk):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        full_text.append(text)

            # Get final result
            final_result = json.loads(self.recognizer.FinalResult())
            final_text = final_result.get("text", "").strip()
            if final_text:
                full_text.append(final_text)

            return " ".join(full_text) if full_text else ""

        except Exception as e:
            logger.error(f"Error in full audio transcription: {e}")
            return ""

    def cleanup(self):
        """Cleanup resources"""
        self.stop_listening()
        logger.info("LiveTranscriber cleanup completed")


# Global transcriber manager
class TranscriptionManager:
    _instance = None
    _transcribers = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_transcriber(self, session_id: str) -> LiveTranscriber:
        """Get or create transcriber for session"""
        if session_id not in self._transcribers:
            self._transcribers[session_id] = LiveTranscriber(session_id)
            self._transcribers[session_id].start_listening()
        return self._transcribers[session_id]

    def remove_transcriber(self, session_id: str):
        """Remove transcriber for session"""
        if session_id in self._transcribers:
            self._transcribers[session_id].cleanup()
            del self._transcribers[session_id]

    def cleanup_all(self):
        """Cleanup all transcribers"""
        for session_id in list(self._transcribers.keys()):
            self.remove_transcriber(session_id)
