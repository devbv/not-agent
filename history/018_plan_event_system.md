# 2.4 이벤트 시스템 도입 계획

**작성일**: 2026-01-11
**우선순위**: 🟡 중간
**예상 작업량**: 중간

---

## 1. 현재 문제점

### 1.1 컴포넌트 간 직접 호출

**현재 구조**:
```
AgentLoop
├── 직접 호출 → ToolExecutor.execute()
├── 직접 호출 → Session.add_message()
├── 직접 호출 → ContextManager.compact()
└── 직접 호출 → _debug_log()
```

**문제**:
- 모듈 간 강한 결합
- 새 기능 추가 시 많은 파일 수정 필요
- 로깅/모니터링 확장 어려움

### 1.2 확장성 제한

**예시**: "도구 실행 시간을 측정하고 싶다"
- 현재: `executor.py` 수정 필요
- 이상: 외부에서 이벤트 구독만 하면 됨

### 1.3 디버그 로깅 분산

**현재**: `_debug_log()` 호출이 코드 전체에 분산
- 로깅 로직과 비즈니스 로직 혼재
- 로깅 형식 변경 시 여러 곳 수정

---

## 2. 개선 목표

1. **느슨한 결합**: 이벤트 기반 통신
2. **확장성**: 외부에서 이벤트 구독으로 기능 추가
3. **디버깅 개선**: 로깅을 이벤트 구독자로 분리
4. **간단한 구현**: 복잡한 프레임워크 없이 기본 기능

---

## 3. 상세 설계

### 3.1 Event 기본 클래스

```python
# core/events.py

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, TypeVar
from collections import defaultdict

@dataclass
class Event(ABC):
    """이벤트 기본 클래스."""

    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def event_type(self) -> str:
        """이벤트 타입 (클래스 이름)."""
        return self.__class__.__name__
```

### 3.2 구체적인 이벤트 타입들

```python
# --- 루프 이벤트 ---

@dataclass
class LoopStartedEvent(Event):
    """루프 시작."""
    session_id: str
    user_message: str

@dataclass
class LoopCompletedEvent(Event):
    """루프 완료."""
    session_id: str
    termination_reason: str
    total_turns: int
    duration_ms: float

@dataclass
class TurnStartedEvent(Event):
    """턴 시작."""
    turn_number: int
    max_turns: int

@dataclass
class TurnCompletedEvent(Event):
    """턴 완료."""
    turn_number: int
    tool_calls_count: int


# --- 상태 이벤트 ---

@dataclass
class StateChangedEvent(Event):
    """루프 상태 변경."""
    old_state: str  # LoopState.name
    new_state: str


# --- LLM 이벤트 ---

@dataclass
class LLMRequestEvent(Event):
    """LLM 요청."""
    message_count: int
    has_tools: bool

@dataclass
class LLMResponseEvent(Event):
    """LLM 응답."""
    stop_reason: str
    has_tool_use: bool
    input_tokens: int
    output_tokens: int
    duration_ms: float


# --- 도구 이벤트 ---

@dataclass
class ToolExecutionStartedEvent(Event):
    """도구 실행 시작."""
    tool_name: str
    tool_input: dict[str, Any]

@dataclass
class ToolExecutionCompletedEvent(Event):
    """도구 실행 완료."""
    tool_name: str
    success: bool
    duration_ms: float
    output_preview: str  # 처음 200자

@dataclass
class ToolApprovalRequestedEvent(Event):
    """도구 승인 요청."""
    tool_name: str
    description: str

@dataclass
class ToolApprovalResultEvent(Event):
    """도구 승인 결과."""
    tool_name: str
    approved: bool


# --- 메시지 이벤트 ---

@dataclass
class MessageAddedEvent(Event):
    """메시지 추가."""
    role: str
    part_count: int


# --- 컨텍스트 이벤트 ---

@dataclass
class ContextCompactionEvent(Event):
    """컨텍스트 컴팩션 수행."""
    tokens_before: int
    tokens_after: int
    messages_removed: int
```

### 3.3 EventBus 클래스

```python
EventHandler = Callable[[Event], None]
T = TypeVar('T', bound=Event)

class EventBus:
    """간단한 동기 이벤트 버스."""

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(
        self,
        event_type: type[T],
        handler: Callable[[T], None],
    ) -> Callable[[], None]:
        """
        특정 이벤트 타입 구독.

        Returns:
            구독 해제 함수
        """
        self._handlers[event_type].append(handler)

        def unsubscribe():
            self._handlers[event_type].remove(handler)

        return unsubscribe

    def subscribe_all(self, handler: EventHandler) -> Callable[[], None]:
        """
        모든 이벤트 구독.

        Returns:
            구독 해제 함수
        """
        self._global_handlers.append(handler)

        def unsubscribe():
            self._global_handlers.remove(handler)

        return unsubscribe

    def publish(self, event: Event) -> None:
        """이벤트 발행."""
        # 타입별 핸들러
        for handler in self._handlers.get(type(event), []):
            try:
                handler(event)
            except Exception as e:
                # 핸들러 에러가 발행자에 영향 주지 않음
                print(f"[EventBus] Handler error: {e}")

        # 전역 핸들러
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] Global handler error: {e}")

    def clear(self) -> None:
        """모든 구독 해제."""
        self._handlers.clear()
        self._global_handlers.clear()


# 전역 이벤트 버스 (선택적 사용)
_default_bus: EventBus | None = None

def get_event_bus() -> EventBus:
    """기본 이벤트 버스 반환."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
```

