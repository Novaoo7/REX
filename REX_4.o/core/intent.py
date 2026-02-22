# ==============================================================================
# core/intent.py   –  REX 4.0   Intent Classification
# ==============================================================================
# Design
#   • Every intent is defined declaratively in a PatternDef dataclass
#     (keywords, regexes, required params).  No giant if/elif chain.
#   • classify() scores every PatternDef against the input, picks the winner
#     and extracts parameters in one pass.
#   • A user-correction store (JSON on disk) lets the system learn over time:
#     if the user says "that was wrong, I meant <X>" we record it and replay
#     it instantly next time.
#   • Context-dependent intents (YES / NO / CANCEL / REPEAT) are only
#     returned when there is a pending confirmation in the conversation.
# ==============================================================================

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.config import get_config
from core.logger import get_logger, LogCategory


# ─── Intent catalogue ─────────────────────────────────────────────────────────


class IntentType(Enum):
    # ── greeting / meta
    GREETING         = "greeting"
    FAREWELL         = "farewell"
    HELP             = "help"
    STATUS           = "status"
    LIST_COMMANDS    = "list_commands"
    SHOW_LOGS        = "show_logs"
    REPEAT           = "repeat"

    # ── time / date
    TIME_QUERY       = "time_query"
    DATE_QUERY       = "date_query"

    # ── app control
    APP_OPEN         = "app_open"
    APP_CLOSE        = "app_close"
    APP_MINIMIZE     = "app_minimize"
    APP_MAXIMIZE     = "app_maximize"
    APP_SWITCH       = "app_switch"

    # ── file ops
    FILE_OPEN        = "file_open"
    FILE_SEARCH      = "file_search"
    FOLDER_OPEN      = "folder_open"

    # ── system
    SYSTEM_SHUTDOWN  = "system_shutdown"
    SYSTEM_RESTART   = "system_restart"
    SYSTEM_SLEEP     = "system_sleep"
    SYSTEM_LOCK      = "system_lock"
    VOLUME_CONTROL   = "volume_control"
    BRIGHTNESS       = "brightness"

    # ── advanced
    WEB_SEARCH       = "web_search"
    SET_REMINDER     = "set_reminder"
    SET_ALARM        = "set_alarm"
    SEND_EMAIL       = "send_email"

    # ── routines
    RUN_ROUTINE      = "run_routine"
    LIST_ROUTINES    = "list_routines"
    CREATE_ROUTINE   = "create_routine"

    # ── user mgmt
    CREATE_USER      = "create_user"
    DELETE_USER      = "delete_user"
    CHANGE_PASSWORD  = "change_password"

    # ── config
    CONFIG_VIEW      = "config_view"
    CONFIG_EDIT      = "config_edit"

    # ── clarification  (context-dependent)
    YES              = "yes"
    NO               = "no"
    CANCEL           = "cancel"

    # ── fallback
    UNKNOWN          = "unknown"


# ─── Pattern definition ───────────────────────────────────────────────────────


@dataclass
class PatternDef:
    """Declarative description of one intent."""
    intent:       IntentType
    keywords:     List[str]                        # any of these anywhere → base score
    regexes:      List[str]                        # first match → high score
    param_key:    Optional[str]       = None       # if set, extract this param
    exact_match:  bool                = False      # keyword must == full input
    context_only: bool                = False      # only match when confirmation pending


# ─── Result ───────────────────────────────────────────────────────────────────


@dataclass
class IntentResult:
    intent:       IntentType
    confidence:   float
    parameters:   Dict[str, Any]
    raw_text:     str
    alternatives: List[Tuple[IntentType, float]] = field(default_factory=list)


# ─── Classifier ───────────────────────────────────────────────────────────────


