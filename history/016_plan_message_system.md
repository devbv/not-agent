# 2.2 메시지 시스템 개선 계획

**작성일**: 2026-01-11
**우선순위**: 🔴 높음
**예상 작업량**: 중간

---

## 1. 현재 문제점

### 1.1 타입 안전성 부족

**현재 코드** (`session.py:8-13`):
```python
@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: list[Any] | str  # TextBlock, ToolUseBlock, ToolResultBlock 등
```

**문제**:
- `content`가 `list[Any]`로 타입 추론 불가
- IDE 자동완성/타입 체크 불가능
- 런타임 에러 발생 가능성

### 1.2 메시지 구조 불명확

**현재**: content 내부 구조가 암묵적
- Anthropic SDK 타입에 의존 (TextBlock, ToolUseBlock)
- 커스텀 확장 어려움
- 직렬화/역직렬화 시 문제

### 1.3 OpenCode와의 차이

**OpenCode**: 12가지 Part Types
- TextPart, ReasoningPart, ToolPart, FilePart, PatchPart 등
- 각 파트가 명확한 스키마

**not-agent**: 파트 개념 없음
- Anthropic 응답을 그대로 저장/전달

---

## 2. 개선 목표

1. **타입 안전한 MessagePart 계층**: 명시적 파트 타입
2. **확장 가능한 구조**: 새 파트 타입 추가 용이
3. **Anthropic API 호환**: 기존 API 형식 변환 유지
4. **직렬화 지원**: JSON 저장/로드 가능

---

## 3. 상세 설계

### 3.1 MessagePart 기본 구조

```python
# agent/message.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Literal, Any
from uuid import uuid4

class MessagePart(ABC):
    """메시지 파트 추상 기본 클래스."""

    @property
    @abstractmethod
    def part_type(self) -> str:
        """파트 타입 식별자."""
        pass

    @abstractmethod
    def to_api_format(self) -> dict[str, Any]:
        """Anthropic API 형식으로 변환."""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리 변환."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessagePart":
        """딕셔너리에서 복원."""
        pass
```

### 3.2 구체적인 Part 타입들

```python
@dataclass
class TextPart(MessagePart):
    """텍스트 메시지 파트."""

    text: str

    @property
    def part_type(self) -> Literal["text"]:
        return "text"

    def to_api_format(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text}

    def to_dict(self) -> dict[str, Any]:
        return {"part_type": "text", "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextPart":
        return cls(text=data["text"])


@dataclass
class ToolUsePart(MessagePart):
    """도구 호출 파트."""

    tool_id: str
    tool_name: str
    tool_input: dict[str, Any]

    @property
    def part_type(self) -> Literal["tool_use"]:
        return "tool_use"

    def to_api_format(self) -> dict[str, Any]:
        return {
            "type": "tool_use",
            "id": self.tool_id,
            "name": self.tool_name,
            "input": self.tool_input,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_type": "tool_use",
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolUsePart":
        return cls(
            tool_id=data["tool_id"],
            tool_name=data["tool_name"],
            tool_input=data["tool_input"],
        )


@dataclass
class ToolResultPart(MessagePart):
    """도구 실행 결과 파트."""

    tool_use_id: str
    content: str
    is_error: bool = False

    @property
    def part_type(self) -> Literal["tool_result"]:
        return "tool_result"

    def to_api_format(self) -> dict[str, Any]:
        result = {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
        }
        if self.is_error:
            result["is_error"] = True
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolResultPart":
        return cls(
            tool_use_id=data["tool_use_id"],
            content=data["content"],
            is_error=data.get("is_error", False),
        )
```

### 3.3 Part 팩토리 및 레지스트리

