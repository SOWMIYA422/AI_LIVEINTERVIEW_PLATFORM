# backend/main.py - COMPLETE WITH FACE PROCTORING AND PROCOTRING PENALTIES
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import json
import cv2
import numpy as np
import base64
import time
import uuid
from datetime import datetime
from typing import Dict
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import wave
import speech_recognition as sr
import tempfile
import subprocess
import ffmpeg
from interview_manager import InterviewManager
from config import INTERVIEW_CONFIG, VOSK_MODEL_PATH, SAMPLE_RATE
import aiofiles
import shutil
import mediapipe as mp

# ==================== FACE PROCTORING CLASS ====================


class FaceProctor:
    def __init__(self):
        # Initialize MediaPipe
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_face_mesh = mp.solutions.face_mesh

        # Face detectors
        self.face_detector = self.mp_face_detection.FaceDetection(
            min_detection_confidence=0.5
        )
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1, min_detection_confidence=0.5, refine_landmarks=True
        )

        # State tracking
        self.alerts = []
        self.face_present = False
        self.last_face_time = time.time()
        self.calibration_complete = False
        self.calibration_frames = 0

        # For face/eye covering detection
        self.face_cover_counter = 0
        self.eye_cover_counter = 0
        self.face_cover_threshold = 15
        self.eye_cover_threshold = 10

        # Store previous face brightness
        self.prev_face_brightness = None
        self.brightness_change_threshold = 0.4

        print("🎯 Face Proctoring System Initialized")

    def check_rules(self, frame):
        """Check for face proctoring violations"""
        self.alerts = []  # Reset alerts

        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Check for multiple faces
        face_results = self.face_detector.process(rgb_frame)
        if face_results.detections:
            if len(face_results.detections) > 1:
                self.alerts.append("MULTIPLE PEOPLE DETECTED")
            self.face_present = True
            self.last_face_time = time.time()
        else:
            self.face_present = False

        # Check for no face
        if not self.face_present:
            if time.time() - self.last_face_time > 3:
                self.alerts.append("NO FACE DETECTED")
            self.face_cover_counter = 0
            self.eye_cover_counter = 0
            return self.alerts

        # Check face details with face mesh
        mesh_results = self.face_mesh.process(rgb_frame)

        if mesh_results.multi_face_landmarks:
            for face_landmarks in mesh_results.multi_face_landmarks:
                landmarks = face_landmarks.landmark

                # Calibration on first detection
                if not self.calibration_complete:
                    self.calibration_frames += 1
                    if self.calibration_frames >= 30:
                        self.calibration_complete = True
                        print("✅ Face calibration complete")
                    return self.alerts

                # Check for face/eye covering
                self.check_face_eye_covering_improved(frame, landmarks)

        return self.alerts

    def check_face_eye_covering_improved(self, frame, landmarks):
        """Improved method to detect face/eye covering"""
        try:
            h, w, _ = frame.shape

            # Get face bounding box from landmarks
            xs = [landmark.x * w for landmark in landmarks]
            ys = [landmark.y * h for landmark in landmarks]

            face_x1 = int(min(xs))
            face_y1 = int(min(ys))
            face_x2 = int(max(xs))
            face_y2 = int(max(ys))

            # Ensure bounds
            face_x1 = max(0, face_x1)
            face_y1 = max(0, face_y1)
            face_x2 = min(w, face_x2)
            face_y2 = min(h, face_y2)

            # Extract face region
            if face_x2 > face_x1 and face_y2 > face_y1:
                face_roi = frame[face_y1:face_y2, face_x1:face_x2]

                if face_roi.size > 100:
                    # Convert to grayscale
                    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)

                    # Calculate current face brightness
                    current_brightness = np.mean(gray_face)

                    # Check for sudden brightness drop (face covering)
                    if self.prev_face_brightness is not None:
                        brightness_ratio = (
                            current_brightness / self.prev_face_brightness
                        )

                        if brightness_ratio < 0.6:  # 40% or more brightness drop
                            self.face_cover_counter += 1
                            if self.face_cover_counter >= self.face_cover_threshold:
                                self.alerts.append("FACE COVERED")
                        else:
                            self.face_cover_counter = max(
                                0, self.face_cover_counter - 1
                            )

                    # Store current brightness for next frame
                    self.prev_face_brightness = current_brightness

                    # Check eye regions specifically
                    self.check_eye_covering(frame, landmarks, h, w)

        except Exception as e:
            self.prev_face_brightness = None

    def check_eye_covering(self, frame, landmarks, h, w):
        """Check if eyes are covered"""
        try:
            # Left eye landmarks
            left_eye_points = [33, 133, 160, 159, 158, 144, 145, 153]
            # Right eye landmarks
            right_eye_points = [362, 263, 387, 386, 385, 380, 374, 373]

            # Get eye bounding boxes
            left_eye_xs = [landmarks[idx].x * w for idx in left_eye_points]
            left_eye_ys = [landmarks[idx].y * h for idx in left_eye_points]

            right_eye_xs = [landmarks[idx].x * w for idx in right_eye_points]
            right_eye_ys = [landmarks[idx].y * h for idx in right_eye_points]

            # Calculate eye regions
            left_eye_x1 = int(min(left_eye_xs))
            left_eye_y1 = int(min(left_eye_ys))
            left_eye_x2 = int(max(left_eye_xs))
            left_eye_y2 = int(max(left_eye_ys))

            right_eye_x1 = int(min(right_eye_xs))
            right_eye_y1 = int(min(right_eye_ys))
            right_eye_x2 = int(max(right_eye_xs))
            right_eye_y2 = int(max(right_eye_ys))

            # Add padding around eyes
            padding = 10
            left_eye_x1 = max(0, left_eye_x1 - padding)
            left_eye_y1 = max(0, left_eye_y1 - padding)
            left_eye_x2 = min(w, left_eye_x2 + padding)
            left_eye_y2 = min(h, left_eye_y2 + padding)

            right_eye_x1 = max(0, right_eye_x1 - padding)
            right_eye_y1 = max(0, right_eye_y1 - padding)
            right_eye_x2 = min(w, right_eye_x2 + padding)
            right_eye_y2 = min(h, right_eye_y2 + padding)

            # Check both eye regions
            eyes_dark = 0

            # Left eye
            if left_eye_x2 > left_eye_x1 and left_eye_y2 > left_eye_y1:
                left_eye_roi = frame[left_eye_y1:left_eye_y2, left_eye_x1:left_eye_x2]
                if left_eye_roi.size > 0:
                    left_eye_gray = cv2.cvtColor(left_eye_roi, cv2.COLOR_BGR2GRAY)
                    left_brightness = np.mean(left_eye_gray)

                    if left_brightness < 50:
                        eyes_dark += 1

            # Right eye
            if right_eye_x2 > right_eye_x1 and right_eye_y2 > right_eye_y1:
                right_eye_roi = frame[
                    right_eye_y1:right_eye_y2, right_eye_x1:right_eye_x2
                ]
                if right_eye_roi.size > 0:
                    right_eye_gray = cv2.cvtColor(right_eye_roi, cv2.COLOR_BGR2GRAY)
                    right_brightness = np.mean(right_eye_gray)

                    if right_brightness < 50:
                        eyes_dark += 1

            # Check if both eyes are dark
            if eyes_dark >= 2:
                self.eye_cover_counter += 1
                if self.eye_cover_counter >= self.eye_cover_threshold:
                    self.alerts.append("EYES COVERED")
            else:
                self.eye_cover_counter = max(0, self.eye_cover_counter - 1)

        except:
            pass


