# ==============================================================================
# intelligence/history.py   –  REX 4.0   Command History
# ==============================================================================
# Design
#   • A fixed-size ring buffer (default 200 entries) that stores every
#     executed command with its result, timestamp, and duration.
#   • Supports search by intent, date range, success/failure.
#   • Can export to CSV for external analysis.
#   • Future extension point: undo/redo stack (not implemented yet but the
#     data structure is ready).
# ==============================================================================

from __future__ import annotations

import csv
import json
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional

from core.config import get_config
from core.logger import get_logger, LogCategory


# ─── HistoryEntry ─────────────────────────────────────────────────────────────


@dataclass
class HistoryEntry:
    id:         int
    intent:     str                  # IntentType.value
    raw_text:   str
    success:    bool
    message:    str                  # what was spoken back
    duration:   float                # seconds
    timestamp:  float                # epoch
    username:   str         = ""
    error:      str         = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "HistoryEntry":
        return cls(**d)


# ─── CommandHistory ───────────────────────────────────────────────────────────


class CommandHistory:
    """
    Fixed-size ring buffer for command execution history.

    Usage
    -----
        history = CommandHistory()
        history.add("app_open", "open chrome", True, "Opening Chrome", 0.5, "john")
        recent = history.search(limit=10)
        history.export_csv("commands.csv")
    """

    def __init__(self, max_size: Optional[int] = None) -> None:
        cfg = get_config()
        self._max_size = max_size or cfg.performance.command_history_size
        self._logger   = get_logger()
        self._entries: Deque[HistoryEntry] = deque(maxlen=self._max_size)
        self._next_id  = 1

        # persistence
        self._path = Path(cfg.paths.memory_dir) / "command_history.json"
        self._load()

    # ── persistence ───────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            for e in raw:
                self._entries.append(HistoryEntry.from_dict(e))
            if self._entries:
                self._next_id = max(e.id for e in self._entries) + 1
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            self._logger.warning(LogCategory.SYSTEM, f"History load failed: {exc}")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump([e.to_dict() for e in self._entries], fh, indent=2)

    # ── CRUD ──────────────────────────────────────────────────────────────
    def add(self, intent: str, raw_text: str, success: bool, message: str,
            duration: float, username: str = "", error: str = "") -> HistoryEntry:
        entry = HistoryEntry(
            id=self._next_id,
            intent=intent,
            raw_text=raw_text,
            success=success,
            message=message,
            duration=duration,
            timestamp=time.time(),
            username=username,
            error=error,
        )
        self._entries.append(entry)
        self._next_id += 1
        self._save()
        return entry

    def clear(self) -> None:
        self._entries.clear()
        self._save()

    # ── search ────────────────────────────────────────────────────────────
    def search(self, *,
               intent:    Optional[str]   = None,
               success:   Optional[bool]  = None,
               username:  Optional[str]   = None,
               since:     Optional[float] = None,
               until:     Optional[float] = None,
               limit:     int             = 50) -> List[HistoryEntry]:
        """Filter history.  All criteria are AND-ed."""
        results = list(self._entries)

        if intent:
            results = [e for e in results if e.intent == intent]
        if success is not None:
            results = [e for e in results if e.success == success]
        if username:
            results = [e for e in results if e.username == username]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if until:
            results = [e for e in results if e.timestamp <= until]

        # most recent first
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_all(self) -> List[HistoryEntry]:
        return list(self._entries)

    # ── stats ─────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        total    = len(self._entries)
        success  = sum(1 for e in self._entries if e.success)
        by_intent = {}
        for e in self._entries:
            by_intent[e.intent] = by_intent.get(e.intent, 0) + 1

        avg_duration = 0.0
        if total:
            avg_duration = sum(e.duration for e in self._entries) / total

        return {
            "total":        total,
            "successful":   success,
            "failed":       total - success,
            "avg_duration": round(avg_duration, 3),
            "by_intent":    by_intent,
        }

    # ── export ────────────────────────────────────────────────────────────
    def export_csv(self, filepath: str) -> None:
        """Write all entries to a CSV file."""
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "id", "timestamp", "username", "intent", "raw_text",
                "success", "message", "error", "duration",
            ])
            writer.writeheader()
            for e in self._entries:
                writer.writerow({
                    "id":        e.id,
                    "timestamp": datetime.fromtimestamp(e.timestamp).isoformat(),
                    "username":  e.username,
                    "intent":    e.intent,
                    "raw_text":  e.raw_text,
                    "success":   e.success,
                    "message":   e.message,
                    "error":     e.error,
                    "duration":  round(e.duration, 3),
                })
        self._logger.info(LogCategory.SYSTEM, f"Exported {len(self._entries)} commands to {filepath}")