```python
# Part 타입 레지스트리
_PART_TYPES: dict[str, type[MessagePart]] = {
    "text": TextPart,
    "tool_use": ToolUsePart,
    "tool_result": ToolResultPart,
}

def register_part_type(part_type: str, cls: type[MessagePart]) -> None:
    """새 파트 타입 등록."""
    _PART_TYPES[part_type] = cls

def part_from_dict(data: dict[str, Any]) -> MessagePart:
    """딕셔너리에서 적절한 Part 인스턴스 생성."""
    part_type = data.get("part_type")
    if part_type not in _PART_TYPES:
        raise ValueError(f"Unknown part type: {part_type}")
    return _PART_TYPES[part_type].from_dict(data)

def part_from_anthropic(block: Any) -> MessagePart:
    """Anthropic SDK 블록에서 Part 변환."""
    if hasattr(block, 'type'):
        if block.type == 'text':
            return TextPart(text=block.text)
        elif block.type == 'tool_use':
            return ToolUsePart(
                tool_id=block.id,
                tool_name=block.name,
                tool_input=dict(block.input),
            )

    # dict 형태 (tool_result)
    if isinstance(block, dict):
        if block.get('type') == 'tool_result':
            return ToolResultPart(
                tool_use_id=block['tool_use_id'],
                content=block['content'],
                is_error=block.get('is_error', False),
            )
        elif block.get('type') == 'text':
            return TextPart(text=block['text'])

    raise ValueError(f"Cannot convert to MessagePart: {block}")
```

### 3.4 개선된 Message 클래스

```python
@dataclass
class Message:
    """타입 안전한 대화 메시지."""

    role: Literal["user", "assistant"]
    parts: list[MessagePart] = field(default_factory=list)

    def add_part(self, part: MessagePart) -> None:
        """파트 추가."""
        self.parts.append(part)

    def get_parts_by_type(self, part_type: type[MessagePart]) -> list[MessagePart]:
        """특정 타입의 파트만 반환."""
        return [p for p in self.parts if isinstance(p, part_type)]

    def get_text_content(self) -> str:
        """모든 텍스트 파트를 합쳐서 반환."""
        text_parts = self.get_parts_by_type(TextPart)
        return "\n".join(p.text for p in text_parts)

    def get_tool_uses(self) -> list[ToolUsePart]:
        """모든 도구 호출 파트 반환."""
        return self.get_parts_by_type(ToolUsePart)

    def to_api_format(self) -> dict[str, Any]:
        """Anthropic API 형식으로 변환."""
        content = [part.to_api_format() for part in self.parts]
        return {"role": self.role, "content": content}

    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리."""
        return {
            "role": self.role,
            "parts": [part.to_dict() for part in self.parts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """딕셔너리에서 복원."""
        parts = [part_from_dict(p) for p in data["parts"]]
        return cls(role=data["role"], parts=parts)

    @classmethod
    def from_anthropic_response(cls, role: str, content: list[Any]) -> "Message":
        """Anthropic 응답에서 Message 생성."""
        parts = [part_from_anthropic(block) for block in content]
        return cls(role=role, parts=parts)
```

### 3.5 개선된 Session 클래스

```python
class Session:
    """타입 안전한 대화 세션 관리."""

    def __init__(self) -> None:
        self.id: str = str(uuid4())
        self.messages: list[Message] = []

    def add_user_message(self, content: str | list[MessagePart]) -> Message:
        """사용자 메시지 추가."""
        if isinstance(content, str):
            parts = [TextPart(text=content)]
        else:
            parts = content

        msg = Message(role="user", parts=parts)
        self.messages.append(msg)
        return msg

    def add_assistant_message(self, content: list[Any]) -> Message:
        """어시스턴트 메시지 추가 (Anthropic 응답에서)."""
        parts = [part_from_anthropic(block) for block in content]
        msg = Message(role="assistant", parts=parts)
        self.messages.append(msg)
        return msg

    def add_tool_results(self, results: list[dict[str, Any]]) -> Message:
        """도구 결과를 사용자 메시지로 추가."""
        parts = []
        for result in results:
            parts.append(ToolResultPart(
                tool_use_id=result["tool_use_id"],
                content=result["content"],
                is_error=result.get("is_error", False),
            ))

        msg = Message(role="user", parts=parts)
        self.messages.append(msg)
        return msg

    def to_api_format(self) -> list[dict[str, Any]]:
        """API 호출용 형식으로 변환."""
        return [msg.to_api_format() for msg in self.messages]

    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리."""
        return {
            "id": self.id,
            "messages": [msg.to_dict() for msg in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """딕셔너리에서 복원."""
        session = cls()
        session.id = data["id"]
        session.messages = [Message.from_dict(m) for m in data["messages"]]
        return session

    # 하위 호환성
    def get_messages(self) -> list[dict[str, Any]]:
        """Legacy: to_api_format 별칭."""
        return self.to_api_format()

    def set_messages(self, messages: list[dict[str, Any]]) -> None:
        """Legacy: API 형식에서 메시지 설정."""
        self.messages = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                self.add_user_message(content)
            elif isinstance(content, list):
                if role == "assistant":
                    self.add_assistant_message(content)
                else:
                    # tool_result 처리
                    self.add_tool_results(content)

    def clear(self) -> None:
        """세션 초기화."""
        self.messages.clear()
        self.id = str(uuid4())

    def __len__(self) -> int:
        return len(self.messages)
```

