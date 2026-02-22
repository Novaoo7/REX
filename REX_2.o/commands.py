# ============================================
# FILE: commands.py - FIXED
# ============================================

import os
import datetime
from speech import speak
from logger import log_action, list_all_log_files, search_logs
from auth import has_permission

# Import system control module
try:
    from system_control import (
        open_item, create_folder, delete_item,
        open_camera, test_microphone, open_settings
    )
    SYSTEM_CONTROL_AVAILABLE = True
except ImportError:
    SYSTEM_CONTROL_AVAILABLE = False
    print("Warning: system_control.py not found. Advanced features disabled.")

# Import advanced modules
try:
    from rex_advanced import get_advanced_modules
    modules = get_advanced_modules()
    ADVANCED_FEATURES = True
except ImportError:
    ADVANCED_FEATURES = False
    print("Warning: rex_advanced.py not found. Some features disabled.")

# -------------------------------------------------
# COMMAND GROUPS (ALIASES)
# -------------------------------------------------
CHECK = ["rex"]

GREETINGS = ["hello", "hi", "hey", "greetings"]

TIME_COMMANDS = ["time", "current time", "what time", "tell me the time"]

DATE_COMMANDS = ["date", "today", "today date", "what date", "what's the date"]

OPEN_NOTEPAD = ["open notepad", "start notepad", "launch notepad"]

OPEN_CHROME = [
    "open chrome", "start chrome", "launch chrome",
    "open browser", "start browser", "open google"
]

OPEN_CALCULATOR = ["open calculator", "open calc", "start calc", "launch calculator"]

SHOW_LOGS = ["show all logs", "list logs", "show logs"]

OPEN_LOGS = ["open logs", "view logs"]

SEARCH_LOGS = ["search logs", "find logs", "search in logs"]

SLEEP_COMMANDS = ["sleep", "go to sleep", "rest", "sleep mode"]

EXIT_COMMANDS = ["exit", "shutdown rex", "quit rex", "close rex"]

# -------------------------------------------------
# CONFIRMATION HANDLER
# -------------------------------------------------

def confirm_action(question, listen_func):
    """
    Ask user for yes/no confirmation
    Returns True if confirmed, False otherwise
    """
    speak(question)
    result = listen_func()
    
    if not result:
        speak("Cancelled")
        return False
    
    reply, _ = result

    if reply and any(word in reply for word in ["yes", "yeah", "confirm", "sure", "ok", "okay"]):
        log_action("USER", f"Confirmed: {reply}")
        return True

    speak("Cancelled")
    log_action("USER", f"Cancelled: {reply}")
    return False


# -------------------------------------------------
# MAIN COMMAND HANDLER
# -------------------------------------------------

def handle_command(command, name, role, listen_func=None):
    """
    Process voice commands with permission checking and advanced features
    """
    log_action("USER", command)
    
    # ============== PERMISSION CHECK ==============
    if not has_permission(role, command):
        speak("You do not have permission to do that")
        log_action("SYSTEM", f"Permission denied for {name} ({role}): {command}")
        return True
    
    # ============== EXIT COMMANDS (Handle FIRST) ==============
    if any(cmd in command for cmd in EXIT_COMMANDS):
        if not listen_func:
            speak(f"Goodbye {name}")
            return False

        if confirm_action("Do you want to shut down REX?", listen_func):
            speak(f"Goodbye {name}")
            log_action("SYSTEM", "REX shutdown initiated")
            return False
        else:
            return True
    
    # ============== BASIC COMMANDS ==============

    if any(word in command for word in GREETINGS):
        hour = datetime.datetime.now().hour
        if hour < 12:
            speak(f"Good morning {name}")
        elif hour < 18:
            speak(f"Good afternoon {name}")
        else:
            speak(f"Good evening {name}")

    elif any(word in command for word in CHECK):
        speak(f"Yes sir")

    elif any(word in command for word in TIME_COMMANDS):
        now = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {now}")

    elif any(word in command for word in DATE_COMMANDS):
        today = datetime.date.today().strftime("%B %d, %Y")
        speak(f"Today is {today}")

    # ============== BASIC OPEN APPLICATIONS ==============

    elif any(cmd in command for cmd in OPEN_NOTEPAD):
        speak("Opening Notepad")
        os.system("start notepad")
        log_action("SYSTEM", "Opened Notepad")

    elif any(cmd in command for cmd in OPEN_CHROME):
        speak("Opening Chrome")
        os.system("start chrome")
        log_action("SYSTEM", "Opened Chrome")

    elif any(cmd in command for cmd in OPEN_CALCULATOR):
        speak("Opening Calculator")
        os.system("start calc")
        log_action("SYSTEM", "Opened Calculator")

    # ============== LOG COMMANDS ==============

    elif any(cmd in command for cmd in SHOW_LOGS):
        log_files = list_all_log_files()
        if log_files:
            speak(f"Found {len(log_files)} log files")
            print("\nAvailable log files:")
            for log_file in log_files:
                print(f"  - {log_file}")
            speak("Say open logs and specify a date")
        else:
            speak("No log files found")

    elif any(cmd in command for cmd in SEARCH_LOGS):
        speak("What do you want to search for?")
        return "ASK_SEARCH_KEYWORD"

    elif any(cmd in command for cmd in OPEN_LOGS):
        speak("Which date? Say today, yesterday, or a specific date")
        return "ASK_LOG_DATE"

    # ============== CLOSE APPLICATIONS (ADMIN ONLY) ==============

    elif command.startswith("close "):
        if not listen_func:
            speak("Confirmation not available")
            return True

        app = command.replace("close ", "").strip()

        app_map = {
            "notepad": "notepad.exe",
            "chrome": "chrome.exe",
            "browser": "chrome.exe",
            "google": "chrome.exe",
            "vscode": "Code.exe",
            "code": "Code.exe",
            "edge": "msedge.exe",
            "calculator": "Calculator.exe",
            "calc": "Calculator.exe"
        }

        if app in app_map:
            if confirm_action(f"Do you want me to close {app}?", listen_func):
                speak(f"Closing {app}")
                os.system(f"taskkill /f /im {app_map[app]}")
                log_action("SYSTEM", f"Closed {app}")
        else:
            speak("Unknown application")

    # ============== ADVANCED FEATURES ==============
    
    elif ADVANCED_FEATURES:
        result = handle_advanced_features(command, name, role, listen_func)
        if result is not None:
            return result
        else:
            # If advanced features didn't handle it, try system control
            if SYSTEM_CONTROL_AVAILABLE:
                return handle_system_control(command, name, role, listen_func)
            else:
                speak("Command not recognized")
    
    # ============== SYSTEM CONTROL COMMANDS ==============
    elif SYSTEM_CONTROL_AVAILABLE:
        return handle_system_control(command, name, role, listen_func)
    
    else:
        speak("Command not recognized")
    
    return True


