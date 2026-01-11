# Phase 4.1: 구조 리팩토링 계획

**작성일:** 2026-01-11
**상태:** ✅ 완료 (2026-01-11)

## 개요

opencode 프로젝트 구조를 참고하여 not-agent의 아키텍처를 개선합니다. 주요 목표는 확장성, 유지보수성, 모듈화 향상입니다.

## 배경

### 현재 문제점

1. **도구 등록 시스템**: `get_all_tools()` 수동 팩토리 함수, 새 도구 추가시 `__init__.py` 수정 필요
2. **설정 시스템 부재**: 모델명, 토큰 제한 등 하드코딩, CLI 플래그로만 설정 가능
3. **에이전트 루프 비대화**: `loop.py`가 600+ lines, 여러 책임 혼재
4. **LLM 종속성**: Claude API 직접 사용, 다른 LLM 지원 어려움

### opencode에서 참고할 패턴

- 데코레이터 기반 도구 등록
- 계층적 설정 시스템 (global → project)
- 프로바이더 추상화
- 세션/컨텍스트 분리

---

## 목표 구조

```
not_agent/
├── config/              # [신규] 설정 시스템
│   ├── __init__.py
│   ├── config.py        # Config 클래스
│   └── defaults.py      # 기본값 정의
├── provider/            # [신규] LLM 프로바이더 추상화
│   ├── __init__.py
│   ├── base.py          # BaseProvider 인터페이스
│   ├── claude.py        # Claude 프로바이더
│   └── registry.py      # 프로바이더 레지스트리
├── agent/
│   ├── __init__.py
│   ├── loop.py          # [수정] 간소화된 에이전트 루프
│   ├── session.py       # [신규] 세션/메시지 관리
│   ├── context.py       # [신규] 컨텍스트 관리
│   ├── executor.py      # [유지] 도구 실행기
│   └── approval.py      # [유지] 승인 관리자
├── tools/
│   ├── __init__.py      # [수정] 레지스트리 사용
│   ├── base.py          # [수정] 데코레이터 추가
│   ├── registry.py      # [신규] 도구 레지스트리
│   └── [개별 도구들]    # [수정] @register_tool 적용
├── llm/                 # [삭제 예정] → provider/로 이동
│   └── claude.py
└── cli/
    └── main.py          # [수정] Config, Provider 사용
```

---

## 구현 상세

### Step 1: 설정 시스템 (config/)

#### 1.1 config/defaults.py
```python
"""기본 설정값 정의."""

DEFAULT_CONFIG = {
    # LLM 설정
    "provider": "claude",
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 16384,

    # 에이전트 설정
    "max_turns": 20,
    "context_limit": 100000,
    "compact_threshold": 0.75,

    # 기능 설정
    "approval_enabled": True,
    "debug": False,
}
```

#### 1.2 config/config.py
```python
"""설정 관리 클래스."""

class Config:
    """
    계층적 설정 로더.
    우선순위: CLI 오버라이드 > 환경변수 > 프로젝트 설정 > 글로벌 설정 > 기본값
    """

    def __init__(self):
        self._config: dict = {}
        self._load_defaults()
        self._load_global()      # ~/.not_agent/config.json
        self._load_project()     # .not_agent.json
        self._load_env()         # NOT_AGENT_* 환경변수

    def get(self, key: str, default=None) -> Any:
        """설정값 조회."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """CLI 오버라이드용 설정."""
        self._config[key] = value

    def _load_defaults(self) -> None:
        """기본값 로드."""
        from .defaults import DEFAULT_CONFIG
        self._config.update(DEFAULT_CONFIG)

    def _load_global(self) -> None:
        """글로벌 설정 파일 로드 (~/.not_agent/config.json)."""
        global_path = Path.home() / ".not_agent" / "config.json"
        if global_path.exists():
            with open(global_path) as f:
                self._config.update(json.load(f))

    def _load_project(self) -> None:
        """프로젝트 설정 파일 로드 (.not_agent.json)."""
        project_path = Path.cwd() / ".not_agent.json"
        if project_path.exists():
            with open(project_path) as f:
                self._config.update(json.load(f))

    def _load_env(self) -> None:
        """환경변수 로드 (NOT_AGENT_*)."""
        prefix = "NOT_AGENT_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                self._config[config_key] = self._parse_value(value)
```

