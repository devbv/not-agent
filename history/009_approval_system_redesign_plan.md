# Phase 4: Approval System Redesign Plan

**작성일**: 2026-01-10
**목표**: Tool 실행 전 사용자 승인을 받는 시스템을 Plugin 패턴으로 재설계

## 1. 현재 문제점

### 현재 구조의 문제
```python
# 현재: Executor가 승인 로직을 직접 처리
class Executor:
    def _needs_approval(self, tool_name, tool_input):
        # ❌ Executor가 "어떤 도구가 위험한지" 판단해야 함
        if tool_name in ["write", "edit"]:
            return True
        if tool_name == "bash" and self._is_file_modifying_command(tool_input):
            # ❌ Executor가 bash 명령어까지 파싱
            return True
```

**문제점**:
1. Executor와 Tool 사이에 강한 결합
2. 새 도구 추가 시 Executor 수정 필요
3. 도구별 승인 로직 커스터마이징 불가능
4. Bash 명령어 파싱 등 도메인 로직이 Executor에 섞임

## 2. 핵심 설계 원칙

### 승인 메커니즘의 두 가지 분리

```
┌─────────────────────┬──────────────────┬─────────────────────┐
│                     │ Approval         │ AskUserQuestion     │
├─────────────────────┼──────────────────┼─────────────────────┤
│ 트리거              │ Executor 자동    │ LLM 명시적 호출     │
│ 입력 방식           │ y/n만            │ 번호 선택 or 자유   │
│ 설명 추가           │ 불가             │ 가능                │
│ UI 프롬프트         │ "Approve?"       │ "Select:" / "Answer:" │
│ 거부 시             │ 도구 실행 취소   │ 답변을 LLM에 전달   │
│ 목적                │ 안전 장치        │ 정보 수집           │
│ 피드백 루프         │ 간접적 (에러)    │ 직접적 (답변)       │
└─────────────────────┴──────────────────┴─────────────────────┘
```

### Approval = Plugin (도구가 아님!)

```
Approval의 특징:
├─ LLM이 호출하지 않음 (도구 목록에 없음)
├─ Executor에 주입됨 (Dependency Injection)
├─ Tool 실행 전 자동으로 실행됨 (Hook)
├─ Tool은 플러그인 존재를 몰라도 됨
└─ 켜고 끌 수 있음 (enabled flag)
```

## 3. 새로운 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────┐
│         Executor (오케스트레이터)            │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  ApprovalManager (플러그인)         │   │
│  │  - enabled: bool                    │   │
│  │  - request(desc) -> bool            │   │
│  └─────────────────────────────────────┘   │
│                   ▲                         │
│                   │ 주입됨                  │
│  ┌────────────────┴──────────────────────┐ │
│  │  Tool Execution Pipeline             │ │
│  │                                       │ │
│  │  1. Tool.get_approval_description()  │ │
│  │  2. ApprovalManager.request()  ◄──── 플러그인 호출
│  │  3. Tool.execute()                   │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘

각 Tool:
├─ WriteTool
│  └─ get_approval_description() 구현
├─ EditTool
│  └─ get_approval_description() 구현
├─ BashTool
│  └─ get_approval_description() 구현 (동적)
└─ ReadTool
   └─ get_approval_description() = None (승인 불필요)
```

### 역할 분담

```
Executor:
├─ 도구 실행 오케스트레이션
├─ 플러그인 호출 (Approval, Logging 등)
└─ 결과 반환

Tool:
├─ 자신이 승인 필요한지 판단
├─ 승인 설명 제공
└─ 실제 작업 수행

