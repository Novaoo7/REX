# commands/__init__.py  — REX 4.0 Commands Package
#
# Exposes the single entry-point every caller needs:
#   result = await CommandRouter.execute(intent_result, session_id)

from commands.types            import CommandResult
from commands.handler          import CommandRouter
from commands.system_control   import SystemCommands
from commands.advanced_features import AdvancedCommands

__all__ = ["CommandResult", "CommandRouter", "SystemCommands", "AdvancedCommands"]