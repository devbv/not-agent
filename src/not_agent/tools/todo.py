"""Todo tools - Task planning and tracking for the agent."""

from dataclasses import dataclass, field

from .base import BaseTool, ToolResult


@dataclass
class TodoItem:
    """A single todo item."""

    content: str  # Task content (e.g., "Run the build")
    status: str  # pending | in_progress | completed


class TodoManager:
    """Instance-based todo state management - injected into AgentLoop."""

    def __init__(self) -> None:
        self._todos: list[dict] = []

    def get_todos(self) -> list[dict]:
        """Return current todo list."""
        return self._todos.copy()

    def set_todos(self, todos: list[dict]) -> None:
        """Replace entire todo list."""
        self._todos = [todo.copy() for todo in todos]

    def clear(self) -> None:
        """Clear todo list."""
        self._todos = []

    def get_summary(self) -> dict:
        """Get summary for CLI display."""
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
        """Get current in-progress task (for CLI status bar)."""
        for t in self._todos:
            if t.get("status") == "in_progress":
                return t.get("content")
        return None


class TodoWriteTool(BaseTool):
    """Todo list update tool - replaces entire list."""

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
        # Uses project's simple format (handled by to_anthropic_tool override)
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
                                    "description": "Task content (e.g., 'Run the build')",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "Task status",
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
        """Update todo list."""
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
    """Todo list read tool."""

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
        return {}  # No parameters

    def __init__(self, todo_manager: TodoManager) -> None:
        self.todo_manager = todo_manager

    def execute(self, **kwargs) -> ToolResult:
        """Return current todo list."""
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