class IntentClassifier:
    """
    Stateful intent classifier with on-disk learning.

    Parameters
    ----------
    learning_path   Where to persist user corrections.  None → no persistence.
    """

    def __init__(self, learning_path: Optional[str] = None) -> None:
        self._logger = get_logger()
        cfg          = get_config()
        self._learning_path = Path(learning_path) if learning_path else \
                              Path(cfg.paths.memory_dir) / "intent_corrections.json"

        # learned overrides  {raw_text → IntentType.value}
        self._corrections: Dict[str, str] = {}
        self._load_corrections()

        # pattern table – built once
        self._patterns: List[PatternDef] = _build_patterns()

        # conversation state: set to True when the system is waiting for
        # a yes / no / cancel from the user
        self.awaiting_confirmation: bool = False

        # stats
        self._total = 0
        self._by_intent: Dict[str, int] = {}

    # ── public API ────────────────────────────────────────────────────────
    def classify(self, text: str) -> IntentResult:
        """Return the best-matching intent with extracted parameters."""
        if not text or not text.strip():
            return IntentResult(IntentType.UNKNOWN, 0.0, {}, "")

        text = text.strip()
        normalised = text.lower()

        # ── 1. check learned corrections first ──
        if normalised in self._corrections:
            self._total += 1
            intent = IntentType(self._corrections[normalised])
            self._by_intent[intent.value] = self._by_intent.get(intent.value, 0) + 1
            return IntentResult(intent, 1.0, {}, text)

        # ── 2. score every pattern ──
        scored: List[Tuple[float, PatternDef, Dict[str, Any]]] = []
        for pdef in self._patterns:
            # context-only patterns are skipped when no confirmation pending
            if pdef.context_only and not self.awaiting_confirmation:
                continue
            score, params = self._score(normalised, pdef)
            if score > 0:
                scored.append((score, pdef, params))

        if not scored:
            self._total += 1
            self._by_intent["unknown"] = self._by_intent.get("unknown", 0) + 1
            return IntentResult(IntentType.UNKNOWN, 0.0, {}, text)

        scored.sort(key=lambda t: t[0], reverse=True)
        best_score, best_pdef, best_params = scored[0]

        # alternatives (top-3 excluding winner)
        alts = [(s[1].intent, s[0]) for s in scored[1:4]]

        self._total += 1
        self._by_intent[best_pdef.intent.value] = \
            self._by_intent.get(best_pdef.intent.value, 0) + 1

        self._logger.debug(LogCategory.INTENT,
                           f"Classified '{text}' → {best_pdef.intent.value} ({best_score:.2f})")

        return IntentResult(best_pdef.intent, best_score, best_params, text, alts)

    # ── learning ──────────────────────────────────────────────────────────
    def learn_correction(self, raw_text: str, correct_intent: IntentType) -> None:
        """Record a user correction and persist it."""
        key = raw_text.lower().strip()
        self._corrections[key] = correct_intent.value
        self._save_corrections()
        self._logger.info(LogCategory.INTENT,
                          f"Learned correction: '{key}' → {correct_intent.value}")

    # ── stats ─────────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return {
            "total_classified": self._total,
            "by_intent":        dict(self._by_intent),
            "corrections":      len(self._corrections),
        }

    # ── scoring engine ────────────────────────────────────────────────────
    @staticmethod
    def _score(text: str, pdef: PatternDef) -> Tuple[float, Dict[str, Any]]:
        """Return (score 0.0–1.0, extracted parameters)."""
        score  = 0.0
        params: Dict[str, Any] = {}

        # exact match override
        if pdef.exact_match:
            if text in pdef.keywords:
                return 1.0, params
            return 0.0, params

        # keyword hits → base score  (0.3 per keyword, capped at 0.6)
        hits = sum(1 for kw in pdef.keywords if kw in text)
        if hits:
            score = min(0.6, 0.3 * hits)

        # regex hits → high score  (0.85)
        for pattern in pdef.regexes:
            m = re.search(pattern, text)
            if m:
                score = max(score, 0.85)
                # ── parameter extraction ────────────────────────────────
                if pdef.param_key == "app_name":
                    params["app_name"] = _extract_after(text, ("open","start","launch","run",
                                                               "close","quit","exit","kill",
                                                               "minimize","maximise","maximize",
                                                               "switch to"))
                elif pdef.param_key == "file_name":
                    params["file_name"] = _extract_after(text, ("open","find","search","locate","create"))
                elif pdef.param_key == "folder_name":
                    params["folder_name"] = _extract_after(text, ("open folder","open directory"))
                elif pdef.param_key == "query":
                    params["query"] = _extract_after(text, ("search","google","look up","find","search for"))
                elif pdef.param_key == "reminder":
                    params["reminder"] = _extract_after(text, ("remind me","set reminder","reminder"))
                elif pdef.param_key == "volume_action":
                    if any(w in text for w in ("up","increase","raise","louder")):
                        params["action"] = "increase"
                    elif any(w in text for w in ("down","decrease","lower","quieter")):
                        params["action"] = "decrease"
                    elif "mute" in text and "unmute" not in text:
                        params["action"] = "mute"
                    elif "unmute" in text:
                        params["action"] = "unmute"
                    # optional numeric amount
                    nums = re.findall(r"\b(\d+)\b", text)
                    if nums:
                        params["amount"] = int(nums[0])
                elif pdef.param_key == "routine_name":
                    params["routine_name"] = _extract_after(text, ("run","start","execute","routine"))
                elif pdef.param_key == "brightness_action":
                    if any(w in text for w in ("up","increase","raise","brighter")):
                        params["action"] = "increase"
                    elif any(w in text for w in ("down","decrease","lower","dimmer","dim")):
                        params["action"] = "decrease"
                break   # first regex match wins

        return score, params

    # ── persistence ───────────────────────────────────────────────────────
    def _load_corrections(self) -> None:
        if not self._learning_path.exists():
            return
        try:
            with open(self._learning_path, "r", encoding="utf-8") as fh:
                self._corrections = json.load(fh).get("corrections", {})
        except (json.JSONDecodeError, OSError):
            pass

    def _save_corrections(self) -> None:
        try:
            self._learning_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._learning_path, "w", encoding="utf-8") as fh:
                json.dump({"corrections": self._corrections,
                           "updated_at": time.time()}, fh, indent=2)
        except OSError as exc:
            self._logger.error(LogCategory.INTENT, f"Cannot save corrections: {exc}")


