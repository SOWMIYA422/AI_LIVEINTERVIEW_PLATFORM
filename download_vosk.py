import os
import sys
import requests
import zipfile
import tarfile
import shutil
import time


def download_vosk_model():
    """
    Download and extract VOSK model for AI Interview Platform
    """
    print("=" * 60)
    print("📥 DOWNLOADING VOSK MODEL FOR AI INTERVIEW PLATFORM")
    print("=" * 60)

    # Model URL (direct download link)
    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"

    # Paths
    download_dir = r"C:\Users\lenovo\Downloads"
    zip_path = os.path.join(download_dir, "vosk-model-small-en-us-0.15.zip")
    extract_dir = os.path.join(download_dir, "vosk-model-small-en-us-0.15")

    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)

    # Clean up old files
    print("🧹 Cleaning up old files...")
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)
        print(f"✅ Removed old directory: {extract_dir}")

    if os.path.exists(zip_path):
        os.remove(zip_path)
        print(f"✅ Removed old zip: {zip_path}")

    # Download the model
    print(f"\n📥 Downloading VOSK model from: {model_url}")
    print(f"💾 Saving to: {zip_path}")

    try:
        # Download with progress
        response = requests.get(model_url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192
        downloaded = 0

        with open(zip_path, "wb") as file:
            for data in response.iter_content(block_size):
                downloaded += len(data)
                file.write(data)

                # Show progress
                percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                print(
                    f"\r📊 Downloading... {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB)",
                    end="",
                )

        print(
            f"\n✅ Download complete! File size: {os.path.getsize(zip_path) / 1024 / 1024:.1f} MB"
        )

    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        print("\n🔗 Alternative download options:")
        print("1. Download manually from: https://alphacephei.com/vosk/models")
        print("2. Choose: 'vosk-model-small-en-us-0.15'")
        print("3. Save to: C:\\Users\\lenovo\\Downloads")
        return False

    # Verify zip file
    if (
        not os.path.exists(zip_path) or os.path.getsize(zip_path) < 1000000
    ):  # Less than 1MB
        print(
            f"❌ Downloaded file is too small or corrupted: {os.path.getsize(zip_path)} bytes"
        )
        return False

    # Extract the model
    print(f"\n📦 Extracting model to: {extract_dir}")

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Get list of files
            file_list = zip_ref.namelist()
            print(f"📄 Found {len(file_list)} files in archive")

            # Extract all files
            zip_ref.extractall(download_dir)

        print("✅ Extraction complete!")

    except zipfile.BadZipFile:
        print("❌ Zip file is corrupted!")
        return False
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return False

    # Check if extraction created the right folder structure
    print(f"\n🔍 Checking extracted structure...")

    # Sometimes the extraction creates a different folder name
    extracted_items = [
        f
        for f in os.listdir(download_dir)
        if os.path.isdir(os.path.join(download_dir, f)) and "vosk" in f.lower()
    ]

    if not extracted_items:
        print("❌ No VOSK folder found after extraction!")
        return False

    actual_folder = os.path.join(download_dir, extracted_items[0])
    print(f"✅ Found extracted folder: {actual_folder}")

    # Rename to standard name if needed
    if os.path.basename(actual_folder) != "vosk-model-small-en-us-0.15":
        new_path = os.path.join(download_dir, "vosk-model-small-en-us-0.15")
        if os.path.exists(new_path):
            shutil.rmtree(new_path, ignore_errors=True)

        # Move the folder
        shutil.move(actual_folder, new_path)
        actual_folder = new_path
        print(f"✅ Renamed to: {actual_folder}")

    # Verify critical files
    print(f"\n📋 Verifying model files...")

    critical_files = [
        ("am/final.mdl", "Main acoustic model", 80),  # Should be ~80MB
        ("graph/phones.txt", "Phoneme dictionary", 0.1),
        ("conf/model.conf", "Model configuration", 0.01),
        ("ivector/final.dubm", "iVector extractor", 20),
    ]

    all_good = True
    for file_path, description, min_size_mb in critical_files:
        full_path = os.path.join(actual_folder, file_path)

        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path) / 1024 / 1024  # Convert to MB
            if file_size > min_size_mb:
                status = "✅"
                print(f"{status} {file_path:25} {description:30} {file_size:.1f} MB")
            else:
                status = "⚠️"
                print(
                    f"{status} {file_path:25} {description:30} {file_size:.1f} MB (TOO SMALL!)"
                )
                all_good = False
        else:
            status = "❌"
            print(f"{status} {file_path:25} {description:30} MISSING")
            all_good = False

    if all_good:
        print("\n🎉 VOSK MODEL IS READY FOR AI INTERVIEW!")
        print(f"\n📍 Model path: {actual_folder}")
        print("\n📁 Update your config.py with:")
        print(f'VOSK_MODEL_PATH = r"{actual_folder}"')

        # Test with vosk library
        print("\n🧪 Testing VOSK library integration...")
        try:
            from vosk import Model

            model = Model(actual_folder)
            print("✅ VOSK model loaded successfully!")

            # Quick test
            from vosk import KaldiRecognizer

            recognizer = KaldiRecognizer(model, 16000)
            print("✅ KaldiRecognizer initialized!")
            print("✅ VOSK is ready for live transcription!")

        except ImportError:
            print("⚠️ VOSK library not installed. Install with: pip install vosk")
        except Exception as e:
            print(f"⚠️ Model test failed: {e}")

        return True
    else:
        print("\n❌ Model files are incomplete or corrupted!")
        print("\n💡 Try downloading manually:")
        print("1. Go to: https://alphacephei.com/vosk/models")
        print("2. Download 'vosk-model-small-en-us-0.15.zip'")
        print(
            "3. Extract ALL files to: C:\\Users\\lenovo\\Downloads\\vosk-model-small-en-us-0.15"
        )
        return False


