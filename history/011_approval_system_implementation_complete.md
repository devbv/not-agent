# Approval System Implementation Complete

**작성일**: 2026-01-10
**목표**: 승인 시스템을 Plugin 패턴으로 재설계 및 구현

## 개요

[009_approval_system_redesign_plan.md](009_approval_system_redesign_plan.md)에서 계획한 승인 시스템을 성공적으로 구현했습니다.

## 구현 내용

### 1. ApprovalManager Plugin 구현

**파일**: `src/not_agent/agent/approval.py`

```python
class ApprovalManager:
    """Tool 실행 전 사용자 승인 플러그인"""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.history: list[tuple[str, bool]] = []

    async def request(self, tool_name: str, details: str) -> bool:
        """y/n만 허용하는 간단한 승인 요청"""
```

**특징**:
- y/n 입력만 허용
- 승인 이력 관리
- 간단하고 빠른 게이트

### 2. Tool Base Class 수정

**파일**: `src/not_agent/tools/base.py`

```python
class BaseTool(ABC):
    async def get_approval_description(self, **kwargs: Any) -> str | None:
        """
        승인 플러그인에게 제공할 설명

        Returns:
            None: 승인 불필요
            str: 승인 필요 - 설명
        """
        return None  # 기본값: 승인 불필요
```

### 3. 각 Tool에 승인 로직 구현

#### WriteTool
```python
async def get_approval_description(self, file_path: str, content: str, **kwargs) -> str:
    """항상 승인 필요"""
    lines = len(content.split("\n"))
    exists = Path(file_path).exists()

    if exists:
        return f"Overwrite {file_path} ({lines} lines)"
    else:
        return f"Write {lines} lines to {file_path} (new file)"
```

#### EditTool
```python
async def get_approval_description(self, file_path: str, old_string: str, new_string: str, **kwargs) -> str:
    """항상 승인 필요"""
    old_lines = len(old_string.split("\n"))
    new_lines = len(new_string.split("\n"))
    return f"Edit {file_path} ({old_lines}→{new_lines} lines)"
```

#### BashTool (동적 판단)
```python
DANGEROUS_PATTERNS = ["rm ", "mv ", "dd ", "format", ">", ">>", "|"]

async def get_approval_description(self, command: str, **kwargs) -> str | None:
    """위험한 명령어만 승인 요청"""
    for pattern in self.DANGEROUS_PATTERNS:
        if pattern in command:
            return f"Run command: {command}"
    return None  # 안전한 명령어는 승인 불필요
```

### 4. Executor 대폭 단순화

**Before** (193 lines):
- 복잡한 대화 히스토리 분석
- LLM을 사용한 승인 확인
- AskUserQuestion 응답 파싱
- 강한 결합

**After** (112 lines):
```python
class ToolExecutor:
    def __init__(self, tools=None, approval_manager=None):
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}
        self.approval = approval_manager

    async def execute_async(self, tool_name, tool_input):
        tool = self.tools[tool_name]

        # Plugin Hook: Approval
        if self.approval and self.approval.enabled:
            approval_desc = await tool.get_approval_description(**tool_input)
            if approval_desc:
                approved = await self.approval.request(tool.name, approval_desc)
                if not approved:
                    return ToolResult(error="User denied permission")

        # 실제 도구 실행
        return tool.execute(**tool_input)
```

**개선 사항**:
- ❌ 제거: `_check_approval_given()` (68 lines)
- ❌ 제거: `_ask_llm_for_approval_decision()` (29 lines)
- ❌ 제거: `set_conversation_history()`
- ❌ 제거: Anthropic client 의존성
- ✅ 추가: 간단한 플러그인 호출 (9 lines)

### 5. AgentLoop 수정

**파일**: `src/not_agent/agent/loop.py`

```python
class AgentLoop:
    def __init__(
        self,
        ...,
        executor: ToolExecutor | None = None,  # 추가
    ):
        self.executor = executor or ToolExecutor()
```

- Executor를 주입받도록 변경
- `set_conversation_history()` 호출 제거

### 6. CLI 통합

**파일**: `src/not_agent/cli/main.py`

```bash
# --approval 옵션 추가
not-agent agent --approval
not-agent run "task" --approval
```

**구현**:
```python
@cli.command()
@click.option("--approval/--no-approval", default=False)
def agent(approval: bool):
    # Create approval manager
    approval_manager = ApprovalManager(enabled=approval) if approval else None

    # Create executor with plugin
    executor = ToolExecutor(approval_manager=approval_manager)

    # Create agent loop
    agent_loop = AgentLoop(executor=executor)

    if approval:
        console.print("⚠️  Approval mode enabled")
```

### 7. AskUserQuestion 도구

이미 번호 선택 기능이 잘 구현되어 있어 추가 수정 불필요.

```python
# options 제공 시: 번호 선택
# options 미제공 시: 자유 입력
```

