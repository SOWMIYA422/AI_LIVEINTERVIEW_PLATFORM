# test_diagnose.py
import sys
import os

print("=== AI Interview Platform Diagnostics ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# Check critical imports
print("\n=== Checking Imports ===")
try:
    import fastapi

    print(f"✓ FastAPI: {fastapi.__version__}")
except ImportError as e:
    print(f"✗ FastAPI import failed: {e}")

try:
    import google.generativeai as genai

    print("✓ Google Generative AI")
except ImportError as e:
    print(f"✗ Google Generative AI import failed: {e}")

try:
    from gtts import gTTS

    print("✓ gTTS")
except ImportError as e:
    print(f"✗ gTTS import failed: {e}")

try:
    import speech_recognition as sr

    print("✓ SpeechRecognition")
except ImportError as e:
    print(f"✗ SpeechRecognition import failed: {e}")

# Check config
print("\n=== Checking Configuration ===")
try:
    from config import GEMINI_API_KEY, VOSK_MODEL_PATH

    print(
        f"Gemini API Key: {'Set' if GEMINI_API_KEY and GEMINI_API_KEY != 'your-api-key-here' else 'NOT SET'}"
    )
    print(f"Vosk Model Path: {VOSK_MODEL_PATH}")
    print(f"Vosk Model Exists: {os.path.exists(VOSK_MODEL_PATH)}")
except Exception as e:
    print(f"Config error: {e}")

# Check directories
print("\n=== Checking Directories ===")
dirs = ["interview_sessions", "models"]
for d in dirs:
    exists = os.path.exists(d)
    print(f"{d}: {'✓ Exists' if exists else '✗ Missing'}")
    if exists:
        print(f"  Contents: {os.listdir(d)[:5] if os.listdir(d) else 'Empty'}")

# Test InterviewManager
print("\n=== Testing InterviewManager ===")
try:
    from interview_manager import InterviewManager

    print("✓ InterviewManager import successful")

    # Quick test
    test_manager = InterviewManager("software_engineer", "Test Candidate")
    opening = test_manager.get_opening_question()
    print(f"✓ Opening question generated: {opening[:50]}...")
except Exception as e:
    print(f"✗ InterviewManager test failed: {e}")
    import traceback

    traceback.print_exc()

print("\n=== Diagnostics Complete ===")
