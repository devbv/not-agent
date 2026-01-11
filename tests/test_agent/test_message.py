"""Tests for message parts and session."""

import pytest

from not_agent.agent.message import (
    MessagePart,
    TextPart,
    ToolUsePart,
    ToolResultPart,
    part_from_dict,
    part_from_anthropic,
    parts_from_content,
    register_part_type,
)
from not_agent.agent.session import Message, Session


class TestTextPart:
    """TextPart 테스트."""

    def test_creation(self):
        part = TextPart(text="hello")
        assert part.text == "hello"
        assert part.part_type == "text"

    def test_to_api_format(self):
        part = TextPart(text="hello world")
        api = part.to_api_format()
        assert api == {"type": "text", "text": "hello world"}

    def test_to_dict(self):
        part = TextPart(text="test")
        d = part.to_dict()
        assert d == {"part_type": "text", "text": "test"}

    def test_from_dict(self):
        data = {"part_type": "text", "text": "restored"}
        part = TextPart.from_dict(data)
        assert part.text == "restored"


class TestToolUsePart:
    """ToolUsePart 테스트."""

    def test_creation(self):
        part = ToolUsePart(
            tool_id="123",
            tool_name="read",
            tool_input={"file_path": "/tmp/test.txt"},
        )
        assert part.tool_id == "123"
        assert part.tool_name == "read"
        assert part.tool_input == {"file_path": "/tmp/test.txt"}
        assert part.part_type == "tool_use"

    def test_to_api_format(self):
        part = ToolUsePart(
            tool_id="abc",
            tool_name="write",
            tool_input={"content": "hello"},
        )
        api = part.to_api_format()
        assert api == {
            "type": "tool_use",
            "id": "abc",
            "name": "write",
            "input": {"content": "hello"},
        }

    def test_to_dict(self):
        part = ToolUsePart(
            tool_id="xyz",
            tool_name="bash",
            tool_input={"command": "ls"},
        )
        d = part.to_dict()
        assert d["part_type"] == "tool_use"
        assert d["tool_id"] == "xyz"
        assert d["tool_name"] == "bash"

    def test_from_dict(self):
        data = {
            "part_type": "tool_use",
            "tool_id": "id1",
            "tool_name": "glob",
            "tool_input": {"pattern": "*.py"},
        }
        part = ToolUsePart.from_dict(data)
        assert part.tool_id == "id1"
        assert part.tool_name == "glob"


class TestToolResultPart:
    """ToolResultPart 테스트."""

    def test_creation(self):
        part = ToolResultPart(
            tool_use_id="123",
            content="file content",
            is_error=False,
        )
        assert part.tool_use_id == "123"
        assert part.content == "file content"
        assert part.is_error is False
        assert part.part_type == "tool_result"

    def test_to_api_format_success(self):
        part = ToolResultPart(tool_use_id="abc", content="result")
        api = part.to_api_format()
        assert api == {
            "type": "tool_result",
            "tool_use_id": "abc",
            "content": "result",
        }
        assert "is_error" not in api

    def test_to_api_format_error(self):
        part = ToolResultPart(tool_use_id="abc", content="error msg", is_error=True)
        api = part.to_api_format()
        assert api["is_error"] is True

    def test_from_dict(self):
        data = {
            "part_type": "tool_result",
            "tool_use_id": "id1",
            "content": "output",
            "is_error": False,
        }
        part = ToolResultPart.from_dict(data)
        assert part.tool_use_id == "id1"


class TestPartFromDict:
    """part_from_dict 팩토리 테스트."""

    def test_text_part(self):
        data = {"part_type": "text", "text": "hello"}
        part = part_from_dict(data)
        assert isinstance(part, TextPart)
        assert part.text == "hello"

    def test_tool_use_part(self):
        data = {
            "part_type": "tool_use",
            "tool_id": "123",
            "tool_name": "read",
            "tool_input": {},
        }
        part = part_from_dict(data)
        assert isinstance(part, ToolUsePart)

    def test_tool_result_part(self):
        data = {
            "part_type": "tool_result",
            "tool_use_id": "123",
            "content": "result",
        }
        part = part_from_dict(data)
        assert isinstance(part, ToolResultPart)

    def test_unknown_type(self):
        data = {"part_type": "unknown", "data": "something"}
        with pytest.raises(ValueError, match="Unknown part type"):
            part_from_dict(data)


class TestPartFromAnthropic:
    """part_from_anthropic 변환 테스트."""

    def test_dict_text(self):
        block = {"type": "text", "text": "hello"}
        part = part_from_anthropic(block)
        assert isinstance(part, TextPart)
        assert part.text == "hello"

    def test_dict_tool_use(self):
        block = {
            "type": "tool_use",
            "id": "123",
            "name": "read",
            "input": {"path": "/tmp"},
        }
        part = part_from_anthropic(block)
        assert isinstance(part, ToolUsePart)
        assert part.tool_id == "123"

    def test_dict_tool_result(self):
        block = {
            "type": "tool_result",
            "tool_use_id": "123",
            "content": "result",
        }
        part = part_from_anthropic(block)
        assert isinstance(part, ToolResultPart)

    def test_invalid_block(self):
        with pytest.raises(ValueError, match="Cannot convert"):
            part_from_anthropic("invalid")