### 3.4 이벤트 기반 로거

```python
# core/event_logger.py

from rich.console import Console
from .events import (
    Event, EventBus,
    LoopStartedEvent, LoopCompletedEvent,
    TurnStartedEvent, TurnCompletedEvent,
    LLMRequestEvent, LLMResponseEvent,
    ToolExecutionStartedEvent, ToolExecutionCompletedEvent,
    StateChangedEvent,
)

class EventLogger:
    """이벤트를 콘솔에 로깅하는 구독자."""

    def __init__(self, console: Console | None = None, verbose: bool = False):
        self.console = console or Console()
        self.verbose = verbose
        self._unsubscribers: list[Callable[[], None]] = []

    def attach(self, bus: EventBus) -> None:
        """이벤트 버스에 연결."""
        handlers = [
            (LoopStartedEvent, self._on_loop_started),
            (LoopCompletedEvent, self._on_loop_completed),
            (TurnStartedEvent, self._on_turn_started),
            (ToolExecutionStartedEvent, self._on_tool_started),
            (ToolExecutionCompletedEvent, self._on_tool_completed),
            (LLMResponseEvent, self._on_llm_response),
        ]

        for event_type, handler in handlers:
            unsub = bus.subscribe(event_type, handler)
            self._unsubscribers.append(unsub)

        if self.verbose:
            # 상세 모드: 모든 이벤트 로깅
            unsub = bus.subscribe_all(self._on_any_event)
            self._unsubscribers.append(unsub)

    def detach(self) -> None:
        """이벤트 버스에서 분리."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    def _on_loop_started(self, event: LoopStartedEvent) -> None:
        self.console.print(f"[dim]{'='*60}[/dim]")
        self.console.print(f"[dim][AGENT LOOP] Starting...[/dim]")

    def _on_loop_completed(self, event: LoopCompletedEvent) -> None:
        self.console.print(f"[dim][COMPLETE] {event.termination_reason}[/dim]")
        self.console.print(f"[dim]Duration: {event.duration_ms:.0f}ms, Turns: {event.total_turns}[/dim]")

    def _on_turn_started(self, event: TurnStartedEvent) -> None:
        self.console.print(f"[dim]{'─'*60}[/dim]")
        self.console.print(f"[dim][TURN {event.turn_number}/{event.max_turns}][/dim]")

    def _on_tool_started(self, event: ToolExecutionStartedEvent) -> None:
        self.console.print(f"[dim]  Tool: {event.tool_name}[/dim]")

    def _on_tool_completed(self, event: ToolExecutionCompletedEvent) -> None:
        status = "✓" if event.success else "✗"
        self.console.print(
            f"[dim]  {status} {event.tool_name} ({event.duration_ms:.0f}ms)[/dim]"
        )

    def _on_llm_response(self, event: LLMResponseEvent) -> None:
        self.console.print(
            f"[dim]  LLM: {event.input_tokens}→{event.output_tokens} tokens "
            f"({event.duration_ms:.0f}ms)[/dim]"
        )

    def _on_any_event(self, event: Event) -> None:
        self.console.print(f"[dim][EVENT] {event.event_type}[/dim]")
```

---

## 4. AgentLoop 통합

```python
# agent/loop.py

class AgentLoop:
    def __init__(
        self,
        config: Config | None = None,
        event_bus: EventBus | None = None,
        # ...
    ):
        # ...
        self.event_bus = event_bus

    def _emit(self, event: Event) -> None:
        """이벤트 발행 (버스가 있는 경우)."""
        if self.event_bus:
            self.event_bus.publish(event)

    def run(self, user_message: str, ...) -> str:
        import time
        start_time = time.time()

        self._emit(LoopStartedEvent(
            session_id=self.session.id,
            user_message=user_message[:100],
        ))

        # ...

        for turn in range(self.max_turns):
            self._emit(TurnStartedEvent(
                turn_number=turn + 1,
                max_turns=self.max_turns,
            ))

            # LLM 호출
            llm_start = time.time()
            response = self._call_llm()
            llm_duration = (time.time() - llm_start) * 1000

            self._emit(LLMResponseEvent(
                stop_reason=response.stop_reason,
                has_tool_use=bool(tool_uses),
                input_tokens=response.usage.get("input_tokens", 0),
                output_tokens=response.usage.get("output_tokens", 0),
                duration_ms=llm_duration,
            ))

            # 도구 실행
            for tool_use in tool_uses:
                self._emit(ToolExecutionStartedEvent(
                    tool_name=tool_use.name,
                    tool_input=dict(tool_use.input),
                ))

                tool_start = time.time()
                result = self.executor.execute(tool_use.name, tool_input)
                tool_duration = (time.time() - tool_start) * 1000

                self._emit(ToolExecutionCompletedEvent(
                    tool_name=tool_use.name,
                    success=result.success,
                    duration_ms=tool_duration,
                    output_preview=result.output[:200] if result.output else "",
                ))

        # 완료
        duration = (time.time() - start_time) * 1000
        self._emit(LoopCompletedEvent(
            session_id=self.session.id,
            termination_reason=self.context.termination_reason.name,
            total_turns=self.context.current_turn,
            duration_ms=duration,
        ))
```

