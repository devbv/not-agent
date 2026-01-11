# 2.1 에이전트 루프 구조 개선 계획

**작성일**: 2026-01-11
**우선순위**: 🔴 높음
**예상 작업량**: 중간

---

## 1. 현재 문제점

### 1.1 종료 조건이 단순함

**현재 코드** (`loop.py:216-298`):
```python
for turn in range(self.max_turns):
    response = self._call_llm()
    tool_uses = [block for block in response.content if isinstance(block, ToolUseBlock)]

    if not tool_uses:
        # 텍스트 응답만 있으면 종료
        return text_response

    # 도구 실행...

return "Max turns reached."
```

**문제**:
- 종료 조건이 `tool_uses` 유무 또는 `max_turns`에만 의존
- `stop_reason` 값을 활용하지 않음
- 사용자 중단, 에러 복구 등 상황 처리 없음

### 1.2 루프 상태 추적 없음

**현재**: 어떤 단계를 실행 중인지 외부에서 알 수 없음
- 디버깅 시 `_debug_log`만 의존
- 확장/모니터링 불가

### 1.3 에러 복구 전략 부족

**현재**: 에러 발생 시 예외 전파만
```python
except RateLimitError as e:
    raise  # 복구 없이 전파
```

---

## 2. 개선 목표

1. **명시적 루프 상태 정의**: enum으로 현재 단계 추적
2. **종료 조건 체계화**: 다양한 종료 사유 구분
3. **상태 변경 훅 포인트**: 이벤트 시스템 연동 준비
4. **에러 복구 기초**: 재시도 가능한 에러 처리

---

## 3. 상세 설계

### 3.1 LoopState Enum

```python
# agent/states.py

from enum import Enum, auto

class LoopState(Enum):
    """에이전트 루프의 현재 상태."""

    IDLE = auto()              # 대기 중 (run() 호출 전)
    RECEIVING_INPUT = auto()   # 사용자 입력 수신 중
    CALLING_LLM = auto()       # LLM API 호출 중
    PROCESSING_RESPONSE = auto()  # LLM 응답 분석 중
    EXECUTING_TOOLS = auto()   # 도구 실행 중
    CHECKING_CONTEXT = auto()  # 컨텍스트 크기 확인 중
    COMPLETED = auto()         # 정상 완료
    ERROR = auto()             # 에러 발생
```

### 3.2 TerminationReason Enum

```python
class TerminationReason(Enum):
    """루프 종료 사유."""

    END_TURN = auto()          # LLM이 도구 없이 응답 (정상 종료)
    MAX_TURNS = auto()         # 최대 턴 수 도달
    STOP_REASON = auto()       # LLM stop_reason이 특정 값
    USER_INTERRUPT = auto()    # 사용자가 중단 (Ctrl+C)
    ERROR = auto()             # 에러 발생으로 종료
    TOOL_STOP = auto()         # 도구가 종료 요청 (예: exit 명령)
```

### 3.3 LoopContext 클래스

```python
@dataclass
class LoopContext:
    """현재 루프 실행 컨텍스트."""

    state: LoopState = LoopState.IDLE
    termination_reason: TerminationReason | None = None
    current_turn: int = 0
    max_turns: int = 20
    last_error: Exception | None = None

    # 통계
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    start_time: float | None = None
    end_time: float | None = None

    def is_running(self) -> bool:
        """루프가 실행 중인지 확인."""
        return self.state not in (
            LoopState.IDLE,
            LoopState.COMPLETED,
            LoopState.ERROR
        )

    def duration_ms(self) -> float | None:
        """실행 시간 (밀리초)."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
```

### 3.4 AgentLoop 수정

