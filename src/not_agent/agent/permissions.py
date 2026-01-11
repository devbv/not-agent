"""
Permission System - Rule-based permission management.

A system for determining automatic approval/denial/prompting before tool execution.
- Permission enum: ALLOW, DENY, ASK
- PermissionRule: Rule based on tool/path/command patterns
- PermissionManager: Rule evaluation and user prompting
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable
import fnmatch

if TYPE_CHECKING:
    from not_agent.config import Config


class Permission(Enum):
    """Permission decision type."""

    ALLOW = auto()  # Auto approve
    DENY = auto()   # Auto deny
    ASK = auto()    # Ask user


@dataclass
class PermissionRule:
    """Permission rule definition."""

    # Matching conditions
    tool_pattern: str = "*"              # "write", "bash", "read", "*"
    path_pattern: str | None = None      # "/tmp/*", "*.test.py", None
    command_pattern: str | None = None   # "pytest*", "rm *", None

    # Decision
    permission: Permission = Permission.ASK

    # Metadata
    description: str = ""
    priority: int = 0  # Higher priority evaluated first

    def matches(self, tool_name: str, context: dict[str, Any]) -> bool:
        """Check if rule matches the current request."""
        # Tool name matching
        if not fnmatch.fnmatch(tool_name, self.tool_pattern):
            return False

        # Path matching (for file-related tools)
        if self.path_pattern:
            path = context.get("file_path") or context.get("path")
            if not path:
                return False
            # Also check path basename (when pattern is filename only)
            if not fnmatch.fnmatch(path, self.path_pattern):
                # Try with basename
                from pathlib import Path
                basename = Path(path).name
                if not fnmatch.fnmatch(basename, self.path_pattern):
                    return False

        # Command matching (for bash tool)
        if self.command_pattern:
            command = context.get("command")
            if not command:
                return False
            if not fnmatch.fnmatch(command, self.command_pattern):
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
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
        """Create from dictionary."""
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
    """Rule-based permission manager."""

    # Default rules optimized for code generation/testing
    DEFAULT_RULES = [
        # === Read-only tools: always allow ===
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

        # === Test-related: auto approve ===
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

        # === Linting/type checking: auto approve ===
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

        # === Temp directory: allow ===
        PermissionRule(
            tool_pattern="write",
            path_pattern="/tmp/*",
            permission=Permission.ALLOW,
            description="Writing to /tmp is safe",
            priority=-50,
        ),

        # === Dangerous commands: deny ===
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

        # === Default: ask user ===
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
        Initialize PermissionManager.

        Args:
            enabled: Whether permission system is enabled
            rules: Custom rule list
            use_default_rules: Whether to use default rules
            show_diff: Whether to show diff
        """
        self.enabled = enabled
        self.show_diff = show_diff
        self.rules: list[PermissionRule] = []

        if use_default_rules:
            self.rules.extend(self.DEFAULT_RULES)

        if rules:
            self.rules.extend(rules)

        # Sort by priority (higher first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

        # History
        self.history: list[tuple[str, Permission]] = []

        # Spinner callbacks (set by CLI)
        self.pause_spinner: Callable[[], None] | None = None
        self.resume_spinner: Callable[[], None] | None = None

    def add_rule(self, rule: PermissionRule) -> None:
        """Add rule and re-sort."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, tool_name: str, context: dict[str, Any]) -> Permission:
        """Evaluate rules in order to determine permission."""
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
        Check permission (auto-decide or prompt user).

        Args:
            tool_name: Tool name
            details: Approval request description
            context: Tool input context (file_path, command, etc.)
            diff: Optional diff string

        Returns:
            True: approved, False: denied
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

        # Permission.ASK: prompt user
        return self._ask_user(tool_name, details, diff)

    def _ask_user(self, tool_name: str, details: str, diff: str | None) -> bool:
        """Request approval from user."""
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
        """Format diff for display."""
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
        """Return history."""
        return self.history.copy()

    def clear_history(self) -> None:
        """Clear history."""
        self.history.clear()

    @classmethod
    def from_config(cls, config: "Config") -> "PermissionManager":
        """Create PermissionManager from config."""
        enabled = config.get("approval_enabled", True)
        show_diff = config.get("show_diff", True)

        # Load rules from config file
        rules_data = config.get("permission_rules", [])
        rules = [PermissionRule.from_dict(r) for r in rules_data]

        return cls(
            enabled=enabled,
            rules=rules,
            show_diff=show_diff,
        )
