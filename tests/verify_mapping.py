
import piexif
from pathlib import Path
from src.core import image_processing
import os
import shutil

# Create a dummy image for testing
test_img = Path("test_mapping.jpg")
if test_img.exists(): os.remove(test_img)

# Use PILLOW to create a tiny black image
from PIL import Image
img = Image.new('RGB', (100, 100), color = 'black')
img.save(test_img)

print(f"Created test image: {test_img}")

# Mock data
category = "Architecture"
keywords = ["theatre", "seating", "indoor"]
description = "A wide shot of a theatre with purple seats and lit stairs."

# Run the mapping
print("Applying metadata...")
success = image_processing.write_metadata(test_img, category, keywords, description)

if success:
    print("Metadata written. Reading back...")
    exif_dict = piexif.load(str(test_img))
    
    mapping = {
        "XPSubject (Windows Subject)": piexif.ImageIFD.XPSubject,
        "XPTitle (Windows Title)": piexif.ImageIFD.XPTitle,
        "XPComment (Windows Comments)": piexif.ImageIFD.XPComment,
        "ImageDescription (Standard)": piexif.ImageIFD.ImageDescription
    }
    
    print("\n--- EXIF VERIFICATION ---")
    for name, tag in mapping.items():
        val = exif_dict['0th'].get(tag)
        if val:
            try:
                if isinstance(val, tuple):
                    val = bytes(val)
                
                if name.startswith("XP"):
                    decoded = val.decode('utf-16le').rstrip('\x00')
                else:
                    decoded = val.decode('utf-8')
                print(f"{name}: {decoded}")
            except Exception as e:
                print(f"{name}: [Error decoding: {e}] Raw: {val}")
        else:
            print(f"{name}: MISSING")
else:
    print("Failed to write metadata.")

# Cleanup
if test_img.exists(): os.remove(test_img)