```python
class AgentLoop:
    def __init__(self, ...):
        # 기존 초기화...
        self.context = LoopContext(max_turns=self.max_turns)
        self._state_change_callbacks: list[Callable[[LoopState, LoopState], None]] = []

    def _set_state(self, new_state: LoopState) -> None:
        """상태 변경 및 콜백 호출."""
        old_state = self.context.state
        self.context.state = new_state

        # 콜백 호출 (이벤트 시스템 연동 포인트)
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                self._debug_log(f"State callback error: {e}")

    def on_state_change(self, callback: Callable[[LoopState, LoopState], None]) -> None:
        """상태 변경 콜백 등록."""
        self._state_change_callbacks.append(callback)

    def run(self, user_message: str, ...) -> str:
        """개선된 메인 루프."""
        import time

        self.context = LoopContext(max_turns=self.max_turns)
        self.context.start_time = time.time()

        try:
            self._set_state(LoopState.RECEIVING_INPUT)
            self.session.add_user_message(user_message)

            for turn in range(self.max_turns):
                self.context.current_turn = turn + 1

                # LLM 호출
                self._set_state(LoopState.CALLING_LLM)
                response = self._call_llm()
                self.context.total_llm_calls += 1

                # 응답 분석
                self._set_state(LoopState.PROCESSING_RESPONSE)
                tool_uses = self._extract_tool_uses(response)

                # 종료 조건 확인
                termination = self._check_termination(response, tool_uses)
                if termination:
                    self.context.termination_reason = termination
                    self._set_state(LoopState.COMPLETED)
                    return self._get_text_response(response)

                # 도구 실행
                self._set_state(LoopState.EXECUTING_TOOLS)
                tool_results = self._execute_tools(tool_uses)
                self.context.total_tool_calls += len(tool_uses)

                # 컨텍스트 확인
                self._set_state(LoopState.CHECKING_CONTEXT)
                self._check_context_size()

            # 최대 턴 도달
            self.context.termination_reason = TerminationReason.MAX_TURNS
            self._set_state(LoopState.COMPLETED)
            return "Max turns reached. Please continue with a new message."

        except KeyboardInterrupt:
            self.context.termination_reason = TerminationReason.USER_INTERRUPT
            self._set_state(LoopState.ERROR)
            return "Interrupted by user."

        except Exception as e:
            self.context.last_error = e
            self.context.termination_reason = TerminationReason.ERROR
            self._set_state(LoopState.ERROR)
            raise

        finally:
            self.context.end_time = time.time()

    def _check_termination(
        self,
        response: Any,
        tool_uses: list
    ) -> TerminationReason | None:
        """종료 조건 확인."""
        # 도구 호출이 없으면 종료
        if not tool_uses:
            return TerminationReason.END_TURN

        # stop_reason 확인 (향후 확장)
        if hasattr(response, 'stop_reason'):
            if response.stop_reason == 'end_turn':
                return TerminationReason.STOP_REASON

        return None  # 계속 진행
```

---

## 4. 파일 변경 계획

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `agent/states.py` | 신규 | LoopState, TerminationReason, LoopContext |
| `agent/loop.py` | 수정 | 상태 관리 통합, 종료 조건 체계화 |
| `agent/__init__.py` | 수정 | states 모듈 export 추가 |

---

## 5. 테스트 계획

### 5.1 단위 테스트

```python
# tests/test_loop_states.py

def test_loop_state_transitions():
    """상태 전환 순서 확인."""
    loop = AgentLoop(config=Config())
    states_visited = []

    loop.on_state_change(lambda old, new: states_visited.append(new))
    loop.run("hello")

    assert LoopState.RECEIVING_INPUT in states_visited
    assert LoopState.CALLING_LLM in states_visited
    assert LoopState.COMPLETED in states_visited

def test_termination_reasons():
    """종료 사유 확인."""
    loop = AgentLoop(config=Config(), max_turns=1)
    loop.run("do many things")

    # 1턴 후 도구 계속 호출하면 MAX_TURNS
    assert loop.context.termination_reason in [
        TerminationReason.END_TURN,
        TerminationReason.MAX_TURNS
    ]

def test_loop_context_statistics():
    """루프 통계 확인."""
    loop = AgentLoop(config=Config())
    loop.run("read file.txt")

    assert loop.context.total_llm_calls >= 1
    assert loop.context.duration_ms() is not None
```

---

## 6. 마이그레이션 가이드

### 6.1 기존 코드 호환성

- `run()` 메서드 시그니처 유지
- 반환값 유지 (문자열)
- 새 기능은 `loop.context`로 접근

### 6.2 새 기능 활용

```python
# 상태 모니터링
loop = AgentLoop(config)
loop.on_state_change(lambda old, new: print(f"{old} -> {new}"))
result = loop.run("task")

# 실행 통계 확인
print(f"Turns: {loop.context.current_turn}")
print(f"LLM calls: {loop.context.total_llm_calls}")
print(f"Duration: {loop.context.duration_ms():.0f}ms")
```

---

## 7. 이벤트 시스템 연동 포인트

`_set_state()` 메서드가 상태 변경 훅 포인트 역할:

```python
# 향후 이벤트 시스템 연동 시
def _set_state(self, new_state: LoopState) -> None:
    old_state = self.context.state
    self.context.state = new_state

    # 기존 콜백
    for callback in self._state_change_callbacks:
        callback(old_state, new_state)

    # 이벤트 버스 연동 (2.4에서 추가)
    if self.event_bus:
        self.event_bus.publish(StateChangedEvent(old_state, new_state))
```

---

## 8. 체크리스트

- [ ] `agent/states.py` 생성
  - [ ] LoopState enum
  - [ ] TerminationReason enum
  - [ ] LoopContext dataclass
- [ ] `agent/loop.py` 수정
  - [ ] LoopContext 통합
  - [ ] `_set_state()` 메서드
  - [ ] `on_state_change()` 메서드
  - [ ] `_check_termination()` 메서드
  - [ ] run() 리팩토링
- [ ] `agent/__init__.py` 수정
- [ ] 테스트 작성
- [ ] 문서 업데이트
