"""Permission System Tests."""

import pytest

from not_agent.agent.permissions import (
    Permission,
    PermissionRule,
    PermissionManager,
)
from not_agent.config import Config


class TestPermissionRule:
    """PermissionRule 테스트."""

    def test_tool_pattern_matching(self):
        """도구 이름 패턴 매칭."""
        rule = PermissionRule(tool_pattern="write", permission=Permission.ALLOW)

        assert rule.matches("write", {})
        assert not rule.matches("read", {})
        assert not rule.matches("edit", {})

    def test_tool_pattern_wildcard(self):
        """와일드카드 패턴 매칭."""
        rule = PermissionRule(tool_pattern="*", permission=Permission.ASK)

        assert rule.matches("write", {})
        assert rule.matches("read", {})
        assert rule.matches("bash", {})

    def test_tool_pattern_prefix(self):
        """접두사 패턴 매칭."""
        rule = PermissionRule(tool_pattern="web_*", permission=Permission.ALLOW)

        assert rule.matches("web_search", {})
        assert rule.matches("web_fetch", {})
        assert not rule.matches("read", {})

    def test_path_pattern_matching(self):
        """경로 패턴 매칭."""
        rule = PermissionRule(
            tool_pattern="write",
            path_pattern="*.py",
            permission=Permission.ALLOW,
        )

        assert rule.matches("write", {"file_path": "test.py"})
        assert rule.matches("write", {"file_path": "/home/user/test.py"})
        assert not rule.matches("write", {"file_path": "test.txt"})
        assert not rule.matches("write", {})  # 경로 없으면 매칭 안됨

    def test_path_pattern_directory(self):
        """디렉토리 패턴 매칭."""
        rule = PermissionRule(
            tool_pattern="write",
            path_pattern="tests/*",
            permission=Permission.ALLOW,
        )

        assert rule.matches("write", {"file_path": "tests/test_example.py"})
        assert rule.matches("write", {"file_path": "tests/unit/test_foo.py"})
        assert not rule.matches("write", {"file_path": "src/main.py"})

    def test_path_pattern_test_files(self):
        """테스트 파일 패턴 매칭."""
        rule = PermissionRule(
            tool_pattern="write",
            path_pattern="*test*.py",
            permission=Permission.ALLOW,
        )

        assert rule.matches("write", {"file_path": "test_example.py"})
        assert rule.matches("write", {"file_path": "example_test.py"})
        assert rule.matches("write", {"file_path": "/path/to/test_foo.py"})
        assert not rule.matches("write", {"file_path": "example.py"})

    def test_command_pattern_matching(self):
        """명령어 패턴 매칭."""
        rule = PermissionRule(
            tool_pattern="bash",
            command_pattern="pytest*",
            permission=Permission.ALLOW,
        )

        assert rule.matches("bash", {"command": "pytest"})
        assert rule.matches("bash", {"command": "pytest tests/"})
        assert rule.matches("bash", {"command": "pytest -v tests/"})
        assert not rule.matches("bash", {"command": "python test.py"})
        assert not rule.matches("bash", {})  # 명령어 없으면 매칭 안됨

    def test_command_pattern_rm(self):
        """rm 명령어 패턴 매칭."""
        rule = PermissionRule(
            tool_pattern="bash",
            command_pattern="rm -rf *",
            permission=Permission.DENY,
        )

        assert rule.matches("bash", {"command": "rm -rf /"})
        assert rule.matches("bash", {"command": "rm -rf /tmp/test"})
        assert not rule.matches("bash", {"command": "rm file.txt"})
        assert not rule.matches("bash", {"command": "ls -la"})

    def test_to_dict_and_from_dict(self):
        """직렬화/역직렬화."""
        rule = PermissionRule(
            tool_pattern="write",
            path_pattern="*.py",
            command_pattern=None,
            permission=Permission.ALLOW,
            description="Allow Python files",
            priority=10,
        )

        data = rule.to_dict()
        restored = PermissionRule.from_dict(data)

        assert restored.tool_pattern == rule.tool_pattern
        assert restored.path_pattern == rule.path_pattern
        assert restored.permission == rule.permission
        assert restored.description == rule.description
        assert restored.priority == rule.priority


