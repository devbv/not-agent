"""
Permission System - 규칙 기반 권한 관리

도구 실행 전 자동 승인/거부/질의를 결정하는 시스템.
- Permission enum: ALLOW, DENY, ASK
- PermissionRule: 도구/경로/명령어 패턴 기반 규칙
- PermissionManager: 규칙 평가 및 사용자 질의
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable
import fnmatch

if TYPE_CHECKING:
    from not_agent.config import Config


class Permission(Enum):
    """권한 결정 타입."""

    ALLOW = auto()  # 자동 승인
    DENY = auto()   # 자동 거부
    ASK = auto()    # 사용자에게 물어보기


@dataclass
class PermissionRule:
    """권한 규칙 정의."""

    # 매칭 조건
    tool_pattern: str = "*"              # "write", "bash", "read", "*"
    path_pattern: str | None = None      # "/tmp/*", "*.test.py", None
    command_pattern: str | None = None   # "pytest*", "rm *", None

    # 결정
    permission: Permission = Permission.ASK

    # 메타데이터
    description: str = ""
    priority: int = 0  # 높을수록 먼저 평가

    def matches(self, tool_name: str, context: dict[str, Any]) -> bool:
        """규칙이 현재 요청에 매칭되는지 확인."""
        # 도구 이름 매칭
        if not fnmatch.fnmatch(tool_name, self.tool_pattern):
            return False

        # 경로 매칭 (파일 관련 도구)
        if self.path_pattern:
            path = context.get("file_path") or context.get("path")
            if not path:
                return False
            # 경로의 basename도 체크 (패턴이 파일명만 있을 때)
            if not fnmatch.fnmatch(path, self.path_pattern):
                # basename으로도 시도
                import os
                basename = os.path.basename(path)
                if not fnmatch.fnmatch(basename, self.path_pattern):
                    return False

        # 명령어 매칭 (bash 도구)
        if self.command_pattern:
            command = context.get("command")
            if not command:
                return False
            if not fnmatch.fnmatch(command, self.command_pattern):
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """직렬화."""
        return {
            "tool_pattern": self.tool_pattern,
            "path_pattern": self.path_pattern,
            "command_pattern": self.command_pattern,
            "permission": self.permission.name.lower(),
            "description": self.description,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PermissionRule":
        """딕셔너리에서 생성."""
        permission_str = data.get("permission", "ask").upper()
        permission = Permission[permission_str]

        return cls(
            tool_pattern=data.get("tool_pattern", "*"),
            path_pattern=data.get("path_pattern"),
            command_pattern=data.get("command_pattern"),
            permission=permission,
            description=data.get("description", ""),
            priority=data.get("priority", 0),
        )


class PermissionManager:
    """규칙 기반 권한 관리자."""

    # 코드 생성/테스트에 최적화된 기본 규칙
    DEFAULT_RULES = [
        # === 읽기 전용 도구: 항상 허용 ===
        PermissionRule(
            tool_pattern="read",
            permission=Permission.ALLOW,
            description="Reading files is safe",
            priority=-100,
        ),
        PermissionRule(
            tool_pattern="glob",
            permission=Permission.ALLOW,
            description="Finding files is safe",
            priority=-100,
        ),
        PermissionRule(
            tool_pattern="grep",
            permission=Permission.ALLOW,
            description="Searching files is safe",
            priority=-100,
        ),

        # === 테스트 관련: 자동 승인 ===
        PermissionRule(
            tool_pattern="write",
            path_pattern="*test*.py",
            permission=Permission.ALLOW,
            description="Writing test files",
            priority=10,
        ),
        PermissionRule(
            tool_pattern="write",
            path_pattern="tests/*",
            permission=Permission.ALLOW,
            description="Writing to tests directory",
            priority=10,
        ),
        PermissionRule(
            tool_pattern="bash",
            command_pattern="pytest*",
            permission=Permission.ALLOW,
            description="Running pytest",
            priority=10,
        ),
        PermissionRule(
            tool_pattern="bash",
            command_pattern="python -m pytest*",
            permission=Permission.ALLOW,
            description="Running pytest via python -m",
            priority=10,
        ),
        PermissionRule(
            tool_pattern="bash",
            command_pattern="python*pytest*",
            permission=Permission.ALLOW,
            description="Running pytest via python",
            priority=10,
        ),

        # === 린팅/타입체크: 자동 승인 ===
        PermissionRule(
            tool_pattern="bash",
            command_pattern="ruff *",
            permission=Permission.ALLOW,
            description="Running ruff linter",
            priority=10,
        ),
        PermissionRule(
            tool_pattern="bash",
            command_pattern="ruff check*",
            permission=Permission.ALLOW,
            description="Running ruff check",
            priority=10,
        ),
        PermissionRule(
            tool_pattern="bash",
            command_pattern="mypy *",
            permission=Permission.ALLOW,
            description="Running mypy type checker",
            priority=10,
        ),
        PermissionRule(
            tool_pattern="bash",
            command_pattern="black *",
            permission=Permission.ALLOW,
            description="Running black formatter",
            priority=10,
        ),

        # === 임시 디렉토리: 허용 ===
        PermissionRule(
            tool_pattern="write",
            path_pattern="/tmp/*",
            permission=Permission.ALLOW,
            description="Writing to /tmp is safe",
            priority=-50,
        ),

        # === 위험한 명령어: 거부 ===
        PermissionRule(
            tool_pattern="bash",
            command_pattern="rm -rf *",
            permission=Permission.DENY,
            description="Dangerous recursive delete",
            priority=100,
        ),
        PermissionRule(
            tool_pattern="bash",
            command_pattern="rm -r *",
            permission=Permission.DENY,
            description="Dangerous recursive delete",
            priority=100,
        ),

        # === 기본: 물어보기 ===
        PermissionRule(
            tool_pattern="*",
            permission=Permission.ASK,
            description="Default: ask user",
            priority=-1000,
        ),
    ]

    def __init__(
        self,
        enabled: bool = True,
        rules: list[PermissionRule] | None = None,
        use_default_rules: bool = True,
        show_diff: bool = True,
    ):
        """
        PermissionManager 초기화.

        Args:
            enabled: 권한 시스템 활성화 여부
            rules: 사용자 정의 규칙 목록
            use_default_rules: 기본 규칙 사용 여부
            show_diff: diff 표시 여부
        """
        self.enabled = enabled
        self.show_diff = show_diff
        self.rules: list[PermissionRule] = []

        if use_default_rules:
            self.rules.extend(self.DEFAULT_RULES)

        if rules:
            self.rules.extend(rules)

        # 우선순위로 정렬 (높은 것 먼저)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

        # 이력
        self.history: list[tuple[str, Permission]] = []

        # Spinner 콜백 (CLI에서 설정)
        self.pause_spinner: Callable[[], None] | None = None
        self.resume_spinner: Callable[[], None] | None = None

    def add_rule(self, rule: PermissionRule) -> None:
        """규칙 추가 후 재정렬."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, tool_name: str, context: dict[str, Any]) -> Permission:
        """규칙을 순서대로 평가하여 권한 결정."""
        for rule in self.rules:
            if rule.matches(tool_name, context):
                return rule.permission
        return Permission.ASK

    def check(
        self,
        tool_name: str,
        details: str,
        context: dict[str, Any],
        diff: str | None = None,
    ) -> bool:
        """
        권한 확인 (자동 결정 또는 사용자 질의).

        Args:
            tool_name: 도구 이름
            details: 승인 요청 설명
            context: 도구 입력 컨텍스트 (file_path, command 등)
            diff: 선택적 diff 문자열

        Returns:
            True: 승인, False: 거부
        """
        if not self.enabled:
            return True

        permission = self.evaluate(tool_name, context)

        if permission == Permission.ALLOW:
            self.history.append((f"{tool_name}: {details}", permission))
            return True

        if permission == Permission.DENY:
            self.history.append((f"{tool_name}: {details}", permission))
            return False

        # Permission.ASK: 사용자에게 물어보기
        return self._ask_user(tool_name, details, diff)

    def _ask_user(self, tool_name: str, details: str, diff: str | None) -> bool:
        """사용자에게 승인 요청."""
        if self.pause_spinner:
            self.pause_spinner()

        print(f"\n⚠️  Permission required: {tool_name}")
        print(f"   {details}")

        if self.show_diff and diff:
            print("\n   Changes:")
            print(self._format_diff(diff))
            print()

        try:
            while True:
                try:
                    response = input("   Approve? [y/n]: ").strip().lower()
                    if response in ["y", "yes"]:
                        self.history.append((f"{tool_name}: {details}", Permission.ALLOW))
                        return True
                    elif response in ["n", "no"]:
                        self.history.append((f"{tool_name}: {details}", Permission.DENY))
                        return False
                    else:
                        print("   Invalid input. Please enter 'y' or 'n'")
                except (EOFError, KeyboardInterrupt):
                    print("\n   Cancelled. Denying permission.")
                    self.history.append((f"{tool_name}: {details}", Permission.DENY))
                    return False
        finally:
            if self.resume_spinner:
                self.resume_spinner()

    def _format_diff(self, diff: str) -> str:
        """diff 포맷팅."""
        lines = []
        for line in diff.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                lines.append(f"  {line}")
            elif line.startswith("@@"):
                lines.append(f"  {line}")
            elif line.startswith("+"):
                lines.append(f"  + {line[1:]}")
            elif line.startswith("-"):
                lines.append(f"  - {line[1:]}")
            else:
                lines.append(f"    {line}")
        return "\n".join(lines)

    def get_history(self) -> list[tuple[str, Permission]]:
        """이력 반환."""
        return self.history.copy()

    def clear_history(self) -> None:
        """이력 초기화."""
        self.history.clear()

    @classmethod
    def from_config(cls, config: "Config") -> "PermissionManager":
        """설정에서 PermissionManager 생성."""
        enabled = config.get("approval_enabled", True)
        show_diff = config.get("show_diff", True)

        # 설정 파일에서 규칙 로드
        rules_data = config.get("permission_rules", [])
        rules = [PermissionRule.from_dict(r) for r in rules_data]

        return cls(
            enabled=enabled,
            rules=rules,
            show_diff=show_diff,
        )
