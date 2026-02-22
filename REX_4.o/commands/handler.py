# ==============================================================================
# commands/handler.py   –  REX 4.0   Command Router
# ==============================================================================
# Design
#   • CommandRouter is the single entry-point for every recognised intent.
#   • It holds a registry (dict) mapping IntentType → (handler_fn, Permission).
#     Adding a new command = one line in the registry.
#   • Before calling the handler it checks the caller's session has the
#     required permission; on failure it returns a clear error envelope.
#   • Every handler returns a CommandResult dataclass.  The caller (main loop)
#     speaks result.message and logs result.success / result.error.
#   • Execution is wrapped in a timer so we can log & alert on slow commands.
# ==============================================================================

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.intent import IntentType, IntentResult
from core.auth   import Permission, get_auth
from core.logger import get_logger, LogCategory
from core.config import get_config

from commands.types             import CommandResult
from commands.system_control    import SystemCommands
from commands.advanced_features import AdvancedCommands


# ─── Registry entry ───────────────────────────────────────────────────────────


@dataclass
class _RouteEntry:
    handler:    Callable[[IntentResult, str], CommandResult]
    permission: Optional[Permission]   # None = no permission required


# ─── Router ───────────────────────────────────────────────────────────────────


class CommandRouter:
    """
    Maps intents to handler functions, checks permissions, logs everything.

    Instantiate once at startup; call  execute(intent_result, session_token).
    """

    # Slow-command threshold (seconds) – triggers a warning log
    SLOW_THRESHOLD = 5.0

    def __init__(self) -> None:
        self._logger  = get_logger()
        self._sys     = SystemCommands()
        self._adv     = AdvancedCommands()
        self._routes: Dict[IntentType, _RouteEntry] = {}
        self._build_routes()

    # ── route table ───────────────────────────────────────────────────────
    def _build_routes(self) -> None:
        S = self._sys
        A = self._adv
        P = Permission

        self._routes = {
            # ── meta (no permission needed) ──
            IntentType.GREETING:        _RouteEntry(self._handle_greeting,      None),
            IntentType.FAREWELL:        _RouteEntry(self._handle_farewell,      None),
            IntentType.HELP:            _RouteEntry(self._handle_help,          None),
            IntentType.STATUS:          _RouteEntry(self._handle_status,        None),
            IntentType.REPEAT:          _RouteEntry(self._handle_repeat,        None),
            IntentType.TIME_QUERY:      _RouteEntry(self._handle_time,          None),
            IntentType.DATE_QUERY:      _RouteEntry(self._handle_date,          None),

            # ── app control ──
            IntentType.APP_OPEN:        _RouteEntry(S.open_app,                 P.APP_OPEN),
            IntentType.APP_CLOSE:       _RouteEntry(S.close_app,               P.APP_CLOSE),
            IntentType.APP_MINIMIZE:    _RouteEntry(S.minimize_window,         P.APP_OPEN),
            IntentType.APP_MAXIMIZE:    _RouteEntry(S.maximize_window,         P.APP_OPEN),
            IntentType.APP_SWITCH:      _RouteEntry(S.switch_window,           P.APP_OPEN),

            # ── file ops ──
            IntentType.FILE_OPEN:       _RouteEntry(S.open_file,               P.FILE_READ),
            IntentType.FILE_SEARCH:     _RouteEntry(S.search_file,             P.FILE_READ),
            IntentType.FOLDER_OPEN:     _RouteEntry(S.open_folder,             P.FILE_READ),

            # ── system ──
            IntentType.SYSTEM_SHUTDOWN: _RouteEntry(S.shutdown_system,         P.SYSTEM_SHUTDOWN),
            IntentType.SYSTEM_RESTART:  _RouteEntry(S.restart_system,          P.SYSTEM_RESTART),
            IntentType.SYSTEM_SLEEP:    _RouteEntry(S.sleep_system,            P.SYSTEM_SLEEP),
            IntentType.SYSTEM_LOCK:     _RouteEntry(S.lock_system,             P.SYSTEM_LOCK),
            IntentType.VOLUME_CONTROL:  _RouteEntry(S.volume_control,          P.VOLUME_CONTROL),
            IntentType.BRIGHTNESS:      _RouteEntry(S.brightness_control,      P.VOLUME_CONTROL),

            # ── advanced ──
            IntentType.WEB_SEARCH:      _RouteEntry(A.web_search,              P.WEB_SEARCH),
            IntentType.SET_REMINDER:    _RouteEntry(A.set_reminder,            P.SET_REMINDER),
            IntentType.SET_ALARM:       _RouteEntry(A.set_alarm,               P.SET_REMINDER),
            IntentType.SEND_EMAIL:      _RouteEntry(A.send_email,              P.SEND_EMAIL),

            # ── routines ──
            IntentType.RUN_ROUTINE:     _RouteEntry(A.run_routine,             P.ROUTINE_RUN),
            IntentType.LIST_ROUTINES:   _RouteEntry(A.list_routines,           P.ROUTINE_RUN),

            # ── user mgmt ──
            IntentType.CREATE_USER:     _RouteEntry(A.create_user,             P.USER_MANAGE),
            IntentType.DELETE_USER:     _RouteEntry(A.delete_user,             P.USER_MANAGE),
            IntentType.CHANGE_PASSWORD: _RouteEntry(A.change_password,         None),   # own password

            # ── config ──
            IntentType.CONFIG_VIEW:     _RouteEntry(self._handle_config_view,  P.LOG_VIEW),
            IntentType.CONFIG_EDIT:     _RouteEntry(self._handle_config_edit,  P.CONFIG_EDIT),

            # ── clarification ──
            IntentType.YES:             _RouteEntry(self._handle_confirmation, None),
            IntentType.NO:              _RouteEntry(self._handle_confirmation, None),
            IntentType.CANCEL:          _RouteEntry(self._handle_confirmation, None),
        }

    # ── execute ───────────────────────────────────────────────────────────
    def execute(self, intent_result: IntentResult, session_token: str) -> CommandResult:
        """
        Route *intent_result* to the right handler after permission checks.

        Returns a CommandResult in all cases – never raises.
        """
        intent = intent_result.intent
        route  = self._routes.get(intent)

        if route is None:
            self._logger.warning(LogCategory.COMMAND, f"No route for intent: {intent.value}")
            return CommandResult(
                success=False,
                message=f"I don't know how to handle '{intent.value}'. Say 'help' for a list of commands.",
                error="no_route",
            )

        # ── permission gate ──
        if route.permission is not None:
            auth = get_auth()
            if not auth.session_has_permission(session_token, route.permission):
                self._logger.warning(LogCategory.SECURITY,
                                     f"Permission denied: {route.permission.value}",
                                     {"intent": intent.value})
                return CommandResult(
                    success=False,
                    message="Sorry, you don't have permission to do that.",
                    error="permission_denied",
                )

        # ── execute with timing ──
        start = time.time()
        try:
            result = route.handler(intent_result, session_token)
        except Exception as exc:
            elapsed = time.time() - start
            self._logger.error(LogCategory.COMMAND,
                               f"Handler for {intent.value} raised: {exc}",
                               {"duration_sec": round(elapsed, 3)})
            return CommandResult(success=False,
                                 message="An error occurred while processing that command.",
                                 error=str(exc),
                                 duration=elapsed)

        elapsed = time.time() - start
        result.duration = elapsed

        if elapsed > self.SLOW_THRESHOLD:
            self._logger.warning(LogCategory.PERFORMANCE,
                                 f"Slow command: {intent.value} took {elapsed:.2f}s")

        self._logger.info(LogCategory.COMMAND,
                          f"{intent.value} → {'OK' if result.success else 'FAIL'}",
                          {"duration_sec": round(elapsed, 3), "error": result.error})
        return result

    # ── list of supported intents (for help) ──────────────────────────────
    def supported_intents(self) -> List[str]:
        return [i.value for i in self._routes]

    # ── built-in handlers ─────────────────────────────────────────────────
    # (simple handlers that don't need their own module)

    # last spoken message – stored so REPEAT works
    _last_message: str = ""

    @staticmethod
    def _handle_greeting(ir: IntentResult, _token: str) -> CommandResult:
        from datetime import datetime
        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        msg = f"{greeting}! How can I help you?"
        CommandRouter._last_message = msg
        return CommandResult(success=True, message=msg)

    @staticmethod
    def _handle_farewell(ir: IntentResult, _token: str) -> CommandResult:
        msg = "Goodbye! Have a great day."
        CommandRouter._last_message = msg
        return CommandResult(success=True, message=msg, data={"action": "farewell"})

    @staticmethod
    def _handle_help(ir: IntentResult, _token: str) -> CommandResult:
        categories = {
            "Apps":       "open, close, minimize, maximize, switch",
            "Files":      "open file, find file, open folder",
            "System":     "shutdown, restart, sleep, lock, volume, brightness",
            "Info":       "time, date, status, show logs, show config",
            "Advanced":   "search, remind me, set alarm, send email",
            "Routines":   "run routine, list routines",
            "Users":      "create user, delete user, change password",
            "Meta":       "help, repeat, cancel",
        }
        lines = ["Here's what I can do:"]
        for cat, cmds in categories.items():
            lines.append(f"{cat}: {cmds}.")
        msg = " ".join(lines)
        CommandRouter._last_message = msg
        return CommandResult(success=True, message=msg)

    @staticmethod
    def _handle_status(ir: IntentResult, _token: str) -> CommandResult:
        import psutil, platform
        cpu  = psutil.cpu_percent(interval=0.3)
        ram  = psutil.virtual_memory().percent
        msg  = (f"REX 4.0 is running on {platform.node()}. "
                f"CPU usage is {cpu} percent. RAM usage is {ram} percent. All systems operational.")
        CommandRouter._last_message = msg
        return CommandResult(success=True, message=msg,
                             data={"cpu": cpu, "ram": ram})

    @staticmethod
    def _handle_time(ir: IntentResult, _token: str) -> CommandResult:
        from datetime import datetime
        from core.speech import SpeechFormatter
        now = datetime.now()
        msg = f"The current time is {SpeechFormatter.format_time(now.hour, now.minute)}."
        CommandRouter._last_message = msg
        return CommandResult(success=True, message=msg)

    @staticmethod
    def _handle_date(ir: IntentResult, _token: str) -> CommandResult:
        from datetime import datetime
        now  = datetime.now()
        days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        months = ["January","February","March","April","May","June",
                  "July","August","September","October","November","December"]
        msg = f"Today is {days[now.weekday()]}, {months[now.month-1]} {now.day}, {now.year}."
        CommandRouter._last_message = msg
        return CommandResult(success=True, message=msg)

    @staticmethod
    def _handle_repeat(ir: IntentResult, _token: str) -> CommandResult:
        if CommandRouter._last_message:
            return CommandResult(success=True, message=CommandRouter._last_message)
        return CommandResult(success=True, message="I don't have anything to repeat yet.")

    @staticmethod
    def _handle_config_view(ir: IntentResult, _token: str) -> CommandResult:
        cfg = get_config()
        cfg.display()
        return CommandResult(success=True, message="Configuration displayed on screen.")

    @staticmethod
    def _handle_config_edit(ir: IntentResult, _token: str) -> CommandResult:
        return CommandResult(success=True,
                             message="Configuration editing is available through the console. "
                                     "Please modify config.json directly and restart REX.")

    @staticmethod
    def _handle_confirmation(ir: IntentResult, _token: str) -> CommandResult:
        # The actual confirmation logic lives in the main loop which checks
        # intent_result.intent and resolves the pending action.  This handler
        # is a placeholder that the main loop intercepts before it gets here.
        return CommandResult(success=True, message=f"Understood: {ir.intent.value}.",
                             data={"confirmation": ir.intent.value})