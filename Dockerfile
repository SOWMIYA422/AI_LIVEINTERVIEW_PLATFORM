FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    portaudio19-dev \
    libasound2-dev \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p interview_sessions models

# Download Vosk model (optional - you can mount it as volume)
# RUN wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip \
#     && unzip vosk-model-small-en-us-0.15.zip \
#     && mv vosk-model-small-en-us-0.15 models/ \
#     && rm vosk-model-small-en-us-0.15.zip

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]