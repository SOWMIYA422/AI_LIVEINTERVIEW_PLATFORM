# backend/voice_processor.py - UNIFIED VOICE PROCESSING SOLUTION
import json
import logging
import threading
import time
import base64
import os
from typing import Optional, Dict
from vosk import Model, KaldiRecognizer
from config import VOSK_MODEL_PATH, SAMPLE_RATE

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """Unified voice processor for both live and batch transcription"""
    
    def __init__(self):
        self.model = self._load_vosk_model()
        self.lock = threading.Lock()
        
    def _load_vosk_model(self) -> Model:
        """Load VOSK model with error handling"""
        try:
            if not os.path.exists(VOSK_MODEL_PATH):
                raise FileNotFoundError(
                    f"VOSK model not found at {VOSK_MODEL_PATH}\n"
                    f"Please download from: https://alphacephei.com/vosk/models\n"
                    f"and extract to: {VOSK_MODEL_PATH}"
                )
            
            logger.info(f"Loading VOSK model from: {VOSK_MODEL_PATH}")
            model = Model(VOSK_MODEL_PATH)
            logger.info("VOSK model loaded successfully")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load VOSK model: {e}")
            raise
    
    def transcribe_audio(self, audio_base64: str, is_live: bool = False) -> Dict:
        """
        Transcribe audio from base64 string
        
        Args:
            audio_base64: Base64 encoded audio
            is_live: Whether this is live audio (returns partial results)
            
        Returns:
            Dict with transcription and metadata
        """
        try:
            # Decode base64
            audio_bytes = base64.b64decode(audio_base64)
            
            with self.lock:
                # Create new recognizer for this transcription
                recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
                recognizer.SetWords(True)
                
                # Process audio in chunks
                chunk_size = 4000  # 0.25 seconds at 16kHz
                transcriptions = []
                
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i + chunk_size]
                    
                    if recognizer.AcceptWaveform(chunk):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            transcriptions.append(text)
                    
                    # If live transcription, return partial results immediately
                    elif is_live:
                        partial = json.loads(recognizer.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            return {
                                "success": True,
                                "text": partial_text,
                                "is_final": False,
                                "type": "partial"
                            }
                
                # Get final result
                final_result = json.loads(recognizer.FinalResult())
                final_text = final_result.get("text", "").strip()
                
                if final_text:
                    transcriptions.append(final_text)
                
                full_text = " ".join(transcriptions) if transcriptions else ""
                
                return {
                    "success": True,
                    "text": full_text,
                    "is_final": True,
                    "type": "final",
                    "word_count": len(full_text.split())
                }
                
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
    
    def check_audio_quality(self, audio_base64: str) -> Dict:
        """Check audio quality before processing"""
        try:
            audio_bytes = base64.b64decode(audio_base64)
            
            return {
                "success": True,
                "size_bytes": len(audio_bytes),
                "duration_seconds": len(audio_bytes) / (SAMPLE_RATE * 2),  # Assuming 16-bit mono
                "has_audio": len(audio_bytes) > 100  # Basic check
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# Singleton instance
voice_processor = VoiceProcessor()