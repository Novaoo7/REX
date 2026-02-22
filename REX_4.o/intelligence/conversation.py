# ==============================================================================
# intelligence/conversation.py   –  REX 4.0   Conversation Manager
# ==============================================================================
# Design
#   • ConversationManager owns the short-term dialog state: what the system
#     just asked, what confirmation is pending, and the last N turns so
#     "repeat" works.
#   • A PendingAction dataclass captures "what we're waiting the user to
#     confirm / provide input for".  The main loop queries
#     has_pending() before routing an intent; if there IS a pending action
#     and the user says YES/NO/CANCEL the manager resolves it without ever
#     hitting the router.
#   • Every turn is also forwarded to ContextMemory so the long-term store
#     stays in sync automatically.
# ==============================================================================

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger, LogCategory
from intelligence.context_memory import ContextMemory


# ─── Pending action ───────────────────────────────────────────────────────────


@dataclass
class PendingAction:
    """Describes what the system is waiting for from the user."""
    action_type:   str                                      # e.g. "confirm_shutdown"
    prompt:        str                                      # what was spoken to the user
    on_confirm:    Optional[Callable[[], Any]]  = None      # called on YES
    on_deny:       Optional[Callable[[], Any]]  = None      # called on NO
    on_cancel:     Optional[Callable[[], Any]]  = None      # called on CANCEL
    created_at:    float                        = 0.0
    expires_at:    float                        = 0.0       # 0 = no expiry


# ─── Turn ─────────────────────────────────────────────────────────────────────


@dataclass
class Turn:
    role:      str          # "user" | "assistant"
    text:      str
    intent:    str          # IntentType.value or ""
    timestamp: float        = 0.0


# ─── ConversationManager ──────────────────────────────────────────────────────


class ConversationManager:
    """
    Tracks short-term conversational state and integrates with long-term memory.

    Usage
    -----
        conv = ConversationManager()
        conv.add_turn("user",      "open chrome",  "app_open")
        conv.add_turn("assistant", "Opening Chrome.", "app_open")

        conv.set_pending(PendingAction(
            action_type="confirm_shutdown",
            prompt="Are you sure you want to shut down?",
            on_confirm=lambda: ...,
        ))

        if conv.has_pending():
            result = conv.resolve_pending("yes")   # → calls on_confirm
    """

    MAX_TURNS = 30   # keep last N turns in memory

    def __init__(self) -> None:
        self._logger  = get_logger()
        self._memory  = ContextMemory()
        self._turns:  List[Turn]              = []
        self._pending: Optional[PendingAction] = None

    # ── turn management ───────────────────────────────────────────────────
    def add_turn(self, role: str, text: str, intent: str = "") -> None:
        turn = Turn(role=role, text=text, intent=intent, timestamp=time.time())
        self._turns.append(turn)
        if len(self._turns) > self.MAX_TURNS:
            self._turns.pop(0)

        # mirror to long-term memory
        tags = ContextMemory.extract_tags(text)
        self._memory.store("interaction", f"[{role}] {text}",
                           tags=tags,
                           metadata={"intent": intent})

    def last_assistant_message(self) -> str:
        """Return the most recent assistant turn's text, or empty."""
        for turn in reversed(self._turns):
            if turn.role == "assistant":
                return turn.text
        return ""

    def get_recent_turns(self, n: int = 5) -> List[Turn]:
        return self._turns[-n:]

    # ── pending action (confirmation flow) ────────────────────────────────
    def set_pending(self, action: PendingAction) -> None:
        action.created_at = time.time()
        if action.expires_at == 0:
            action.expires_at = action.created_at + 30   # default 30 s timeout
        self._pending = action
        self._logger.debug(LogCategory.MEMORY,
                           f"Pending action set: {action.action_type}")

    def has_pending(self) -> bool:
        if self._pending is None:
            return False
        # auto-expire
        if time.time() > self._pending.expires_at:
            self._logger.info(LogCategory.MEMORY,
                              f"Pending action expired: {self._pending.action_type}")
            self._pending = None
            return False
        return True

    def resolve_pending(self, verdict: str) -> Optional[str]:
        """
        *verdict* is one of "yes", "no", "cancel".
        Calls the appropriate callback and returns a response string.
        """
        if not self.has_pending():
            return None

        action = self._pending
        self._pending = None   # consume it

        self._logger.info(LogCategory.MEMORY,
                          f"Pending {action.action_type} resolved: {verdict}")

        if verdict == "yes" and action.on_confirm:
            action.on_confirm()
            return f"Confirmed. Proceeding with {action.action_type.replace('_', ' ')}."

        if verdict == "no" and action.on_deny:
            action.on_deny()
            return "Understood, I won't do that."

        if verdict == "cancel" and action.on_cancel:
            action.on_cancel()
            return "Cancelled."

        # generic fallbacks
        if verdict == "yes":
            return "Confirmed."
        if verdict == "no":
            return "Okay, I won't do that."
        return "Action cancelled."

    def clear_pending(self) -> None:
        self._pending = None

    # ── context summary (for proactive engine) ───────────────────────────
    def context_summary(self) -> str:
        """Short text summary of the last few turns – useful for proactive suggestions."""
        parts = []
        for t in self.get_recent_turns(3):
            parts.append(f"{t.role}: {t.text}")
        return "\n".join(parts)