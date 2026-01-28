# backend/vosk_transcriber.py
import vosk
import json
import logging
import wave
import io
import numpy as np
from typing import Optional, Generator
import threading
import queue

logger = logging.getLogger(__name__)


class VoskTranscriber:
    def __init__(self, model_path: str, sample_rate: int = 16000):
        """Initialize Vosk transcriber"""
        try:
            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, sample_rate)
            self.sample_rate = sample_rate
            self.is_listening = False
            self.audio_queue = queue.Queue()
            self.transcription_queue = queue.Queue()
            self.last_text = ""
            logger.info(f"Vosk model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load Vosk model: {e}")
            raise

    def transcribe_chunk(self, audio_data: bytes) -> str:
        """Transcribe a single audio chunk"""
        try:
            if self.recognizer.AcceptWaveform(audio_data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    logger.info(f"Transcribed: {text}")
                    return text
            else:
                # Partial result
                partial = json.loads(self.recognizer.PartialResult())
                text = partial.get("partial", "").strip()
                if text:
                    return text
        except Exception as e:
            logger.error(f"Transcription error: {e}")
        return ""

    def transcribe_stream(
        self, audio_stream: Generator[bytes, None, None]
    ) -> Generator[str, None, None]:
        """Transcribe a stream of audio chunks"""
        for chunk in audio_stream:
            text = self.transcribe_chunk(chunk)
            if text:
                yield text

    def start_listening(self):
        """Start listening for real-time transcription"""
        self.is_listening = True
        logger.info("Started listening for transcription")

    def stop_listening(self):
        """Stop listening"""
        self.is_listening = False
        logger.info("Stopped listening")

    def process_audio_chunk(self, chunk: bytes):
        """Process incoming audio chunk"""
        if self.is_listening:
            text = self.transcribe_chunk(chunk)
            if text and text != self.last_text:
                self.last_text = text
                self.transcription_queue.put(text)
                return text
        return ""

    def get_transcriptions(self) -> Generator[str, None, None]:
        """Get transcription results"""
        while self.is_listening or not self.transcription_queue.empty():
            try:
                yield self.transcription_queue.get(timeout=1)
            except queue.Empty:
                continue
