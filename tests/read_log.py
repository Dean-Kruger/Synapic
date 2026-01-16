from pathlib import Path

log_path = Path(r"c:\Users\deank\.synapic\logs\synapic.log")
if log_path.exists():
    try:
        content = log_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        Path("log_dump.txt").write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        print(f"Error reading log: {e}")
else:
    print(f"Log file not found at {log_path}")
