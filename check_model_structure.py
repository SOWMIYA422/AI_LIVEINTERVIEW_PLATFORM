# backend/check_model_structure.py
import os

model_path = r"D:\Downloads\vosk-model-small-en-us-0.15"

print("🔍 Checking Vosk model structure...")
print(f"Path: {model_path}")
print(f"Exists: {os.path.exists(model_path)}")

if os.path.exists(model_path):
    print("\n📁 Contents:")
    for item in os.listdir(model_path):
        item_path = os.path.join(model_path, item)
        if os.path.isdir(item_path):
            print(f"  📂 {item}/")
            try:
                subitems = os.listdir(item_path)[:3]  # Show first 3 items
                for sub in subitems:
                    print(f"    📄 {sub}")
                if len(os.listdir(item_path)) > 3:
                    print(f"    ... and {len(os.listdir(item_path)) - 3} more")
            except:
                pass
        else:
            print(f"  📄 {item}")

    # Check for critical files
    print("\n🔍 Checking for required model files:")
    critical_files = [
        "am/final.mdl",
        "graph/phones.txt",
        "ivector/final.dubm",
        "conf/model.conf",
    ]

    all_good = True
    for file in critical_files:
        full_path = os.path.join(model_path, file)
        exists = os.path.exists(full_path)
        status = "✅" if exists else "❌"
        print(f"{status} {file}: {exists}")
        if not exists:
            all_good = False

    if all_good:
        print("\n🎉 Model structure looks correct!")
    else:
        print("\n⚠️ Some files are missing. The model might be corrupted.")
else:
    print("\n❌ Path does not exist!")
