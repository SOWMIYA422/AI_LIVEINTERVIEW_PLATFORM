import os
import sys
from vosk import Model

print("=== MANUAL VOSK TEST ===")
model_path = r"D:\\Downloads\\vosk-model-small-en-us-0.15"

print(f"Checking path: {model_path}")
print(f"Exists: {os.path.exists(model_path)}")

if os.path.exists(model_path):
    try:
        model = Model(model_path)
        print("✅ VOSK MODEL LOADED SUCCESSFULLY!")
        
        # Check model files
        print("\nModel structure:")
        for item in os.listdir(model_path):
            item_path = os.path.join(model_path, item)
            if os.path.isdir(item_path):
                print(f"📁 {item}/")
            else:
                print(f"📄 {item}")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
else:
    print("❌ PATH DOES NOT EXIST!")