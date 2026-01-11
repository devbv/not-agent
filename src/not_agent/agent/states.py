"""Agent loop states and context.

Defines enum and context classes for agent loop state management.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
import time


class LoopState(Enum):
    """Current state of agent loop."""

    IDLE = auto()               # Waiting (before run() call)
    RECEIVING_INPUT = auto()    # Receiving user input
    CALLING_LLM = auto()        # Calling LLM API
    PROCESSING_RESPONSE = auto()  # Analyzing LLM response
    EXECUTING_TOOLS = auto()    # Executing tools
    CHECKING_CONTEXT = auto()   # Checking context size
    COMPLETED = auto()          # Completed successfully
    ERROR = auto()              # Error occurred


class TerminationReason(Enum):
    """Loop termination reason."""

    END_TURN = auto()           # LLM responded without tools (normal end)
    MAX_TURNS = auto()          # Max turns reached
    STOP_REASON = auto()        # LLM stop_reason has specific value
    USER_INTERRUPT = auto()     # User interrupted (Ctrl+C)
    ERROR = auto()              # Terminated due to error
    TOOL_STOP = auto()          # Tool requested stop (e.g., exit command)


@dataclass
class LoopContext:
    """Current loop execution context.

    Tracks loop execution state, statistics, and termination info.
    """

    # State
    state: LoopState = LoopState.IDLE
    termination_reason: TerminationReason | None = None

    # Turn info
    current_turn: int = 0
    max_turns: int = 20

    # Error
    last_error: Exception | None = None

    # Statistics
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    start_time: float | None = None
    end_time: float | None = None

    # State change history (for debugging)
    _state_history: list[tuple[float, LoopState]] = field(default_factory=list)

    def is_running(self) -> bool:
        """Check if loop is running."""
        return self.state not in (
            LoopState.IDLE,
            LoopState.COMPLETED,
            LoopState.ERROR,
        )

    def is_finished(self) -> bool:
        """Check if loop has finished."""
        return self.state in (LoopState.COMPLETED, LoopState.ERROR)

    def duration_ms(self) -> float | None:
        """Execution time (milliseconds)."""
        if self.start_time is not None:
            end = self.end_time or time.time()
            return (end - self.start_time) * 1000
        return None

    def record_state(self, state: LoopState) -> None:
        """Record state change (for history tracking)."""
        self._state_history.append((time.time(), state))
        self.state = state

    def reset(self) -> None:
        """Reset context."""
        self.state = LoopState.IDLE
        self.termination_reason = None
        self.current_turn = 0
        self.last_error = None
        self.total_tool_calls = 0
        self.total_llm_calls = 0
        self.start_time = None
        self.end_time = None
        self._state_history.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary (for serialization)."""
        return {
            "state": self.state.name,
            "termination_reason": self.termination_reason.name if self.termination_reason else None,
            "current_turn": self.current_turn,
            "max_turns": self.max_turns,
            "total_tool_calls": self.total_tool_calls,
            "total_llm_calls": self.total_llm_calls,
            "duration_ms": self.duration_ms(),
            "has_error": self.last_error is not None,
        }
