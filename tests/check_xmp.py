
from pathlib import Path

img_path = r"C:/Users/deank/.gemini/antigravity/brain/2d8363ff-920d-47f8-8cbd-add7a7ee80e2/uploaded_image_1768472113163.jpg"

def check_xmp(path):
    print(f"Checking XMP in {path}")
    try:
        with open(path, 'rb') as f:
            data = f.read()
            xmp_start = data.find(b'<x:xmpmeta')
            xmp_end = data.find(b'</x:xmpmeta>')
            if xmp_start != -1 and xmp_end != -1:
                xmp_str = data[xmp_start:xmp_end+12].decode('utf-8', errors='ignore')
                print("--- XMP FOUND ---")
                print(xmp_str[:1000]) # Print first 1000 chars
                if "Test Decsription" in xmp_str:
                    print("\nFOUND 'Test Decsription' in XMP!")
                else:
                    print("\n'Test Decsription' NOT found in XMP.")
            else:
                print("No XMP packet found.")
                
            # Search for the string anywhere in the binary
            pos = data.find(b"Test Decsription")
            if pos != -1:
                print(f"FOUND 'Test Decsription' at binary position {pos}")
                # Print context
                start = max(0, pos - 50)
                end = min(len(data), pos + 100)
                print(f"Context: {data[start:end]}")
            else:
                 print("'Test Decsription' NOT found in binary.")

    except Exception as e:
        print(f"Error: {e}")

check_xmp(img_path)
