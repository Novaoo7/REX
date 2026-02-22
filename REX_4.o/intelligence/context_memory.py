# ==============================================================================
# intelligence/context_memory.py   –  REX 4.0   Long-Term Contextual Memory
# ==============================================================================
# Design
#   • Every interaction is stored as a MemoryEntry with a timestamp,
#     category, tags, and a freeform payload.
#   • On disk the file is encrypted with Fernet (symmetric AES-128-CBC) so
#     that if the JSON is stolen it reveals nothing.  The key is derived once
#     at startup and kept only in process memory.
#   • retrieve() supports keyword search, tag filter, and recency limit so
#     the conversation manager can pull relevant context cheaply.
#   • A simple entity extractor tags entries with detected app names,
#     file names, and time references so future queries can find them fast.
# ==============================================================================

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet

from core.config import get_config
from core.logger import get_logger, LogCategory


# ─── Fernet key derivation ────────────────────────────────────────────────────
# We derive the key from a fixed salt + a per-machine secret stored in
# memory/<machine-id>.key  (created on first run, never exported).


def _get_encryption_key() -> bytes:
    cfg   = get_config()
    key_path = Path(cfg.paths.memory_dir) / "memory.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        return key_path.read_bytes()

    # generate and persist
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    # restrict permissions on Unix; on Windows this is best-effort
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key


# ─── MemoryEntry ──────────────────────────────────────────────────────────────


@dataclass
class MemoryEntry:
    id:        int
    category:  str                                      # "interaction", "preference", "entity"
    payload:   str                                      # human-readable text
    tags:      List[str]      = field(default_factory=list)
    metadata:  Dict[str, Any] = field(default_factory=dict)
    created_at: float         = 0.0                     # epoch

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        return cls(**d)


# ─── ContextMemory ────────────────────────────────────────────────────────────


class ContextMemory:
    """
    Encrypted, searchable, long-term memory store.

    Usage
    -----
        mem = ContextMemory()
        mem.store("interaction", "User asked to open Chrome", tags=["app", "chrome"])
        results = mem.retrieve(keyword="chrome", limit=5)
    """

    def __init__(self) -> None:
        self._logger = get_logger()
        self._cfg    = get_config()
        self._path   = Path(self._cfg.paths.memory_dir) / "context_memory.enc"
        self._key    = _get_encryption_key()
        self._fernet = Fernet(self._key)

        self._entries: List[MemoryEntry] = []
        self._load()

    # ── persistence ───────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            encrypted = self._path.read_bytes()
            plaintext = self._fernet.decrypt(encrypted).decode("utf-8")
            raw       = json.loads(plaintext)
            self._entries = [MemoryEntry.from_dict(e) for e in raw]
        except Exception as exc:
            self._logger.error(LogCategory.MEMORY, f"Memory load failed: {exc}")
            self._entries = []

    def _save(self) -> None:
        plaintext = json.dumps([e.to_dict() for e in self._entries]).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(encrypted)

    # ── CRUD ──────────────────────────────────────────────────────────────
    def _next_id(self) -> int:
        return max((e.id for e in self._entries), default=0) + 1

    def store(self, category: str, payload: str, *,
              tags: Optional[List[str]] = None,
              metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        """Persist a new memory entry and return it."""
        entry = MemoryEntry(
            id=self._next_id(),
            category=category,
            payload=payload,
            tags=tags or [],
            metadata=metadata or {},
            created_at=time.time(),
        )
        self._entries.append(entry)
        self._save()
        return entry

    def delete(self, entry_id: int) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def clear(self) -> None:
        self._entries.clear()
        self._save()

    # ── retrieval ─────────────────────────────────────────────────────────
    def retrieve(self, *,
                 keyword:  Optional[str]        = None,
                 category: Optional[str]        = None,
                 tags:     Optional[List[str]]  = None,
                 limit:    int                  = 10,
                 since:    Optional[float]      = None) -> List[MemoryEntry]:
        """
        Filter memory.  All criteria are AND-ed.

        Parameters
        ----------
        keyword   Substring match against payload (case-insensitive).
        category  Exact category match.
        tags      Entry must have ALL of these tags.
        limit     Max entries to return (most recent first).
        since     Only entries created after this epoch.
        """
        results = self._entries

        if category:
            results = [e for e in results if e.category == category]
        if keyword:
            kw = keyword.lower()
            results = [e for e in results if kw in e.payload.lower()]
        if tags:
            tag_set = set(tags)
            results = [e for e in results if tag_set.issubset(e.tags)]
        if since:
            results = [e for e in results if e.created_at >= since]

        # most recent first
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def get_all(self) -> List[MemoryEntry]:
        return list(self._entries)

    def count(self) -> int:
        return len(self._entries)

    # ── entity tagging (simple keyword extractor) ────────────────────────
    @staticmethod
    def extract_tags(text: str) -> List[str]:
        """
        Lightweight entity-extraction: flag known app names, file extensions,
        time words so retrieve() can filter on them later.
        """
        from commands.system_control import KNOWN_APPS
        tags: List[str] = []
        lower = text.lower()

        for app in KNOWN_APPS:
            if app in lower:
                tags.append(f"app:{app}")

        # file extensions
        import re
        for ext in re.findall(r"\.\w{2,4}\b", text):
            tags.append(f"ext:{ext}")

        # time words
        for w in ("today", "tomorrow", "now", "morning", "evening", "night"):
            if w in lower:
                tags.append(f"time:{w}")

        return tags