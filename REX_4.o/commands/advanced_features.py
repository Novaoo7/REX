# ==============================================================================
# commands/advanced_features.py   –  REX 4.0   Advanced / Intelligent Commands
# ==============================================================================
# Design
#   • Web search: opens the default browser to a Google search URL.  No API
#     key required – fully offline-friendly (the browser handles the request).
#   • Reminders / alarms: stored in memory/reminders.json and checked by the
#     ProactiveEngine every tick.  The helpers here just persist them.
#   • Email: delegates to the OS default mail-to: handler via webbrowser.
#   • Routines: thin wrapper around RoutineEngine (intelligence layer).
#   • User management: delegates to AuthManager.
#
# Every method returns a CommandResult; nothing raises.
# ==============================================================================

from __future__ import annotations

import json
import re
import time
import webbrowser
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from commands.types import CommandResult
from core.intent import IntentResult
from core.config import get_config
from core.logger import get_logger, LogCategory
from core.auth   import get_auth


# ─── Reminder persistence ────────────────────────────────────────────────────


@dataclass
class Reminder:
    id:         int
    text:       str
    due_at:     float          # epoch
    created_at: float          # epoch
    triggered:  bool = False

    def to_dict(self) -> dict:  return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Reminder":
        return cls(**d)


def _reminder_path() -> Path:
    return Path(get_config().paths.memory_dir) / "reminders.json"


def _load_reminders() -> List[Reminder]:
    p = _reminder_path()
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return [Reminder.from_dict(r) for r in json.load(fh)]
    except (json.JSONDecodeError, KeyError, OSError):
        return []


def _save_reminders(reminders: List[Reminder]) -> None:
    p = _reminder_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump([r.to_dict() for r in reminders], fh, indent=2)


def _next_reminder_id(reminders: List[Reminder]) -> int:
    return max((r.id for r in reminders), default=0) + 1


# ─── Time parsing ─────────────────────────────────────────────────────────────


def _parse_time_offset(text: str) -> Optional[float]:
    """
    Best-effort extraction of a future epoch from phrases like
    "in 5 minutes", "in 2 hours", "at 3 pm", "tomorrow".
    Returns epoch or None.
    """
    text = text.lower()
    now  = time.time()

    # "in X minutes / hours / seconds"
    m = re.search(r"in\s+(\d+)\s*(minute|hour|second|min|hr|sec)s?", text)
    if m:
        amount = int(m.group(1))
        unit   = m.group(2)
        if unit.startswith("min"):  return now + amount * 60
        if unit.startswith("hr") or unit.startswith("hour"):  return now + amount * 3600
        if unit.startswith("sec"):  return now + amount
        return now + amount * 60   # default minutes

    # "tomorrow"
    if "tomorrow" in text:
        return now + 86400

    # "at HH:MM" or "at H am/pm"
    m = re.search(r"at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", text)
    if m:
        hour   = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm   = m.group(3)
        if ampm == "pm" and hour != 12:  hour += 12
        if ampm == "am" and hour == 12:  hour = 0
        dt = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt.timestamp() < now:
            dt = dt.replace(day=dt.day + 1)   # push to tomorrow
        return dt.timestamp()

    # fallback: 10 minutes
    return now + 600


# ─── AdvancedCommands ─────────────────────────────────────────────────────────


