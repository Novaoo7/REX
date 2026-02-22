# ==============================================================================
# commands/types.py   –  REX 4.0   Shared Command Types
# ==============================================================================
# This module contains shared types used across the commands package to avoid
# circular imports between handler.py and system_control.py.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CommandResult:
    """
    Standard envelope for all command execution results.
    
    Every handler returns this so the main loop knows:
    - Did it work? (success)
    - What should I say? (message)
    - Any extra data? (data)
    - What went wrong? (error)
    - How long did it take? (duration)
    """
    success:  bool
    message:  str                                       # what to speak back
    data:     Dict[str, Any]     = field(default_factory=dict)
    error:    Optional[str]      = None
    duration: float              = 0.0                  # seconds