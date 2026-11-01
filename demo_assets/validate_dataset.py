"""
validate_dataset.py

A validation script for the Aletheia demonstration dataset.
Ensures that all images in the `real` and `ai` directories:
- Are valid image files (not corrupted)
- Meet a minimum resolution (e.g., 224x224)
- Have acceptable formats (PNG, JPG, JPEG, WEBP)
- Are not exact file duplicates (checked via SHA-256 hash)

Requirements:
- Python 3
- Pillow (PIL)
"""

import os
import hashlib
from pathlib import Path
from collections import defaultdict
from PIL import Image

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
DIRS_TO_CHECK = [BASE_DIR / "real", BASE_DIR / "ai"]
MIN_RESOLUTION = (224, 224)
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"} # MPO is often used for JPEGs
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

def get_file_hash(filepath: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        # Read in chunks to handle large files efficiently
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def validate_dataset():
    print("Aletheia Demo Dataset Validator")
    print("===============================\n")

    total_files = 0
    valid_files = 0
    errors = []
    
    # Store hashes to detect duplicates
    file_hashes = defaultdict(list)

    for directory in DIRS_TO_CHECK:
        if not directory.exists():
            print(f"[!] Directory not found: {directory}")
            continue

        # Walk through directory and subdirectories
        for root, _, files in os.walk(directory):
            for file in files:
                filepath = Path(root) / file
                
                # Skip non-image files (e.g., .DS_Store, README)
                if filepath.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue

                total_files += 1
                rel_path = filepath.relative_to(BASE_DIR)
                
                try:
                    # 1. Check if image can be opened (not corrupt)
                    with Image.open(filepath) as img:
                        img.verify() # Verify file integrity without fully loading
                    
                    # Reopen to check properties (verify() closes the file)
                    with Image.open(filepath) as img:
                        # 2. Check format
                        if img.format not in ALLOWED_FORMATS:
                            errors.append(f"{rel_path}: Unsupported format '{img.format}'")
                            continue
                        
                        # 3. Check resolution
                        width, height = img.size
                        if width < MIN_RESOLUTION[0] or height < MIN_RESOLUTION[1]:
                            errors.append(f"{rel_path}: Resolution too small ({width}x{height} < {MIN_RESOLUTION[0]}x{MIN_RESOLUTION[1]})")
                            continue

                    # 4. Check for duplicates
                    file_hash = get_file_hash(filepath)
                    file_hashes[file_hash].append(rel_path)

                    valid_files += 1
                except Exception as e:
                    errors.append(f"{rel_path}: Corrupted or unreadable image. ({e})")

    # Process duplicates
    duplicates_found = 0
    for file_hash, paths in file_hashes.items():
        if len(paths) > 1:
            duplicates_found += 1
            errors.append(f"Duplicate found: {paths[0]} is identical to {', '.join(str(p) for p in paths[1:])}")

    # Print summary
    print(f"Total files checked: {total_files}")
    print(f"Valid files:         {valid_files}")
    print(f"Errors/Issues found: {len(errors)}")

    if errors:
        print("\nIssues Details:")
        print("-" * 15)
        for error in errors:
            print(f" - {error}")
        print("\nPlease fix these issues for optimal benchmarking.")
    else:
        print("\n[OK] Dataset is perfectly valid and ready for Aletheia!")

if __name__ == "__main__":
    validate_dataset()
