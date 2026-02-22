import os
import datetime
from speech import speak
from logger import log_action

class CommandResult:
    CONTINUE = "CONTINUE"
    EXIT = "EXIT"
    NEED_INPUT = "NEED_INPUT"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

def handle_command(command, intent, entities, confidence, user_name, user_role, listen_func=None):
    log_action("USER", command)

    if "hello" in command:
        speak(f"Hello {user_name}")
        return CommandResult.SUCCESS, None

    elif "time" in command:
        now = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {now}")
        return CommandResult.SUCCESS, None

    elif "open notepad" in command:
        speak("Opening Notepad")
        os.system("start notepad")
        return CommandResult.SUCCESS, None

    elif "exit" in command:
        speak("Goodbye")
        return CommandResult.EXIT, None

    else:
        speak("Command not recognized")
        return CommandResult.FAILED, None
