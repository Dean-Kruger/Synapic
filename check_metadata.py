
import piexif
from iptcinfo3 import IPTCInfo
from pathlib import Path
import logging

# Disable IPTC logging to avoid noise
logging.getLogger('iptcinfo').setLevel(logging.ERROR)

img_path = r"C:/Users/deank/.gemini/antigravity/brain/2d8363ff-920d-47f8-8cbd-add7a7ee80e2/uploaded_image_1768472113163.jpg"

def read_metadata(path):
    print(f"Checking all metadata for: {path}")
    
    # Check EXIF
    try:
        exif_dict = piexif.load(path)
        print("\n--- EXIF ---")
        for ifd in ("0th", "Exif", "GPS", "1st"):
            for tag in exif_dict.get(ifd, {}):
                try:
                    tag_name = piexif.TAGS[ifd][tag]["name"]
                    val = exif_dict[ifd][tag]
                    print(f"{ifd}.{tag_name}: {val}")
                except KeyError:
                    print(f"{ifd}.Tag({tag}): {exif_dict[ifd][tag]}")
    except Exception as e:
        print(f"Error reading EXIF: {e}")

    # Check IPTC
    try:
        info = IPTCInfo(path, force=True)
        print("\n--- IPTC ---")
        for key in info._data:
            val = info[key]
            if val:
                print(f"{key}: {val}")
    except Exception as e:
        print(f"Error reading IPTC: {e}")

read_metadata(img_path)
