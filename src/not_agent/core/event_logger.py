"""Event-based logger for debugging and monitoring.

Subscribes to events and logs them to the console.
"""

from typing import Callable

from rich.console import Console

from .events import (
    Event,
    EventBus,
    LoopStartedEvent,
    LoopCompletedEvent,
    TurnStartedEvent,
    TurnCompletedEvent,
    LLMResponseEvent,
    ToolExecutionStartedEvent,
    ToolExecutionCompletedEvent,
    StateChangedEvent,
    ContextCompactionEvent,
)


class EventLogger:
    """Logs events to the console for debugging.

    Can be attached to an EventBus to receive and display events.
    Supports normal and verbose modes.
    """

    def __init__(
        self,
        console: Console | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the event logger.

        Args:
            console: Rich console for output. Creates new one if not provided.
            verbose: If True, logs all events. If False, logs only key events.
        """
        self.console = console or Console()
        self.verbose = verbose
        self._unsubscribers: list[Callable[[], None]] = []

    def attach(self, bus: EventBus) -> None:
        """Attach to an event bus and start logging.

        Args:
            bus: The event bus to subscribe to
        """
        # Define handlers for specific events
        handlers: list[tuple[type[Event], Callable[[Event], None]]] = [
            (LoopStartedEvent, self._on_loop_started),  # type: ignore[list-item]
            (LoopCompletedEvent, self._on_loop_completed),  # type: ignore[list-item]
            (TurnStartedEvent, self._on_turn_started),  # type: ignore[list-item]
            (TurnCompletedEvent, self._on_turn_completed),  # type: ignore[list-item]
            (ToolExecutionStartedEvent, self._on_tool_started),  # type: ignore[list-item]
            (ToolExecutionCompletedEvent, self._on_tool_completed),  # type: ignore[list-item]
            (LLMResponseEvent, self._on_llm_response),  # type: ignore[list-item]
            (StateChangedEvent, self._on_state_changed),  # type: ignore[list-item]
            (ContextCompactionEvent, self._on_context_compaction),  # type: ignore[list-item]
        ]

        for event_type, handler in handlers:
            unsub = bus.subscribe(event_type, handler)
            self._unsubscribers.append(unsub)

        if self.verbose:
            # Verbose mode: log all events
            unsub = bus.subscribe_all(self._on_any_event)
            self._unsubscribers.append(unsub)

    def detach(self) -> None:
        """Detach from the event bus and stop logging."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def _on_loop_started(self, event: LoopStartedEvent) -> None:
        """Handle loop started event."""
        self.console.print(f"[dim]{'=' * 60}[/dim]")
        msg_preview = event.user_message[:80] + "..." if len(event.user_message) > 80 else event.user_message
        self.console.print(f"[dim][LOOP START] {msg_preview}[/dim]")

    def _on_loop_completed(self, event: LoopCompletedEvent) -> None:
        """Handle loop completed event."""
        self.console.print(f"[dim][LOOP END] {event.termination_reason}[/dim]")
        self.console.print(
            f"[dim]  Duration: {event.duration_ms:.0f}ms | Turns: {event.total_turns}[/dim]"
        )
        self.console.print(f"[dim]{'=' * 60}[/dim]")

    def _on_turn_started(self, event: TurnStartedEvent) -> None:
        """Handle turn started event."""
        self.console.print(f"[dim]{'─' * 60}[/dim]")
        self.console.print(f"[dim][TURN {event.turn_number}/{event.max_turns}][/dim]")

    def _on_turn_completed(self, event: TurnCompletedEvent) -> None:
        """Handle turn completed event."""
        if event.tool_calls_count > 0:
            self.console.print(
                f"[dim]  Turn {event.turn_number} completed: {event.tool_calls_count} tool(s)[/dim]"
            )

    def _on_tool_started(self, event: ToolExecutionStartedEvent) -> None:
        """Handle tool execution started event."""
        self.console.print(f"[dim]  ▶ {event.tool_name}[/dim]")

    def _on_tool_completed(self, event: ToolExecutionCompletedEvent) -> None:
        """Handle tool execution completed event."""
        status = "✓" if event.success else "✗"
        self.console.print(
            f"[dim]  {status} {event.tool_name} ({event.duration_ms:.0f}ms)[/dim]"
        )

    def _on_llm_response(self, event: LLMResponseEvent) -> None:
        """Handle LLM response event."""
        self.console.print(
            f"[dim]  LLM: {event.input_tokens}→{event.output_tokens} tokens "
            f"({event.duration_ms:.0f}ms)[/dim]"
        )

    def _on_state_changed(self, event: StateChangedEvent) -> None:
        """Handle state changed event."""
        if self.verbose:
            self.console.print(
                f"[dim][STATE] {event.old_state} → {event.new_state}[/dim]"
            )

    def _on_context_compaction(self, event: ContextCompactionEvent) -> None:
        """Handle context compaction event."""
        self.console.print(
            f"[dim]  [COMPACT] {event.tokens_before:,}→{event.tokens_after:,} tokens "
            f"(-{event.messages_removed} msgs)[/dim]"
        )

    def _on_any_event(self, event: Event) -> None:
        """Handle any event (verbose mode only)."""
        # Skip events that have dedicated handlers
        if isinstance(
            event,
            (
                LoopStartedEvent,
                LoopCompletedEvent,
                TurnStartedEvent,
                TurnCompletedEvent,
                ToolExecutionStartedEvent,
                ToolExecutionCompletedEvent,
                LLMResponseEvent,
                StateChangedEvent,
                ContextCompactionEvent,
            ),
        ):
            return

        self.console.print(f"[dim]  [EVENT] {event.event_type}[/dim]")