ApprovalManager (Plugin):
├─ y/n 입력 받기
├─ 승인 이력 관리
└─ 사용자와 직접 상호작용
```

## 4. 구현 계획

### 4.1. ApprovalManager 플러그인 구현

**파일**: `src/not_agent/agent/approval.py`

```python
class ApprovalManager:
    """
    Tool 실행 전 사용자 승인을 받는 플러그인

    - Tool이 아님 (LLM이 호출하지 않음)
    - Executor에 주입되어 모든 Tool 실행 전 실행됨
    - Tool이 제공한 설명을 기반으로 y/n 확인
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.history: list[tuple[str, bool]] = []

    async def request(self, tool_name: str, details: str) -> bool:
        """
        사용자에게 승인 요청 (y/n만 허용)

        Returns:
            True: 승인
            False: 거부
        """
```

**특징**:
- 오직 `y/n` 입력만 받음
- 간단하고 빠른 게이트
- 추가 설명 불가 (필요하면 거부 후 LLM이 AskUserQuestion 사용)

### 4.2. Tool 베이스 클래스 수정

**파일**: `src/not_agent/tools/base.py`

```python
class Tool(ABC):
    """도구 베이스 클래스"""

    name: str
    description: str

    @abstractmethod
    async def execute(self, **params) -> Any:
        """도구 실행"""
        pass

    async def get_approval_description(self, **params) -> str | None:
        """
        승인 플러그인에게 제공할 설명

        Returns:
            None: 이 도구는 승인 불필요
            str: 승인 필요 - 사용자에게 보여줄 설명
        """
        return None  # 기본값: 승인 불필요
```

### 4.3. 각 Tool에 승인 로직 추가

#### WriteTool
```python
class WriteTool(Tool):
    name = "write"
    requires_approval = True  # 항상 승인 필요

    async def get_approval_description(self, file_path: str, content: str) -> str:
        lines = len(content.split('\n'))
        return f"Write {lines} lines to {file_path}"
```

#### EditTool
```python
class EditTool(Tool):
    name = "edit"
    requires_approval = True

    async def get_approval_description(self, file_path: str, **params) -> str:
        return f"Edit {file_path}"
```

#### BashTool (동적 판단)
```python
class BashTool(Tool):
    name = "bash"
    DANGEROUS_COMMANDS = ['rm', 'mv', 'dd', 'format', '>', '|']

    async def get_approval_description(self, command: str) -> str | None:
        """위험한 명령어만 승인 요청"""
        if any(dangerous in command for dangerous in self.DANGEROUS_COMMANDS):
            return f"Run command: {command}"
        return None  # 안전한 명령어는 승인 불필요
```

#### ReadTool, GlobTool, GrepTool
```python
# 읽기 전용 도구들은 승인 불필요
async def get_approval_description(self, **params) -> str | None:
    return None
```

### 4.4. Executor 수정

**파일**: `src/not_agent/agent/executor.py`

```python
class Executor:
    """도구 실행 호스트 (플러그인 지원)"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        approval_plugin: ApprovalManager | None = None,
    ):
        self.tool_registry = tool_registry
        self.approval = approval_plugin

    async def execute_tool(self, tool_use: ToolUse) -> ToolResult:
        """도구 실행 파이프라인 (플러그인 적용)"""

        tool = self.tool_registry.get(tool_use.name)

        # === Plugin Hook: Approval ===
        if self.approval:
            approval_desc = await tool.get_approval_description(**tool_use.input)

            if approval_desc:
                approved = await self.approval.request(tool.name, approval_desc)

                if not approved:
                    return ToolResult(
                        tool_use_id=tool_use.id,
                        output="User denied permission. Ask what to do instead."
                    )

        # === 실제 실행 ===
        try:
            result = await tool.execute(**tool_use.input)
            return ToolResult(tool_use_id=tool_use.id, output=str(result))
        except Exception as e:
            return ToolResult(tool_use_id=tool_use.id, is_error=True, output=str(e))
```

**변경 사항**:
- ❌ 제거: `_needs_approval()` 메서드
- ❌ 제거: `_is_file_modifying_command()` 메서드
- ❌ 제거: `_get_user_approval()` 메서드
- ✅ 추가: `approval_plugin` 파라미터
- ✅ 단순화: 플러그인에 위임

### 4.5. AskUserQuestion 도구 개선

**파일**: `src/not_agent/tools/ask_user.py`

```python
class AskUserQuestionTool(Tool):
    """LLM이 사용자에게 질문하는 도구 (Approval과 별개)"""

    name = "ask_user_question"
    description = """Ask the user a question when you need:
    - Clarification on requirements
    - Decision between multiple options
    - Additional information

    Use 'options' for multiple choice, omit for free-form answer.
    """

    async def execute(
        self,
        question: str,
        options: list[str] | None = None,
        allow_freeform: bool = True
    ) -> str:
        """
        번호 선택 또는 자유 입력

        Args:
            question: 질문 내용
            options: 선택지 (있으면 번호 선택)
            allow_freeform: 자유 입력 허용 여부
        """
        print(f"\n❓ {question}")

        if options:
            for i, opt in enumerate(options, 1):
                print(f"   {i}. {opt}")

            if allow_freeform:
                print(f"   {len(options)+1}. Other (custom input)")

            while True:
                choice = input("\n   Select (number): ").strip()

                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(options):
                        return options[idx]
                    elif allow_freeform and idx == len(options):
                        return input("   Enter custom response: ").strip()

                print("   Invalid selection. Try again.")
        else:
            # 자유 형식 질문
            return input("   Your answer: ").strip()
