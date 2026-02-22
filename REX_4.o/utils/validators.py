# ==============================================================================
# utils/validators.py   –  REX 4.0   Input Validation & Sanitisation
# ==============================================================================
# Design
#   • Static methods only – pure functions that take input and return
#     (valid: bool, error_msg: str).
#   • Used everywhere user input enters the system: login, command parameters,
#     file paths, config edits.
#   • Path validation uses a whitelist approach: only allow paths under
#     known-safe roots (user home, Desktop, Documents, Downloads).  This
#     prevents command injection via crafted file paths.
# ==============================================================================

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple


class Validators:
    """
    Collection of input validation helpers.

    Every method returns (ok: bool, error_msg: str).
    """

    # ── username ──────────────────────────────────────────────────────────
    @staticmethod
    def username(value: str) -> Tuple[bool, str]:
        """Valid usernames: 3–32 chars, alphanumeric + underscore."""
        if not value:
            return False, "Username cannot be empty"
        if len(value) < 3:
            return False, "Username must be at least 3 characters"
        if len(value) > 32:
            return False, "Username cannot exceed 32 characters"
        if not re.match(r"^[a-zA-Z0-9_]+$", value):
            return False, "Username can only contain letters, digits, and underscores"
        return True, ""

    # ── password ──────────────────────────────────────────────────────────
    @staticmethod
    def password(value: str, min_length: int = 8) -> Tuple[bool, str]:
        """
        Basic password strength.
        Callers should also use the policy from SecurityConfig for full checks.
        """
        if len(value) < min_length:
            return False, f"Password must be at least {min_length} characters"
        return True, ""

    # ── file path ─────────────────────────────────────────────────────────
    @staticmethod
    def file_path(value: str, must_exist: bool = False) -> Tuple[bool, str]:
        """
        Safe file path: must be under a known-safe root, no path traversal.
        """
        try:
            p = Path(value).resolve()
        except (ValueError, OSError):
            return False, "Invalid file path"

        # whitelist of safe roots
        safe_roots = [
            Path.home(),
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Pictures",
            Path.home() / "Music",
            Path.home() / "Videos",
            Path("C:/Users") if os.name == "nt" else Path("/home"),
        ]

        # check if path is under any safe root
        is_safe = False
        for root in safe_roots:
            try:
                p.relative_to(root.resolve())
                is_safe = True
                break
            except ValueError:
                continue

        if not is_safe:
            return False, "Path is outside allowed directories"

        if must_exist and not p.exists():
            return False, f"Path does not exist: {value}"

        return True, ""

    # ── app name ──────────────────────────────────────────────────────────
    @staticmethod
    def app_name(value: str) -> Tuple[bool, str]:
        """App names: 1–64 chars, alphanumeric + space + dash."""
        if not value or not value.strip():
            return False, "App name cannot be empty"
        if len(value) > 64:
            return False, "App name is too long"
        # allow letters, digits, space, dash, underscore
        if not re.match(r"^[a-zA-Z0-9 _\-]+$", value):
            return False, "App name contains invalid characters"
        return True, ""

    # ── integer range ─────────────────────────────────────────────────────
    @staticmethod
    def int_range(value: int, min_val: int, max_val: int, name: str = "value") -> Tuple[bool, str]:
        """Check if *value* is in [min_val, max_val]."""
        if value < min_val or value > max_val:
            return False, f"{name} must be between {min_val} and {max_val}"
        return True, ""

    # ── float range ───────────────────────────────────────────────────────
    @staticmethod
    def float_range(value: float, min_val: float, max_val: float, name: str = "value") -> Tuple[bool, str]:
        """Check if *value* is in [min_val, max_val]."""
        if value < min_val or value > max_val:
            return False, f"{name} must be between {min_val} and {max_val}"
        return True, ""

    # ── non-empty ─────────────────────────────────────────────────────────
    @staticmethod
    def non_empty(value: str, name: str = "value") -> Tuple[bool, str]:
        """Check string is not empty after stripping."""
        if not value or not value.strip():
            return False, f"{name} cannot be empty"
        return True, ""

    # ── email (basic) ─────────────────────────────────────────────────────
    @staticmethod
    def email(value: str) -> Tuple[bool, str]:
        """Very basic email format check."""
        if not value or "@" not in value or "." not in value.split("@")[-1]:
            return False, "Invalid email format"
        return True, ""

    # ── URL (basic) ───────────────────────────────────────────────────────
    @staticmethod
    def url(value: str) -> Tuple[bool, str]:
        """Basic URL format check."""
        if not value.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"
        return True, ""

    # ── sanitize for speech ───────────────────────────────────────────────
    @staticmethod
    def sanitize_for_speech(text: str) -> str:
        """
        Remove or replace characters that could break TTS or cause confusion.
        """
        # strip control chars
        text = "".join(c for c in text if c.isprintable() or c.isspace())
        # collapse multiple spaces
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # ── sanitize for logging ──────────────────────────────────────────────
    @staticmethod
    def sanitize_for_log(text: str) -> str:
        """
        Remove sensitive patterns before logging (passwords, tokens).
        """
        # redact things that look like passwords or tokens
        text = re.sub(r"password[:\s=]+\S+", "password=***", text, flags=re.IGNORECASE)
        text = re.sub(r"token[:\s=]+\S+", "token=***", text, flags=re.IGNORECASE)
        text = re.sub(r"key[:\s=]+\S+", "key=***", text, flags=re.IGNORECASE)
        return text