"""Todo tools - Task planning and tracking for the agent."""

from dataclasses import dataclass, field

from .base import BaseTool, ToolResult


@dataclass
class TodoItem:
    """A single todo item."""

    content: str  # 작업 내용 (예: "Run the build")
    status: str  # pending | in_progress | completed


class TodoManager:
    """인스턴스 기반 Todo 상태 관리 - AgentLoop에 주입."""

    def __init__(self) -> None:
        self._todos: list[dict] = []

    def get_todos(self) -> list[dict]:
        """현재 Todo 목록 반환."""
        return self._todos.copy()

    def set_todos(self, todos: list[dict]) -> None:
        """Todo 목록 전체 교체."""
        self._todos = [todo.copy() for todo in todos]

    def clear(self) -> None:
        """Todo 목록 초기화."""
        self._todos = []

    def get_summary(self) -> dict:
        """CLI 표시용 요약 정보."""
        total = len(self._todos)
        completed = sum(1 for t in self._todos if t.get("status") == "completed")
        in_progress = sum(1 for t in self._todos if t.get("status") == "in_progress")
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": total - completed - in_progress,
        }

    def get_current_task(self) -> str | None:
        """현재 진행 중인 작업 (CLI 상태바용)."""
        for t in self._todos:
            if t.get("status") == "in_progress":
                return t.get("content")
        return None


class TodoWriteTool(BaseTool):
    """Todo 목록 업데이트 도구 - 전체 목록을 덮어씁니다."""

    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return """Update the todo list. Replaces the entire list.

Use this tool to:
- Plan complex multi-step tasks (3+ steps)
- Track progress on multiple tasks
- Mark tasks as completed or in_progress

When to use:
- Complex tasks with 3+ steps
- User requests multiple things
- After receiving new instructions

When NOT to use:
- Single, simple tasks
- Tasks under 3 steps
- Pure conversation/information requests

Status values:
- pending: Not yet started
- in_progress: Currently working on (only ONE at a time!)
- completed: Finished

Example:
{
    "todos": [
        {"content": "Run the build", "status": "completed"},
        {"content": "Fix error in main.py", "status": "in_progress"},
        {"content": "Run tests", "status": "pending"}
    ]
}"""

    @property
    def parameters(self) -> dict:
        # 이 프로젝트의 간단한 형식 사용 (to_anthropic_tool 오버라이드로 처리)
        return {
            "todos": {
                "type": "array",
                "description": "The updated todo list (replaces entire list)",
                "required": True,
            }
        }

    def __init__(self, todo_manager: TodoManager) -> None:
        self.todo_manager = todo_manager

    def to_anthropic_tool(self) -> dict:
        """Convert to Anthropic API tool format with proper array schema."""
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
                                "content": {
                                    "type": "string",
                                    "description": "작업 내용 (예: 'Run the build')",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "작업 상태",
                                },
                            },
                            "required": ["content", "status"],
                        },
                        "description": "The updated todo list (replaces entire list)",
                    }
                },
                "required": ["todos"],
            },
        }

    def execute(self, **kwargs) -> ToolResult:
        """Todo 목록 업데이트."""
        todos = kwargs.get("todos", [])

        if not isinstance(todos, list):
            return ToolResult(
                success=False,
                output="",
                error="'todos' must be a list",
            )

        # Validate each todo item
        valid_statuses = {"pending", "in_progress", "completed"}
        for i, todo in enumerate(todos):
            if not isinstance(todo, dict):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Todo item {i} must be an object",
                )
            if "content" not in todo:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Todo item {i} missing 'content'",
                )
            if "status" not in todo:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Todo item {i} missing 'status'",
                )
            if todo["status"] not in valid_statuses:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Todo item {i} has invalid status '{todo['status']}'. Must be one of: {valid_statuses}",
                )

        # Update the todo list
        self.todo_manager.set_todos(todos)

        # Generate summary
        summary = self.todo_manager.get_summary()
        output_lines = [f"Updated {len(todos)} todo(s)."]
        output_lines.append(
            f"Status: {summary['completed']}/{summary['total']} completed, "
            f"{summary['in_progress']} in progress, {summary['pending']} pending"
        )

        return ToolResult(success=True, output="\n".join(output_lines))


class TodoReadTool(BaseTool):
    """Todo 목록 조회 도구."""

    @property
    def name(self) -> str:
        return "todo_read"

    @property
    def description(self) -> str:
        return """Read the current todo list.

Returns all todos with their status.
Useful when you need to check current progress or after context compaction."""

    @property
    def parameters(self) -> dict:
        return {}  # 파라미터 없음

    def __init__(self, todo_manager: TodoManager) -> None:
        self.todo_manager = todo_manager

    def execute(self, **kwargs) -> ToolResult:
        """현재 Todo 목록 반환."""
        todos = self.todo_manager.get_todos()

        if not todos:
            return ToolResult(success=True, output="No todos in the list.")

        # Format output
        status_icons = {
            "completed": "✓",
            "in_progress": "→",
            "pending": "○",
        }

        lines = []
        for i, todo in enumerate(todos, 1):
            status = todo.get("status", "pending")
            icon = status_icons.get(status, "?")
            content = todo.get("content", "")
            lines.append(f"{i}. [{icon}] {content}")

        # Add summary
        summary = self.todo_manager.get_summary()
        lines.append("")
        lines.append(
            f"Total: {summary['total']} | "
            f"Completed: {summary['completed']} | "
            f"In Progress: {summary['in_progress']} | "
            f"Pending: {summary['pending']}"
        )

        return ToolResult(success=True, output="\n".join(lines))