```

**특징**:
- 번호 선택 또는 자유 입력 가능
- LLM이 명시적으로 호출
- 풍부한 피드백 제공
- 나중에 UI 개선 가능 (structured data)

### 4.6. CLI 통합

**파일**: `src/not_agent/cli/main.py`

```python
@click.command()
@click.option('--approval/--no-approval', default=False, help='Require approval for file modifications')
def agent(approval: bool):
    """Run the agent in interactive mode"""

    # ApprovalManager 생성 (옵션에 따라)
    approval_manager = ApprovalManager(enabled=approval) if approval else None

    # Executor에 플러그인 주입
    executor = Executor(
        tool_registry=tool_registry,
        approval_plugin=approval_manager
    )

    # Agent 생성
    agent = Agent(llm=llm, executor=executor)

    # 시작 메시지
    if approval:
        print("⚠️  Approval mode enabled. You will be asked before file modifications.")

    # 루프 시작
    ...
```

**사용법**:
```bash
# 승인 없이 실행 (기본)
not-agent agent

# 승인 활성화
not-agent agent --approval
```

## 5. 시각적 구분

### Approval vs AskUserQuestion

```python
# Approval - 경고 스타일
⚠️  Permission required: write
   Write 42 lines to src/main.py
   Approve? [y/n]:

# AskUserQuestion - 중립 스타일
❓ Which framework should I use?
   1. FastAPI
   2. Flask
   3. Django
   4. Other (custom input)

   Select (number):
```

**색상** (Rich 라이브러리 활용):
- Approval: 노란색/빨간색 (경고)
- AskUserQuestion: 파란색 (중립)

## 6. 구현 순서

### Step 1: ApprovalManager 플러그인 구현
- [x] `src/not_agent/agent/approval.py` 생성
- [ ] y/n 입력 로직
- [ ] 승인 이력 관리

### Step 2: Tool 베이스 클래스 수정
- [ ] `get_approval_description()` 메서드 추가
- [ ] 기본 구현 (None 반환)

### Step 3: 각 Tool에 승인 로직 구현
- [ ] WriteTool
- [ ] EditTool
- [ ] BashTool (동적 판단)
- [ ] 나머지 도구들 (None 반환)

### Step 4: Executor 단순화
- [ ] 기존 승인 로직 제거
- [ ] 플러그인 호출 로직 추가
- [ ] 거부 시 메시지 개선

### Step 5: AskUserQuestion 도구 개선
- [ ] 번호 선택 기능 추가
- [ ] 자유 입력 옵션 추가
- [ ] description 업데이트

### Step 6: CLI 통합
- [ ] `--approval` 옵션 추가
- [ ] ApprovalManager 생성 및 주입
- [ ] 시작 메시지 추가

### Step 7: 테스트 작성
- [ ] ApprovalManager 단위 테스트
- [ ] 각 Tool의 `get_approval_description()` 테스트
- [ ] Executor 통합 테스트
- [ ] AskUserQuestion 도구 테스트

### Step 8: 문서화
- [ ] 사용자 가이드 업데이트
- [ ] API 문서 업데이트
- [ ] 예시 추가

## 7. 예상 시나리오

### 시나리오 1: Approval 승인

```bash
$ not-agent agent --approval

> User: src/main.py 파일을 수정해서 버그를 고쳐줘

🤔 Thinking...

⚠️  Permission required: edit
   Edit src/main.py
   Approve? [y/n]: y

