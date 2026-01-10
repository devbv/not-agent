# Phase 4: Todo 도구 구현

## 개요

에이전트가 복잡한 작업을 계획하고 추적할 수 있는 Todo 도구를 구현합니다.

**상태: ✅ 구현 완료**

---

## 1. Todo 도구 (단순 상태 관리)

### 1.1 핵심 개념

Todo는 에이전트가 아니라 **세션 내 작업 목록을 관리하는 단순 도구**입니다.
- LLM이 복잡한 작업을 계획하고 추적하는 데 사용
- 사용자에게 진행 상황을 시각적으로 보여줌
- 에이전트가 자기 작업을 잊지 않도록 도움

### 1.2 사용 시점

**사용해야 할 때:**
- 3단계 이상의 복잡한 작업
- 사용자가 여러 작업을 요청할 때
- 새 지시사항을 받았을 때 즉시 캡처
- 작업 완료 시 상태 업데이트

**사용하지 말아야 할 때:**
- 단일/단순 작업
- 3단계 미만으로 끝나는 작업
- 순수 대화/정보 요청

### 1.3 상태 관리

```
pending     → 아직 시작 안함
in_progress → 현재 작업 중 (한 번에 하나만!)
completed   → 완료됨
```

### 1.4 데이터 모델

```python
@dataclass
class TodoItem:
    content: str      # 작업 내용 ("Run the build")
    status: str       # pending | in_progress | completed
```

**Note:** id/timestamp 없이 단순하게 유지.
LLM이 전체 목록을 덮어쓰는 방식으로 관리.

---

## 2. 구현된 도구: TodoWrite & TodoRead

### 2.1 TodoWriteTool ✅

전체 Todo 목록을 덮어쓰기 방식으로 업데이트합니다.

**파일:** `src/not_agent/tools/todo.py`

```python
class TodoWriteTool(BaseTool):
    name = "TodoWrite"
    description = "Update the todo list. Replaces the entire list."

    def __init__(self, todo_manager: TodoManager) -> None:
        self.todo_manager = todo_manager

    def to_anthropic_tool(self) -> dict:
        """Anthropic API 형식으로 변환 (array 스키마 지원)"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"]
                                }
                            },
                            "required": ["content", "status"]
                        }
                    }
                },
                "required": ["todos"]
            }
        }

    def execute(self, **kwargs) -> ToolResult:
        todos = kwargs.get("todos", [])
        # 유효성 검사 후 저장
        self.todo_manager.set_todos(todos)
        summary = self.todo_manager.get_summary()
        return ToolResult(
            success=True,
            output=f"Updated {len(todos)} todo(s).\n"
                   f"Status: {summary['completed']}/{summary['total']} completed, "
                   f"{summary['in_progress']} in progress, {summary['pending']} pending"
        )
```

### 2.2 TodoReadTool ✅

현재 Todo 목록을 조회합니다.

```python
class TodoReadTool(BaseTool):
    name = "TodoRead"
    description = "Read the current todo list."

    def __init__(self, todo_manager: TodoManager) -> None:
        self.todo_manager = todo_manager

    def execute(self, **kwargs) -> ToolResult:
        todos = self.todo_manager.get_todos()
        if not todos:
            return ToolResult(success=True, output="No todos in the list.")

        # 아이콘으로 상태 표시
        status_icons = {"completed": "✓", "in_progress": "→", "pending": "○"}
        lines = [f"{i}. [{icon}] {content}" for i, todo in enumerate(todos, 1)
                 for icon, content in [(status_icons.get(todo['status'], '?'), todo['content'])]]

        summary = self.todo_manager.get_summary()
        lines.append(f"\nTotal: {summary['total']} | Completed: {summary['completed']} | "
                    f"In Progress: {summary['in_progress']} | Pending: {summary['pending']}")

        return ToolResult(success=True, output="\n".join(lines))
```

---

## 3. TodoManager (상태 저장) ✅

**파일:** `src/not_agent/tools/todo.py`

