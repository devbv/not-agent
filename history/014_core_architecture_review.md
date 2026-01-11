# 코어 아키텍처 점검 및 개선 계획

**작성일**: 2026-01-11
**참고 자료**: OpenCode Agent Architecture (https://github.com/devbv/opencode)
**범위**: 신규 기능 제외, 코어 구조 개선만

---

## 1. 비교 분석 요약

### OpenCode 아키텍처 핵심 특징

| 레이어 | OpenCode | 설명 |
|--------|----------|------|
| Interface | CLI/TUI, Desktop, ACP Server | 다양한 인터페이스 지원 |
| Core SDK | SessionPrompt.loop() | 메인 에이전트 루프 |
| Message | 12 Part Types | text, reasoning, tools, files, subtasks, patches 등 |
| Tool | ~20 Built-in + Registry | 상태 머신 기반 실행 |
| Provider | 20+ LLM | 통합 인터페이스 |
| Permission | Ruleset-based | 도구별 세분화된 권한 |
| Event | Event Bus | 세션/메시지/도구 이벤트 발행 |
| Storage | MessageV2 Storage | 세션 지속성 |
| MCP | Model Context Protocol | 외부 서버 연동 |

### not-agent 현재 상태 (Phase 4.1)

| 레이어 | 현재 상태 | 평가 |
|--------|----------|------|
| Interface | CLI만 지원 | 단일 인터페이스 |
| Core SDK | AgentLoop.run() | 기본 구현 완료 |
| Message | Message, Session | 단순 구조 |
| Tool | 9 Tools + Registry | 데코레이터 기반 등록 |
| Provider | Claude만 | 추상화는 완료 |
| Permission | ApprovalManager | 단순 y/n 승인 |
| Event | 없음 | 미구현 |
| Storage | 없음 | 메모리 only |
| MCP | 없음 | 미구현 |

---

## 2. 부족한 부분 분석 (코어 구조)

### 2.1 에이전트 루프 구조 🔴 중요

**현재 문제**:
- 종료 조건이 `stop_reason`에만 의존
- 루프 상태 추적이 없음 (어떤 단계인지 알 수 없음)
- 에러 복구 전략 부족

**OpenCode 방식**:
```
message retrieval → termination checks → tool resolution
→ LLM streaming → stream processing → continuation evaluation
```

**개선 방향**:
- 루프 상태 명시적 정의 (LoopState enum)
- 각 단계별 훅 포인트 추가
- 종료 조건 체계화 (max_turns, stop_reason, user_interrupt 등)

### 2.2 메시지 시스템 🔴 중요

**현재 문제**:
- `Message` 클래스가 단순 데이터 컨테이너
- content 타입이 `list[Any] | str`로 타입 안전성 부족
- 메시지 파트 구조가 없음

**OpenCode 방식**:
- 12가지 Part Types: TextPart, ToolPart, ReasoningPart, FilePart, PatchPart 등
- 각 파트가 명확한 스키마와 동작을 가짐

**개선 방향**:
- `MessagePart` 기본 클래스 정의
- `TextPart`, `ToolUsePart`, `ToolResultPart` 등 명시적 타입
- 타입 안전한 메시지 구성

### 2.3 권한 시스템 🟡 중간

**현재 문제**:
- `ApprovalManager`가 단순 y/n 승인만 처리
- 도구별 세분화된 권한 규칙 없음
- 자동 승인 규칙 설정 불가

**OpenCode 방식**:
- Ruleset 기반 권한 평가
- 도구별, 경로별, 액션별 세분화

**개선 방향**:
- `PermissionRule` 클래스 도입
- 규칙 기반 자동 승인/거부
- 설정 파일에서 규칙 로드

### 2.4 이벤트 시스템 🟡 중간

**현재 문제**:
- 컴포넌트 간 직접 호출만 사용
- 확장성 제한 (새 기능 추가 시 많은 수정 필요)
- 로깅/모니터링 훅 없음

**OpenCode 방식**:
- Event Bus 패턴
- 세션, 메시지, 권한, 도구 이벤트 발행

**개선 방향**:
- 간단한 `EventBus` 클래스 도입
- 주요 이벤트 정의: `LoopStart`, `ToolExecuted`, `MessageAdded` 등
- 로깅/디버깅을 이벤트 구독으로 처리

### 2.5 도구 실행 상태 관리 🟡 중간

**현재 문제**:
- 도구 실행이 단순 함수 호출
- 실행 중 상태 추적 없음
- 취소/타임아웃 처리 미흡

**OpenCode 방식**:
- 상태 머신 기반 도구 실행
- pending → running → completed/failed

**개선 방향**:
- `ToolExecution` 클래스 도입 (상태 추적)
- 타임아웃, 취소 지원
- 비동기 실행 개선

### 2.6 세션 지속성 🟢 낮음

**현재 문제**:
- 세션이 메모리에만 존재
- 재시작 시 컨텍스트 손실

**개선 방향**:
- 선택적 세션 저장/복원 기능
- JSON 파일 기반 간단한 스토리지

---

## 3. 개선 우선순위

### Phase 4.2-A: 코어 구조 강화 (권장)

| 순서 | 항목 | 난이도 | 영향도 |
|------|------|--------|--------|
| 1 | 메시지 파트 타입 체계화 | 중 | 높음 |
| 2 | 에이전트 루프 상태 관리 | 중 | 높음 |
| 3 | 이벤트 시스템 기본 구현 | 중 | 중간 |
| 4 | 권한 시스템 확장 | 중 | 중간 |
| 5 | 도구 실행 상태 관리 | 낮 | 낮음 |

### 비권장 (Phase 4.2 범위 외)

- 세션 지속성: 현재 필요성 낮음
- MCP 통합: 신규 기능에 해당
- 다중 인터페이스: 신규 기능에 해당
- 다중 프로바이더: 신규 기능에 해당

---

## 4. 상세 개선 계획

### 4.1 메시지 파트 타입 체계화

**목표**: 타입 안전한 메시지 구조

```python
# 제안 구조
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

class MessagePart(ABC):
    """메시지 파트 기본 클래스"""
    @property
    @abstractmethod
    def part_type(self) -> str:
        pass

@dataclass
class TextPart(MessagePart):
    text: str
    part_type: Literal["text"] = "text"

@dataclass
class ToolUsePart(MessagePart):
    tool_id: str
    tool_name: str
    tool_input: dict
    part_type: Literal["tool_use"] = "tool_use"

@dataclass
class ToolResultPart(MessagePart):
    tool_id: str
    content: str
    is_error: bool = False
    part_type: Literal["tool_result"] = "tool_result"

@dataclass
class Message:
    role: Literal["user", "assistant"]
    parts: list[MessagePart]

    def to_api_format(self) -> dict:
        """Anthropic API 형식으로 변환"""
        ...
```

**파일 변경**:
- `agent/message.py` 신규 생성
- `agent/session.py` 수정

### 4.2 에이전트 루프 상태 관리

**목표**: 명시적 루프 상태와 훅 포인트

```python
from enum import Enum, auto

class LoopState(Enum):
    IDLE = auto()
    RECEIVING_INPUT = auto()
    CALLING_LLM = auto()
    PROCESSING_RESPONSE = auto()
    EXECUTING_TOOLS = auto()
    CHECKING_TERMINATION = auto()
    COMPLETED = auto()
    ERROR = auto()

class TerminationReason(Enum):
    END_TURN = auto()       # LLM이 종료 선택
    MAX_TURNS = auto()      # 최대 턴 도달
    USER_INTERRUPT = auto() # 사용자 중단
    ERROR = auto()          # 에러 발생
    TOOL_STOP = auto()      # 도구가 종료 요청

class AgentLoop:
    state: LoopState
    termination_reason: TerminationReason | None

    def run(self, user_message: str) -> str:
        self._set_state(LoopState.RECEIVING_INPUT)
        # ...

    def _set_state(self, state: LoopState):
        old_state = self.state
        self.state = state
        self._emit_event(StateChangedEvent(old_state, state))
```

**파일 변경**:
- `agent/loop.py` 수정
- `agent/states.py` 신규 생성

### 4.3 이벤트 시스템 기본 구현

**목표**: 간단하고 효과적인 이벤트 버스

```python
from typing import Callable, Any
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Event:
    """이벤트 기본 클래스"""
    pass

@dataclass
class LoopStartedEvent(Event):
    session_id: str

@dataclass
class ToolExecutedEvent(Event):
    tool_name: str
    tool_input: dict
    result: ToolResult
    duration_ms: float

@dataclass
class MessageAddedEvent(Event):
    message: Message

class EventBus:
    _subscribers: dict[type, list[Callable]]

    def subscribe(self, event_type: type, handler: Callable):
        self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        for handler in self._subscribers.get(type(event), []):
            handler(event)

    def unsubscribe(self, event_type: type, handler: Callable):
        self._subscribers[event_type].remove(handler)
```

**파일 변경**:
- `core/events.py` 신규 생성
- `agent/loop.py` 이벤트 발행 추가

### 4.4 권한 시스템 확장

**목표**: 규칙 기반 권한 평가

```python
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable
import fnmatch

class Permission(Enum):
    ALLOW = auto()
    DENY = auto()
    ASK = auto()  # 사용자에게 물어보기

@dataclass
class PermissionRule:
    tool_pattern: str          # "write", "bash", "*"
    path_pattern: str | None   # "/tmp/*", "*.py"
    action: Permission

    def matches(self, tool_name: str, path: str | None) -> bool:
        if not fnmatch.fnmatch(tool_name, self.tool_pattern):
            return False
        if self.path_pattern and path:
            return fnmatch.fnmatch(path, self.path_pattern)
        return True

class PermissionManager:
    rules: list[PermissionRule]
    fallback: Permission = Permission.ASK

    def evaluate(self, tool_name: str, context: dict) -> Permission:
        path = context.get("file_path") or context.get("path")
        for rule in self.rules:
            if rule.matches(tool_name, path):
                return rule.action
        return self.fallback
```

**파일 변경**:
- `agent/permissions.py` 신규 생성
- `agent/approval.py` → `permissions.py`로 통합

---

## 5. 작업 순서 제안

```
Phase 4.2-A: 코어 구조 강화
├── Step 1: 메시지 파트 타입 체계화 (1-2일)
│   ├── agent/message.py 생성
│   ├── agent/session.py 리팩토링
│   └── 테스트 작성
│
├── Step 2: 에이전트 루프 상태 관리 (1일)
│   ├── agent/states.py 생성
│   ├── agent/loop.py 리팩토링
│   └── 종료 조건 체계화
│
├── Step 3: 이벤트 시스템 도입 (1일)
│   ├── core/events.py 생성
│   ├── 주요 이벤트 정의
│   └── 로깅을 이벤트로 전환
│
└── Step 4: 권한 시스템 확장 (1일)
    ├── agent/permissions.py 생성
    ├── 규칙 기반 평가 구현
    └── 설정 파일 연동
```

---

## 6. 예상 효과

| 개선 항목 | 효과 |
|----------|------|
| 메시지 파트 타입 | 타입 안전성 ↑, 버그 감소, IDE 지원 개선 |
| 루프 상태 관리 | 디버깅 용이, 확장성 ↑ |
| 이벤트 시스템 | 모듈 결합도 ↓, 확장성 ↑, 모니터링 용이 |
| 권한 시스템 | 보안 ↑, 사용자 편의성 ↑ |

---

## 7. 결론

현재 not-agent의 코어 구조는 Phase 4.1에서 잘 정립되었지만, OpenCode와 비교 시 다음 영역에서 개선이 필요합니다:

1. **메시지 시스템**: 타입 안전성 강화 필요
2. **에이전트 루프**: 상태 관리 명시화 필요
3. **이벤트 시스템**: 확장성을 위해 도입 필요
4. **권한 시스템**: 규칙 기반으로 고도화 필요

이러한 개선은 신규 기능 추가 없이 기존 코어 구조를 더욱 견고하게 만드는 데 집중합니다.
