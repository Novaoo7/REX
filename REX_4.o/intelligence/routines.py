# ==============================================================================
# intelligence/routines.py   –  REX 4.0   Routine / Macro Engine
# ==============================================================================
# Design
#   • A routine is a named list of steps.  Each step is itself a mini
#     IntentResult so the existing CommandRouter can execute it without
#     special-casing.
#   • Routines are persisted to memory/routines.json (plaintext – they contain
#     no secrets, just command names).
#   • execute() runs steps sequentially; if one fails it logs the error and
#     continues with the rest (configurable via skip_on_error).
#   • Built-in routines ("morning", "evening", "work", "sleep") are seeded
#     automatically if no routines exist yet.
# ==============================================================================

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_config
from core.logger import get_logger, LogCategory
from core.intent import IntentResult, IntentType


# ─── Step ─────────────────────────────────────────────────────────────────────


@dataclass
class RoutineStep:
    """One command inside a routine."""
    intent:     str                                  # IntentType.value
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str           = ""                  # human-readable label

    def to_dict(self) -> dict:  return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RoutineStep":
        return cls(**d)

    def as_intent_result(self) -> IntentResult:
        """Wrap this step as an IntentResult so CommandRouter can handle it."""
        return IntentResult(
            intent=IntentType(self.intent),
            confidence=1.0,
            parameters=self.parameters,
            raw_text=self.description or self.intent,
        )


# ─── Routine ──────────────────────────────────────────────────────────────────


@dataclass
class Routine:
    name:           str
    description:    str                  = ""
    steps:          List[RoutineStep]    = field(default_factory=list)
    created_at:     float                = 0.0
    last_run:       Optional[float]      = None
    skip_on_error:  bool                 = True       # continue past failed steps

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Routine":
        d["steps"] = [RoutineStep.from_dict(s) for s in d.get("steps", [])]
        return cls(**d)


# ─── Built-in routines ────────────────────────────────────────────────────────


def _default_routines() -> List[Routine]:
    return [
        Routine(
            name="morning",
            description="Morning start-up routine",
            steps=[
                RoutineStep("time_query",   {},                        "Tell time"),
                RoutineStep("date_query",   {},                        "Tell date"),
                RoutineStep("app_open",     {"app_name": "chrome"},    "Open Chrome"),
            ],
        ),
        Routine(
            name="evening",
            description="Evening wind-down routine",
            steps=[
                RoutineStep("volume_control", {"action": "decrease", "amount": 5}, "Lower volume"),
                RoutineStep("app_close",      {"app_name": "chrome"},              "Close Chrome"),
            ],
        ),
        Routine(
            name="work",
            description="Work session start",
            steps=[
                RoutineStep("app_open", {"app_name": "vscode"},       "Open VS Code"),
                RoutineStep("app_open", {"app_name": "chrome"},       "Open Chrome"),
                RoutineStep("app_open", {"app_name": "slack"},        "Open Slack"),
            ],
        ),
        Routine(
            name="sleep",
            description="Prepare for sleep",
            steps=[
                RoutineStep("volume_control", {"action": "mute"},     "Mute volume"),
                RoutineStep("system_sleep",   {},                     "Sleep computer"),
            ],
        ),
    ]


# ─── RoutineEngine ────────────────────────────────────────────────────────────


class RoutineEngine:
    """
    CRUD + execution engine for user-defined and built-in routines.
    """

    def __init__(self) -> None:
        self._logger  = get_logger()
        self._cfg     = get_config()
        self._path    = Path(self._cfg.paths.memory_dir) / "routines.json"
        self._routines: Dict[str, Routine] = {}
        self._load()

    # ── persistence ───────────────────────────────────────────────────────
    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                self._routines = {r["name"]: Routine.from_dict(r) for r in raw}
                return
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                self._logger.error(LogCategory.ROUTINE, f"Routine load failed: {exc}")

        # seed defaults
        for r in _default_routines():
            self._routines[r.name] = r
        self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump([r.to_dict() for r in self._routines.values()], fh, indent=2)

    # ── CRUD ──────────────────────────────────────────────────────────────
    def create(self, name: str, description: str, steps: List[RoutineStep]) -> Dict[str, Any]:
        if name.lower() in self._routines:
            return {"success": False, "message": f"A routine named '{name}' already exists."}
        routine = Routine(name=name.lower(), description=description,
                          steps=steps, created_at=time.time())
        self._routines[name.lower()] = routine
        self._save()
        return {"success": True, "message": f"Routine '{name}' created with {len(steps)} steps."}

    def delete(self, name: str) -> Dict[str, Any]:
        key = name.lower()
        if key not in self._routines:
            return {"success": False, "message": f"No routine named '{name}'."}
        del self._routines[key]
        self._save()
        return {"success": True, "message": f"Routine '{name}' deleted."}

    def list_routines(self) -> List[str]:
        return list(self._routines.keys())

    def get(self, name: str) -> Optional[Routine]:
        return self._routines.get(name.lower())

    # ── execution ─────────────────────────────────────────────────────────
    def execute(self, name: str, session_token: str = "") -> Dict[str, Any]:
        """
        Run every step in the routine through CommandRouter.

        Returns a summary dict with per-step results.
        """
        routine = self._routines.get(name.lower())
        if routine is None:
            return {"success": False, "message": f"No routine named '{name}'.",
                    "error": "not_found"}

        # lazy import to avoid circular
        from commands.handler import CommandRouter
        router = CommandRouter()

        results: List[Dict[str, Any]] = []
        for i, step in enumerate(routine.steps):
            intent_result = step.as_intent_result()
            try:
                cmd_result = router.execute(intent_result, session_token)
                results.append({
                    "step": i,
                    "description": step.description or step.intent,
                    "success": cmd_result.success,
                    "message": cmd_result.message,
                })
                if not cmd_result.success and not routine.skip_on_error:
                    self._logger.warning(LogCategory.ROUTINE,
                                         f"Routine '{name}' stopped at step {i}: {cmd_result.error}")
                    break
            except Exception as exc:
                results.append({"step": i, "description": step.description, "success": False, "error": str(exc)})
                self._logger.error(LogCategory.ROUTINE, f"Step {i} exception: {exc}")
                if not routine.skip_on_error:
                    break

        routine.last_run = time.time()
        self._save()

        success_count = sum(1 for r in results if r.get("success"))
        self._logger.info(LogCategory.ROUTINE,
                          f"Routine '{name}': {success_count}/{len(results)} steps succeeded")

        return {
            "success":  success_count == len(results),
            "message":  f"Routine '{name}' finished: {success_count} of {len(results)} steps completed.",
            "steps":    results,
        }