# 2.5 도구 실행 상태 관리 계획

**작성일**: 2026-01-11
**우선순위**: 🟢 낮음
**예상 작업량**: 낮음

---

## 1. 현재 문제점

### 1.1 도구 실행이 단순 함수 호출

**현재 코드** (`executor.py:118-134`):
```python
def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
    # Check if we're already in an event loop
    try:
        asyncio.get_running_loop()
        return self._execute_sync(tool_name, tool_input)
    except RuntimeError:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.execute_async(tool_name, tool_input))
```

**문제**:
- 실행 중 상태 추적 없음
- 외부에서 실행 상태 조회 불가
- 취소/타임아웃 처리 미흡

### 1.2 타임아웃 처리 없음

**현재**: 도구 실행에 시간 제한 없음
- 긴 bash 명령이 무한 대기 가능
- 네트워크 요청 (WebFetch) 타임아웃 미처리

### 1.3 실행 이력 없음

**현재**: 도구 실행 결과만 반환
- 실행 시간, 재시도 횟수 등 메타데이터 없음
- 디버깅/분석 어려움

---

## 2. 개선 목표

1. **실행 상태 추적**: 상태 머신 기반 실행 관리
2. **타임아웃 지원**: 도구별 타임아웃 설정
3. **취소 지원**: 진행 중인 실행 취소 가능
4. **실행 메타데이터**: 시간, 재시도 등 추적

---

## 3. 상세 설계

### 3.1 ToolExecutionState Enum

```python
# agent/tool_execution.py

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime
import asyncio

class ToolExecutionState(Enum):
    """도구 실행 상태."""

    PENDING = auto()     # 대기 중
    RUNNING = auto()     # 실행 중
    COMPLETED = auto()   # 성공적 완료
    FAILED = auto()      # 실패
    CANCELLED = auto()   # 취소됨
    TIMEOUT = auto()     # 타임아웃
```

### 3.2 ToolExecution 클래스

```python
@dataclass
class ToolExecution:
    """단일 도구 실행을 추적."""

    # 식별
    id: str = field(default_factory=lambda: str(uuid4()))
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)

    # 상태
    state: ToolExecutionState = ToolExecutionState.PENDING

    # 결과
    result: ToolResult | None = None
    error: str | None = None

    # 타이밍
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # 메타데이터
    attempt: int = 1
    timeout_seconds: float | None = None

    # 취소 토큰
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def duration_ms(self) -> float | None:
        """실행 시간 (밀리초)."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    @property
    def is_finished(self) -> bool:
        """완료 상태인지 확인."""
        return self.state in (
            ToolExecutionState.COMPLETED,
            ToolExecutionState.FAILED,
            ToolExecutionState.CANCELLED,
            ToolExecutionState.TIMEOUT,
        )

    def cancel(self) -> None:
        """실행 취소 요청."""
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        """취소 요청되었는지 확인."""
        return self._cancel_event.is_set()

    def to_dict(self) -> dict[str, Any]:
        """직렬화."""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "state": self.state.name,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "attempt": self.attempt,
        }
```

### 3.3 개선된 ToolExecutor

