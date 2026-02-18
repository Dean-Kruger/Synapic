
import os

log_file = r"c:\Users\Dean\source\repos\Synapic\logs\synapic.log"
bytes_to_read = 5000

try:
    with open(log_file, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        f.seek(max(file_size - bytes_to_read, 0))
        content = f.read().decode('utf-8', errors='ignore')
        with open("latest_log.txt", "w", encoding="utf-8") as out:
            out.write(content)
        print("Log tail written to latest_log.txt")
except Exception as e:
    print(f"Error reading file: {e}")
