"""Event system for loose coupling between components.

This module provides a simple synchronous event bus for decoupling
components and enabling extensibility through event subscription.
"""

from abc import ABC
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, TypeVar

from rich.console import Console

_console = Console(stderr=True)

# Type aliases
EventHandler = Callable[["Event"], None]
T = TypeVar("T", bound="Event")


# =============================================================================
# Base Event Class
# =============================================================================


@dataclass
class Event(ABC):
    """Base class for all events.

    All events should inherit from this class and define their
    specific attributes as dataclass fields.
    """

    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def event_type(self) -> str:
        """Return the event type name (class name)."""
        return self.__class__.__name__


# =============================================================================
# Loop Events
# =============================================================================


@dataclass
class LoopStartedEvent(Event):
    """Emitted when the agent loop starts."""

    session_id: str = ""
    user_message: str = ""


@dataclass
class LoopCompletedEvent(Event):
    """Emitted when the agent loop completes."""

    session_id: str = ""
    termination_reason: str = ""
    total_turns: int = 0
    duration_ms: float = 0.0


@dataclass
class TurnStartedEvent(Event):
    """Emitted when a new turn starts."""

    turn_number: int = 0
    max_turns: int = 0


@dataclass
class TurnCompletedEvent(Event):
    """Emitted when a turn completes."""

    turn_number: int = 0
    tool_calls_count: int = 0


# =============================================================================
# State Events
# =============================================================================


@dataclass
class StateChangedEvent(Event):
    """Emitted when the loop state changes."""

    old_state: str = ""
    new_state: str = ""


# =============================================================================
# LLM Events
# =============================================================================


@dataclass
class LLMRequestEvent(Event):
    """Emitted before an LLM request."""

    message_count: int = 0
    has_tools: bool = False


@dataclass
class LLMResponseEvent(Event):
    """Emitted after receiving an LLM response."""

    stop_reason: str = ""
    has_tool_use: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0


# =============================================================================
# Tool Events
# =============================================================================


@dataclass
class ToolExecutionStartedEvent(Event):
    """Emitted before a tool is executed."""

    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionCompletedEvent(Event):
    """Emitted after a tool execution completes."""

    tool_name: str = ""
    success: bool = True
    duration_ms: float = 0.0
    output_preview: str = ""  # First 200 characters


@dataclass
class ToolApprovalRequestedEvent(Event):
    """Emitted when tool approval is requested."""

    tool_name: str = ""
    description: str = ""


@dataclass
class ToolApprovalResultEvent(Event):
    """Emitted when tool approval result is received."""

    tool_name: str = ""
    approved: bool = False


# =============================================================================
# Message Events
# =============================================================================


@dataclass
class MessageAddedEvent(Event):
    """Emitted when a message is added to the session."""

    role: str = ""
    part_count: int = 0


# =============================================================================
# Context Events
# =============================================================================


@dataclass
class ContextCompactionEvent(Event):
    """Emitted when context compaction is performed."""

    tokens_before: int = 0
    tokens_after: int = 0
    messages_removed: int = 0


# =============================================================================
# EventBus
# =============================================================================


class EventBus:
    """Simple synchronous event bus.

    Supports subscribing to specific event types or all events.
    Handlers are called synchronously in subscription order.
    Handler errors are caught and logged but don't affect other handlers.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(
        self,
        event_type: type[T],
        handler: Callable[[T], None],
    ) -> Callable[[], None]:
        """Subscribe to a specific event type.

        Args:
            event_type: The event class to subscribe to
            handler: Callback function that receives the event

        Returns:
            Unsubscribe function - call to remove the subscription
        """
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

        def unsubscribe() -> None:
            try:
                self._handlers[event_type].remove(handler)  # type: ignore[arg-type]
            except ValueError:
                pass  # Already removed

        return unsubscribe

    def subscribe_all(self, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to all events.

        Args:
            handler: Callback function that receives any event

        Returns:
            Unsubscribe function - call to remove the subscription
        """
        self._global_handlers.append(handler)

        def unsubscribe() -> None:
            try:
                self._global_handlers.remove(handler)
            except ValueError:
                pass  # Already removed

        return unsubscribe

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        Type-specific handlers are called first, then global handlers.
        Handler errors are caught and printed but don't stop other handlers.

        Args:
            event: The event to publish
        """
        # Type-specific handlers
        for handler in self._handlers.get(type(event), []):
            try:
                handler(event)
            except Exception as e:
                _console.print(f"[yellow][EventBus][/yellow] Handler error for {event.event_type}: {e}")

        # Global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                _console.print(f"[yellow][EventBus][/yellow] Global handler error for {event.event_type}: {e}")

    def clear(self) -> None:
        """Clear all subscriptions."""
        self._handlers.clear()
        self._global_handlers.clear()


# =============================================================================
# Global EventBus Instance
# =============================================================================

_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the default global event bus instance.

    Creates a new instance on first call. Use this for simple cases
    where dependency injection is not needed.
    """
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