---

## 4. 파일 변경 계획

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `agent/message.py` | 신규 | MessagePart 계층 구조 |
| `agent/session.py` | 대폭 수정 | 새 Message 시스템 사용 |
| `agent/loop.py` | 수정 | 새 API 사용 (호환성 유지) |
| `agent/__init__.py` | 수정 | message 모듈 export |

---

## 5. 마이그레이션 전략

### 5.1 단계적 적용

1. **Phase A**: `message.py` 생성, 새 타입들 정의
2. **Phase B**: `session.py`에서 새 타입 사용
3. **Phase C**: `loop.py`에서 타입 힌트 적용 (기능 동일)

### 5.2 하위 호환성

```python
# 기존 코드
session.add_user_message("hello")
messages = session.to_api_format()

# 새 코드 (동일하게 동작)
session.add_user_message("hello")
messages = session.to_api_format()

# 새 기능 활용
msg = session.messages[-1]
text_parts = msg.get_parts_by_type(TextPart)
```

---

## 6. 테스트 계획

```python
# tests/test_message.py

def test_text_part():
    part = TextPart(text="hello")
    assert part.part_type == "text"
    assert part.to_api_format() == {"type": "text", "text": "hello"}

def test_tool_use_part():
    part = ToolUsePart(
        tool_id="123",
        tool_name="read",
        tool_input={"file_path": "/tmp/test.txt"}
    )
    assert part.part_type == "tool_use"
    api = part.to_api_format()
    assert api["id"] == "123"
    assert api["name"] == "read"

def test_message_from_anthropic():
    # Anthropic 응답 시뮬레이션
    from anthropic.types import TextBlock
    blocks = [TextBlock(type="text", text="Hello")]
    msg = Message.from_anthropic_response("assistant", blocks)
    assert len(msg.parts) == 1
    assert isinstance(msg.parts[0], TextPart)

def test_session_serialization():
    session = Session()
    session.add_user_message("hello")

    # 직렬화
    data = session.to_dict()

    # 역직렬화
    restored = Session.from_dict(data)
    assert len(restored.messages) == 1
    assert restored.messages[0].get_text_content() == "hello"

def test_backward_compatibility():
    session = Session()
    session.add_user_message("test")

    # 기존 API 동작 확인
    messages = session.to_api_format()
    assert messages[0]["role"] == "user"
    assert messages[0]["content"][0]["type"] == "text"
```

---

## 7. 향후 확장 가능성

### 7.1 새 파트 타입 추가

```python
# 예: 파일 첨부 파트
@dataclass
class FilePart(MessagePart):
    file_path: str
    content: str
    mime_type: str = "text/plain"

    @property
    def part_type(self) -> Literal["file"]:
        return "file"

    # ...

# 등록
register_part_type("file", FilePart)
```

### 7.2 이벤트 시스템 연동

```python
def add_user_message(self, content: str) -> Message:
    msg = Message(role="user", parts=[TextPart(text=content)])
    self.messages.append(msg)

    # 이벤트 발행 (2.4에서 추가)
    if self.event_bus:
        self.event_bus.publish(MessageAddedEvent(msg))

    return msg
```

---

## 8. 체크리스트

- [ ] `agent/message.py` 생성
  - [ ] MessagePart ABC
  - [ ] TextPart
  - [ ] ToolUsePart
  - [ ] ToolResultPart
  - [ ] Part 레지스트리/팩토리
- [ ] `agent/session.py` 수정
  - [ ] 새 Message 클래스 사용
  - [ ] 직렬화/역직렬화 지원
  - [ ] 하위 호환성 유지
- [ ] `agent/loop.py` 수정
  - [ ] 새 API 활용
  - [ ] 타입 힌트 개선
- [ ] `agent/__init__.py` 수정
- [ ] 테스트 작성
- [ ] 문서 업데이트
