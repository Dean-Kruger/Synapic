
from PIL import Image
from PIL.ExifTags import TAGS
from pathlib import Path

img_path = r"C:/Users/deank/.gemini/antigravity/brain/2d8363ff-920d-47f8-8cbd-add7a7ee80e2/uploaded_image_1768472113163.jpg"

def dump_exif(path):
    print(f"Dumping EXIF for {path}")
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                print("No EXIF found")
                # Try image info
                print(f"Image info: {img.info}")
                return
            
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                print(f"{tag}: {value}")
    except Exception as e:
        print(f"Error: {e}")

dump_exif(img_path)