# ─── Pattern catalogue ────────────────────────────────────────────────────────
# Centralised, easy to extend.  Add a new PatternDef to the list to add a command.


def _build_patterns() -> List[PatternDef]:
    return [
        # ── greeting / meta ──────────────────────────────────────────────
        PatternDef(IntentType.GREETING,
                   ["hello","hi","hey","greetings","good morning","good afternoon","good evening"],
                   [r"^(hello|hi|hey|greetings|good (morning|afternoon|evening))"],
                   exact_match=True),

        PatternDef(IntentType.FAREWELL,
                   ["goodbye","bye","see you","farewell","later","good night"],
                   [r"^(goodbye|bye|see you|farewell|good night)"],
                   exact_match=True),

        PatternDef(IntentType.HELP,
                   ["help","commands","what can you do"],
                   [r"(help|what can you do|show commands|list commands)"]),

        PatternDef(IntentType.STATUS,
                   ["status","how are you","are you working","system status"],
                   [r"(status|how are you|are you (working|ok))"]),

        PatternDef(IntentType.SHOW_LOGS,
                   ["show logs","view logs","display logs","check logs"],
                   [r"(show|view|display|check) logs"]),

        PatternDef(IntentType.REPEAT,
                   ["repeat","again","say again","what did you say"],
                   [r"(repeat|again|say again|what did you say)"]),

        # ── time / date ───────────────────────────────────────────────────
        PatternDef(IntentType.TIME_QUERY,
                   ["what time","current time","tell me the time","time"],
                   [r"(what (is |'?s )?the time|tell me the time|current time|what time is it)"]),

        PatternDef(IntentType.DATE_QUERY,
                   ["what date","today","what day","current date","tell me the date"],
                   [r"(what (is |'?s )?(the )?date|what day is (it|today)|tell me the date|today.?s date)"]),

        # ── app control ───────────────────────────────────────────────────
        PatternDef(IntentType.APP_OPEN,
                   ["open","start","launch","run"],
                   [r"(open|start|launch|run)\s+(.+)"],
                   param_key="app_name"),

        PatternDef(IntentType.APP_CLOSE,
                   ["close","quit","exit","kill","terminate","shut down"],
                   [r"(close|quit|exit|kill|terminate)\s+(.+)"],
                   param_key="app_name"),

        PatternDef(IntentType.APP_MINIMIZE,
                   ["minimize","minimise","minimize window"],
                   [r"(minimize|minimise)( window| .+)?"]),

        PatternDef(IntentType.APP_MAXIMIZE,
                   ["maximize","maximise","full screen","fullscreen"],
                   [r"(maximize|maximise|full\s*screen)( window| .+)?"]),

        PatternDef(IntentType.APP_SWITCH,
                   ["switch to","switch window","alt tab"],
                   [r"switch (to )?(.+)"],
                   param_key="app_name"),

        # ── file ops ──────────────────────────────────────────────────────
        PatternDef(IntentType.FILE_OPEN,
                   ["open file","open document"],
                   [r"open (file|document)\s+(.+)"],
                   param_key="file_name"),

        PatternDef(IntentType.FILE_SEARCH,
                   ["find file","search file","locate file","where is"],
                   [r"(find|search|locate) (file|document)\s+(.+)|where is (.+)"],
                   param_key="file_name"),

        PatternDef(IntentType.FOLDER_OPEN,
                   ["open folder","open directory"],
                   [r"open (folder|directory)\s+(.+)"],
                   param_key="folder_name"),

        # ── system ────────────────────────────────────────────────────────
        PatternDef(IntentType.SYSTEM_SHUTDOWN,
                   ["shutdown","shut down","power off","turn off computer","exit rex"],
                   [r"(shutdown|shut down|power off|turn off (the )?(computer|system|pc)|exit rex)"]),

        PatternDef(IntentType.SYSTEM_RESTART,
                   ["restart","reboot","restart computer"],
                   [r"(restart|reboot)( (the )?(computer|system|pc))?"]),

        PatternDef(IntentType.SYSTEM_SLEEP,
                   ["sleep","hibernate","go to sleep"],
                   [r"(sleep|hibernate|go to sleep)"]),

        PatternDef(IntentType.SYSTEM_LOCK,
                   ["lock","lock computer","lock screen"],
                   [r"lock( (the )?(computer|screen|pc))?"]),

        PatternDef(IntentType.VOLUME_CONTROL,
                   ["volume","mute","unmute","louder","quieter"],
                   [r"(volume (up|down)|increase volume|decrease volume|raise volume|lower volume"
                    r"|mute|unmute|louder|quieter|set volume)"],
                   param_key="volume_action"),

        PatternDef(IntentType.BRIGHTNESS,
                   ["brightness","brighter","dimmer","dim"],
                   [r"(brightness (up|down)|increase brightness|decrease brightness"
                    r"|brighter|dimmer|dim (the )?screen)"],
                   param_key="brightness_action"),

        # ── advanced ──────────────────────────────────────────────────────
        PatternDef(IntentType.WEB_SEARCH,
                   ["search","google","look up","search for","search online"],
                   [r"(search (for )?|google |look up )(.+)"],
                   param_key="query"),

        PatternDef(IntentType.SET_REMINDER,
                   ["remind me","set reminder","reminder"],
                   [r"(remind me |set (a )?reminder )(.+)"],
                   param_key="reminder"),

        PatternDef(IntentType.SET_ALARM,
                   ["set alarm","alarm"],
                   [r"set (an? )?alarm (.+)"],
                   param_key="reminder"),

        PatternDef(IntentType.SEND_EMAIL,
                   ["send email","email","send message"],
                   [r"send (an? )?(email|message) (to )?(.+)"]),

        # ── routines ──────────────────────────────────────────────────────
        PatternDef(IntentType.RUN_ROUTINE,
                   ["run routine","start routine","morning routine","evening routine"],
                   [r"(run|start|execute) (routine )?(.+)|"
                    r"(morning|evening|night|work|sleep) routine"],
                   param_key="routine_name"),

        PatternDef(IntentType.LIST_ROUTINES,
                   ["list routines","show routines","what routines"],
                   [r"(list|show|what) routines"]),

        # ── user management ───────────────────────────────────────────────
        PatternDef(IntentType.CREATE_USER,
                   ["create user","add user","new user"],
                   [r"(create|add|new) user"]),

        PatternDef(IntentType.DELETE_USER,
                   ["delete user","remove user"],
                   [r"(delete|remove) user"]),

        PatternDef(IntentType.CHANGE_PASSWORD,
                   ["change password","reset password","new password"],
                   [r"(change|reset|update) password"]),

        # ── config ────────────────────────────────────────────────────────
        PatternDef(IntentType.CONFIG_VIEW,
                   ["show config","view config","display config","configuration"],
                   [r"(show|view|display) config(uration)?"]),

        PatternDef(IntentType.CONFIG_EDIT,
                   ["edit config","change config","set config","update config"],
                   [r"(edit|change|set|update) config(uration)?"]),

        # ── clarification (context-only) ──────────────────────────────────
        PatternDef(IntentType.YES,
                   ["yes","yeah","yep","sure","ok","okay","confirm","correct","right","absolutely"],
                   [r"^(yes|yeah|yep|sure|ok|okay|confirm|correct|right|absolutely)$"],
                   exact_match=True, context_only=True),

        PatternDef(IntentType.NO,
                   ["no","nope","nah","negative","wrong","incorrect","not really"],
                   [r"^(no|nope|nah|negative|wrong|incorrect|not really)$"],
                   exact_match=True, context_only=True),

        PatternDef(IntentType.CANCEL,
                   ["cancel","nevermind","never mind","forget it","stop","abort"],
                   [r"^(cancel|nevermind|never mind|forget it|stop|abort)$"],
                   exact_match=True, context_only=True),
    ]


# ─── Extraction helpers ───────────────────────────────────────────────────────


def _extract_after(text: str, triggers: tuple) -> str:
    """Return everything after the first trigger word/phrase found in *text*."""
    for trigger in triggers:
        idx = text.find(trigger)
        if idx != -1:
            remainder = text[idx + len(trigger):].strip()
            # strip leading articles / filler
            for filler in ("the", "a", "an", "for", "me"):
                if remainder.startswith(filler + " "):
                    remainder = remainder[len(filler) + 1:]
            return remainder
    return text   # fallback: return whole text