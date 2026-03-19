"""
Development Log Tail Helper
===========================

This small utility copies the last portion of the application's primary log
file into a local text file for quick inspection.

Why it exists:
- Speeds up manual debugging when the full log is large.
- Produces a lightweight artifact (`latest_log.txt`) that can be shared or
  attached to an issue without exposing the entire log history.
- Avoids having to remember the exact PowerShell or shell command to tail the
  bundled application log.

This script is intentionally simple and is meant for local developer use.
"""

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