## 핵심 설계 원칙

### Approval vs AskUserQuestion 명확한 분리

```
┌─────────────────┬──────────────────┬─────────────────────┐
│                 │ Approval         │ AskUserQuestion     │
├─────────────────┼──────────────────┼─────────────────────┤
│ 트리거          │ Executor 자동    │ LLM 명시적 호출     │
│ 입력 방식       │ y/n만            │ 번호 선택 or 자유   │
│ UI 프롬프트     │ "⚠️  Approve?"   │ "❓ Question"       │
│ 거부 시         │ 도구 실행 취소   │ 답변을 LLM에 전달   │
│ 목적            │ 안전 장치        │ 정보 수집           │
│ 피드백 루프     │ 간접적 (에러)    │ 직접적 (답변)       │
└─────────────────┴──────────────────┴─────────────────────┘
```

### Plugin 패턴의 장점

```
Approval = Plugin (도구가 아님!)

특징:
├─ LLM이 호출하지 않음
├─ Executor에 주입됨 (DI)
├─ Tool 실행 전 자동 실행 (Hook)
├─ Tool은 플러그인 존재를 모름
└─ 켜고 끌 수 있음 (--approval)

장점:
├─ 관심사 분리
├─ Executor 코드 42% 감소 (193→112 lines)
├─ Tool과 느슨한 결합
├─ 확장 가능 (다른 플러그인 추가 가능)
└─ 테스트 용이
```

## 테스트

### CLI 옵션 확인
```bash
$ not-agent agent --help
Usage: not-agent agent [OPTIONS]

Options:
  --approval / --no-approval  Require approval for file modifications
                              (default: disabled)
  --help                      Show this message and exit.
```

### 예상 시나리오

#### 1. 승인 모드 활성화
```bash
$ not-agent agent --approval

⚠️  Approval mode enabled
You will be asked before file modifications

> User: src/main.py 파일 수정해줘

⚠️  Permission required: edit
   Edit src/main.py (5→10 lines)
   Approve? [y/n]: y

✅ Successfully edited src/main.py
```

#### 2. 승인 거부 → LLM이 대안 제시
```bash
⚠️  Permission required: bash
   Run command: rm *.log
   Approve? [y/n]: n

User denied permission. Please ask what to do instead.

[LLM이 AskUserQuestion 사용하여 대안 제시]
```

#### 3. BashTool 동적 판단
```bash
# 안전한 명령어 - 승인 불필요
$ ls -la
(승인 없이 바로 실행)

# 위험한 명령어 - 승인 필요
$ rm -rf /
⚠️  Permission required: bash
   Run command: rm -rf /
   Approve? [y/n]:
```

## 성과

### 코드 품질 개선

- **Executor 단순화**: 193 lines → 112 lines (42% 감소)
- **복잡도 감소**: LLM 기반 승인 체크 제거
- **의존성 감소**: Executor의 Anthropic client 제거
- **결합도 감소**: Tool과 Executor 느슨한 결합

### 아키텍처 개선

```
Before: Executor가 모든 것을 알아야 함
- 어떤 도구가 위험한지
- 대화 히스토리 파싱
- 승인 응답 해석

After: 각자의 책임만 수행
- Tool: 자신이 위험한지 판단
- ApprovalManager: y/n 입력 처리
- Executor: 플러그인 호출만
```

### 확장성

미래에 쉽게 추가 가능:
```python
# 다른 플러그인 추가
executor = ToolExecutor(
    approval_manager=ApprovalManager(enabled=True),
    logging_plugin=LoggingPlugin(),
    rate_limit_plugin=RateLimitPlugin(),
    cost_tracking_plugin=CostTrackingPlugin(),
)
```

## 다음 단계

- [x] 승인 시스템 재설계 완료
- [x] Plugin 패턴 구현 완료
- [x] CLI 통합 완료
- [ ] 실제 사용 테스트
- [ ] 필요시 UI 개선 (색상, 아이콘 등)
- [ ] 다른 플러그인 고려 (로깅, 속도 제한 등)

## 참고

- 계획 문서: [009_approval_system_redesign_plan.md](009_approval_system_redesign_plan.md)
- 관련 파일:
  - [src/not_agent/agent/approval.py](../src/not_agent/agent/approval.py)
  - [src/not_agent/agent/executor.py](../src/not_agent/agent/executor.py)
  - [src/not_agent/agent/loop.py](../src/not_agent/agent/loop.py)
  - [src/not_agent/cli/main.py](../src/not_agent/cli/main.py)
  - [src/not_agent/tools/base.py](../src/not_agent/tools/base.py)
  - [src/not_agent/tools/write.py](../src/not_agent/tools/write.py)
  - [src/not_agent/tools/edit.py](../src/not_agent/tools/edit.py)
  - [src/not_agent/tools/bash.py](../src/not_agent/tools/bash.py)
