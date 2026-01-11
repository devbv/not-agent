"""Agent core module."""

from .executor import ToolExecutor
from .loop import AgentLoop
from .session import Session, Message
from .context import ContextManager
from .states import LoopState, TerminationReason, LoopContext
from .message import (
    MessagePart,
    TextPart,
    ToolUsePart,
    ToolResultPart,
    part_from_dict,
    part_from_anthropic,
    register_part_type,
)
from .permissions import (
    Permission,
    PermissionRule,
    PermissionManager,
)

__all__ = [
    "ToolExecutor",
    "AgentLoop",
    "Session",
    "Message",
    "ContextManager",
    "LoopState",
    "TerminationReason",
    "LoopContext",
    # Message parts
    "MessagePart",
    "TextPart",
    "ToolUsePart",
    "ToolResultPart",
    "part_from_dict",
    "part_from_anthropic",
    "register_part_type",
    # Permissions
    "Permission",
    "PermissionRule",
    "PermissionManager",
]