세션 단위로 Todo 목록을 메모리에 저장합니다.

### 3.1 설계 결정

- **인스턴스 방식** 채택: 테스트 용이성과 세션 격리를 위해
- AgentLoop에 주입하여 세션별 격리 가능

### 3.2 구현

```python
class TodoManager:
    """인스턴스 기반 Todo 상태 관리 - AgentLoop에 주입"""

    def __init__(self) -> None:
        self._todos: list[dict] = []

    def get_todos(self) -> list[dict]:
        return self._todos.copy()

    def set_todos(self, todos: list[dict]) -> None:
        self._todos = [todo.copy() for todo in todos]

    def clear(self) -> None:
        self._todos = []

    def get_summary(self) -> dict:
        """CLI 표시용 요약 정보"""
        total = len(self._todos)
        completed = sum(1 for t in self._todos if t.get('status') == 'completed')
        in_progress = sum(1 for t in self._todos if t.get('status') == 'in_progress')
        return {
            'total': total,
            'completed': completed,
            'in_progress': in_progress,
            'pending': total - completed - in_progress
        }

    def get_current_task(self) -> str | None:
        """현재 진행 중인 작업 (CLI 상태바용)"""
        for t in self._todos:
            if t.get('status') == 'in_progress':
                return t.get('content')
        return None
```

### 3.3 AgentLoop 통합 ✅

**파일:** `src/not_agent/agent/loop.py`

```python
class AgentLoop:
    def __init__(self, ..., todo_manager: TodoManager | None = None, ...):
        # TodoManager 인스턴스 생성 (세션별 격리)
        self.todo_manager = todo_manager or TodoManager()

        # Executor 설정 - TodoManager 주입
        if executor:
            self.executor = executor
        else:
            tools = get_all_tools(todo_manager=self.todo_manager)
            self.executor = ToolExecutor(tools=tools)
```

### 3.4 도구 등록 ✅

**파일:** `src/not_agent/tools/__init__.py`

```python
def get_all_tools(todo_manager: TodoManager | None = None) -> list[BaseTool]:
    tools = [ReadTool(), WriteTool(), EditTool(), ...]

    # Todo 도구는 manager가 있을 때만 추가
    if todo_manager is not None:
        tools.extend([
            TodoWriteTool(todo_manager),
            TodoReadTool(todo_manager),
        ])

    return tools
```

---

## 4. CLI 통합 ✅

**파일:** `src/not_agent/cli/main.py`

### 4.1 TodoSpinner (실시간 표시)

에이전트 실행 중 Todo 목록과 현재 작업을 실시간으로 표시합니다.

```python
class TodoSpinner:
    """Spinner that shows todo list and current task using Rich Live display."""

    def __init__(self, console: Console, todo_manager: TodoManager):
        self.console = console
        self.todo_manager = todo_manager
        self._live: Live | None = None

    def _build_display(self) -> Group:
        """Build the complete display with todo list and spinner."""
        parts = []

        # Todo list
        todos = self.todo_manager.get_todos()
        if todos:
            status_icons = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}
            summary = self.todo_manager.get_summary()
            parts.append(Text(f"📋 Tasks ({summary['completed']}/{summary['total']})"))

            for todo in todos:
                status = todo.get("status", "pending")
                icon = status_icons.get(status, "⬜")
                content = todo.get("content", "")
                # 상태별 스타일 적용
                if status == "completed":
                    parts.append(Text(f"  {icon} {content}", style="strike"))
                elif status == "in_progress":
                    parts.append(Text(f"  {icon} {content}", style="bold"))
                else:
                    parts.append(Text(f"  {icon} {content}"))

        # Spinner line
        current_task = self.todo_manager.get_current_task()
        if current_task:
            spinner_text = f"[bold green]Thinking...[/bold green] | [yellow]🔄 {current_task}[/yellow]"
        else:
            spinner_text = "[bold green]Thinking...[/bold green]"

        parts.append(Spinner("dots", text=spinner_text, style="green"))
        return Group(*parts)

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def update(self) -> None:
        """Update the live display with current todo state."""
        if self._live:
            self._live.update(self._build_display())
```

