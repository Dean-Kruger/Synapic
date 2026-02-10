
import os

log_path = r'c:\Users\Dean\source\repos\Synapic\logs\synapic.log'
out_path = r'c:\Users\Dean\source\repos\Synapic\log_tail.txt'

try:
    if os.path.exists(log_path):
        with open(log_path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            # Read last 50KB
            seek_pos = max(0, file_size - 51200)
            f.seek(seek_pos)
            content = f.read()
        
        with open(out_path, 'w', encoding='utf-8', errors='ignore') as f_out:
            f_out.write(content.decode('utf-8', errors='ignore'))
            
        print(f"Successfully wrote tail to {out_path}")
    else:
        print(f"Log file not found: {log_path}")

except Exception as e:
    print(f"Error reading log file: {e}")
