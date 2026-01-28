# backend/audio_processor.py - UPDATED WITH VOSK
import numpy as np
import speech_recognition as sr
from vosk import Model, KaldiRecognizer
import json
import io
import wave
import tempfile
import logging
from typing import Optional, Tuple, Generator
import queue
import threading

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self, vosk_model_path: str = None):
        # Initialize Vosk model
        self.vosk_model = None
        self.vosk_recognizer = None
        self.vosk_partial_recognizer = None

        if vosk_model_path:
            self._initialize_vosk(vosk_model_path)

        # Initialize Google recognizer as fallback
        self.google_recognizer = sr.Recognizer()
        self.google_recognizer.energy_threshold = 300
        self.google_recognizer.dynamic_energy_threshold = True

        # Transcription queue for live results
        self.transcription_queue = queue.Queue()
        self.is_listening = False

    def _initialize_vosk(self, model_path: str):
        """Initialize Vosk model for live transcription"""
        try:
            self.vosk_model = Model(model_path)
            self.vosk_recognizer = KaldiRecognizer(self.vosk_model, 16000)
            self.vosk_partial_recognizer = KaldiRecognizer(self.vosk_model, 16000)
            self.vosk_partial_recognizer.SetWords(True)
            logger.info("Vosk model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Vosk model: {e}")

    def process_live_audio_chunk(self, audio_chunk: bytes) -> str:
        """Process live audio chunk and return transcription"""
        if not self.vosk_recognizer:
            return ""

        try:
            # Process the chunk
            if self.vosk_recognizer.AcceptWaveform(audio_chunk):
                result = json.loads(self.vosk_recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    logger.info(f"Vosk final: {text}")
                    return text
            else:
                # Get partial result
                partial_result = json.loads(self.vosk_recognizer.PartialResult())
                partial_text = partial_result.get("partial", "").strip()
                if partial_text:
                    logger.debug(f"Vosk partial: {partial_text}")
                    return partial_text
        except Exception as e:
            logger.error(f"Vosk processing error: {e}")

        return ""

    def transcribe_audio_file(self, audio_data: bytes) -> str:
        """Transcribe complete audio file"""
        transcriptions = []

        # Try Vosk first
        if self.vosk_recognizer:
            try:
                # Reset recognizer
                self.vosk_recognizer = KaldiRecognizer(self.vosk_model, 16000)

                # Process in chunks
                chunk_size = 4000  # 0.25 seconds at 16kHz
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i : i + chunk_size]
                    if self.vosk_recognizer.AcceptWaveform(chunk):
                        result = json.loads(self.vosk_recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            transcriptions.append(text)

                # Get final result
                final_result = json.loads(self.vosk_recognizer.FinalResult())
                final_text = final_result.get("text", "").strip()
                if final_text:
                    transcriptions.append(final_text)

                if transcriptions:
                    full_text = " ".join(transcriptions)
                    logger.info(f"Vosk transcription: {full_text}")
                    return full_text

            except Exception as e:
                logger.error(f"Vosk transcription failed: {e}")

        # Fallback to Google
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Write WAV file
                self._write_wav_header(temp_file, audio_data)
                temp_file.write(audio_data)
                temp_path = temp_file.name

            with sr.AudioFile(temp_path) as source:
                audio = self.google_recognizer.record(source)
                text = self.google_recognizer.recognize_google(audio)
                logger.info(f"Google transcription: {text}")
                return text

        except sr.UnknownValueError:
            logger.warning("Google could not understand audio")
        except sr.RequestError as e:
            logger.error(f"Google API error: {e}")
        except Exception as e:
            logger.error(f"Transcription error: {e}")

        return ""

    def _write_wav_header(self, file, audio_data: bytes):
        """Write WAV header for raw audio data"""
        nchannels = 1
        sampwidth = 2
        framerate = 16000
        nframes = len(audio_data) // sampwidth

        file.write(b"RIFF")
        file.write((36 + len(audio_data)).to_bytes(4, "little"))
        file.write(b"WAVE")
        file.write(b"fmt ")
        file.write((16).to_bytes(4, "little"))
        file.write((1).to_bytes(2, "little"))
        file.write(nchannels.to_bytes(2, "little"))
        file.write(framerate.to_bytes(4, "little"))
        file.write((framerate * nchannels * sampwidth).to_bytes(4, "little"))
        file.write((nchannels * sampwidth).to_bytes(2, "little"))
        file.write((sampwidth * 8).to_bytes(2, "little"))
        file.write(b"data")
        file.write(len(audio_data).to_bytes(4, "little"))

    def start_live_transcription(self):
        """Start live transcription mode"""
        self.is_listening = True
        if self.vosk_recognizer:
            # Reset recognizer for new session
            self.vosk_recognizer = KaldiRecognizer(self.vosk_model, 16000)
        logger.info("Live transcription started")

    def stop_live_transcription(self):
        """Stop live transcription"""
        self.is_listening = False
        logger.info("Live transcription stopped")
