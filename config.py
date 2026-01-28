# backend/config.py - UPDATED WITH OPTIMIZATIONS
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# Vosk Config
VOSK_MODEL_PATH = r"D:\\Downloads\\vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000
# Add to config.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("interview_debug.log"), logging.StreamHandler()],
)
# OPTIMIZED CONFIGURATION
INTERVIEW_CONFIG = {
    "max_questions": 9,
    "time_per_question": 120,  # Reduced from 180
    "levels": ["easy", "medium", "hard"],
    "questions_per_level": 3,
    "optimized": True,
    "face_detection_interval": 4,  # Seconds
    "camera_quality": "adaptive",  # low, medium, high
}

# Performance settings
PERFORMANCE_CONFIG = {
    "max_concurrent_sessions": 3,
    "audio_chunk_size": 4000,  # 250ms chunks
    "face_detection_workers": 2,
    "enable_cpu_monitoring": True,
}

# Output Directory
OUTPUT_DIR = "interview_sessions"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Job Role Prompts (unchanged)
JOB_ROLE_PROMPTS = {
    "data_scientist": {
        "opening": "Welcome! I'm your AI interviewer for the Data Scientist position. Let's start with a brief introduction. Could you please introduce yourself and tell me about your background in data science?",
        "context": "Data Scientist interview focusing on analytical skills and experience.",
        "level_context": {
            "easy": "Ask basic data science questions about statistics, simple ML concepts, and data manipulation.",
            "medium": "Ask intermediate questions about model evaluation, feature engineering, and practical data analysis.",
            "hard": "Ask advanced questions about complex ML algorithms, deep learning, and strategic data insights.",
        },
    },
    "software_engineer": {
        "opening": "Hello! I'm your AI interviewer for the Software Engineer role. To begin, could you please introduce yourself and share your experience with software development?",
        "context": "Software Engineer interview focusing on technical skills and experience.",
        "level_context": {
            "easy": "Ask basic software engineering questions about programming fundamentals, simple algorithms, and general experience.",
            "medium": "Ask intermediate questions about system design, data structures, and real-world problem solving.",
            "hard": "Ask advanced questions about complex algorithms, architecture, scalability, and challenging technical scenarios.",
        },
    },
    "product_manager": {
        "opening": "Welcome! I'm your AI interviewer for the Product Manager position. Let's start with you introducing yourself and your product experience.",
        "context": "Product Manager interview focusing on product strategy and experience.",
        "level_context": {
            "easy": "Ask basic product management questions about user research, basic strategy, and team collaboration.",
            "medium": "Ask intermediate questions about product lifecycle, metrics, and stakeholder management.",
            "hard": "Ask advanced questions about product vision, complex decision-making, and strategic leadership.",
        },
    },
    "default": {
        "opening": "Welcome! I'm your AI interviewer. Please introduce yourself and tell me about your professional background.",
        "context": "Professional job interview.",
        "level_context": {
            "easy": "Ask basic professional questions about experience, skills, and general knowledge.",
            "medium": "Ask intermediate questions about problem-solving, decision-making, and practical experience.",
            "hard": "Ask advanced questions about strategic thinking, leadership, and complex professional scenarios.",
        },
    },
}
