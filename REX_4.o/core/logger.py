# ==============================================================================
# core/logger.py   –  REX 4.0   Structured Logging
# ==============================================================================
# Design
#   • Every log entry is one JSON object per line (JSONL) so you can grep /
#     stream / ingest it into any log platform.
#   • Rotation: when the active file exceeds MAX_BYTES we rename it and open a
#     fresh one.  At most BACKUP_COUNT rotated files are kept.
#   • LogCategory lets callers tag entries so search() can filter by domain
#     (AUTH, COMMAND, AUDIO …) instead of grepping strings.
#   • log_performance() is a dedicated path for timing data; it emits a
#     normal INFO entry but with a guaranteed "duration_ms" key so dashboards
#     can query it cheaply.
#   • get_logger() returns a singleton; every module in the tree calls it the
#     same way so there is exactly one file handle open at a time.
# ==============================================================================

from __future__ import annotations

import json
import os
import time
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_config


# ─── Enums ────────────────────────────────────────────────────────────────────


class LogLevel(Enum):
    DEBUG    = 0
    INFO     = 1
    WARNING  = 2
    ERROR    = 3
    CRITICAL = 4


class LogCategory(Enum):
    SYSTEM      = "system"
    COMMAND     = "command"
    AUDIO       = "audio"
    SPEECH      = "speech"
    AUTH        = "auth"
    MEMORY      = "memory"
    PERFORMANCE = "performance"
    ERROR       = "error"
    SECURITY    = "security"
    INTENT      = "intent"
    ROUTINE     = "routine"


# ─── Logger ───────────────────────────────────────────────────────────────────


