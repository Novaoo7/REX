# ==============================================================================
# core/auth.py   –  REX 4.0   Authentication & Authorisation
# ==============================================================================
# Responsibilities
#   • Password hashing  – PBKDF2-SHA256, 200 000 iterations, random 32-byte salt.
#   • User store        – JSON file on disk; loaded into memory, written back
#                         atomically (write temp → rename) on every mutation.
#   • Session tokens    – random 32-byte hex strings; stored in memory with an
#                         expiry timestamp.  validate_session() is the single
#                         gate every protected operation passes through.
#   • RBAC              – four Roles (ADMIN > POWER_USER > USER > GUEST) each
#                         with a fixed Permission set.  has_permission() is the
#                         only authorisation check the rest of the codebase needs.
#   • Account lockout   – after N failed attempts in a row the account is frozen
#                         for a configurable duration.
#   • Audit log         – every auth event is written to a separate
#                         auth_audit.jsonl file via the shared Logger.
#   • Password policy   – min length, upper, lower, digit, special, expiry.
#
# Thread safety
#   All mutable state is guarded by a single threading.Lock.
# ==============================================================================

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.config import get_config
from core.logger import get_logger, LogCategory


# ─── Enums ────────────────────────────────────────────────────────────────────


class Role(Enum):
    ADMIN      = "admin"
    POWER_USER = "power_user"
    USER       = "user"
    GUEST      = "guest"


class Permission(Enum):
    # application
    APP_OPEN       = "app_open"
    APP_CLOSE      = "app_close"
    # files
    FILE_READ      = "file_read"
    FILE_WRITE     = "file_write"
    FILE_DELETE    = "file_delete"
    # system
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_RESTART  = "system_restart"
    SYSTEM_SLEEP    = "system_sleep"
    SYSTEM_LOCK     = "system_lock"
    VOLUME_CONTROL  = "volume_control"
    # intelligence
    ROUTINE_CREATE  = "routine_create"
    ROUTINE_RUN     = "routine_run"
    ROUTINE_DELETE  = "routine_delete"
    MEMORY_WRITE    = "memory_write"
    # advanced
    WEB_SEARCH     = "web_search"
    SEND_EMAIL     = "send_email"
    SET_REMINDER   = "set_reminder"
    # admin
    USER_MANAGE    = "user_manage"
    CONFIG_EDIT    = "config_edit"
    LOG_VIEW       = "log_view"
    AUDIT_VIEW     = "audit_view"


# Pre-computed sets so has_permission() is O(1)
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.GUEST: {
        Permission.APP_OPEN,
        Permission.FILE_READ,
        Permission.WEB_SEARCH,
    },
    Role.USER: {
        Permission.APP_OPEN,    Permission.APP_CLOSE,
        Permission.FILE_READ,   Permission.FILE_WRITE,
        Permission.SYSTEM_SLEEP, Permission.SYSTEM_LOCK,
        Permission.VOLUME_CONTROL,
        Permission.WEB_SEARCH,  Permission.SET_REMINDER,
        Permission.ROUTINE_RUN,
        Permission.MEMORY_WRITE,
    },
    Role.POWER_USER: set(),   # filled below
    Role.ADMIN:      set(),   # filled below
}
# POWER_USER = USER + routine-management + log-view
ROLE_PERMISSIONS[Role.POWER_USER] = ROLE_PERMISSIONS[Role.USER] | {
    Permission.FILE_DELETE,
    Permission.ROUTINE_CREATE, Permission.ROUTINE_DELETE,
    Permission.LOG_VIEW,
    Permission.SEND_EMAIL,
    Permission.SYSTEM_SHUTDOWN, Permission.SYSTEM_RESTART,
}
# ADMIN = everything
ROLE_PERMISSIONS[Role.ADMIN] = set(Permission)


# ─── Data shapes ──────────────────────────────────────────────────────────────


