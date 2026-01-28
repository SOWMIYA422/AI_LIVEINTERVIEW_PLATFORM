import sys
import os
import json
import queue
from vosk import Model, KaldiRecognizer
import pyaudio


class LiveTranscriber:
    def __init__(self, model_path="vosk-model-small-en-us-0.15"):
        """Initialize live transcriber"""
        self.model_path = model_path

        # Check if model exists
        if not os.path.exists(model_path):
            print(f"❌ Error: Model not found at {model_path}")
            sys.exit(1)

        # Load model
        print("📥 Loading VOSK model...")
        self.model = Model(model_path)
        print("✅ Model loaded")

        # Audio settings
        self.sample_rate = 16000
        self.chunk_size = 4000

        # Create recognizer
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.recognizer.SetWords(True)  # Get word timestamps

        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()

        # Queue for audio data
        self.audio_queue = queue.Queue()

        print(f"\n🎤 Live Transcription Ready!")
        print(f"   Sample rate: {self.sample_rate}Hz")
        print(f"   Chunk size: {self.chunk_size} bytes")
        print("\n" + "=" * 50)

    def callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback function"""
        self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def start_transcription(self, duration_seconds=None):
        """Start live transcription"""
        print("\n🔊 Listening... Speak into your microphone!")
        print("   Press Ctrl+C to stop\n")

        # Open microphone stream
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self.callback,
        )

        stream.start_stream()

        try:
            frame_count = 0
            while True:
                # Get audio data from queue
                if not self.audio_queue.empty():
                    data = self.audio_queue.get()

                    # Process with VOSK
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        if result.get("text"):
                            print(f"\n📝 Full: {result['text']}")
                    else:
                        partial = json.loads(self.recognizer.PartialResult())
                        if partial.get("partial"):
                            # Clear line and print partial result
                            sys.stdout.write("\r" + " " * 80 + "\r")
                            sys.stdout.write(f"🎤 Partial: {partial['partial']}")
                            sys.stdout.flush()

                    frame_count += 1

                    # Stop after duration if specified
                    if (
                        duration_seconds
                        and frame_count * self.chunk_size / self.sample_rate
                        >= duration_seconds
                    ):
                        print("\n⏰ Time's up!")
                        break

        except KeyboardInterrupt:
            print("\n\n🛑 Stopped by user")

        finally:
            # Cleanup
            stream.stop_stream()
            stream.close()
            self.audio.terminate()

            # Get final result
            final_result = json.loads(self.recognizer.FinalResult())
            if final_result.get("text"):
                print(f"\n📄 Final transcription: {final_result['text']}")


if __name__ == "__main__":
    # Create transcriber
    transcriber = LiveTranscriber()

    # Start transcription (optional: specify duration in seconds)
    transcriber.start_transcription(duration_seconds=30)  # Records for 30 seconds
