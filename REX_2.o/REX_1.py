# ============================================
# FILE: main.py (REX_1.py) - FIXED
# ============================================
from speech import speak
from listener import listen, start_stream, stop_stream
from commands import handle_command
from logger import open_logs, log_action, search_logs
from auth import authenticate
import datetime

# Import REX Brain (Phase 1)
try:
    from rex_brain import get_rex_brain
    BRAIN_AVAILABLE = True
except ImportError:
    BRAIN_AVAILABLE = False
    print("Warning: rex_brain.py not found. Running in basic mode.")

# ===================== AUTHENTICATION =====================
name, role = authenticate()
if not name:
    print("Access Denied")
    exit()

# ===================== INITIALIZE REX BRAIN =====================
if BRAIN_AVAILABLE:
    brain = get_rex_brain()
    memory = brain["memory"]
    conversation = brain["conversation"]
    routines = brain["routines"]
    proactive = brain["proactive"]
    
    # Set user preferences
    memory.set_preference("user_name", name)
    memory.set_preference("user_role", role)
else:
    # Basic context without REX Brain
    memory = None
    conversation = None
    routines = None
    proactive = None

# ===================== STATE SETUP =====================
rex_state = "SLEEP"
WAKE_WORDS = ["rex", "wake up", "hey rex"]
SLEEP_WORDS = ["sleep", "go to sleep", "rest"]

# ===================== START VOICE SYSTEM =====================
speak(f"Welcome {name}. REX 2.0 is online but sleeping.")
speak(f"Your access level is {role}")
start_stream()
log_action("SYSTEM", f"REX 2.0 initialized - User: {name} ({role})")

# Check for proactive suggestions on startup
if BRAIN_AVAILABLE and proactive:
    suggestion = proactive.get_suggestion()
    if suggestion:
        speak(suggestion)

# ===================== MAIN LOOP =====================
try:
    while True:
        result = listen()
        if not result:
            continue
        
        # Unpack command and confidence
        command, confident = result
        
        print("You said:", command)
        if not confident:
            print("⚠️ Low confidence detected")
        
        # ===================== SLEEP MODE =====================
        if rex_state == "SLEEP":
            if any(word in command for word in WAKE_WORDS):
                rex_state = "ACTIVE"
                speak("I am awake and listening")
                log_action("SYSTEM", "REX activated")
                
                # Check for proactive suggestions after waking
                if BRAIN_AVAILABLE and proactive:
                    suggestion = proactive.get_suggestion()
                    if suggestion:
                        speak(suggestion)
            else:
                # Ignore everything while sleeping
                continue
        
        # ===================== ASK_SEARCH_KEYWORD MODE =====================
        elif rex_state == "ASK_SEARCH_KEYWORD":
            keyword = command.strip()
            results = search_logs(keyword)
            
            if results:
                speak(f"Found {len(results)} files with {keyword}")
                print(f"\nLogs containing '{keyword}':")
                for result in results:
                    print(f"  - {result}")
                speak("Say open logs to view a specific date")
            else:
                speak(f"No logs found containing {keyword}")
            
            rex_state = "ACTIVE"
            continue
        
        # ===================== ASK_LOG_DATE MODE =====================
        elif rex_state == "ASK_LOG_DATE":
            # Parse date from command
            if "today" in command:
                date_str = datetime.date.today().isoformat()
            elif "yesterday" in command:
                yesterday = datetime.date.today() - datetime.timedelta(days=1)
                date_str = yesterday.isoformat()
            else:
                # Try to extract date from command
                date_str = command.replace(" ", "-")
            
            # Try to open the log file in Notepad
            if open_logs(date_str):
                speak(f"Opening logs for {date_str}")
                log_action("SYSTEM", f"Opened logs: {date_str}")
            else:
                speak(f"No logs found for {date_str}")
            
            rex_state = "ACTIVE"
            continue
        
        # ===================== ACTIVE MODE =====================
        elif rex_state == "ACTIVE":
            # ---- Check if in conversation state ----
            if BRAIN_AVAILABLE and conversation and conversation.current_state != "IDLE":
                action, data = conversation.handle_input(command)
                
                if action == "WAIT":
                    continue
                elif action == "CANCEL":
                    continue
                elif action == "PROCESS_COMMAND":
                    command = data
                else:
                    pass
            
            # ---- Check for Routine Commands BEFORE context resolution ----
            if BRAIN_AVAILABLE and routines:
                if "routine" in command or ("mode" in command and "work" in command):
                    if "morning" in command:
                        routines.execute_routine("morning", lambda t, d: handle_command(f"open {d}", name, role, listen))
                        continue
                    elif "work" in command:
                        routines.execute_routine("work", lambda t, d: handle_command(f"open {d}", name, role, listen))
                        continue
                    elif "sleep mode" in command:
                        routines.execute_routine("sleep", lambda t, d: None)
                        rex_state = "SLEEP"
                        continue
            
            # ---- Check for EXIT commands BEFORE context resolution ----
            if any(exit_word in command for exit_word in ["exit", "shutdown rex", "quit rex", "close rex"]):
                # Don't apply context resolution to exit commands
                result = handle_command(command, name, role, listen_func=listen)
                if result is False:
                    break
                continue
            
            # ---- Resolve Context References (ONLY for non-exit commands) ----
            original_command = command
            if BRAIN_AVAILABLE and memory:
                command = memory.resolve_reference(command)
                
                if command != original_command:
                    speak(f"I understand you mean {command}")
            
            # ---- Sleep Command ----
            if any(word in command for word in SLEEP_WORDS):
                speak("Going to sleep. Say rex to wake me")
                log_action("SYSTEM", "REX deactivated")
                rex_state = "SLEEP"
                continue
            
            # ---- Confidence Check (Human-like clarification) ----
            if not confident:
                speak(f"Did you mean {command}? Please say yes or no")
                confirmation_result = listen()
                
                if not confirmation_result:
                    speak("I didn't hear you. Cancelling")
                    continue
                
                confirmation, _ = confirmation_result
                
                if "yes" not in confirmation and "yeah" not in confirmation and "sure" not in confirmation:
                    speak("Okay, cancelled")
                    log_action("SYSTEM", f"Low confidence command cancelled: {command}")
                    continue
                else:
                    speak("Understood")
                    log_action("SYSTEM", f"Low confidence command confirmed: {command}")
            
            # ---- Update Context Memory ----
            if BRAIN_AVAILABLE and memory:
                if "open" in command:
                    if "notepad" in command:
                        memory.update_short_term(command, "open_app", "notepad")
                    elif "chrome" in command or "browser" in command:
                        memory.update_short_term(command, "open_app", "chrome")
                    elif "calculator" in command:
                        memory.update_short_term(command, "open_app", "calculator")
                else:
                    memory.update_short_term(command)
            
            # ---- Normal Commands (with role-based permissions) ----
            result = handle_command(command, name, role, listen_func=listen)
            
            if result == "ASK_LOG_DATE":
                rex_state = "ASK_LOG_DATE"
            elif result == "ASK_SEARCH_KEYWORD":
                rex_state = "ASK_SEARCH_KEYWORD"
            elif result is False:
                break

# ===================== SHUTDOWN =====================
finally:
    speak("System shutting down")
    stop_stream()
    
    # Save REX Brain state
    if BRAIN_AVAILABLE:
        if memory:
            memory.save_long_term()
        if routines:
            routines.save_routines()
    
    log_action("SYSTEM", "REX 2.0 shutdown complete")
    print("REX 2.0 shutdown complete")