✅ Successfully edited src/main.py
```

### 시나리오 2: Approval 거부 → LLM이 질문

```bash
> User: 모든 .log 파일을 삭제해줘

🤔 Thinking...

⚠️  Permission required: bash
   Run command: rm *.log
   Approve? [y/n]: n

🤔 Thinking...

❓ I need approval to delete files. Would you like to:
   1. Delete only old logs (7+ days)
   2. Move logs to archive folder
   3. Compress logs instead of deleting
   4. Other (custom input)

   Select (number): 2

🤔 Thinking...

⚠️  Permission required: bash
   Run command: mkdir -p archive && mv *.log archive/
   Approve? [y/n]: y

✅ Moved log files to archive/
```

### 시나리오 3: AskUserQuestion (승인 무관)

```bash
> User: 새로운 API를 추가해줘

🤔 Thinking...

❓ Which framework should I use for the API?
   1. FastAPI (Recommended)
   2. Flask
   3. Django REST Framework
   4. Other (custom input)

   Select (number): 1

🤔 Thinking...

⚠️  Permission required: write
   Write 50 lines to src/api/main.py
   Approve? [y/n]: y

✅ Created API endpoint using FastAPI
```

## 8. 장점 정리

### 관심사의 분리
```
Executor: 오케스트레이션만
Tool: 자신의 위험성 판단
ApprovalManager: 사용자 상호작용
```

### 확장성
```
새 도구 추가:
├─ Executor 수정 불필요
├─ 도구별 승인 로직 커스터마이징
└─ 동적 판단 가능 (Bash 예시)

새 플러그인 추가:
├─ LoggingPlugin: 실행 로깅
├─ RateLimitPlugin: 속도 제한
├─ CostTrackingPlugin: 비용 추적
└─ 기존 코드 수정 최소화
```

### 테스트 용이성
```
각 컴포넌트 독립 테스트:
├─ Tool: 승인 설명 생성 테스트
├─ ApprovalManager: y/n 입력 테스트
├─ Executor: 플러그인 호출 테스트
└─ Mock 없이 단위 테스트 가능
```

### 사용자 경험
```
명확한 구분:
├─ Approval: ⚠️ y/n (빠른 게이트)
├─ Question: ❓ 번호/텍스트 (풍부한 대화)
└─ 시각적으로 다른 프롬프트
```

## 9. 미래 확장 가능성

### 승인 레벨
```python
class Tool:
    approval_level: str = "none"  # "none" | "info" | "warning" | "danger"

    async def get_approval_info(self, **params):
        return {
            "level": self.approval_level,
            "description": "...",
            "risk": "Irreversible file deletion",  # danger인 경우
        }
```

### 다른 플러그인
```python
class LoggingPlugin:
    async def before_execute(self, tool_name: str, params: dict):
        ...

    async def after_execute(self, tool_name: str, result: Any):
        ...

class RateLimitPlugin:
    async def check(self, tool_name: str) -> bool:
        ...

class CostTrackingPlugin:
    async def track(self, tool_name: str, result: Any):
        ...
```

### UI 개선
```python
# CLI: 단순 텍스트
# GUI: Structured form with dropdowns
# Web: React components

class AskUserQuestionTool:
    async def execute(self, question: str, options: list[str] = None):
        if self.ui_mode == "cli":
            # 현재 구현
        elif self.ui_mode == "gui":
            # Rich TUI with forms
        elif self.ui_mode == "web":
            # JSON response for React
```

## 10. 성공 기준

- [ ] 모든 파일 수정 작업이 승인 플러그인을 거침
- [ ] Tool은 승인 플러그인 존재를 모름 (느슨한 결합)
- [ ] Executor 코드가 50% 이상 단순해짐
- [ ] 새 도구 추가 시 Executor 수정 불필요
- [ ] Approval과 AskUserQuestion이 시각적으로 구분됨
- [ ] `--approval` 옵션으로 쉽게 켜고 끌 수 있음
- [ ] 모든 단위 테스트 통과

## 참고

- Claude Code의 approval 시스템 참고
- Plugin 패턴: 느슨한 결합, 높은 확장성
- Approval ≠ Tool (이것이 핵심!)
