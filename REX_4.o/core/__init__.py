# core/__init__.py  — REX 4.0 Core Package
#
# Public surface that every other package imports from.
# Nothing else in the tree should reach into core's internals directly.

from core.config  import SystemConfig, get_config
from core.logger  import Logger, get_logger, LogLevel, LogCategory
from core.auth    import AuthManager, Permission, Role
from core.speech  import SpeechEngine
from core.listener import VoiceListener
from core.intent  import IntentClassifier, IntentType, IntentResult

__all__ = [
    # config
    "SystemConfig", "get_config",
    # logger
    "Logger", "get_logger", "LogLevel", "LogCategory",
    # auth
    "AuthManager", "Permission", "Role",
    # speech
    "SpeechEngine",
    # listener
    "VoiceListener",
    # intent
    "IntentClassifier", "IntentType", "IntentResult",
]