---

### Step 2: LLM 프로바이더 추상화 (provider/)

#### 2.1 provider/base.py
```python
"""LLM 프로바이더 기본 인터페이스."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class ProviderResponse:
    """프로바이더 응답 표준 형식."""
    content: list[Any]  # TextBlock, ToolUseBlock 등
    stop_reason: str
    usage: dict[str, int]  # input_tokens, output_tokens

class BaseProvider(ABC):
    """LLM 프로바이더 추상 클래스."""

    @property
    @abstractmethod
    def name(self) -> str:
        """프로바이더 이름."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 16384,
    ) -> ProviderResponse:
        """LLM 호출."""
        pass

    @abstractmethod
    def format_tool(self, tool: "BaseTool") -> dict:
        """도구를 프로바이더 형식으로 변환."""
        pass
```

#### 2.2 provider/claude.py
```python
"""Claude 프로바이더 구현."""

from anthropic import Anthropic
from .base import BaseProvider, ProviderResponse

class ClaudeProvider(BaseProvider):
    """Anthropic Claude API 프로바이더."""

    name = "claude"

    def __init__(self, config: "Config"):
        self.config = config
        self.client = Anthropic(
            api_key=config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = config.get("model")

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 16384,
    ) -> ProviderResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "",
            messages=messages,
            tools=tools or [],
        )
        return ProviderResponse(
            content=list(response.content),
            stop_reason=response.stop_reason,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    def format_tool(self, tool: "BaseTool") -> dict:
        """Anthropic 도구 형식으로 변환."""
        return tool.to_anthropic_tool()
```

#### 2.3 provider/registry.py
```python
"""프로바이더 레지스트리."""

from typing import Type
from .base import BaseProvider
from .claude import ClaudeProvider

PROVIDERS: dict[str, Type[BaseProvider]] = {
    "claude": ClaudeProvider,
}

def get_provider(name: str, config: "Config") -> BaseProvider:
    """이름으로 프로바이더 인스턴스 생성."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name](config)

def register_provider(name: str, provider_class: Type[BaseProvider]) -> None:
    """프로바이더 등록 (확장용)."""
    PROVIDERS[name] = provider_class
```

---

### Step 3: 도구 레지스트리 (tools/)

#### 3.1 tools/registry.py
```python
"""도구 레지스트리 시스템."""

from typing import Type, Callable

class ToolRegistry:
    """도구 등록 및 관리."""

    _tools: dict[str, Type["BaseTool"]] = {}
    _instances: dict[str, "BaseTool"] = {}

    @classmethod
    def register(cls, tool_class: Type["BaseTool"]) -> Type["BaseTool"]:
        """도구 클래스 등록."""
        cls._tools[tool_class.name] = tool_class
        return tool_class

    @classmethod
    def get(cls, name: str) -> "BaseTool":
        """이름으로 도구 인스턴스 조회."""
        if name not in cls._instances:
            if name not in cls._tools:
                raise KeyError(f"Unknown tool: {name}")
            cls._instances[name] = cls._tools[name]()
        return cls._instances[name]

    @classmethod
    def get_all(cls) -> list["BaseTool"]:
        """모든 등록된 도구 인스턴스 반환."""
        return [cls.get(name) for name in cls._tools]

    @classmethod
    def clear(cls) -> None:
        """레지스트리 초기화 (테스트용)."""
        cls._tools.clear()
        cls._instances.clear()

def register_tool(cls: Type["BaseTool"]) -> Type["BaseTool"]:
    """도구 등록 데코레이터."""
    return ToolRegistry.register(cls)
```

#### 3.2 tools/base.py 수정
```python
"""도구 기본 클래스."""

from abc import ABC, abstractmethod

class BaseTool(ABC):
    """도구 기본 클래스."""

    # 서브클래스에서 클래스 변수로 정의
    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema 파라미터 정의."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> "ToolResult":
        """도구 실행."""
        pass

    # ... 기존 메서드 유지
```

