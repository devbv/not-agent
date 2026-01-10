"""Tests for Todo tools - TodoManager, TodoWriteTool, TodoReadTool."""

import pytest

from not_agent.tools.todo import TodoManager, TodoWriteTool, TodoReadTool


class TestTodoManager:
    """TodoManager 단위 테스트."""

    def test_init_empty(self):
        """초기화 시 빈 목록."""
        manager = TodoManager()
        assert manager.get_todos() == []

    def test_set_and_get_todos(self):
        """Todo 설정 및 조회."""
        manager = TodoManager()
        todos = [
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "in_progress"},
        ]
        manager.set_todos(todos)

        result = manager.get_todos()
        assert len(result) == 2
        assert result[0]["content"] == "Task 1"
        assert result[1]["status"] == "in_progress"

    def test_get_todos_returns_copy(self):
        """get_todos()는 복사본을 반환해야 함."""
        manager = TodoManager()
        todos = [{"content": "Task 1", "status": "pending"}]
        manager.set_todos(todos)

        result = manager.get_todos()
        result.append({"content": "Task 2", "status": "pending"})

        # 원본은 변경되지 않아야 함
        assert len(manager.get_todos()) == 1

    def test_set_todos_makes_copy(self):
        """set_todos()는 입력값을 복사해야 함."""
        manager = TodoManager()
        todos = [{"content": "Task 1", "status": "pending"}]
        manager.set_todos(todos)

        # 원본 수정
        todos[0]["content"] = "Modified"

        # 내부 데이터는 변경되지 않아야 함
        assert manager.get_todos()[0]["content"] == "Task 1"

    def test_clear(self):
        """Todo 목록 초기화."""
        manager = TodoManager()
        manager.set_todos([{"content": "Task 1", "status": "pending"}])
        manager.clear()

        assert manager.get_todos() == []

    def test_get_summary_empty(self):
        """빈 목록의 요약."""
        manager = TodoManager()
        summary = manager.get_summary()

        assert summary == {
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "pending": 0,
        }

    def test_get_summary_with_todos(self):
        """Todo가 있는 경우의 요약."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "completed"},
            {"content": "Task 3", "status": "in_progress"},
            {"content": "Task 4", "status": "pending"},
            {"content": "Task 5", "status": "pending"},
        ])

        summary = manager.get_summary()
        assert summary == {
            "total": 5,
            "completed": 2,
            "in_progress": 1,
            "pending": 2,
        }

    def test_get_current_task_none(self):
        """진행 중인 작업이 없을 때."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "pending"},
        ])

        assert manager.get_current_task() is None

    def test_get_current_task_exists(self):
        """진행 중인 작업이 있을 때."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "in_progress"},
            {"content": "Task 3", "status": "pending"},
        ])

        assert manager.get_current_task() == "Task 2"

    def test_get_current_task_first_in_progress(self):
        """여러 in_progress가 있을 때 첫 번째 반환."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "Task 1", "status": "in_progress"},
            {"content": "Task 2", "status": "in_progress"},
        ])

        assert manager.get_current_task() == "Task 1"


class TestTodoWriteTool:
    """TodoWriteTool 단위 테스트."""

    def test_name_and_description(self):
        """도구 이름과 설명."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        assert tool.name == "TodoWrite"
        assert "Update the todo list" in tool.description

    def test_execute_success(self):
        """정상적인 Todo 업데이트."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        result = tool.execute(todos=[
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "in_progress"},
        ])

        assert result.success is True
        assert "Updated 2 todo(s)" in result.output
        assert len(manager.get_todos()) == 2

    def test_execute_empty_list(self):
        """빈 목록으로 업데이트."""
        manager = TodoManager()
        manager.set_todos([{"content": "Old task", "status": "pending"}])
        tool = TodoWriteTool(manager)

        result = tool.execute(todos=[])

        assert result.success is True
        assert len(manager.get_todos()) == 0

    def test_execute_invalid_todos_not_list(self):
        """todos가 리스트가 아닌 경우."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        result = tool.execute(todos="not a list")

        assert result.success is False
        assert "must be a list" in result.error

    def test_execute_invalid_todo_not_dict(self):
        """Todo 항목이 dict가 아닌 경우."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        result = tool.execute(todos=["not a dict"])

        assert result.success is False
        assert "must be an object" in result.error

    def test_execute_missing_content(self):
        """content 필드가 없는 경우."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        result = tool.execute(todos=[{"status": "pending"}])

        assert result.success is False
        assert "missing 'content'" in result.error

    def test_execute_missing_status(self):
        """status 필드가 없는 경우."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        result = tool.execute(todos=[{"content": "Task 1"}])

        assert result.success is False
        assert "missing 'status'" in result.error

    def test_execute_invalid_status(self):
        """잘못된 status 값."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        result = tool.execute(todos=[{"content": "Task 1", "status": "unknown"}])

        assert result.success is False
        assert "invalid status" in result.error

    def test_execute_output_shows_summary(self):
        """출력에 요약 정보 포함."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        result = tool.execute(todos=[
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "in_progress"},
            {"content": "Task 3", "status": "pending"},
        ])

        assert "1/3 completed" in result.output
        assert "1 in progress" in result.output
        assert "1 pending" in result.output

    def test_to_anthropic_tool(self):
        """Anthropic API 형식 변환."""
        manager = TodoManager()
        tool = TodoWriteTool(manager)

        api_format = tool.to_anthropic_tool()

        assert api_format["name"] == "TodoWrite"
        assert "input_schema" in api_format
        assert api_format["input_schema"]["type"] == "object"
        assert "todos" in api_format["input_schema"]["properties"]

        todos_schema = api_format["input_schema"]["properties"]["todos"]
        assert todos_schema["type"] == "array"
        assert "items" in todos_schema