```python
class ToolExecutor:
    """상태 추적을 지원하는 도구 실행기."""

    # 도구별 기본 타임아웃 (초)
    DEFAULT_TIMEOUTS = {
        "bash": 120.0,      # 2분
        "WebFetch": 30.0,   # 30초
        "WebSearch": 30.0,  # 30초
        "read": 10.0,       # 10초
        "write": 10.0,      # 10초
        "edit": 10.0,       # 10초
        "glob": 30.0,       # 30초
        "grep": 60.0,       # 1분
    }

    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        permission_manager: PermissionManager | None = None,
        default_timeout: float = 120.0,
    ) -> None:
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}
        self.permission = permission_manager
        self.default_timeout = default_timeout

        # 현재 실행 중인 작업들
        self._current_executions: dict[str, ToolExecution] = {}

        # 실행 이력
        self._history: list[ToolExecution] = []
        self._max_history = 100

    def get_current_executions(self) -> list[ToolExecution]:
        """현재 실행 중인 작업 목록."""
        return [e for e in self._current_executions.values() if not e.is_finished]

    def get_execution(self, execution_id: str) -> ToolExecution | None:
        """ID로 실행 조회."""
        return self._current_executions.get(execution_id)

    def get_history(self, limit: int = 10) -> list[ToolExecution]:
        """실행 이력 조회."""
        return self._history[-limit:]

    def cancel_execution(self, execution_id: str) -> bool:
        """실행 취소."""
        execution = self._current_executions.get(execution_id)
        if execution and not execution.is_finished:
            execution.cancel()
            return True
        return False

    async def execute_async(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolResult:
        """도구 비동기 실행 (상태 추적 포함)."""

        # 실행 객체 생성
        execution = ToolExecution(
            tool_name=tool_name,
            tool_input=tool_input,
            timeout_seconds=timeout or self.DEFAULT_TIMEOUTS.get(
                tool_name, self.default_timeout
            ),
        )
        self._current_executions[execution.id] = execution

        try:
            # 도구 확인
            if tool_name not in self.tools:
                execution.state = ToolExecutionState.FAILED
                execution.error = f"Unknown tool: {tool_name}"
                return ToolResult(success=False, output="", error=execution.error)

            tool = self.tools[tool_name]

            # 권한 확인
            if self.permission and self.permission.enabled:
                approval_desc = tool.get_approval_description(**tool_input)
                if approval_desc:
                    context = dict(tool_input)
                    diff = None
                    if tool.name == "write" and hasattr(tool, "generate_diff"):
                        diff = tool.generate_diff(
                            tool_input.get("file_path", ""),
                            tool_input.get("content", ""),
                        )

                    if not self.permission.check(tool.name, approval_desc, context, diff):
                        execution.state = ToolExecutionState.CANCELLED
                        execution.error = "User denied permission"
                        return ToolResult(
                            success=False,
                            output="User denied permission.",
                            error=None,
                        )

            # 실행 시작
            execution.state = ToolExecutionState.RUNNING
            execution.started_at = datetime.now()

            # 타임아웃과 취소 처리
            try:
                result = await asyncio.wait_for(
                    self._run_tool(tool, tool_input, execution),
                    timeout=execution.timeout_seconds,
                )

                execution.state = ToolExecutionState.COMPLETED
                execution.result = result
                return result

            except asyncio.TimeoutError:
                execution.state = ToolExecutionState.TIMEOUT
                execution.error = f"Timeout after {execution.timeout_seconds}s"
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool execution timed out after {execution.timeout_seconds} seconds",
                )

            except asyncio.CancelledError:
                execution.state = ToolExecutionState.CANCELLED
                execution.error = "Cancelled"
                return ToolResult(
                    success=False,
                    output="",
                    error="Tool execution was cancelled",
                )

        except Exception as e:
            execution.state = ToolExecutionState.FAILED
            execution.error = str(e)
            return ToolResult(success=False, output="", error=str(e))

        finally:
            execution.completed_at = datetime.now()
            self._add_to_history(execution)

    async def _run_tool(
        self,
        tool: BaseTool,
        tool_input: dict[str, Any],
        execution: ToolExecution,
    ) -> ToolResult:
        """실제 도구 실행 (취소 확인 포함)."""

        # 취소 확인
        if execution.is_cancelled:
            raise asyncio.CancelledError()

        try:
            return tool.execute(**tool_input)
        except TypeError as e:
            error_msg = str(e)
            if "missing" in error_msg and "required" in error_msg:
                guidance = self._get_parameter_guidance(tool.name)
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Missing parameters: {error_msg}{guidance}",
                )
            raise

    def _add_to_history(self, execution: ToolExecution) -> None:
        """이력에 추가."""
        self._history.append(execution)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 현재 실행에서 제거
        self._current_executions.pop(execution.id, None)

    def _get_parameter_guidance(self, tool_name: str) -> str:
        """파라미터 가이드 메시지."""
        if tool_name == "write":
            return (
                "\n\nFor 'write' tool, provide:\n"
                "- file_path: The path\n"
                "- content: The FULL content"
            )
        elif tool_name == "edit":
            return (
                "\n\nFor 'edit' tool, provide:\n"
                "- file_path: The path\n"
                "- old_string: Text to replace\n"
                "- new_string: Replacement text"
            )
        return ""

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """동기 실행 래퍼."""
        try:
            asyncio.get_running_loop()
            # 이미 루프 안에 있으면 동기 버전 사용
            return self._execute_sync(tool_name, tool_input)
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.execute_async(tool_name, tool_input))

    def _execute_sync(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """동기 실행 (상태 추적 간소화)."""
        # 기존 로직 유지 (상태 추적 생략)
        # ...
```