#### 3.3 개별 도구에 데코레이터 적용
```python
# tools/read.py
from .registry import register_tool

@register_tool
class ReadTool(BaseTool):
    name = "read"
    description = "Read the contents of a file"
    # ...
```

---

### Step 4: 세션 관리 (agent/session.py)

```python
"""세션 및 메시지 관리."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

@dataclass
class Message:
    """대화 메시지."""
    role: str  # "user" | "assistant"
    content: list[Any]  # TextBlock, ToolUseBlock, ToolResultBlock 등

class Session:
    """대화 세션 관리."""

    def __init__(self):
        self.id: str = str(uuid4())
        self.messages: list[Message] = []

    def add_user_message(self, content: str | list) -> None:
        """사용자 메시지 추가."""
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: list) -> None:
        """어시스턴트 메시지 추가."""
        self.messages.append(Message(role="assistant", content=content))

    def add_tool_results(self, results: list[dict]) -> None:
        """도구 결과를 사용자 메시지로 추가."""
        self.messages.append(Message(role="user", content=results))

    def to_api_format(self) -> list[dict]:
        """API 호출용 형식으로 변환."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]

    def clear(self) -> None:
        """세션 초기화."""
        self.messages.clear()
        self.id = str(uuid4())
```

---

### Step 5: 컨텍스트 관리 (agent/context.py)

```python
"""컨텍스트 크기 관리 및 컴팩션."""

class ContextManager:
    """컨텍스트 크기 관리."""

    def __init__(self, config: "Config", provider: "BaseProvider"):
        self.config = config
        self.provider = provider
        self.limit = config.get("context_limit", 100000)
        self.threshold = config.get("compact_threshold", 0.75)

    def estimate_tokens(self, session: "Session") -> int:
        """세션의 토큰 수 추정."""
        text = str(session.to_api_format())
        return len(text) // 4  # 대략적 추정

    def should_compact(self, session: "Session") -> bool:
        """컴팩션 필요 여부 확인."""
        tokens = self.estimate_tokens(session)
        return tokens > self.limit * self.threshold

    def compact(self, session: "Session") -> "Session":
        """세션 컴팩션 수행."""
        # 구현: 오래된 메시지 요약 후 새 세션 생성
        # 기존 loop.py의 _compact_context 로직 이동
        pass

    def get_usage_ratio(self, session: "Session") -> float:
        """컨텍스트 사용 비율 반환."""
        return self.estimate_tokens(session) / self.limit
```

---

### Step 6: 에이전트 루프 간소화 (agent/loop.py)

```python
"""에이전트 실행 루프."""

class AgentLoop:
    """에이전트 메인 루프."""

    def __init__(self, config: "Config"):
        self.config = config
        self.provider = get_provider(config.get("provider", "claude"), config)
        self.session = Session()
        self.context_manager = ContextManager(config, self.provider)
        self.executor = ToolExecutor(
            tools=ToolRegistry.get_all(),
            approval_plugin=ApprovalManager() if config.get("approval_enabled") else None,
        )
        self.system_prompt = self._build_system_prompt()
        self.turn_count = 0
        self.max_turns = config.get("max_turns", 20)

    def run(self, user_message: str) -> str:
        """사용자 메시지 처리 및 응답 반환."""
        self.session.add_user_message(user_message)

        while self.turn_count < self.max_turns:
            self.turn_count += 1

            # LLM 호출
            response = self._call_llm()
            self.session.add_assistant_message(response.content)

            # 도구 호출 추출
            tool_calls = self._extract_tool_calls(response.content)

            if not tool_calls:
                return self._extract_text(response.content)

            # 도구 실행
            results = self._execute_tools(tool_calls)
            self.session.add_tool_results(results)

            # 컨텍스트 관리
            if self.context_manager.should_compact(self.session):
                self._compact_session()

        return "Maximum turns reached."

    def _call_llm(self) -> "ProviderResponse":
        """LLM API 호출."""
        return self.provider.chat(
            messages=self.session.to_api_format(),
            system=self.system_prompt,
            tools=self._get_tool_definitions(),
            max_tokens=self.config.get("max_tokens", 16384),
        )

    # ... 나머지 헬퍼 메서드
```

