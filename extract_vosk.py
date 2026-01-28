import os
import zipfile
import tarfile
import shutil


def extract_vosk_model():
    print("🔧 Setting up VOSK Model for AI Interview Platform")
    print("=" * 60)

    # Paths
    download_dir = r"D:\\Downloads\\vosk-model-small-en-us-0.15.zip"
    model_zip = os.path.join(download_dir, "vosk-model-small-en-us-0.15.zip")
    model_tar = os.path.join(download_dir, "vosk-model-small-en-us-0.15.tar.gz")
    extracted_dir = os.path.join(download_dir, "vosk-model-small-en-us-0.15")

    print(f"Download directory: {download_dir}")
    print(f"Extracted directory: {extracted_dir}")

    # Check what files exist
    print("\n📁 Checking downloaded files...")
    files = os.listdir(download_dir)
    vosk_files = [f for f in files if "vosk" in f.lower()]

    print("Found VOSK-related files:")
    for f in vosk_files:
        print(f"  - {f}")

    # If already extracted but wrong structure
    if os.path.exists(extracted_dir):
        print(f"\n📂 Found existing folder: {extracted_dir}")
        contents = os.listdir(extracted_dir)
        print(f"Contents: {contents}")

        # Check if it's just the zip file inside
        if len(contents) == 1 and contents[0].endswith(".zip"):
            print("⚠️ Found zip inside folder - need to extract again")
            inner_zip = os.path.join(extracted_dir, contents[0])
            shutil.rmtree(extracted_dir)
            print("✅ Removed old structure")

    # Extract from zip
    if os.path.exists(model_zip):
        print(f"\n📦 Found ZIP file: {model_zip}")
        print("Extracting...")

        try:
            with zipfile.ZipFile(model_zip, "r") as zip_ref:
                zip_ref.extractall(download_dir)
            print("✅ Extraction complete!")
        except Exception as e:
            print(f"❌ Extraction error: {e}")

    # Extract from tar.gz
    elif os.path.exists(model_tar):
        print(f"\n📦 Found TAR.GZ file: {model_tar}")
        print("Extracting...")

        try:
            with tarfile.open(model_tar, "r:gz") as tar_ref:
                tar_ref.extractall(download_dir)
            print("✅ Extraction complete!")
        except Exception as e:
            print(f"❌ Extraction error: {e}")
    else:
        print("\n❌ No VOSK model archive found!")
        print("\n📥 Please download the model from:")
        print("https://alphacephei.com/vosk/models")
        print("\n📋 Choose: 'vosk-model-small-en-us-0.15'")
        print("\n💡 Save it to: C:\\Users\\lenovo\\Downloads")
        return

    # Verify extraction
    print("\n🔍 Verifying extracted structure...")

    # The extracted folder might have a different name
    possible_folders = ["vosk-model-small-en-us-0.15", "vosk-model-en-us-0.15", "model"]

    actual_folder = None
    for folder in possible_folders:
        folder_path = os.path.join(download_dir, folder)
        if os.path.exists(folder_path):
            actual_folder = folder_path
            break

    if not actual_folder:
        # List what was extracted
        print("Looking for extracted folders...")
        extracted_items = [
            f
            for f in os.listdir(download_dir)
            if os.path.isdir(os.path.join(download_dir, f))
        ]
        print(f"Found directories: {extracted_items}")

        if extracted_items:
            actual_folder = os.path.join(download_dir, extracted_items[0])
        else:
            print("❌ No folders extracted!")
            return

    print(f"✅ Found model folder: {actual_folder}")

    # Rename to standard name if needed
    if os.path.basename(actual_folder) != "vosk-model-small-en-us-0.15":
        new_path = os.path.join(download_dir, "vosk-model-small-en-us-0.15")
        if os.path.exists(new_path):
            shutil.rmtree(new_path)
        os.rename(actual_folder, new_path)
        actual_folder = new_path
        print(f"✅ Renamed to: {actual_folder}")

    # Check structure
    print("\n📁 Checking model structure...")

    critical_files = [
        ("am/final.mdl", "Model file"),
        ("graph/phones.txt", "Phoneme dictionary"),
        ("conf/model.conf", "Configuration file"),
        ("ivector/final.dubm", "iVector file"),
    ]

    all_good = True
    for file_path, description in critical_files:
        full_path = os.path.join(actual_folder, file_path)
        exists = os.path.exists(full_path)
        status = "✅" if exists else "❌"
        print(f"{status} {file_path}: {description} - {exists}")
        if not exists:
            all_good = False

    if all_good:
        print("\n🎉 VOSK model is ready for AI Interview Platform!")
        print(f"\n📍 Update your config.py with this path:")
        print(f'VOSK_MODEL_PATH = r"{actual_folder}"')
    else:
        print("\n⚠️ Some files are missing. Model might be corrupted.")
        print("\n🔄 Try downloading again from:")
        print("https://alphacephei.com/vosk/models")

    print(f"\n📂 Final model path: {actual_folder}")
    print(
        f" Total size: {
            sum(
                os.path.getsize(os.path.join(actual_folder, f))
                for f in os.listdir(actual_folder)
                if os.path.isfile(os.path.join(actual_folder, f))
            )
            / 1024
            / 1024:.1f} MB"
    )


if __name__ == "__main__":
    extract_vosk_model()