def handle_advanced_features(command, name, role, listen_func):
    """Handle advanced features from rex_advanced.py"""
    
    # ---- EMAIL COMMANDS ----
    if "check email" in command or "check inbox" in command:
        modules["email"].check_inbox()
        return True
    
    # ---- CALENDAR COMMANDS ----                                   
    elif "what's on my calendar" in command or "schedule today" in command:
        modules["calendar"].speak_today_schedule()
        return True
    
    # ---- WEB SEARCH ----
    elif "search for" in command or ("search" in command and "logs" not in command):
        query = command.replace("search for", "").replace("search", "").strip()
        if query:
            modules["web"].search_web(query)
            return True
    
    elif "weather" in command:
        location = command.replace("weather", "").replace("in", "").strip()
        modules["web"].get_weather(location if location else "current")
        return True
    
    elif "news" in command:
        topic = command.replace("news", "").replace("about", "").strip()
        modules["web"].get_news(topic if topic else "headlines")
        return True
    
    # ---- MUSIC CONTROL ----
    elif "play music" in command or ("play" in command and "music" not in command):
        query = command.replace("play music", "").replace("play", "").strip()
        modules["media"].play_music(query if query else None)
        return True
    
    elif "pause" in command:
        modules["media"].control_playback("pause")
        return True
    
    # ---- REMINDERS ----
    elif "remind me" in command:
        text = command.replace("remind me to", "").replace("remind me", "").strip()
        if text:
            modules["reminders"].add_reminder(text)
        return True
    
    # ---- KNOWLEDGE BASE ----
    elif "remember that" in command:
        text = command.replace("remember that", "").strip()
        if " is " in text:
            key, value = text.split(" is ", 1)
            modules["smart"].remember_fact(key.strip(), value.strip())
        return True
    
    elif "what is" in command:
        key = command.replace("what is", "").strip()
        modules["smart"].recall_fact(key)
        return True
    
    # ---- SYSTEM OPTIMIZATION ----
    elif "system health" in command:
        modules["optimizer"].check_system_health()
        return True
    
    elif "clean temp" in command:
        modules["optimizer"].clean_temp_files()
        return True
    
    # Not handled by advanced features
    return None


def handle_system_control(command, name, role, listen_func):
    """Handle system control commands"""
    
    # ---- OPEN FILE/FOLDER/APP (Advanced Search) ----
    if command.startswith("open ") or command.startswith("start ") or command.startswith("launch "):
        query = command.replace("open ", "").replace("start ", "").replace("launch ", "").strip()
        
        # Skip if already handled by basic commands
        if query not in ["notepad", "chrome", "browser", "calculator", "calc"]:
            open_item(query, listen_func)
            return True
    
    # ---- CREATE FOLDER ----
    elif "create folder" in command or "make folder" in command:
        folder_name = command.replace("create folder", "").replace("make folder", "").strip()
        
        if folder_name:
            speak(f"Creating folder: {folder_name}")
            create_folder(folder_name)
        else:
            speak("Please specify a folder name")
        return True
    
    # ---- DELETE FILE/FOLDER ----
    elif "delete " in command or "remove " in command:
        query = command.replace("delete ", "").replace("remove ", "").strip()
        
        if query:
            delete_item(query, listen_func)
        else:
            speak("Please specify what to delete")
        return True
    
    # ---- CAMERA CONTROL ----
    elif "open camera" in command or "start camera" in command:
        open_camera(listen_func)
        return True
    
    # ---- MICROPHONE TEST ----
    elif "test microphone" in command or "test mic" in command:
        test_microphone()
        return True
    
    # ---- SYSTEM SETTINGS ----
    elif "open settings" in command:
        setting_type = command.replace("open ", "").strip()
        open_settings(setting_type, listen_func)
        return True
    
    elif "control panel" in command:
        open_settings("control panel", listen_func)
        return True
    
    elif "task manager" in command:
        open_settings("task manager", listen_func)
        return True
    
    else:
        speak("Command not recognized")
        return True