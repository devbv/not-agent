"""Agent loop states and context.

에이전트 루프의 상태 관리를 위한 enum과 컨텍스트 클래스 정의.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
import time


class LoopState(Enum):
    """에이전트 루프의 현재 상태."""

    IDLE = auto()               # 대기 중 (run() 호출 전)
    RECEIVING_INPUT = auto()    # 사용자 입력 수신 중
    CALLING_LLM = auto()        # LLM API 호출 중
    PROCESSING_RESPONSE = auto()  # LLM 응답 분석 중
    EXECUTING_TOOLS = auto()    # 도구 실행 중
    CHECKING_CONTEXT = auto()   # 컨텍스트 크기 확인 중
    COMPLETED = auto()          # 정상 완료
    ERROR = auto()              # 에러 발생


class TerminationReason(Enum):
    """루프 종료 사유."""

    END_TURN = auto()           # LLM이 도구 없이 응답 (정상 종료)
    MAX_TURNS = auto()          # 최대 턴 수 도달
    STOP_REASON = auto()        # LLM stop_reason이 특정 값
    USER_INTERRUPT = auto()     # 사용자가 중단 (Ctrl+C)
    ERROR = auto()              # 에러 발생으로 종료
    TOOL_STOP = auto()          # 도구가 종료 요청 (예: exit 명령)


@dataclass
class LoopContext:
    """현재 루프 실행 컨텍스트.

    루프의 실행 상태, 통계, 종료 정보를 추적합니다.
    """

    # 상태
    state: LoopState = LoopState.IDLE
    termination_reason: TerminationReason | None = None

    # 턴 정보
    current_turn: int = 0
    max_turns: int = 20

    # 에러
    last_error: Exception | None = None

    # 통계
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    start_time: float | None = None
    end_time: float | None = None

    # 상태 변경 이력 (디버깅용)
    _state_history: list[tuple[float, LoopState]] = field(default_factory=list)

    def is_running(self) -> bool:
        """루프가 실행 중인지 확인."""
        return self.state not in (
            LoopState.IDLE,
            LoopState.COMPLETED,
            LoopState.ERROR,
        )

    def is_finished(self) -> bool:
        """루프가 종료되었는지 확인."""
        return self.state in (LoopState.COMPLETED, LoopState.ERROR)

    def duration_ms(self) -> float | None:
        """실행 시간 (밀리초)."""
        if self.start_time is not None:
            end = self.end_time or time.time()
            return (end - self.start_time) * 1000
        return None

    def record_state(self, state: LoopState) -> None:
        """상태 변경 기록 (이력 추적용)."""
        self._state_history.append((time.time(), state))
        self.state = state

    def reset(self) -> None:
        """컨텍스트 초기화."""
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
        """컨텍스트를 딕셔너리로 변환 (직렬화용)."""
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