---

## 4. 파일 변경 계획

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `agent/tool_execution.py` | 신규 | ToolExecutionState, ToolExecution |
| `agent/executor.py` | 수정 | 상태 추적, 타임아웃, 취소 지원 |
| `agent/__init__.py` | 수정 | tool_execution 모듈 export |

---

## 5. 이벤트 시스템 연동

```python
# executor.py에서 이벤트 발행

async def execute_async(self, ...):
    execution = ToolExecution(...)

    if self.event_bus:
        self.event_bus.publish(ToolExecutionStartedEvent(
            execution_id=execution.id,
            tool_name=tool_name,
            tool_input=tool_input,
        ))

    # ... 실행 ...

    if self.event_bus:
        self.event_bus.publish(ToolExecutionCompletedEvent(
            execution_id=execution.id,
            tool_name=tool_name,
            state=execution.state.name,
            duration_ms=execution.duration_ms,
        ))
```

---

## 6. 테스트 계획

```python
# tests/test_tool_execution.py

def test_execution_state_lifecycle():
    execution = ToolExecution(tool_name="read")
    assert execution.state == ToolExecutionState.PENDING

    execution.state = ToolExecutionState.RUNNING
    execution.started_at = datetime.now()
    assert not execution.is_finished

    execution.state = ToolExecutionState.COMPLETED
    execution.completed_at = datetime.now()
    assert execution.is_finished
    assert execution.duration_ms is not None

def test_execution_cancellation():
    execution = ToolExecution(tool_name="bash")
    assert not execution.is_cancelled

    execution.cancel()
    assert execution.is_cancelled

@pytest.mark.asyncio
async def test_executor_timeout():
    # 긴 실행 도구 시뮬레이션
    class SlowTool(BaseTool):
        name = "slow"
        async def execute(self, **kwargs):
            await asyncio.sleep(10)
            return ToolResult(success=True, output="done")

    executor = ToolExecutor(tools=[SlowTool()])
    result = await executor.execute_async("slow", {}, timeout=0.1)

    assert not result.success
    assert "timeout" in result.error.lower()

def test_executor_history():
    executor = ToolExecutor()
    executor.execute("read", {"file_path": "/tmp/test.txt"})

    history = executor.get_history()
    assert len(history) >= 1
    assert history[-1].tool_name == "read"
```

---

## 7. 체크리스트

- [ ] `agent/tool_execution.py` 생성
  - [ ] ToolExecutionState enum
  - [ ] ToolExecution dataclass
- [ ] `agent/executor.py` 수정
  - [ ] 상태 추적 통합
  - [ ] 타임아웃 지원
  - [ ] 취소 지원
  - [ ] 실행 이력
- [ ] `agent/__init__.py` 수정
- [ ] 테스트 작성
- [ ] 문서 업데이트

---

## 8. 구현 노트

### 8.1 타임아웃 전략

- **도구별 기본값**: bash(2분), WebFetch(30초) 등
- **설정 오버라이드**: config에서 도구별 타임아웃 지정 가능
- **실행 시 오버라이드**: execute() 호출 시 개별 지정

### 8.2 취소 메커니즘

- **asyncio.CancelledError**: 비동기 실행 취소
- **_cancel_event**: 협력적 취소 (도구가 확인)
- **강제 종료**: bash 등은 subprocess 종료 필요

### 8.3 하위 호환성

- `execute()` 시그니처 유지
- 상태 추적은 선택적 기능
- 기존 코드 변경 없이 동작