# ==================== FACE PROCTORING FUNCTION ====================


def detect_face_proctoring(frame_data: bytes) -> dict:
    """Enhanced face detection with proctoring rules"""
    try:
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"detected": False, "alerts": [], "proctoring_data": {}}

        # Create a face proctor for this detection
        proctor = FaceProctor()
        alerts = proctor.check_rules(frame)

        # Get proctoring data
        proctoring_data = {
            "face_present": proctor.face_present,
            "alerts": alerts,
            "calibration_complete": proctor.calibration_complete,
            "calibration_frames": proctor.calibration_frames,
            "face_cover_counter": proctor.face_cover_counter,
            "eye_cover_counter": proctor.eye_cover_counter,
            "multiple_faces": "MULTIPLE PEOPLE DETECTED" in alerts,
            "face_covered": "FACE COVERED" in alerts,
            "eyes_covered": "EYES COVERED" in alerts,
            "no_face": "NO FACE DETECTED" in alerts,
        }

        return {
            "detected": proctor.face_present,
            "count": 1 if proctor.face_present else 0,
            "alerts": alerts,
            "proctoring_data": proctoring_data,
        }

    except Exception as e:
        return {"detected": False, "error": str(e), "alerts": []}


# ==================== LIFESPAN ====================


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🎯 AI Interview Platform - WITH FACE PROCTORING AND PROCOTRING PENALTIES")
    print(
        "📹 FFmpeg Audio Extraction | Google Speech-to-Text | MediaPipe Face Proctoring"
    )
    print("=" * 60)

    # Check if FFmpeg is available
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg available")
        else:
            print("⚠️ FFmpeg not found in PATH")
    except:
        print("⚠️ FFmpeg not found in PATH")

    yield
    print("Shutting down...")