---

## 5. CLI 통합

```python
# cli/main.py

@click.command()
@click.option("--debug", is_flag=True)
def agent(debug: bool):
    config = Config()

    # 이벤트 버스 설정
    event_bus = EventBus()

    if debug:
        logger = EventLogger(verbose=True)
        logger.attach(event_bus)

    loop = AgentLoop(config=config, event_bus=event_bus)
    # ...
```

---

## 6. 파일 변경 계획

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `core/__init__.py` | 신규 | core 패키지 초기화 |
| `core/events.py` | 신규 | Event, EventBus, 이벤트 타입들 |
| `core/event_logger.py` | 신규 | EventLogger (디버그 로깅) |
| `agent/loop.py` | 수정 | 이벤트 발행 추가 |
| `cli/main.py` | 수정 | 이벤트 버스 연결 |

---

## 7. 테스트 계획

```python
# tests/test_events.py

def test_event_bus_subscribe():
    bus = EventBus()
    received = []

    bus.subscribe(LoopStartedEvent, lambda e: received.append(e))
    bus.publish(LoopStartedEvent(session_id="123", user_message="test"))

    assert len(received) == 1
    assert received[0].session_id == "123"

def test_event_bus_unsubscribe():
    bus = EventBus()
    received = []

    unsub = bus.subscribe(LoopStartedEvent, lambda e: received.append(e))
    bus.publish(LoopStartedEvent(session_id="1", user_message=""))

    unsub()  # 구독 해제
    bus.publish(LoopStartedEvent(session_id="2", user_message=""))

    assert len(received) == 1  # 두 번째는 수신 안 함

def test_event_bus_subscribe_all():
    bus = EventBus()
    received = []

    bus.subscribe_all(lambda e: received.append(e.event_type))
    bus.publish(LoopStartedEvent(session_id="1", user_message=""))
    bus.publish(TurnStartedEvent(turn_number=1, max_turns=10))

    assert "LoopStartedEvent" in received
    assert "TurnStartedEvent" in received

def test_handler_error_isolation():
    bus = EventBus()

    def bad_handler(e):
        raise ValueError("oops")

    def good_handler(e):
        pass  # 정상 동작

    bus.subscribe(LoopStartedEvent, bad_handler)
    bus.subscribe(LoopStartedEvent, good_handler)

    # 에러가 발생해도 다른 핸들러에 영향 없음
    bus.publish(LoopStartedEvent(session_id="1", user_message=""))
```

---

## 8. 활용 예시

### 8.1 도구 실행 시간 측정

```python
from core.events import EventBus, ToolExecutionCompletedEvent

bus = EventBus()
tool_times = {}

def track_tool_time(event: ToolExecutionCompletedEvent):
    name = event.tool_name
    tool_times[name] = tool_times.get(name, []) + [event.duration_ms]

bus.subscribe(ToolExecutionCompletedEvent, track_tool_time)

# 루프 실행 후...
for tool, times in tool_times.items():
    avg = sum(times) / len(times)
    print(f"{tool}: avg {avg:.0f}ms")
```

### 8.2 토큰 사용량 추적

```python
from core.events import EventBus, LLMResponseEvent

total_tokens = {"input": 0, "output": 0}

def track_tokens(event: LLMResponseEvent):
    total_tokens["input"] += event.input_tokens
    total_tokens["output"] += event.output_tokens

bus.subscribe(LLMResponseEvent, track_tokens)
```

---

## 9. 체크리스트

- [ ] `core/__init__.py` 생성
- [ ] `core/events.py` 생성
  - [ ] Event 기본 클래스
  - [ ] 루프/상태/LLM/도구/메시지/컨텍스트 이벤트
  - [ ] EventBus 클래스
- [ ] `core/event_logger.py` 생성
  - [ ] EventLogger 클래스
- [ ] `agent/loop.py` 수정
  - [ ] event_bus 주입
  - [ ] _emit() 메서드
  - [ ] 주요 지점에 이벤트 발행
- [ ] `cli/main.py` 수정
  - [ ] 이벤트 버스 생성/연결
  - [ ] debug 모드 시 로거 활성화
- [ ] 테스트 작성
- [ ] 문서 업데이트
