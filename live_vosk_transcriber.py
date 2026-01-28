# backend/live_vosk_transcriber.py
import json
import logging
import threading
import queue
import time
import wave
import io
import numpy as np
from vosk import Model, KaldiRecognizer
from typing import Optional, Callable
import base64

logger = logging.getLogger(__name__)


class LiveVoskTranscriber:
    def __init__(self, model_path: str):
        """Initialize live Vosk transcriber"""
        self.model_path = model_path
        self.model = None
        self.recognizer = None
        self.is_listening = False
        self.transcription_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self.partial_results = []
        self.final_results = []
        self.callback = None

        # Initialize model in a thread
        self.init_thread = threading.Thread(target=self._initialize_model)
        self.init_thread.daemon = True
        self.init_thread.start()

        # Processing thread
        self.processing_thread = threading.Thread(target=self._process_audio_queue)
        self.processing_thread.daemon = True
        self.processing_thread.start()

    def _initialize_model(self):
        """Initialize Vosk model"""
        try:
            logger.info(f"Loading Vosk model from: {self.model_path}")
            self.model = Model(self.model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.recognizer.SetWords(True)
            logger.info("✅ Vosk model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load Vosk model: {e}")
            self.model = None

    def is_ready(self):
        """Check if model is ready"""
        return self.model is not None and self.recognizer is not None

    def start_listening(self):
        """Start listening for transcription"""
        if self.is_ready():
            self.is_listening = True
            logger.info("🎤 Live transcription started")
        else:
            logger.error("❌ Cannot start listening: Model not ready")

    def stop_listening(self):
        """Stop listening"""
        self.is_listening = False
        logger.info("⏹️ Live transcription stopped")

    def add_audio_chunk(self, audio_base64: str):
        """Add audio chunk for processing"""
        if not self.is_listening or not self.is_ready():
            return

        try:
            # Decode base64 to bytes
            audio_bytes = base64.b64decode(audio_base64)

            # Convert to raw PCM if needed
            # Try to detect if it's WAV/WebM and extract raw audio
            processed_audio = self._process_audio_bytes(audio_bytes)

            if processed_audio:
                self.audio_queue.put(processed_audio)

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")

    def _process_audio_bytes(self, audio_bytes: bytes) -> Optional[bytes]:
        """Process audio bytes to raw PCM format"""
        try:
            # Check if it's WAV format (has RIFF header)
            if audio_bytes[:4] == b"RIFF":
                try:
                    with io.BytesIO(audio_bytes) as wav_io:
                        with wave.open(wav_io, "rb") as wav_file:
                            # Extract raw PCM data
                            frames = wav_file.readframes(wav_file.getnframes())
                            return frames
                except:
                    # If not valid WAV, assume it's already raw PCM
                    return audio_bytes

            # Check if it's WebM/Opus - for now, assume raw PCM
            # In production, you'd use pydub to convert
            return audio_bytes

        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return None

    def _process_audio_queue(self):
        """Process audio queue in background thread"""
        while True:
            try:
                if not self.is_listening or not self.is_ready():
                    time.sleep(0.1)
                    continue

                # Get audio chunk from queue (non-blocking)
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if audio_chunk:
                    # Process with Vosk
                    if self.recognizer.AcceptWaveform(audio_chunk):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            self.final_results.append(text)
                            logger.info(f"✅ Vosk Final: {text}")
                            if self.callback:
                                self.callback(text, is_final=True)

                    else:
                        # Partial result
                        partial = json.loads(self.recognizer.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            self.partial_results.append(partial_text)
                            if self.callback:
                                self.callback(partial_text, is_final=False)

            except Exception as e:
                logger.error(f"Audio processing thread error: {e}")
                time.sleep(0.1)

    def set_callback(self, callback: Callable[[str, bool], None]):
        """Set callback for transcription results"""
        self.callback = callback

    def get_latest_transcription(self) -> str:
        """Get latest transcription"""
        if self.final_results:
            return self.final_results[-1]
        elif self.partial_results:
            return self.partial_results[-1]
        return ""

    def clear(self):
        """Clear transcription state"""
        self.partial_results = []
        self.final_results = []
        if self.recognizer:
            # Reset recognizer
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.recognizer.SetWords(True)