@dataclass
class UserRecord:
    username:        str
    password_hash:   str
    salt:            str          # hex-encoded 32 bytes
    role:            str          # Role.value
    created_at:      str          # ISO 8601
    last_login:      Optional[str] = None
    password_changed_at: Optional[str] = None
    failed_attempts: int          = 0
    locked_until:    Optional[float] = None   # epoch

    def to_dict(self) -> dict:
        return {
            "username":            self.username,
            "password_hash":       self.password_hash,
            "salt":                self.salt,
            "role":                self.role,
            "created_at":          self.created_at,
            "last_login":          self.last_login,
            "password_changed_at": self.password_changed_at,
            "failed_attempts":     self.failed_attempts,
            "locked_until":        self.locked_until,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UserRecord":
        return cls(**d)


@dataclass
class Session:
    token:       str
    username:    str
    role:        Role
    created_at:  float    # epoch
    expires_at:  float    # epoch
    last_active: float    # epoch


# ─── AuthManager ──────────────────────────────────────────────────────────────


class AuthManager:
    """
    Central authentication & authorisation service.

    Instantiate once at application start; pass around by reference or
    access via the module-level singleton get_auth().
    """

    ITERATIONS = 200_000
    SALT_BYTES = 32
    TOKEN_BYTES = 32

    def __init__(self) -> None:
        self._cfg     = get_config()
        self._logger  = get_logger()
        self._lock    = threading.Lock()

        self._users:    Dict[str, UserRecord] = {}
        self._sessions: Dict[str, Session]    = {}

        self._store_path = Path(self._cfg.paths.users_file)
        self._load_users()

        # Seed a default admin if the store is empty
        if not self._users:
            self._seed_admin()

    # ── internal helpers ──────────────────────────────────────────────────
    @staticmethod
    def _hash_password(password: str, salt_hex: str) -> str:
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            200_000,
        )
        return dk.hex()

    def _load_users(self) -> None:
        if not self._store_path.exists():
            return
        try:
            with open(self._store_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            for rec in raw.get("users", []):
                self._users[rec["username"]] = UserRecord.from_dict(rec)
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            self._logger.error(LogCategory.AUTH, f"Failed to load user store: {exc}")

    def _persist_users(self) -> None:
        """Atomic write: temp file → rename."""
        tmp = self._store_path.with_suffix(".tmp")
        data = {"users": [u.to_dict() for u in self._users.values()]}
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            tmp.replace(self._store_path)
        except OSError as exc:
            self._logger.error(LogCategory.AUTH, f"Failed to persist users: {exc}")

    def _seed_admin(self) -> None:
        """Create the initial admin account with a known-weak password.
        The user is expected to change it on first login via the CLI prompt."""
        salt = os.urandom(self.SALT_BYTES).hex()
        hashed = self._hash_password("Admin@123!", salt)
        admin = UserRecord(
            username="admin",
            password_hash=hashed,
            salt=salt,
            role=Role.ADMIN.value,
            created_at=datetime.now().isoformat(),
            password_changed_at=datetime.now().isoformat(),
        )
        self._users["admin"] = admin
        self._persist_users()
        self._logger.info(LogCategory.AUTH, "Default admin account created – change password immediately")

    def _audit(self, event: str, username: str, details: Optional[dict] = None) -> None:
        self._logger.info(LogCategory.SECURITY, event, {
            "username": username,
            **(details or {}),
        })

    # ── password policy ───────────────────────────────────────────────────
    def validate_password(self, password: str) -> Tuple[bool, List[str]]:
        """Return (ok, list-of-violations)."""
        sec  = self._cfg.security
        errs: List[str] = []

        if len(password) < sec.password_min_length:
            errs.append(f"Must be at least {sec.password_min_length} characters")
        if sec.password_require_upper and not any(c.isupper() for c in password):
            errs.append("Must contain at least one uppercase letter")
        if sec.password_require_lower and not any(c.islower() for c in password):
            errs.append("Must contain at least one lowercase letter")
        if sec.password_require_digit and not any(c.isdigit() for c in password):
            errs.append("Must contain at least one digit")
        if sec.password_require_special:
            specials = set("!@#$%^&*()-_=+[]{}|;:',.<>?/`~")
            if not any(c in specials for c in password):
                errs.append("Must contain at least one special character")

        return len(errs) == 0, errs

    # ── account CRUD ──────────────────────────────────────────────────────
    def create_user(self, username: str, password: str, role: Role = Role.USER) -> Tuple[bool, str]:
        """
        Returns (success, message).
        """
        with self._lock:
            if username in self._users:
                return False, f"User '{username}' already exists"

            ok, errs = self.validate_password(password)
            if not ok:
                return False, "Password policy: " + "; ".join(errs)

            salt   = os.urandom(self.SALT_BYTES).hex()
            hashed = self._hash_password(password, salt)

            self._users[username] = UserRecord(
                username=username,
                password_hash=hashed,
                salt=salt,
                role=role.value,
                created_at=datetime.now().isoformat(),
                password_changed_at=datetime.now().isoformat(),
            )
            self._persist_users()
            self._audit("user_created", username, {"role": role.value})
            return True, f"User '{username}' created with role {role.value}"

    def delete_user(self, username: str) -> Tuple[bool, str]:
        with self._lock:
            if username == "admin":
                return False, "Cannot delete the admin account"
            if username not in self._users:
                return False, f"User '{username}' not found"
            del self._users[username]
            # invalidate any live sessions for this user
            dead = [t for t, s in self._sessions.items() if s.username == username]
            for t in dead:
                del self._sessions[t]
            self._persist_users()
            self._audit("user_deleted", username)
            return True, f"User '{username}' deleted"

    def change_password(self, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        with self._lock:
            user = self._users.get(username)
            if user is None:
                return False, "User not found"

            # verify old
            if self._hash_password(old_password, user.salt) != user.password_hash:
                return False, "Current password is incorrect"

            ok, errs = self.validate_password(new_password)
            if not ok:
                return False, "New password policy: " + "; ".join(errs)

            user.salt = os.urandom(self.SALT_BYTES).hex()
            user.password_hash = self._hash_password(new_password, user.salt)
            user.password_changed_at = datetime.now().isoformat()
            user.failed_attempts = 0
            self._persist_users()
            self._audit("password_changed", username)
            return True, "Password changed successfully"

    # ── authentication ────────────────────────────────────────────────────
    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Returns (success, session_token_or_None, error_message_or_None).
        """
        with self._lock:
            user = self._users.get(username)
            if user is None:
                self._audit("login_failed", username, {"reason": "user_not_found"})
                return False, None, "Invalid username or password"

            # lockout check
            if user.locked_until and time.time() < user.locked_until:
                remaining = int(user.locked_until - time.time())
                self._audit("login_blocked", username, {"seconds_remaining": remaining})
                return False, None, f"Account locked. Try again in {remaining} seconds"

            # hash & compare
            if self._hash_password(password, user.salt) != user.password_hash:
                user.failed_attempts += 1
                max_att = self._cfg.security.max_login_attempts
                if user.failed_attempts >= max_att:
                    user.locked_until = time.time() + self._cfg.security.lockout_duration_seconds
                    self._persist_users()
                    self._audit("account_locked", username)
                    return False, None, "Account locked due to too many failed attempts"
                self._persist_users()
                self._audit("login_failed", username, {"reason": "bad_password",
                            "attempts": user.failed_attempts})
                return False, None, "Invalid username or password"

            # ── success ──
            user.failed_attempts = 0
            user.locked_until    = None
            user.last_login      = datetime.now().isoformat()
            self._persist_users()

            # create session
            token    = secrets.token_hex(self.TOKEN_BYTES)
            timeout  = self._cfg.security.session_timeout_seconds
            now      = time.time()
            self._sessions[token] = Session(
                token=token,
                username=username,
                role=Role(user.role),
                created_at=now,
                expires_at=now + timeout,
                last_active=now,
            )
            self._audit("login_success", username)
            return True, token, None

    # ── session management ────────────────────────────────────────────────
    def validate_session(self, token: str) -> Tuple[bool, Optional[Session]]:
        """
        Returns (valid, session_or_None).
        Silently evicts expired sessions.
        """
        session = self._sessions.get(token)
        if session is None:
            return False, None

        if time.time() > session.expires_at:
            del self._sessions[token]
            self._audit("session_expired", session.username)
            return False, None

        # touch
        session.last_active = time.time()
        return True, session

    def logout(self, token: str) -> bool:
        session = self._sessions.pop(token, None)
        if session:
            self._audit("logout", session.username)
            return True
        return False

    def get_active_sessions(self) -> List[dict]:
        now = time.time()
        out = []
        for s in list(self._sessions.values()):
            if now > s.expires_at:
                continue
            out.append({
                "username":   s.username,
                "role":       s.role.value,
                "created_at": datetime.fromtimestamp(s.created_at).isoformat(),
                "expires_at": datetime.fromtimestamp(s.expires_at).isoformat(),
            })
        return out

    # ── authorisation ─────────────────────────────────────────────────────
    @staticmethod
    def has_permission(role: Role, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS.get(role, set())

    def session_has_permission(self, token: str, permission: Permission) -> bool:
        valid, session = self.validate_session(token)
        if not valid or session is None:
            return False
        return self.has_permission(session.role, permission)

    # ── introspection ─────────────────────────────────────────────────────
    def list_users(self) -> List[dict]:
        return [
            {
                "username":  u.username,
                "role":      u.role,
                "created":   u.created_at,
                "last_login": u.last_login,
                "locked":    u.locked_until is not None and time.time() < (u.locked_until or 0),
            }
            for u in self._users.values()
        ]

    def get_user(self, username: str) -> Optional[dict]:
        u = self._users.get(username)
        if u is None:
            return None
        return {
            "username":          u.username,
            "role":              u.role,
            "created_at":        u.created_at,
            "last_login":        u.last_login,
            "password_changed":  u.password_changed_at,
            "locked":            u.locked_until is not None and time.time() < (u.locked_until or 0),
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_AUTH: Optional[AuthManager] = None


def get_auth() -> AuthManager:
    global _AUTH
    if _AUTH is None:
        _AUTH = AuthManager()
    return _AUTH