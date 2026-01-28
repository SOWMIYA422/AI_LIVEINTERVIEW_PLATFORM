# backend/stt_worker.py - FIXED LIVE TRANSCRIPTION
import queue
import sounddevice as sd
import json
import time
import os
import wave
import threading
import numpy as np
from typing import Optional
import logging
import io
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import base64
from config import SAMPLE_RATE, OUTPUT_DIR

logger = logging.getLogger(__name__)


class InterviewSTT:
    def __init__(self, interview_id: str):
        self.interview_id = interview_id
        self.session_dir = f"{OUTPUT_DIR}/{interview_id}"
        os.makedirs(self.session_dir, exist_ok=True)

        # File paths
        self.audio_file = f"{self.session_dir}/audio.wav"
        self.transcript_file = f"{self.session_dir}/transcript.txt"

        # Initialize speech recognition
        logger.info("Initializing speech recognition...")

        # Use speech_recognition with Google
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        # Audio settings
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.last_audio_time = time.time()

        # Initialize transcript
        with open(self.transcript_file, "w", encoding="utf-8") as f:
            f.write(f"Interview Transcript - {interview_id}\n")
            f.write("=" * 50 + "\n\n")

    def audio_callback(self, indata, frames, time_info, status):
        """Audio callback for recording - SIMPLIFIED"""
        if status:
            logger.warning(f"Audio status: {status}")

        if self.is_recording:
            audio_data = bytes(indata)

            # Always queue the audio data
            self.audio_queue.put(audio_data)
            if hasattr(self, "wf"):
                self.wf.writeframes(audio_data)
            self.last_audio_time = time.time()

    def start_recording(self):
        """Start audio recording"""
        logger.info("Starting audio recording...")

        # Initialize audio file
        self.wf = wave.open(self.audio_file, "wb")
        self.wf.setnchannels(1)
        self.wf.setsampwidth(2)
        self.wf.setframerate(SAMPLE_RATE)

        self.is_recording = True
        self.last_audio_time = time.time()

        # Start audio stream
        try:
            self.audio_stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=4096,
                dtype="int16",
                channels=1,
                callback=self.audio_callback,
            )
            self.audio_stream.start()
            logger.info("Audio stream started successfully")
        except Exception as e:
            logger.error(f"Audio stream error: {e}")
            self.is_recording = False

    def transcribe_audio_chunk(self, audio_bytes: bytes) -> str:
        """Transcribe a chunk of audio - SIMPLIFIED AND WORKING"""
        try:
            # Convert raw bytes to AudioSegment
            audio_segment = AudioSegment(
                data=audio_bytes, sample_width=2, frame_rate=SAMPLE_RATE, channels=1
            )

            # Export to WAV format in memory
            with io.BytesIO() as wav_buffer:
                audio_segment.export(wav_buffer, format="wav")
                wav_data = wav_buffer.getvalue()

            # Convert to AudioData for speech_recognition
            audio_data = sr.AudioData(wav_data, SAMPLE_RATE, 2)

            # Try Google Speech Recognition
            try:
                text = self.recognizer.recognize_google(audio_data)
                if text:
                    # Basic cleaning
                    clean_text = text.strip()
                    if clean_text and clean_text[0].islower():
                        clean_text = clean_text[0].upper() + clean_text[1:]
                    if clean_text and not clean_text.endswith((".", "!", "?")):
                        clean_text += "."

                    logger.info(f"✅ Transcribed: {clean_text[:100]}...")
                    self._save_transcription(clean_text)
                    return clean_text

            except sr.UnknownValueError:
                logger.debug("Speech Recognition could not understand audio")
                return ""
            except sr.RequestError as e:
                logger.error(f"Google Speech Recognition error: {e}")
                return ""

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

        return ""

    def transcribe_full_audio(self, audio_base64: str) -> str:
        """Transcribe full audio from base64 - For final submission"""
        try:
            # Decode base64
            audio_bytes = base64.b64decode(audio_base64)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                # Load audio file
                with sr.AudioFile(tmp_path) as source:
                    # Adjust for ambient noise
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    # Record the audio
                    audio = self.recognizer.record(source)

                    # Transcribe
                    text = self.recognizer.recognize_google(audio)

                    if text:
                        clean_text = text.strip()
                        if clean_text and clean_text[0].islower():
                            clean_text = clean_text[0].upper() + clean_text[1:]
                        if clean_text and not clean_text.endswith((".", "!", "?")):
                            clean_text += "."

                        logger.info(f"✅ Full transcription: {clean_text[:100]}...")
                        self._save_transcription(clean_text, "FINAL")
                        return clean_text

            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Full transcription error: {e}")

        return ""

    def _save_transcription(self, text: str, source: str = "GOOGLE"):
        """Save transcription to file"""
        with open(self.transcript_file, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%H:%M:%S")
            f.write(f"[{timestamp}] [{source}] {text}\n")

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up STT resources...")
        self.is_recording = False

        if hasattr(self, "audio_stream"):
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except:
                pass

        if hasattr(self, "wf"):
            try:
                self.wf.close()
            except:
                pass

        logger.info("STT cleanup completed")