class AdvancedCommands:
    """
    Hosts every command that goes beyond simple OS operations.
    """

    def __init__(self) -> None:
        self._logger = get_logger()
        self._cfg    = get_config()

    # ── web search ────────────────────────────────────────────────────────
    def web_search(self, intent: IntentResult, _token: str) -> CommandResult:
        query = intent.parameters.get("query", "").strip()
        if not query:
            return CommandResult(success=False,
                                 message="What would you like me to search for?")

        url = f"https://www.google.com/search?q={quote(query)}"
        try:
            webbrowser.open(url)
            self._logger.info(LogCategory.COMMAND, f"Web search: {query}")
            return CommandResult(success=True, message=f"Searching for {query}.")
        except Exception as exc:
            return CommandResult(success=False,
                                 message=f"I couldn't open the browser: {exc}",
                                 error=str(exc))

    # ── reminders ─────────────────────────────────────────────────────────
    def set_reminder(self, intent: IntentResult, _token: str) -> CommandResult:
        text = intent.parameters.get("reminder", "").strip()
        if not text:
            return CommandResult(success=False,
                                 message="What would you like me to remind you about?")

        reminders = _load_reminders()
        due       = _parse_time_offset(text)

        # strip the time portion from the reminder text for cleaner storage
        clean = re.sub(r"(in \d+ \w+|at \d+[:\d]* (am|pm)?|tomorrow)", "", text).strip()
        if not clean:
            clean = text

        reminder = Reminder(
            id=_next_reminder_id(reminders),
            text=clean,
            due_at=due,
            created_at=time.time(),
        )
        reminders.append(reminder)
        _save_reminders(reminders)

        when = datetime.fromtimestamp(due).strftime("%I:%M %p") if due else "later"
        self._logger.info(LogCategory.COMMAND, f"Reminder set: '{clean}' at {when}")
        return CommandResult(success=True,
                             message=f"Reminder set: {clean}. I'll remind you at {when}.")

    # ── alarms ────────────────────────────────────────────────────────────
    def set_alarm(self, intent: IntentResult, _token: str) -> CommandResult:
        text = intent.parameters.get("reminder", "").strip()
        if not text:
            return CommandResult(success=False, message="What time should I set the alarm for?")

        due = _parse_time_offset(text)
        reminders = _load_reminders()
        alarm = Reminder(
            id=_next_reminder_id(reminders),
            text="⏰ Alarm",
            due_at=due,
            created_at=time.time(),
        )
        reminders.append(alarm)
        _save_reminders(reminders)

        when = datetime.fromtimestamp(due).strftime("%I:%M %p") if due else "the requested time"
        return CommandResult(success=True, message=f"Alarm set for {when}.")

    # ── email ─────────────────────────────────────────────────────────────
    def send_email(self, intent: IntentResult, _token: str) -> CommandResult:
        # We open the OS default mail client via mailto:
        # Full compose (to / subject / body) would need more NLU; for now we
        # just open the compose window and tell the user to fill it in.
        try:
            webbrowser.open("mailto:")
            return CommandResult(success=True,
                                 message="I've opened your email client. Please compose your message.")
        except Exception as exc:
            return CommandResult(success=False,
                                 message=f"I couldn't open the email client: {exc}",
                                 error=str(exc))

    # ── routines ──────────────────────────────────────────────────────────
    def run_routine(self, intent: IntentResult, _token: str) -> CommandResult:
        from intelligence.routines import RoutineEngine

        name = intent.parameters.get("routine_name", "").strip()
        if not name:
            return CommandResult(success=False,
                                 message="Which routine would you like me to run?")

        engine = RoutineEngine()
        result = engine.execute(name)
        if result["success"]:
            return CommandResult(success=True,
                                 message=f"Running the {name} routine.")
        return CommandResult(success=False,
                             message=result.get("message", f"I don't have a routine called '{name}'."),
                             error=result.get("error"))

    def list_routines(self, _intent: IntentResult, _token: str) -> CommandResult:
        from intelligence.routines import RoutineEngine

        engine  = RoutineEngine()
        names   = engine.list_routines()
        if names:
            from core.speech import SpeechFormatter
            msg = f"Available routines: {SpeechFormatter.format_list(names)}."
        else:
            msg = "You don't have any routines set up yet."
        return CommandResult(success=True, message=msg)

    # ── user management ───────────────────────────────────────────────────
    def create_user(self, _intent: IntentResult, _token: str) -> CommandResult:
        # Interactive prompts happen in the main loop; this is reached only
        # when intent is detected. We return a sentinel so the loop knows to
        # prompt interactively.
        return CommandResult(success=True,
                             message="Sure. Please type the new username.",
                             data={"interactive": "create_user"})

    def delete_user(self, _intent: IntentResult, _token: str) -> CommandResult:
        return CommandResult(success=True,
                             message="Sure. Please type the username you want to delete.",
                             data={"interactive": "delete_user"})

    def change_password(self, _intent: IntentResult, _token: str) -> CommandResult:
        return CommandResult(success=True,
                             message="Sure. Please type your current password.",
                             data={"interactive": "change_password"})