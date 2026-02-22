# ============================================
# FILE: logger.py
# ============================================
import os
import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def log_action(source, message):
    """Log action with timestamp to date-specific file"""
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    file_path = os.path.join(LOG_DIR, f"{today}.txt")

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {source}: {message}\n")

def open_logs(date_str):
    """Open log file in Notepad for specified date"""
    file_path = os.path.join(LOG_DIR, f"{date_str}.txt")
    
    # Get absolute path
    abs_path = os.path.abspath(file_path)
    
    if os.path.exists(abs_path):
        os.system(f'notepad "{abs_path}"')
        return True
    else:
        return False

def list_all_log_files():
    """Get list of all available log dates"""
    if not os.path.exists(LOG_DIR):
        return []
    
    log_files = [f.replace(".txt", "") for f in os.listdir(LOG_DIR) if f.endswith(".txt")]
    return sorted(log_files, reverse=True)  # Most recent first

def search_logs(keyword):
    """Search for keyword in all log files"""
    results = []
    
    for log_file in list_all_log_files():
        file_path = os.path.join(LOG_DIR, f"{log_file}.txt")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if keyword.lower() in content.lower():
                results.append(log_file)
    
    return results


# ============================================
# FILE: auth.py
# ============================================
import json
from speech import speak

USERS_FILE = "users.json"

def get_user_role(username):
    """
    Get the role of a user from users.json
    Returns: 'admin', 'user', or 'guest'
    """
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
        role = users.get(username.lower(), "guest")
        return role
    except FileNotFoundError:
        print(f"Warning: {USERS_FILE} not found. Creating default file...")
        create_default_users_file()
        return "guest"

def create_default_users_file():
    """
    Create a default users.json file if it doesn't exist
    """
    default_users = {
        "veer": "admin",
        "admin": "admin",
        "test": "user",
        "guest": "guest"
    }
    with open(USERS_FILE, "w") as f:
        json.dump(default_users, f, indent=4)
    print(f"Created default {USERS_FILE}")

def has_permission(role, command):
    """
    Check if a user role has permission to execute a command
    
    Permission levels:
    - admin: Full access (all commands)
    - user: Normal commands (no close, shutdown, exit)
    - guest: Read-only (hello, time, date, logs view only)
    """
    # Restricted commands (admin only)
    restricted_keywords = [
        "close",
        "shutdown",
        "exit",
        "quit"
    ]
    
    # Guest allowed commands (very limited)
    guest_allowed = [
        "hello", "hi", "hey", "greetings",
        "time", "date", "today", "yesterday",
        "show", "list", "logs"  # View logs only
    ]
    
    # Admin has full access
    if role == "admin":
        return True
    
    # User can do everything except restricted commands
    if role == "user":
        return not any(word in command for word in restricted_keywords)
    
    # Guest can only do read-only commands
    if role == "guest":
        return any(word in command for word in guest_allowed)
    
    return False

def authenticate():
    """Handle user authentication"""
    name = input("Enter your username: ")
    print(f"Hello {name}, system online.")

    code = int(input("Enter your code: "))

    if code != 20:
        print("Access Denied")
        return None, None

    print("Access Granted")

    for i in range(2):
        print("REX test cycle", i + 1)

    # Get user role
    role = get_user_role(name)
    print(f"User role: {role}")

    return name, role
