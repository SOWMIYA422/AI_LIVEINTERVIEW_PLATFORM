# backend/transcription_logger.py
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TranscriptionLogger:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = f"interview_sessions/{session_id}"
        os.makedirs(self.session_dir, exist_ok=True)

        # Transcription files
        self.live_transcription_file = f"{self.session_dir}/live_transcriptions.txt"
        self.final_transcription_file = f"{self.session_dir}/final_transcriptions.json"
        self.transcription_summary_file = (
            f"{self.session_dir}/transcription_summary.json"
        )

        # Initialize files
        self._initialize_files()

        logger.info(f"TranscriptionLogger initialized for session {session_id}")

    def _initialize_files(self):
        """Initialize transcription files"""
        # Live transcription file
        if not os.path.exists(self.live_transcription_file):
            with open(self.live_transcription_file, "w", encoding="utf-8") as f:
                f.write(f"LIVE TRANSCRIPTIONS - Session: {self.session_id}\n")
                f.write("=" * 50 + "\n")
                f.write(f"Started: {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")

        # Final transcription file (JSON)
        if not os.path.exists(self.final_transcription_file):
            with open(self.final_transcription_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

        # Summary file
        if not os.path.exists(self.transcription_summary_file):
            with open(self.transcription_summary_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "session_id": self.session_id,
                        "start_time": datetime.now().isoformat(),
                        "total_transcriptions": 0,
                        "live_transcription_count": 0,
                        "final_transcription_count": 0,
                        "questions_transcribed": 0,
                    },
                    f,
                    indent=2,
                )

    def log_live_transcription(self, text: str, is_partial: bool = False):
        """Log live transcription text"""
        if not text or len(text.strip()) < 2:  # Minimum 2 characters
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = "[PARTIAL]" if is_partial else "[FINAL]"

        with open(self.live_transcription_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {prefix} {text}\n")

        # Update summary
        self._update_summary("live_transcription_count", 1)

        logger.debug(f"Live transcription logged: {text[:50]}...")

    def log_final_transcription(
        self, question: str, answer: str, transcription: str, confidence: float = 0.0
    ):
        """Log final transcription for a question-answer pair"""
        if not transcription or len(transcription.strip()) < 3:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question[:500] if question else "",  # Limit length
            "original_answer": answer[:1000] if answer else "",
            "transcription": transcription,
            "confidence": confidence,
            "transcription_length": len(transcription),
            "word_count": len(transcription.split()),
        }

        try:
            # Load existing data
            with open(self.final_transcription_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Add new entry
            data.append(entry)

            # Save back
            with open(self.final_transcription_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Update summary
            self._update_summary("final_transcription_count", 1)
            self._update_summary("questions_transcribed", 1)

            logger.info(f"Final transcription logged for question: {question[:50]}...")

        except Exception as e:
            logger.error(f"Error saving final transcription: {e}")

    def _update_summary(self, field: str, increment: int = 1):
        """Update transcription summary"""
        try:
            with open(self.transcription_summary_file, "r", encoding="utf-8") as f:
                summary = json.load(f)

            if field in summary:
                summary[field] = summary.get(field, 0) + increment

            summary["total_transcriptions"] = summary.get(
                "live_transcription_count", 0
            ) + summary.get("final_transcription_count", 0)

            summary["last_update"] = datetime.now().isoformat()

            with open(self.transcription_summary_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error updating transcription summary: {e}")

    def get_transcription_summary(self) -> Dict:
        """Get transcription statistics"""
        try:
            with open(self.transcription_summary_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading transcription summary: {e}")
            return {
                "session_id": self.session_id,
                "total_transcriptions": 0,
                "live_transcription_count": 0,
                "final_transcription_count": 0,
                "questions_transcribed": 0,
                "error": str(e),
            }

    def get_live_transcriptions(self, limit: int = 50) -> List[str]:
        """Get recent live transcriptions"""
        try:
            with open(self.live_transcription_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Get non-empty lines (skip header and empty lines)
            transcriptions = [
                line.strip()
                for line in lines
                if line.strip() and not line.startswith("=")
            ]
            return transcriptions[-limit:] if limit > 0 else transcriptions

        except Exception as e:
            logger.error(f"Error reading live transcriptions: {e}")
            return []

    def get_final_transcriptions(self) -> List[Dict]:
        """Get all final transcriptions"""
        try:
            with open(self.final_transcription_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading final transcriptions: {e}")
            return []

    def cleanup(self):
        """Cleanup and finalize transcription logging"""
        try:
            # Update summary with end time
            summary = self.get_transcription_summary()
            summary["end_time"] = datetime.now().isoformat()

            with open(self.transcription_summary_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            logger.info(
                f"TranscriptionLogger cleanup completed for session {self.session_id}"
            )

        except Exception as e:
            logger.error(f"Error during transcription cleanup: {e}")
