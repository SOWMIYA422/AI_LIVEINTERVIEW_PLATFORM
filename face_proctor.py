# backend/face_proctor.py - Save this as a new file
import cv2
import numpy as np
import mediapipe as mp
import time
import base64


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

    def detect_from_base64(self, base64_frame: str) -> dict:
        """Process base64 image and return detection results"""
        try:
            # Decode base64
            img_data = base64.b64decode(base64_frame)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                return {"detected": False, "alerts": ["INVALID_FRAME"]}

            # Flip for mirror view (optional)
            frame = cv2.flip(frame, 1)

            # Check for violations
            self.check_rules(frame)

            return {
                "detected": self.face_present,
                "alerts": self.alerts.copy(),
                "face_count": self._get_face_count(frame),
                "calibration_complete": self.calibration_complete,
                "calibration_frames": self.calibration_frames,
                "face_cover_counter": self.face_cover_counter,
                "eye_cover_counter": self.eye_cover_counter,
            }

        except Exception as e:
            return {"detected": False, "alerts": [f"ERROR: {str(e)}"]}

    def _get_face_count(self, frame):
        """Count faces in frame"""
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detector.process(rgb_frame)
            return len(results.detections) if results.detections else 0
        except:
            return 0

    def check_rules(self, frame):
        """Check for violations (your existing code)"""
        self.alerts = []  # Reset alerts

        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Check for multiple faces
        face_results = self.face_detector.process(rgb_frame)
        if face_results.detections:
            if len(face_results.detections) > 1:
                self.alerts.append("MULTIPLE_PEOPLE")
            self.face_present = True
            self.last_face_time = time.time()
        else:
            self.face_present = False

        # Check for no face
        if not self.face_present:
            if time.time() - self.last_face_time > 3:
                self.alerts.append("NO_FACE")
            self.face_cover_counter = 0
            self.eye_cover_counter = 0
            return

        # Check face details with face mesh
        mesh_results = self.face_mesh.process(rgb_frame)

        if mesh_results.multi_face_landmarks:
            for face_landmarks in mesh_results.multi_face_landmarks:
                landmarks = face_landmarks.landmark

                # Calibrate on first detection
                if not self.calibration_complete:
                    self.calibration_frames += 1
                    if self.calibration_frames >= 30:
                        self.calibration_complete = True
                    else:
                        self.alerts.append(f"CALIBRATING_{self.calibration_frames}/30")
                    return

                # Check gaze and covering
                self.check_gaze(landmarks)
                self.check_face_eye_covering(frame, landmarks)

    def check_gaze(self, landmarks):
        """Check gaze direction (simplified for real-time)"""
        try:
            left_eye = landmarks[133]
            right_eye = landmarks[362]
            eye_center_x = (left_eye.x + right_eye.x) / 2

            if eye_center_x < 0.35:
                self.alerts.append("LOOKING_LEFT")
            elif eye_center_x > 0.65:
                self.alerts.append("LOOKING_RIGHT")
        except:
            pass

    def check_face_eye_covering(self, frame, landmarks):
        """Simplified covering detection for real-time"""
        try:
            h, w, _ = frame.shape

            # Get face region brightness
            xs = [landmark.x * w for landmark in landmarks]
            ys = [landmark.y * h for landmark in landmarks]

            face_x1 = int(max(0, min(xs)))
            face_y1 = int(max(0, min(ys)))
            face_x2 = int(min(w, max(xs)))
            face_y2 = int(min(h, max(ys)))

            if face_x2 > face_x1 and face_y2 > face_y1:
                face_roi = frame[face_y1:face_y2, face_x1:face_x2]

                if face_roi.size > 100:
                    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                    current_brightness = np.mean(gray_face)

                    # Check for face covering
                    if self.prev_face_brightness is not None:
                        if current_brightness < self.prev_face_brightness * 0.6:
                            self.face_cover_counter += 1
                            if self.face_cover_counter >= self.face_cover_threshold:
                                self.alerts.append("FACE_COVERED")
                        else:
                            self.face_cover_counter = max(
                                0, self.face_cover_counter - 1
                            )

                    self.prev_face_brightness = current_brightness

        except:
            self.prev_face_brightness = None


# Global proctor instance (one per session)
proctors = {}
