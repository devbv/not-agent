"""Core components package.

Contains fundamental building blocks used across the application.
"""

from .events import (
    # Base
    Event,
    EventBus,
    EventHandler,
    get_event_bus,
    # Loop events
    LoopStartedEvent,
    LoopCompletedEvent,
    TurnStartedEvent,
    TurnCompletedEvent,
    # State events
    StateChangedEvent,
    # LLM events
    LLMRequestEvent,
    LLMResponseEvent,
    # Tool events
    ToolExecutionStartedEvent,
    ToolExecutionCompletedEvent,
    ToolApprovalRequestedEvent,
    ToolApprovalResultEvent,
    # Message events
    MessageAddedEvent,
    # Context events
    ContextCompactionEvent,
)
from .event_logger import EventLogger

__all__ = [
    # Base
    "Event",
    "EventBus",
    "EventHandler",
    "get_event_bus",
    # Loop events
    "LoopStartedEvent",
    "LoopCompletedEvent",
    "TurnStartedEvent",
    "TurnCompletedEvent",
    # State events
    "StateChangedEvent",
    # LLM events
    "LLMRequestEvent",
    "LLMResponseEvent",
    # Tool events
    "ToolExecutionStartedEvent",
    "ToolExecutionCompletedEvent",
    "ToolApprovalRequestedEvent",
    "ToolApprovalResultEvent",
    # Message events
    "MessageAddedEvent",
    # Context events
    "ContextCompactionEvent",
    # Logger
    "EventLogger",
]
