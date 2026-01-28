import os

model_path = "."  # current directory

required_dirs = ["am", "conf", "graph"]
required_conf_files = ["mfcc.conf", "model.conf", "words.txt"]

print("Checking VOSK model structure...")
print("=" * 40)

# Check directories
for dir_name in required_dirs:
    dir_path = os.path.join(model_path, dir_name)
    if os.path.isdir(dir_path):
        print(f"✓ Found: {dir_name}/")
        # List first few files
        files = os.listdir(dir_path)[:3]
        print(f"  Sample files: {files}")
    else:
        print(f"✗ Missing: {dir_name}/")

print("\nChecking configuration files...")
conf_path = os.path.join(model_path, "conf")
if os.path.isdir(conf_path):
    for file_name in required_conf_files:
        file_path = os.path.join(conf_path, file_name)
        if os.path.isfile(file_path):
            print(f"✓ Found: conf/{file_name}")
        else:
            print(f"✗ Missing: conf/{file_name}")

# Check for model size indicators
print("\n" + "=" * 40)
total_size = 0
for dirpath, dirnames, filenames in os.walk(model_path):
    for f in filenames:
        fp = os.path.join(dirpath, f)
        total_size += os.path.getsize(fp)
print(f"Total model size: {total_size / (1024 * 1024):.1f} MB")
print("=" * 40)