---

### Step 7: CLI 업데이트 (cli/main.py)

```python
"""CLI 메인 엔트리포인트."""

@click.group()
@click.pass_context
def cli(ctx):
    """Not-Agent CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config()

@cli.command()
@click.option("--model", "-m", help="Model to use")
@click.option("--no-approval", is_flag=True, help="Disable approval")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def agent(ctx, model, no_approval, debug):
    """Interactive agent session."""
    config = ctx.obj["config"]

    # CLI 오버라이드 적용
    if model:
        config.set("model", model)
    if no_approval:
        config.set("approval_enabled", False)
    if debug:
        config.set("debug", True)

    loop = AgentLoop(config)
    # ... 대화 루프
```

---

## 파일 목록

### 새로 생성 (10개)
| 파일 | 설명 |
|------|------|
| `config/__init__.py` | 패키지 초기화, Config 내보내기 |
| `config/config.py` | Config 클래스 구현 |
| `config/defaults.py` | 기본값 정의 |
| `provider/__init__.py` | 패키지 초기화 |
| `provider/base.py` | BaseProvider 추상 클래스 |
| `provider/claude.py` | Claude 프로바이더 |
| `provider/registry.py` | 프로바이더 레지스트리 |
| `tools/registry.py` | 도구 레지스트리 |
| `agent/session.py` | 세션 관리 |
| `agent/context.py` | 컨텍스트 관리 |

### 수정 (12개)
| 파일 | 변경 내용 |
|------|-----------|
| `tools/base.py` | name, description을 클래스 변수로 |
| `tools/__init__.py` | ToolRegistry 사용 |
| `tools/read.py` | @register_tool 적용 |
| `tools/write.py` | @register_tool 적용 |
| `tools/edit.py` | @register_tool 적용 |
| `tools/bash.py` | @register_tool 적용 |
| `tools/glob_tool.py` | @register_tool 적용 |
| `tools/grep.py` | @register_tool 적용 |
| `tools/ask_user.py` | @register_tool 적용 |
| `tools/web_search.py` | @register_tool 적용 |
| `tools/web_fetch.py` | @register_tool 적용 |
| `tools/todo.py` | @register_tool 적용 |
| `agent/loop.py` | Session, ContextManager, Provider 사용 |
| `cli/main.py` | Config 사용 |

### 삭제 (2개)
| 파일 | 사유 |
|------|------|
| `llm/__init__.py` | provider/로 이동 |
| `llm/claude.py` | provider/claude.py로 대체 |

---

## 구현 순서

1. **config/** 모듈 생성 - 다른 모듈의 기반
2. **provider/** 모듈 생성 - llm/ 대체
3. **tools/registry.py** 생성 및 base.py 수정
4. **개별 도구에 @register_tool 적용**
5. **agent/session.py** 생성
6. **agent/context.py** 생성
7. **agent/loop.py** 리팩토링
8. **cli/main.py** 업데이트
9. **llm/** 폴더 정리 (삭제)
10. **통합 테스트**

---

## 검증 방법

```bash
# 1. 기존 명령어 동작 확인
source .venv/bin/activate
not-agent agent
not-agent run "현재 디렉토리의 파일 목록을 보여줘"
not-agent chat
not-agent ask "안녕"

# 2. 설정 파일 테스트
echo '{"model": "claude-haiku-4-5-20251001"}' > .not_agent.json
not-agent agent  # haiku 모델 사용 확인
rm .not_agent.json

# 3. 도구 레지스트리 확인
python -c "from not_agent.tools import ToolRegistry; print([t.name for t in ToolRegistry.get_all()])"

# 4. 프로바이더 확인
python -c "from not_agent.provider import get_provider; from not_agent.config import Config; p = get_provider('claude', Config()); print(p.name)"
```

---

## 예상 작업 시간

총 10개 스텝, 각 스텝별로 순차 진행

## 다음 단계

1. 이 계획대로 구현 시작
2. 완료 후 마일스톤 문서 작성 (014_phase4_structure_refactoring_complete.md)
3. CLAUDE.md 및 README.md 업데이트