def test_existing_model():
    """Test if existing model works"""
    print("\n" + "=" * 60)
    print("🧪 TESTING EXISTING VOSK MODEL")
    print("=" * 60)

    model_path = r"C:\Users\lenovo\Downloads\vosk-model-small-en-us-0.15"

    if not os.path.exists(model_path):
        print(f"❌ Model path doesn't exist: {model_path}")
        return False

    print(f"📁 Model path: {model_path}")

    # Check critical file
    critical_file = os.path.join(model_path, "am", "final.mdl")

    if os.path.exists(critical_file):
        size_mb = os.path.getsize(critical_file) / 1024 / 1024
        print(f"📊 Model file size: {size_mb:.1f} MB")

        if size_mb < 1:
            print("❌ Model file is EMPTY or CORRUPTED (should be ~80 MB)")
            return False
        else:
            print(f"✅ Model file looks good ({size_mb:.1f} MB)")

            # Try to load it
            try:
                from vosk import Model

                print("🔄 Loading VOSK model...")
                model = Model(model_path)
                print("✅ VOSK model loaded successfully!")
                return True
            except ImportError:
                print("⚠️ VOSK library not installed")
                return True  # Model file is good at least
            except Exception as e:
                print(f"❌ Failed to load model: {e}")
                return False
    else:
        print("❌ Model file not found at expected location")
        return False


if __name__ == "__main__":
    print("AI Interview Platform - VOSK Model Setup")
    print("=" * 60)

    # Test existing model first
    if test_existing_model():
        print("\n✅ Existing model is working!")
        sys.exit(0)

    print("\n" + "=" * 60)
    print("📥 Need to download new VOSK model...")
    print("=" * 60)

    # Download new model
    success = download_vosk_model()

    if success:
        print("\n" + "=" * 60)
        print("🎉 SETUP COMPLETE! AI Interview Platform is ready!")
        print("=" * 60)
        print("\n🚀 Next steps:")
        print("1. Update config.py with the model path")
        print("2. Start backend: python main.py")
        print("3. Start frontend: npm start")
        print("4. Test interview at: http://localhost:3000")
    else:
        print("\n" + "=" * 60)
        print("❌ SETUP FAILED!")
        print("=" * 60)
        print("\n💡 Manual setup required:")
        print("1. Download from: https://alphacephei.com/vosk/models")
        print(
            "2. Extract ALL files to: C:\\Users\\lenovo\\Downloads\\vosk-model-small-en-us-0.15"
        )
        print("3. Verify am/final.mdl is ~80 MB")
        print("4. Update config.py")

    sys.exit(0 if success else 1)