class TestTodoReadTool:
    """TodoReadTool 단위 테스트."""

    def test_name_and_description(self):
        """도구 이름과 설명."""
        manager = TodoManager()
        tool = TodoReadTool(manager)

        assert tool.name == "TodoRead"
        assert "Read the current todo list" in tool.description

    def test_execute_empty_list(self):
        """빈 목록 조회."""
        manager = TodoManager()
        tool = TodoReadTool(manager)

        result = tool.execute()

        assert result.success is True
        assert "No todos in the list" in result.output

    def test_execute_with_todos(self):
        """Todo가 있는 경우 조회."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "in_progress"},
            {"content": "Task 3", "status": "pending"},
        ])
        tool = TodoReadTool(manager)

        result = tool.execute()

        assert result.success is True
        assert "Task 1" in result.output
        assert "Task 2" in result.output
        assert "Task 3" in result.output

    def test_execute_shows_status_icons(self):
        """상태 아이콘 표시."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "Done", "status": "completed"},
            {"content": "Working", "status": "in_progress"},
            {"content": "Todo", "status": "pending"},
        ])
        tool = TodoReadTool(manager)

        result = tool.execute()

        # 아이콘 확인: ✓ (completed), → (in_progress), ○ (pending)
        assert "[✓]" in result.output
        assert "[→]" in result.output
        assert "[○]" in result.output

    def test_execute_shows_summary(self):
        """요약 정보 표시."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "pending"},
        ])
        tool = TodoReadTool(manager)

        result = tool.execute()

        assert "Total: 2" in result.output
        assert "Completed: 1" in result.output
        assert "Pending: 1" in result.output

    def test_execute_numbered_list(self):
        """번호가 매겨진 목록."""
        manager = TodoManager()
        manager.set_todos([
            {"content": "First", "status": "pending"},
            {"content": "Second", "status": "pending"},
        ])
        tool = TodoReadTool(manager)

        result = tool.execute()

        assert "1." in result.output
        assert "2." in result.output

    def test_parameters_empty(self):
        """파라미터가 없어야 함."""
        manager = TodoManager()
        tool = TodoReadTool(manager)

        assert tool.parameters == {}


class TestTodoToolsIntegration:
    """Todo 도구 통합 테스트."""

    def test_write_then_read(self):
        """TodoWrite 후 TodoRead로 확인."""
        manager = TodoManager()
        write_tool = TodoWriteTool(manager)
        read_tool = TodoReadTool(manager)

        # Write
        write_result = write_tool.execute(todos=[
            {"content": "Build project", "status": "in_progress"},
            {"content": "Run tests", "status": "pending"},
        ])
        assert write_result.success is True

        # Read
        read_result = read_tool.execute()
        assert read_result.success is True
        assert "Build project" in read_result.output
        assert "Run tests" in read_result.output

    def test_update_status_workflow(self):
        """상태 업데이트 워크플로우."""
        manager = TodoManager()
        write_tool = TodoWriteTool(manager)

        # Initial todos
        write_tool.execute(todos=[
            {"content": "Task 1", "status": "in_progress"},
            {"content": "Task 2", "status": "pending"},
        ])

        # Complete Task 1, start Task 2
        write_tool.execute(todos=[
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "in_progress"},
        ])

        summary = manager.get_summary()
        assert summary["completed"] == 1
        assert summary["in_progress"] == 1
        assert manager.get_current_task() == "Task 2"

    def test_shared_manager_between_tools(self):
        """Write와 Read가 같은 Manager를 공유."""
        manager = TodoManager()
        write_tool = TodoWriteTool(manager)
        read_tool = TodoReadTool(manager)

        write_tool.execute(todos=[{"content": "Shared task", "status": "pending"}])

        read_result = read_tool.execute()
        assert "Shared task" in read_result.output

    def test_clear_all_todos(self):
        """모든 Todo 삭제."""
        manager = TodoManager()
        write_tool = TodoWriteTool(manager)
        read_tool = TodoReadTool(manager)

        # Add some todos
        write_tool.execute(todos=[
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "pending"},
        ])

        # Clear by writing empty list
        write_tool.execute(todos=[])

        read_result = read_tool.execute()
        assert "No todos in the list" in read_result.output