app = FastAPI(
    title="AI Interview Platform - With Face Proctoring and Proctoring Penalties",
    version="10.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_sessions: Dict[str, dict] = {}
executor = ThreadPoolExecutor(max_workers=4)

# ==================== INTERVIEW SESSION CLASS ====================


class ReliableInterviewSession:
    def __init__(self, session_id: str, job_role: str, candidate_name: str):
        self.session_id = session_id
        self.job_role = job_role
        self.candidate_name = candidate_name
        self.interview_manager = InterviewManager(job_role, candidate_name)

        # Proctoring data
        self.proctoring_alerts = []
        self.proctoring_stats = {
            "tab_switch_count": 0,
            "multiple_faces": 0,
            "face_coverings": 0,
            "eye_coverings": 0,
            "no_face_count": 0,
            "total_alerts": 0,
            "last_face_time": time.time(),
        }

        # Create session directory
        self.session_dir = f"interview_sessions/{session_id}"
        os.makedirs(self.session_dir, exist_ok=True)

        # Session data
        self.start_time = datetime.now()
        self.tab_switch_count = 0
        self.face_detected = True
        self.is_active = True

        # Interview state
        self.current_question = ""
        self.question_number = 1
        self.current_level = "easy"

        print(f"✅ Session created: {session_id}")
        print(f"📁 Session directory: {self.session_dir}")

    def start_interview(self):
        """Get opening question"""
        opening_question = self.interview_manager.get_opening_question()
        self.current_question = opening_question
        return opening_question

    async def save_video_file(self, video_bytes: bytes):
        """Save video file for current question"""
        if not video_bytes or len(video_bytes) < 100:
            print("⚠️ Video too small or empty")
            return None

        video_path = f"{self.session_dir}/q{self.question_number}_answer.webm"

        try:
            async with aiofiles.open(video_path, "wb") as f:
                await f.write(video_bytes)

            file_size = os.path.getsize(video_path)
            print(f"✅ Video saved: {video_path} ({file_size} bytes)")
            return video_path

        except Exception as e:
            print(f"❌ Error saving video: {e}")
            return None

    def extract_audio_from_video(self, video_path: str) -> str:
        """Extract audio from video using FFmpeg"""
        try:
            if not os.path.exists(video_path):
                print(f"❌ Video file not found: {video_path}")
                return ""

            # Create audio file path
            audio_path = f"{self.session_dir}/q{self.question_number}_audio.wav"

            print(f"🎵 Extracting audio from video...")

            # Method 1: Try FFmpeg command line
            try:
                cmd = [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-vn",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-y",
                    audio_path,
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0 and os.path.exists(audio_path):
                    audio_size = os.path.getsize(audio_path)
                    print(
                        f"✅ Audio extracted with FFmpeg: {audio_path} ({audio_size} bytes)"
                    )
                    return audio_path
                else:
                    print(f"⚠️ FFmpeg failed: {result.stderr}")
            except Exception as ffmpeg_error:
                print(f"⚠️ FFmpeg error: {ffmpeg_error}")

            # Method 2: Try ffmpeg-python library
            try:
                import ffmpeg

                (
                    ffmpeg.input(video_path)
                    .output(audio_path, acodec="pcm_s16le", ar="16000", ac=1)
                    .overwrite_output()
                    .run(quiet=True)
                )

                if os.path.exists(audio_path):
                    audio_size = os.path.getsize(audio_path)
                    print(
                        f"✅ Audio extracted with ffmpeg-python: {audio_path} ({audio_size} bytes)"
                    )
                    return audio_path
            except Exception as ffmpeg_py_error:
                print(f"⚠️ ffmpeg-python error: {ffmpeg_py_error}")

            print("❌ Audio extraction failed")
            return ""

        except Exception as e:
            print(f"❌ Error extracting audio: {e}")
            return ""

    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file to text using Google Speech-to-Text"""
        try:
            if not os.path.exists(audio_path):
                print(f"❌ Audio file not found: {audio_path}")
                return ""

            audio_size = os.path.getsize(audio_path)
            if audio_size < 100:
                print(f"⚠️ Audio file too small: {audio_size} bytes")
                return ""

            print(f"🎤 Transcribing audio ({audio_size} bytes)...")

            # Initialize recognizer
            recognizer = sr.Recognizer()

            # Load audio file
            with sr.AudioFile(audio_path) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)

                # Try Google Speech Recognition
                try:
                    text = recognizer.recognize_google(audio_data)
                    print(f"✅ Transcription successful: {text[:100]}...")
                    return text

                except sr.UnknownValueError:
                    print("❌ Google Speech Recognition could not understand audio")
                    return ""

                except sr.RequestError as e:
                    print(f"❌ Google Speech Recognition error: {e}")
                    return ""

        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return ""

    def process_video_answer(self, video_path: str) -> dict:
        """Process video file: extract audio, transcribe, get next question"""
        try:
            print(f"\n{'=' * 60}")
            print(f"🔄 PROCESSING QUESTION {self.question_number}")
            print(f"{'=' * 60}")

            if not video_path or not os.path.exists(video_path):
                print("⚠️ No video file found - skipping question")
                next_question = self.interview_manager.get_next_question_without_answer(
                    self.current_question
                )

                # Save empty transcript
                transcript_path = (
                    f"{self.session_dir}/q{self.question_number}_transcript.txt"
                )
                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write("NO_ANSWER\n")

                self.current_question = next_question
                self.question_number += 1

                return {
                    "success": True,
                    "next_question": next_question,
                    "analysis": "No video recorded.",
                    "transcription": "",
                    "skipped": True,
                    "current_level": self.current_level,
                    "technical_score": 0,
                }

            # Step 1: Extract audio from video
            print("1️⃣ Extracting audio from video...")
            audio_path = self.extract_audio_from_video(video_path)

            if not audio_path:
                print("❌ Failed to extract audio - skipping question")
                next_question = self.interview_manager.get_next_question_without_answer(
                    self.current_question
                )

                transcript_path = (
                    f"{self.session_dir}/q{self.question_number}_transcript.txt"
                )
                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write("AUDIO_EXTRACTION_FAILED\n")

                self.current_question = next_question
                self.question_number += 1

                return {
                    "success": True,
                    "next_question": next_question,
                    "analysis": "Could not extract audio from video.",
                    "transcription": "",
                    "skipped": True,
                    "current_level": self.current_level,
                    "technical_score": 0,
                }

            # Step 2: Transcribe audio to text
            print("2️⃣ Transcribing audio to text...")
            transcription = self.transcribe_audio(audio_path)

            # Clean up audio file
            try:
                os.remove(audio_path)
            except:
                pass

            if not transcription or len(transcription.strip()) < 3:
                print("⚠️ No valid transcription - skipping question")
                next_question = self.interview_manager.get_next_question_without_answer(
                    self.current_question
                )

                transcript_path = (
                    f"{self.session_dir}/q{self.question_number}_transcript.txt"
                )
                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write("NO_TRANSCRIPTION\n")

                self.current_question = next_question
                self.question_number += 1

                return {
                    "success": True,
                    "next_question": next_question,
                    "analysis": "Could not transcribe audio.",
                    "transcription": "",
                    "skipped": True,
                    "current_level": self.current_level,
                    "technical_score": 0,
                }

            # Step 3: Save transcript
            print("3️⃣ Saving transcript...")
            transcript_path = (
                f"{self.session_dir}/q{self.question_number}_transcript.txt"
            )
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(f"QUESTION: {self.current_question}\n\n")
                f.write(f"TRANSCRIPTION: {transcription}\n")
            print(f"✅ Transcript saved: {transcript_path}")

            # Step 4: Process with Gemini
            print("4️⃣ Processing with Gemini AI...")
            result, next_question = self.interview_manager.process_answer(
                self.current_question, transcription
            )

            # Step 5: Save score
            print("5️⃣ Saving score...")
            score_path = f"{self.session_dir}/q{self.question_number}_score.json"
            with open(score_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "question_number": self.question_number,
                        "question": self.current_question,
                        "transcription": transcription,
                        "technical_score": result.get("technical_score", 0),
                        "level": result.get("level", self.current_level),
                        "analysis": result.get("analysis", ""),
                        "timestamp": datetime.now().isoformat(),
                        "video_file": os.path.basename(video_path),
                        "transcript_file": os.path.basename(transcript_path),
                        "proctoring_stats": self.proctoring_stats,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            print(f"✅ Score saved: {score_path}")

            # Step 6: Update state
            self.current_question = next_question
            self.question_number += 1
            self.current_level = result.get("level", self.current_level)

            print(f"✅ Question {self.question_number - 1} processed successfully!")
            print(f"📝 Transcription: {transcription[:100]}...")
            print(f"📊 Technical score: {result.get('technical_score', 0)}")
            print(f"🎯 New level: {self.current_level}")
            print(f"❓ Next question ready")

            return {
                "success": True,
                "next_question": next_question,
                "analysis": result.get("analysis", ""),
                "transcription": transcription,
                "technical_score": result.get("technical_score", 0),
                "current_level": self.current_level,
                "question_number": self.question_number,
            }

        except Exception as e:
            print(f"❌ Error processing video answer: {e}")
            import traceback

            traceback.print_exc()

            # Fallback: generate next question
            try:
                next_question = self.interview_manager.get_next_question_without_answer(
                    self.current_question
                )
                self.current_question = next_question
                self.question_number += 1

                return {
                    "success": True,
                    "next_question": next_question,
                    "analysis": "Error processing answer.",
                    "transcription": "",
                    "skipped": True,
                    "current_level": self.current_level,
                    "technical_score": 0,
                }
            except:
                return {"success": False, "error": str(e)}

    def end_interview(self, proctoring_stats: dict = None):
        """End interview and return final feedback with proctoring penalties"""
        self.is_active = False

        # Get proctoring stats if not provided
        if proctoring_stats is None:
            proctoring_stats = {
                "tab_switch_count": self.tab_switch_count,
                "multiple_faces": self.proctoring_stats.get("multiple_faces", 0),
                "face_coverings": self.proctoring_stats.get("face_coverings", 0),
                "eye_coverings": self.proctoring_stats.get("eye_coverings", 0),
                "no_face_count": self.proctoring_stats.get("no_face_count", 0),
                "total_alerts": self.proctoring_stats.get("total_alerts", 0),
            }

        # Pass proctoring stats to interview manager
        final_feedback = self.interview_manager.end_interview(proctoring_stats)

        # Save final summary
        summary_path = f"{self.session_dir}/interview_summary.json"

        # Collect all files
        video_files = []
        transcript_files = []
        score_files = []

        for i in range(1, self.question_number):
            video_path = f"{self.session_dir}/q{i}_answer.webm"
            transcript_path = f"{self.session_dir}/q{i}_transcript.txt"
            score_path = f"{self.session_dir}/q{i}_score.json"

            if os.path.exists(video_path):
                video_files.append(f"q{i}_answer.webm")
            if os.path.exists(transcript_path):
                transcript_files.append(f"q{i}_transcript.txt")
            if os.path.exists(score_path):
                score_files.append(f"q{i}_score.json")

        # Get final evaluation from interview manager
        final_evaluation = self.interview_manager.session_data.get(
            "final_evaluation", {}
        )

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "session_id": self.session_id,
                    "job_role": self.job_role,
                    "candidate_name": self.candidate_name,
                    "start_time": self.start_time.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "total_questions": self.question_number - 1,
                    "final_level": self.current_level,
                    "final_feedback": final_feedback,
                    "proctoring_stats": self.proctoring_stats,
                    "final_score": final_evaluation.get("overall_score", 0),
                    "penalty_details": final_evaluation.get("penalty_details", {}),
                    "files": {
                        "videos": video_files,
                        "transcripts": transcript_files,
                        "scores": score_files,
                    },
                    "directory": self.session_dir,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        print(f"📊 Interview summary saved: {summary_path}")
        print(
            f"🎯 Final score with proctoring penalties: {final_evaluation.get('overall_score', 0)}%"
        )

        return final_feedback

    def update_proctoring_stats(self, alerts):
        """Update proctoring statistics based on alerts"""
        if "MULTIPLE PEOPLE DETECTED" in alerts:
            self.proctoring_stats["multiple_faces"] += 1
        if "FACE COVERED" in alerts:
            self.proctoring_stats["face_coverings"] += 1
        if "EYES COVERED" in alerts:
            self.proctoring_stats["eye_coverings"] += 1
        if "NO FACE DETECTED" in alerts:
            self.proctoring_stats["no_face_count"] += 1

        if alerts:
            self.proctoring_stats["total_alerts"] += len(alerts)
            self.proctoring_alerts = alerts


# ==================== WEBSOCKETS ====================


@app.websocket("/ws/video/{session_id}")
async def video_stream(websocket: WebSocket, session_id: str):
    """WebSocket for face detection with proctoring"""
    await websocket.accept()
    print(f"📹 Face proctoring connected: {session_id}")

    if session_id not in active_sessions:
        await websocket.close()
        return

    session = active_sessions[session_id]

    try:
        while session.is_active:
            data = await websocket.receive_json()

            if data["type"] == "video_frame":
                frame_data = base64.b64decode(data["data"])

                # Enhanced face proctoring
                face_result = await asyncio.get_event_loop().run_in_executor(
                    executor, detect_face_proctoring, frame_data
                )

                # Update session state
                session.face_detected = face_result["detected"]
                session.update_proctoring_stats(face_result.get("alerts", []))
                session.proctoring_stats["last_face_time"] = time.time()

                # Send enhanced response
                await websocket.send_json(
                    {
                        "type": "proctoring_result",
                        "detected": face_result["detected"],
                        "alerts": face_result.get("alerts", []),
                        "proctoring_data": face_result.get("proctoring_data", {}),
                        "timestamp": time.time(),
                        "session_stats": session.proctoring_stats,
                    }
                )

    except WebSocketDisconnect:
        print(f"📹 Face proctoring disconnected: {session_id}")
    except Exception as e:
        print(f"📹 Face proctoring error: {e}")


@app.websocket("/ws/monitor/{session_id}")
async def monitor_stream(websocket: WebSocket, session_id: str):
    """WebSocket for tab monitoring"""
    await websocket.accept()
    print(f"🪟 Monitor stream connected: {session_id}")

    if session_id not in active_sessions:
        await websocket.close()
        return

    session = active_sessions[session_id]

    try:
        while session.is_active:
            data = await websocket.receive_json()

            if data["type"] == "tab_switch":
                session.tab_switch_count += 1
                session.proctoring_stats["tab_switch_count"] = session.tab_switch_count

                await websocket.send_json(
                    {
                        "type": "tab_warning",
                        "count": session.tab_switch_count,
                        "message": f"Tab switch detected! (Total: {session.tab_switch_count})",
                        "penalty": f"Penalty: -{min(session.tab_switch_count * 2, 20)} points",
                    }
                )

    except WebSocketDisconnect:
        print(f"🪟 Monitor stream disconnected: {session_id}")


# ==================== REST API ====================


@app.get("/")
async def root():
    return {
        "message": "AI Interview Platform - With Face Proctoring and Proctoring Penalties",
        "version": "10.0",
        "features": [
            "MediaPipe Face Proctoring",
            "Multiple face detection",
            "Face covering detection",
            "Eye covering detection",
            "Tab switching monitoring",
            "Proctoring penalty system",
            "FFmpeg audio extraction",
            "Google Speech-to-Text",
            "Real-time proctoring alerts",
        ],
        "penalty_system": {
            "tab_switching": "2 points per switch (max 20)",
            "multiple_people": "15 points per detection",
            "face_covered": "5 points per occurrence (max 25)",
            "eyes_covered": "5 points per occurrence (max 25)",
            "no_face": "2 points per occurrence (max 15)",
            "max_total_penalty": "70 points",
        },
        "requirements": "FFmpeg + MediaPipe installed",
    }


@app.post("/api/interview/start")
async def start_interview(request: dict):
    """Start new interview"""
    try:
        job_role = request.get("job_role")
        candidate_name = request.get("candidate_name", "")

        if not job_role:
            raise HTTPException(400, "Job role required")

        session_id = f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # Create session
        session = ReliableInterviewSession(session_id, job_role, candidate_name)
        opening_question = session.start_interview()

        active_sessions[session_id] = session

        return {
            "session_id": session_id,
            "question": opening_question,
            "job_role": job_role,
            "candidate_name": candidate_name,
            "max_questions": INTERVIEW_CONFIG["max_questions"],
            "session_dir": session.session_dir,
        }

    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/interview/{session_id}/next-question")
async def next_question(session_id: str, request: dict):
    """Process current answer and get next question"""
    try:
        print(f"\n{'=' * 60}")
        print(f"📥 NEXT-QUESTION REQUEST for {session_id}")
        print(f"{'=' * 60}")

        if session_id not in active_sessions:
            return JSONResponse({"success": False, "error": "Session not found"})

        session = active_sessions[session_id]

        video_bytes = None
        video_path = None

        # Check if video data is in request
        if request and "video" in request and request["video"]:
            try:
                print(f"📹 Processing video data...")
                video_bytes = base64.b64decode(request["video"])
                print(f"✅ Video decoded: {len(video_bytes)} bytes")

                video_path = await session.save_video_file(video_bytes)

                if not video_path:
                    print("⚠️ Failed to save video file")

            except Exception as e:
                print(f"❌ Error processing video: {e}")
                video_path = None
        else:
            print("⚠️ No video data in request")

        # Process video answer
        result = await asyncio.get_event_loop().run_in_executor(
            executor, session.process_video_answer, video_path
        )

        if not result["success"]:
            return JSONResponse({"success": False, "error": result.get("error")})

        print(f"✅ Processing complete for question {session.question_number - 1}")

        # Check if interview completed
        if session.question_number > INTERVIEW_CONFIG["max_questions"]:
            # Collect proctoring stats for penalty calculation
            proctoring_stats = {
                "tab_switch_count": session.tab_switch_count,
                "multiple_faces": session.proctoring_stats.get("multiple_faces", 0),
                "face_coverings": session.proctoring_stats.get("face_coverings", 0),
                "eye_coverings": session.proctoring_stats.get("eye_coverings", 0),
                "no_face_count": session.proctoring_stats.get("no_face_count", 0),
                "total_alerts": session.proctoring_stats.get("total_alerts", 0),
            }

            # End interview with proctoring penalties
            final_feedback = session.end_interview(proctoring_stats)
            del active_sessions[session_id]

            # Get final evaluation details
            final_evaluation = session.interview_manager.session_data.get(
                "final_evaluation", {}
            )

            return JSONResponse(
                {
                    "interview_completed": True,
                    "final_feedback": final_feedback,
                    "proctoring_stats": proctoring_stats,
                    "final_score": final_evaluation.get("overall_score", 0),
                    "penalty_details": final_evaluation.get("penalty_details", {}),
                    "message": "Interview completed successfully with proctoring penalties applied",
                }
            )

        return JSONResponse(
            {
                "success": True,
                "next_question": result["next_question"],
                "analysis": result.get("analysis", ""),
                "transcription": result.get("transcription", ""),
                "current_level": result["current_level"],
                "technical_score": result.get("technical_score", 0),
                "question_number": session.question_number,
                "max_questions": INTERVIEW_CONFIG["max_questions"],
                "proctoring_stats": session.proctoring_stats,
            }
        )

    except Exception as e:
        print(f"❌ Next question error: {e}")
        import traceback

        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)})


@app.post("/api/interview/{session_id}/end")
async def end_interview(session_id: str):
    """End interview manually with proctoring penalties"""
    try:
        if session_id in active_sessions:
            session = active_sessions[session_id]

            # Get proctoring stats before ending
            proctoring_stats = {
                "tab_switch_count": session.tab_switch_count,
                "multiple_faces": session.proctoring_stats.get("multiple_faces", 0),
                "face_coverings": session.proctoring_stats.get("face_coverings", 0),
                "eye_coverings": session.proctoring_stats.get("eye_coverings", 0),
                "no_face_count": session.proctoring_stats.get("no_face_count", 0),
                "total_alerts": session.proctoring_stats.get("total_alerts", 0),
            }

            # Pass proctoring stats to end_interview
            final_feedback = session.end_interview(proctoring_stats)

            # Get final evaluation details
            final_evaluation = session.interview_manager.session_data.get(
                "final_evaluation", {}
            )

            return {
                "success": True,
                "final_feedback": final_feedback,
                "proctoring_stats": proctoring_stats,
                "final_score": final_evaluation.get("overall_score", 0),
                "penalty_details": final_evaluation.get("penalty_details", {}),
                "final_score_details": final_evaluation,
            }

        return {"success": False, "error": "Session not found"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/proctoring/stats/{session_id}")
async def get_proctoring_stats(session_id: str):
    """Get proctoring statistics for session"""
    try:
        if session_id in active_sessions:
            session = active_sessions[session_id]

            # Calculate current penalty estimate
            penalty_estimate = 0
            penalty_estimate += min(session.tab_switch_count * 2, 20)  # Tab switching
            penalty_estimate += min(
                session.proctoring_stats.get("multiple_faces", 0) * 15, 30
            )
            penalty_estimate += min(
                session.proctoring_stats.get("face_coverings", 0) * 5, 25
            )
            penalty_estimate += min(
                session.proctoring_stats.get("eye_coverings", 0) * 5, 25
            )
            penalty_estimate += min(
                session.proctoring_stats.get("no_face_count", 0) * 2, 15
            )
            penalty_estimate += min(
                session.proctoring_stats.get("total_alerts", 0) * 1, 10
            )
            penalty_estimate = min(penalty_estimate, 70)

            return {
                "success": True,
                "proctoring_stats": session.proctoring_stats,
                "alerts": session.proctoring_alerts,
                "face_detected": session.face_detected,
                "tab_switches": session.tab_switch_count,
                "estimated_penalty": penalty_estimate,
                "current_penalty_breakdown": {
                    "tab_switching": min(session.tab_switch_count * 2, 20),
                    "multiple_faces": min(
                        session.proctoring_stats.get("multiple_faces", 0) * 15, 30
                    ),
                    "face_coverings": min(
                        session.proctoring_stats.get("face_coverings", 0) * 5, 25
                    ),
                    "eye_coverings": min(
                        session.proctoring_stats.get("eye_coverings", 0) * 5, 25
                    ),
                    "no_face": min(
                        session.proctoring_stats.get("no_face_count", 0) * 2, 15
                    ),
                    "total_alerts": min(
                        session.proctoring_stats.get("total_alerts", 0) * 1, 10
                    ),
                },
            }
        return {"success": False, "error": "Session not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/debug/session/{session_id}")
async def debug_session(session_id: str):
    """Debug endpoint to check session files"""
    session_dir = f"interview_sessions/{session_id}"

    if not os.path.exists(session_dir):
        return {"error": "Session directory not found"}

    files = {}
    for root, dirs, filenames in os.walk(session_dir):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            files[filename] = {
                "size": os.path.getsize(filepath),
                "path": filepath,
                "exists": True,
            }

    return {
        "session_id": session_id,
        "directory": session_dir,
        "files": files,
        "file_count": len(files),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