class TestPartsFromContent:
    """parts_from_content 변환 테스트."""

    def test_string_content(self):
        parts = parts_from_content("hello world")
        assert len(parts) == 1
        assert isinstance(parts[0], TextPart)
        assert parts[0].text == "hello world"

    def test_list_content(self):
        content = [
            {"type": "text", "text": "msg1"},
            {"type": "text", "text": "msg2"},
        ]
        parts = parts_from_content(content)
        assert len(parts) == 2


class TestMessage:
    """Message 클래스 테스트."""

    def test_add_part(self):
        msg = Message(role="user", parts=[])
        msg.add_part(TextPart(text="hello"))
        assert len(msg.parts) == 1

    def test_get_parts_by_type(self):
        msg = Message(
            role="assistant",
            parts=[
                TextPart(text="hi"),
                ToolUsePart(tool_id="1", tool_name="read", tool_input={}),
                TextPart(text="bye"),
            ],
        )
        text_parts = msg.get_parts_by_type(TextPart)
        assert len(text_parts) == 2

        tool_parts = msg.get_parts_by_type(ToolUsePart)
        assert len(tool_parts) == 1

    def test_get_text_content(self):
        msg = Message(
            role="user",
            parts=[
                TextPart(text="hello"),
                TextPart(text="world"),
            ],
        )
        assert msg.get_text_content() == "hello\nworld"

    def test_get_tool_uses(self):
        msg = Message(
            role="assistant",
            parts=[
                TextPart(text="Let me help"),
                ToolUsePart(tool_id="1", tool_name="read", tool_input={}),
                ToolUsePart(tool_id="2", tool_name="write", tool_input={}),
            ],
        )
        tool_uses = msg.get_tool_uses()
        assert len(tool_uses) == 2
        assert tool_uses[0].tool_name == "read"
        assert tool_uses[1].tool_name == "write"

    def test_to_api_format(self):
        msg = Message(
            role="user",
            parts=[TextPart(text="hello")],
        )
        api = msg.to_api_format()
        assert api == {
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
        }

    def test_to_dict_and_from_dict(self):
        msg = Message(
            role="assistant",
            parts=[
                TextPart(text="response"),
                ToolUsePart(tool_id="1", tool_name="read", tool_input={"p": "v"}),
            ],
        )

        # 직렬화
        data = msg.to_dict()
        assert data["role"] == "assistant"
        assert len(data["parts"]) == 2

        # 역직렬화
        restored = Message.from_dict(data)
        assert restored.role == "assistant"
        assert len(restored.parts) == 2
        assert isinstance(restored.parts[0], TextPart)
        assert isinstance(restored.parts[1], ToolUsePart)

    def test_content_property_backward_compat(self):
        """content 프로퍼티 하위 호환성 테스트."""
        msg = Message(
            role="user",
            parts=[TextPart(text="test")],
        )
        content = msg.content
        assert content == [{"type": "text", "text": "test"}]


class TestSession:
    """Session 클래스 테스트."""

    def test_add_user_message_string(self):
        session = Session()
        msg = session.add_user_message("hello")
        assert len(session) == 1
        assert msg.role == "user"
        assert msg.get_text_content() == "hello"

    def test_add_user_message_parts(self):
        session = Session()
        parts = [TextPart(text="part1"), TextPart(text="part2")]
        msg = session.add_user_message(parts)
        assert len(msg.parts) == 2

    def test_add_assistant_message(self):
        session = Session()
        content = [
            {"type": "text", "text": "assistant response"},
        ]
        msg = session.add_assistant_message(content)
        assert msg.role == "assistant"
        assert isinstance(msg.parts[0], TextPart)

    def test_add_tool_results(self):
        session = Session()
        results = [
            {"tool_use_id": "123", "content": "result1"},
            {"tool_use_id": "456", "content": "result2", "is_error": True},
        ]
        msg = session.add_tool_results(results)
        assert msg.role == "user"
        assert len(msg.parts) == 2
        assert isinstance(msg.parts[0], ToolResultPart)
        assert msg.parts[1].is_error is True

    def test_to_api_format(self):
        session = Session()
        session.add_user_message("hello")
        api = session.to_api_format()
        assert len(api) == 1
        assert api[0]["role"] == "user"
        assert api[0]["content"][0]["type"] == "text"

    def test_to_dict_and_from_dict(self):
        session = Session()
        session.add_user_message("hello")
        session.add_assistant_message([{"type": "text", "text": "hi"}])

        # 직렬화
        data = session.to_dict()
        assert data["id"] == session.id
        assert len(data["messages"]) == 2

        # 역직렬화
        restored = Session.from_dict(data)
        assert restored.id == session.id
        assert len(restored) == 2
        assert restored.messages[0].get_text_content() == "hello"

    def test_set_messages_backward_compat(self):
        """set_messages 하위 호환성 테스트."""
        session = Session()
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "q"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "a"}]},
        ]
        session.set_messages(messages)
        assert len(session) == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"

    def test_set_messages_string_content(self):
        """문자열 content 처리 테스트."""
        session = Session()
        messages = [
            {"role": "user", "content": "simple string"},
        ]
        session.set_messages(messages)
        assert len(session) == 1
        assert session.messages[0].get_text_content() == "simple string"

    def test_get_messages_backward_compat(self):
        """get_messages 하위 호환성 테스트."""
        session = Session()
        session.add_user_message("test")
        messages = session.get_messages()
        assert messages == session.to_api_format()

    def test_clear(self):
        session = Session()
        old_id = session.id
        session.add_user_message("test")
        session.clear()
        assert len(session) == 0
        assert session.id != old_id