class TestPermissionManager:
    """PermissionManager 테스트."""

    def test_evaluate_with_default_rules(self):
        """기본 규칙으로 평가."""
        manager = PermissionManager(enabled=True)

        # 읽기 도구는 항상 허용
        assert manager.evaluate("read", {}) == Permission.ALLOW
        assert manager.evaluate("glob", {}) == Permission.ALLOW
        assert manager.evaluate("grep", {}) == Permission.ALLOW

        # 일반 쓰기는 ASK
        assert manager.evaluate("write", {"file_path": "main.py"}) == Permission.ASK

    def test_evaluate_test_files(self):
        """테스트 파일 쓰기 평가."""
        manager = PermissionManager(enabled=True)

        # 테스트 파일은 자동 승인
        assert manager.evaluate("write", {"file_path": "test_example.py"}) == Permission.ALLOW
        assert manager.evaluate("write", {"file_path": "tests/test_foo.py"}) == Permission.ALLOW

    def test_evaluate_pytest_commands(self):
        """pytest 명령어 평가."""
        manager = PermissionManager(enabled=True)

        # pytest는 자동 승인
        assert manager.evaluate("bash", {"command": "pytest"}) == Permission.ALLOW
        assert manager.evaluate("bash", {"command": "pytest tests/"}) == Permission.ALLOW
        assert manager.evaluate("bash", {"command": "python -m pytest"}) == Permission.ALLOW

    def test_evaluate_dangerous_commands(self):
        """위험한 명령어 평가."""
        manager = PermissionManager(enabled=True)

        # rm -rf는 자동 거부
        assert manager.evaluate("bash", {"command": "rm -rf /"}) == Permission.DENY
        assert manager.evaluate("bash", {"command": "rm -r /tmp"}) == Permission.DENY

    def test_evaluate_tmp_directory(self):
        """/tmp 디렉토리 쓰기 평가."""
        manager = PermissionManager(enabled=True)

        # /tmp는 자동 승인
        assert manager.evaluate("write", {"file_path": "/tmp/test.txt"}) == Permission.ALLOW

    def test_priority_ordering(self):
        """우선순위 정렬 테스트."""
        manager = PermissionManager(enabled=True, use_default_rules=False)

        # 낮은 우선순위 규칙 먼저 추가
        manager.add_rule(PermissionRule(
            tool_pattern="*",
            permission=Permission.ASK,
            priority=0,
        ))
        # 높은 우선순위 규칙 나중에 추가
        manager.add_rule(PermissionRule(
            tool_pattern="read",
            permission=Permission.ALLOW,
            priority=10,
        ))

        # 높은 우선순위가 먼저 평가됨
        assert manager.evaluate("read", {}) == Permission.ALLOW
        assert manager.evaluate("write", {}) == Permission.ASK

    def test_custom_rules(self):
        """사용자 정의 규칙 테스트."""
        custom_rules = [
            PermissionRule(
                tool_pattern="write",
                path_pattern="src/*.py",
                permission=Permission.ALLOW,
                priority=20,
            ),
        ]

        manager = PermissionManager(enabled=True, rules=custom_rules)

        # 사용자 규칙이 적용됨
        assert manager.evaluate("write", {"file_path": "src/main.py"}) == Permission.ALLOW
        # 기본 규칙도 동작
        assert manager.evaluate("read", {}) == Permission.ALLOW

    def test_check_disabled(self):
        """비활성화 시 항상 허용."""
        manager = PermissionManager(enabled=False)

        # 비활성화 시 모두 True
        assert manager.check("write", "test", {"file_path": "main.py"}) is True
        assert manager.check("bash", "test", {"command": "rm -rf /"}) is True

    def test_check_auto_allow(self):
        """자동 승인 테스트."""
        manager = PermissionManager(enabled=True)

        # read는 자동 승인
        assert manager.check("read", "Reading file.txt", {}) is True

        # 이력 확인
        history = manager.get_history()
        assert len(history) == 1
        assert history[0][1] == Permission.ALLOW

    def test_check_auto_deny(self):
        """자동 거부 테스트."""
        manager = PermissionManager(enabled=True)

        # rm -rf는 자동 거부
        assert manager.check("bash", "rm -rf /", {"command": "rm -rf /"}) is False

        # 이력 확인
        history = manager.get_history()
        assert len(history) == 1
        assert history[0][1] == Permission.DENY

    def test_from_config(self):
        """설정에서 생성 테스트."""
        config = Config()
        config.set("approval_enabled", True)
        config.set("show_diff", False)
        config.set("permission_rules", [
            {"tool_pattern": "bash", "command_pattern": "npm*", "permission": "allow", "priority": 15}
        ])

        manager = PermissionManager.from_config(config)

        assert manager.enabled is True
        assert manager.show_diff is False
        assert manager.evaluate("bash", {"command": "npm test"}) == Permission.ALLOW

    def test_history(self):
        """이력 관리 테스트."""
        manager = PermissionManager(enabled=True)

        manager.check("read", "Reading file1.txt", {})
        manager.check("glob", "Finding files", {})

        history = manager.get_history()
        assert len(history) == 2

        manager.clear_history()
        assert len(manager.get_history()) == 0


class TestApprovalManagerCompatibility:
    """ApprovalManager 호환성 테스트."""

    def test_basic_usage(self):
        """기본 사용법 테스트."""
        from not_agent.agent.approval import ApprovalManager

        manager = ApprovalManager(enabled=False)

        # 비활성화 시 항상 True
        assert manager.request("write", "Writing file.txt") is True

    def test_property_access(self):
        """속성 접근 테스트."""
        from not_agent.agent.approval import ApprovalManager

        manager = ApprovalManager(enabled=True, show_diff=False)

        assert manager.enabled is True
        assert manager.show_diff is False

        manager.enabled = False
        assert manager.enabled is False

    def test_history_format(self):
        """이력 형식 테스트 (bool 반환)."""
        from not_agent.agent.approval import ApprovalManager

        manager = ApprovalManager(enabled=True)

        # 내부 PermissionManager를 통해 자동 승인되는 케이스
        manager._manager.check("read", "Reading", {})

        history = manager.get_history()
        assert len(history) == 1
        assert isinstance(history[0][1], bool)  # bool 형식
        assert history[0][1] is True
