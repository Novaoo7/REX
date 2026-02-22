# intelligence/__init__.py  — REX 4.0 Intelligence Package
#
# Exposes memory, conversation manager, routine engine, proactive engine,
# and command-history store.

from intelligence.context_memory  import ContextMemory
from intelligence.conversation    import ConversationManager
from intelligence.routines        import RoutineEngine
from intelligence.proactive       import ProactiveEngine
from intelligence.history         import CommandHistory

__all__ = [
    "ContextMemory",
    "ConversationManager",
    "RoutineEngine",
    "ProactiveEngine",
    "CommandHistory",
]