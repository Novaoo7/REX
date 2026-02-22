import os
import datetime
from pathlib import Path

LOG_DIR = "logs"

Path(LOG_DIR).mkdir(exist_ok=True)

def log_action(source, message, level="INFO", **kwargs):
    log_file = Path(LOG_DIR) / f"{datetime.date.today().isoformat()}.txt"
    with open(log_file, "a") as f:
        f.write(f"[{datetime.datetime.now()}] {source} - {message}\n")

def cleanup_old_logs():
    pass

def get_statistics(days=1):
    return {"total_actions": 0}