class Logger:
    """
    Thread-safe, rotating, structured (JSONL) logger.

    Parameters
    ----------
    log_dir   : directory in which log files live.
    min_level : discard entries below this severity.
    """

    MAX_BYTES     = 10 * 1024 * 1024   # 10 MB before rotation
    BACKUP_COUNT  = 5                  # how many rotated files to keep

    def __init__(self, log_dir: str = "logs", min_level: LogLevel = LogLevel.INFO) -> None:
        self._dir       = Path(log_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._min_level = min_level
        self._lock      = threading.Lock()
        self._file_path = self._dir / "rex.log"
        self._fh: Optional[open] = None
        self._open_file()

        # in-memory ring buffer for search() and stats
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_max = 2000

    # ── internal ──────────────────────────────────────────────────────────
    def _open_file(self) -> None:
        if self._fh and not self._fh.closed:
            self._fh.close()
        self._fh = open(self._file_path, "a", encoding="utf-8")

    def _rotate_if_needed(self) -> None:
        try:
            size = self._file_path.stat().st_size
        except OSError:
            return
        if size < self.MAX_BYTES:
            return

        # close current handle
        if self._fh and not self._fh.closed:
            self._fh.close()

        # shift existing backups  rex.log.4 → deleted, .3→.4, … .0→.1
        for i in range(self.BACKUP_COUNT - 1, 0, -1):
            src  = self._file_path.with_suffix(f".log.{i - 1}" if i > 1 else ".log.0")
            # map: rex.log  → rex.log.0  → rex.log.1  …  rex.log.4
            pass  # handled below with a cleaner loop

        # unified rotation loop
        for i in range(self.BACKUP_COUNT - 1, -1, -1):
            src  = self._file_path if i == 0 else self._file_path.parent / f"rex.log.{i - 1}"
            dest = self._file_path.parent / f"rex.log.{i}"
            if src.exists():
                if dest.exists():
                    dest.unlink()
                src.rename(dest)

        self._open_file()                      # fresh empty file

    # ── core write ────────────────────────────────────────────────────────
    def _emit(self, level: LogLevel, category: LogCategory, message: str,
              extra: Optional[Dict[str, Any]] = None) -> None:
        if level.value < self._min_level.value:
            return

        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "level":     level.name,
            "category":  category.value,
            "message":   message,
        }
        if extra:
            entry["extra"] = extra

        line = json.dumps(entry, default=str) + "\n"

        with self._lock:
            self._rotate_if_needed()
            if self._fh and not self._fh.closed:
                self._fh.write(line)
                self._fh.flush()

            # ring buffer
            self._buffer.append(entry)
            if len(self._buffer) > self._buffer_max:
                self._buffer.pop(0)

    # ── public API ────────────────────────────────────────────────────────
    def debug(self, cat: LogCategory, msg: str,
              extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit(LogLevel.DEBUG, cat, msg, extra)

    def info(self, cat: LogCategory, msg: str,
             extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit(LogLevel.INFO, cat, msg, extra)

    def warning(self, cat: LogCategory, msg: str,
                extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit(LogLevel.WARNING, cat, msg, extra)

    def error(self, cat: LogCategory, msg: str,
              extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit(LogLevel.ERROR, cat, msg, extra)

    def critical(self, cat: LogCategory, msg: str,
                 extra: Optional[Dict[str, Any]] = None) -> None:
        self._emit(LogLevel.CRITICAL, cat, msg, extra)

    # ── performance helper ────────────────────────────────────────────────
    def log_performance(self, operation: str, duration_sec: float,
                        extra: Optional[Dict[str, Any]] = None) -> None:
        """Dedicated path for timing data."""
        payload = {"operation": operation, "duration_ms": round(duration_sec * 1000, 2)}
        if extra:
            payload.update(extra)
        self._emit(LogLevel.INFO, LogCategory.PERFORMANCE,
                   f"{operation} completed in {payload['duration_ms']} ms", payload)

    # ── search / stats ────────────────────────────────────────────────────
    def search(self, *,
               keyword:  Optional[str]         = None,
               level:    Optional[LogLevel]    = None,
               category: Optional[LogCategory] = None,
               max_results: int                = 50) -> List[Dict[str, Any]]:
        """Filter the in-memory ring buffer.  For deeper scans use `search_file`."""
        hits: List[Dict[str, Any]] = []
        for entry in reversed(self._buffer):
            if level and entry["level"] != level.name:
                continue
            if category and entry["category"] != category.value:
                continue
            if keyword and keyword.lower() not in json.dumps(entry).lower():
                continue
            hits.append(entry)
            if len(hits) >= max_results:
                break
        return hits

    def search_file(self, *,
                    keyword:  Optional[str]         = None,
                    level:    Optional[LogLevel]    = None,
                    category: Optional[LogCategory] = None,
                    max_results: int                = 100) -> List[Dict[str, Any]]:
        """Scan the on-disk log file (slower, larger result set)."""
        hits: List[Dict[str, Any]] = []
        try:
            with open(self._file_path, "r", encoding="utf-8") as fh:
                for raw_line in fh:
                    try:
                        entry = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if level and entry.get("level") != level.name:
                        continue
                    if category and entry.get("category") != category.value:
                        continue
                    if keyword and keyword.lower() not in raw_line.lower():
                        continue
                    hits.append(entry)
                    if len(hits) >= max_results:
                        break
        except FileNotFoundError:
            pass
        return hits

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate counts from the in-memory buffer."""
        by_level:    Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        for entry in self._buffer:
            by_level[entry["level"]]        = by_level.get(entry["level"], 0) + 1
            by_category[entry["category"]]  = by_category.get(entry["category"], 0) + 1
        return {
            "total_in_buffer": len(self._buffer),
            "by_level":        by_level,
            "by_category":     by_category,
        }

    # ── lifecycle ─────────────────────────────────────────────────────────
    def close(self) -> None:
        with self._lock:
            if self._fh and not self._fh.closed:
                self._fh.close()

    def __del__(self) -> None:                # pragma: no cover
        self.close()


# ─── Singleton ────────────────────────────────────────────────────────────────

_LOGGER: Optional[Logger] = None


def get_logger() -> Logger:
    """Return the process-wide Logger, creating it on first call."""
    global _LOGGER
    if _LOGGER is None:
        cfg = get_config()
        _LOGGER = Logger(log_dir=cfg.paths.logs_dir)
    return _LOGGER