### 4.2 Todo 패널 표시

응답 완료 후 최종 Todo 상태를 패널로 표시합니다.

```python
def show_todo_panel(todo_manager: TodoManager) -> None:
    """Show the current todo list as a panel."""
    todos = todo_manager.get_todos()
    if not todos:
        return

    status_icons = {
        "completed": "[green]✅[/green]",
        "in_progress": "[yellow]🔄[/yellow]",
        "pending": "[dim]⬜[/dim]",
    }

    lines = []
    for todo in todos:
        status = todo.get("status", "pending")
        icon = status_icons.get(status, "⬜")
        content = todo.get("content", "")
        # 상태별 스타일 적용
        if status == "completed":
            lines.append(f"{icon} [dim strikethrough]{content}[/dim strikethrough]")
        elif status == "in_progress":
            lines.append(f"{icon} [bold]{content}[/bold]")
        else:
            lines.append(f"{icon} {content}")

    title = f"📋 Tasks ({summary['completed']}/{summary['total']} completed)"
    console.print(Panel("\n".join(lines), title=title, border_style="blue"))
```

### 4.3 표시 방식 (구현됨)

- **실시간 표시**: Rich Live를 사용하여 에이전트 실행 중 Todo 목록 + Spinner 표시
- **TodoWrite 시 업데이트**: `update_spinner_callback`으로 즉시 갱신
- **완료 후 패널**: 응답 완료 후 `show_todo_panel()`로 최종 상태 표시

---

## 5. 시스템 프롬프트 업데이트 ✅

**파일:** `src/not_agent/agent/loop.py`

```python
def _get_system_prompt(self) -> str:
    return """...
TODO TOOL USAGE:
Use TodoWrite to plan and track complex tasks (3+ steps).

When to use:
- Complex tasks with 3+ steps
- User requests multiple things at once
- Multi-file changes

When NOT to use:
- Single, simple tasks
- Tasks under 3 steps
- Pure conversation/information requests

Status values:
- pending: Not yet started
- in_progress: Currently working on (only ONE at a time!)
- completed: Finished

Mark tasks as completed IMMEDIATELY after finishing (don't batch).
"""
```

---

## 6. 구현 체크리스트

### Step 1: Todo 도구 구현 ✅
- [x] `src/not_agent/tools/todo.py` 생성
- [x] `TodoManager` 클래스 구현
- [x] `TodoWriteTool` 구현 (유효성 검사 포함)
- [x] `TodoReadTool` 구현 (아이콘 표시)
- [x] `__init__.py`에 등록

### Step 2: AgentLoop 통합 ✅
- [x] TodoManager 인스턴스 주입
- [x] TodoWrite 시 update_spinner_callback 호출

### Step 3: CLI Todo 표시 ✅
- [x] `TodoSpinner` 클래스 구현 (Rich Live)
- [x] `show_todo_panel()` 함수 구현
- [x] 실시간 업데이트 지원

### Step 4: 시스템 프롬프트 업데이트 ✅
- [x] Todo 도구 사용 가이드라인 추가
- [x] 언제 사용하고 언제 사용하지 말지 명시

### Step 5: 테스트 ✅
- [x] TodoManager 단위 테스트 (10개)
- [x] TodoWriteTool 단위 테스트 (10개)
- [x] TodoReadTool 단위 테스트 (7개)
- [x] 통합 테스트 (4개)

**테스트 파일:** `tests/test_tools/test_todo.py` (31개 테스트 전체 통과)

---

## 7. 실제 동작 예시

```
📋 Tasks (2/5)
  ✅ Run the build
  ✅ Fix type error in utils.py
  🔄 Fix type error in main.py
  ⬜ Fix type error in loop.py
  ⬜ Run tests

⠋ Thinking... | 🔄 Fix type error in main.py (2/5)
```

