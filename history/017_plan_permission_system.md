# 2.3 권한 시스템 개선 계획

**작성일**: 2026-01-11
**우선순위**: 🟡 중간
**예상 작업량**: 중간

---

## 1. 현재 문제점

### 1.1 단순 y/n 승인

**현재 코드** (`approval.py:51-95`):
```python
def request(self, tool_name: str, details: str, diff: str | None = None) -> bool:
    # ...
    while True:
        response = input("   Approve? [y/n]: ").strip().lower()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
```

**문제**:
- 모든 도구에 대해 동일한 승인 프로세스
- 자동 승인/거부 규칙 설정 불가
- 경로 기반 권한 분리 없음

### 1.2 도구별 세분화 없음

**현재**: `get_approval_description()`이 있으면 모두 승인 필요
- 안전한 도구 (read, glob)도 구현에 따라 승인 요청 가능
- 위험한 도구 (bash, write)에 대한 차별화 없음

### 1.3 설정 파일 연동 없음

**현재**: 런타임에 `enabled=True/False`만 가능
- 설정 파일에서 규칙 로드 불가
- 프로젝트별 권한 정책 적용 불가

---

## 2. 개선 목표

1. **규칙 기반 권한 평가**: 도구/경로/액션별 규칙
2. **자동 승인/거부**: 규칙 매칭 시 사용자 입력 없이 처리
3. **설정 파일 연동**: config.json에서 규칙 로드
4. **하위 호환성**: 기존 ApprovalManager 인터페이스 유지

---

## 3. 상세 설계

### 3.1 Permission Enum

```python
# agent/permissions.py

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any
import fnmatch

class Permission(Enum):
    """권한 결정."""

    ALLOW = auto()   # 자동 승인
    DENY = auto()    # 자동 거부
    ASK = auto()     # 사용자에게 물어보기
```

### 3.2 PermissionRule 클래스

```python
@dataclass
class PermissionRule:
    """권한 규칙 정의."""

    # 매칭 조건
    tool_pattern: str = "*"           # "write", "bash", "read", "*"
    path_pattern: str | None = None   # "/tmp/*", "*.py", None (경로 무관)
    action_pattern: str | None = None # "delete", "execute", None

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

        # 경로 매칭 (있는 경우)
        if self.path_pattern:
            path = context.get("file_path") or context.get("path") or context.get("command")
            if not path:
                return False
            if not fnmatch.fnmatch(path, self.path_pattern):
                return False

        # 액션 매칭 (있는 경우)
        if self.action_pattern:
            action = context.get("action")
            if not action:
                return False
            if not fnmatch.fnmatch(action, self.action_pattern):
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """직렬화."""
        return {
            "tool_pattern": self.tool_pattern,
            "path_pattern": self.path_pattern,
            "action_pattern": self.action_pattern,
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
            action_pattern=data.get("action_pattern"),
            permission=permission,
            description=data.get("description", ""),
            priority=data.get("priority", 0),
        )
```

### 3.3 PermissionManager 클래스

```python
class PermissionManager:
    """규칙 기반 권한 관리자."""

    # 기본 규칙 (낮은 우선순위)
    DEFAULT_RULES = [
        # 읽기 도구는 항상 허용
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
        # 임시 디렉토리 쓰기는 허용
        PermissionRule(
            tool_pattern="write",
            path_pattern="/tmp/*",
            permission=Permission.ALLOW,
            description="Writing to /tmp is safe",
            priority=-50,
        ),
        # 기본: 물어보기
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
        self.enabled = enabled
        self.show_diff = show_diff
        self.rules: list[PermissionRule] = []

        # 기본 규칙 추가
        if use_default_rules:
            self.rules.extend(self.DEFAULT_RULES)

        # 사용자 규칙 추가
        if rules:
            self.rules.extend(rules)

        # 우선순위로 정렬 (높은 것 먼저)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

        # 이력
        self.history: list[tuple[str, Permission]] = []

        # Spinner 콜백
        self.pause_spinner: callable | None = None
        self.resume_spinner: callable | None = None

    def add_rule(self, rule: PermissionRule) -> None:
        """규칙 추가 후 재정렬."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, tool_name: str, context: dict[str, Any]) -> Permission:
        """규칙을 순서대로 평가하여 권한 결정."""
        for rule in self.rules:
            if rule.matches(tool_name, context):
                return rule.permission

        # 매칭 규칙 없음 (발생하면 안 됨, DEFAULT_RULES에 catch-all 있음)
        return Permission.ASK

    def check(
        self,
        tool_name: str,
        details: str,
        context: dict[str, Any],
        diff: str | None = None,
    ) -> bool:
        """권한 확인 (자동 결정 또는 사용자 질의)."""
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
        """사용자에게 승인 요청 (기존 ApprovalManager 로직)."""
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
```

### 3.4 ApprovalManager 호환 래퍼

```python
class ApprovalManager:
    """
    [Deprecated] 하위 호환성을 위한 래퍼.

    새 코드는 PermissionManager를 직접 사용하세요.
    """

    def __init__(self, enabled: bool = False, show_diff: bool = True):
        import warnings
        warnings.warn(
            "ApprovalManager is deprecated. Use PermissionManager instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._manager = PermissionManager(
            enabled=enabled,
            show_diff=show_diff,
        )

    @property
    def enabled(self) -> bool:
        return self._manager.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._manager.enabled = value

    @property
    def pause_spinner(self):
        return self._manager.pause_spinner

    @pause_spinner.setter
    def pause_spinner(self, value):
        self._manager.pause_spinner = value

    @property
    def resume_spinner(self):
        return self._manager.resume_spinner

    @resume_spinner.setter
    def resume_spinner(self, value):
        self._manager.resume_spinner = value

    def request(self, tool_name: str, details: str, diff: str | None = None) -> bool:
        """기존 인터페이스 호환."""
        # context 추출 시도 (details에서)
        context = {"details": details}
        return self._manager.check(tool_name, details, context, diff)

    def get_history(self) -> list[tuple[str, bool]]:
        """기존 형식으로 이력 반환."""
        return [
            (desc, perm == Permission.ALLOW)
            for desc, perm in self._manager.get_history()
        ]

    def clear_history(self) -> None:
        self._manager.clear_history()
```

---

## 4. 설정 파일 형식

### 4.1 config.json 예시

```json
{
  "approval_enabled": true,
  "show_diff": true,
  "permission_rules": [
    {
      "tool_pattern": "write",
      "path_pattern": "*.test.py",
      "permission": "allow",
      "description": "Allow writing test files",
      "priority": 10
    },
    {
      "tool_pattern": "bash",
      "path_pattern": "rm *",
      "permission": "deny",
      "description": "Never allow rm commands",
      "priority": 100
    },
    {
      "tool_pattern": "write",
      "path_pattern": "/home/user/safe/*",
      "permission": "allow",
      "description": "Safe directory",
      "priority": 5
    }
  ]
}
```

---

## 5. 파일 변경 계획

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `agent/permissions.py` | 신규 | Permission, PermissionRule, PermissionManager |
| `agent/approval.py` | 수정 | 호환 래퍼로 변경 (deprecated) |
| `agent/executor.py` | 수정 | PermissionManager 사용 |
| `agent/__init__.py` | 수정 | permissions 모듈 export |
| `config/defaults.py` | 수정 | 기본 권한 규칙 추가 |

---

## 6. ToolExecutor 수정

```python
# agent/executor.py

class ToolExecutor:
    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        permission_manager: PermissionManager | None = None,
        # 하위 호환
        approval_manager: ApprovalManager | None = None,
    ) -> None:
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}

        # 새 권한 매니저 우선
        if permission_manager:
            self.permission = permission_manager
        elif approval_manager:
            # 기존 ApprovalManager를 내부적으로 PermissionManager로 변환
            self.permission = approval_manager._manager
        else:
            self.permission = None

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        # ...

        if self.permission and self.permission.enabled:
            approval_desc = tool.get_approval_description(**tool_input)

            if approval_desc:
                # context 구성
                context = dict(tool_input)

                # diff 생성 (write 도구)
                diff = None
                if tool.name == "write" and hasattr(tool, "generate_diff"):
                    diff = tool.generate_diff(
                        tool_input.get("file_path", ""),
                        tool_input.get("content", ""),
                    )

                # 권한 확인
                if not self.permission.check(tool.name, approval_desc, context, diff):
                    return ToolResult(
                        success=False,
                        output="User denied permission.",
                        error=None,
                    )

        # 도구 실행...
```

---

## 7. 테스트 계획

```python
# tests/test_permissions.py

def test_permission_rule_matching():
    rule = PermissionRule(
        tool_pattern="write",
        path_pattern="*.py",
        permission=Permission.ALLOW,
    )

    assert rule.matches("write", {"file_path": "test.py"})
    assert not rule.matches("write", {"file_path": "test.txt"})
    assert not rule.matches("read", {"file_path": "test.py"})

def test_permission_manager_evaluation():
    manager = PermissionManager(enabled=True, use_default_rules=False)
    manager.add_rule(PermissionRule(
        tool_pattern="read",
        permission=Permission.ALLOW,
    ))
    manager.add_rule(PermissionRule(
        tool_pattern="*",
        permission=Permission.ASK,
    ))

    assert manager.evaluate("read", {}) == Permission.ALLOW
    assert manager.evaluate("write", {}) == Permission.ASK

def test_priority_ordering():
    manager = PermissionManager(enabled=True, use_default_rules=False)
    manager.add_rule(PermissionRule(
        tool_pattern="*",
        permission=Permission.ASK,
        priority=0,
    ))
    manager.add_rule(PermissionRule(
        tool_pattern="read",
        permission=Permission.ALLOW,
        priority=10,
    ))

    # 높은 우선순위가 먼저 평가됨
    assert manager.evaluate("read", {}) == Permission.ALLOW

def test_from_config():
    config = Config()
    config.set("permission_rules", [
        {"tool_pattern": "bash", "permission": "deny"}
    ])

    manager = PermissionManager.from_config(config)
    assert manager.evaluate("bash", {}) == Permission.DENY
```

---

## 8. 체크리스트

- [ ] `agent/permissions.py` 생성
  - [ ] Permission enum
  - [ ] PermissionRule dataclass
  - [ ] PermissionManager 클래스
- [ ] `agent/approval.py` 수정
  - [ ] deprecated 래퍼로 변경
- [ ] `agent/executor.py` 수정
  - [ ] PermissionManager 지원
  - [ ] 하위 호환성 유지
- [ ] `config/defaults.py` 수정
  - [ ] 기본 권한 규칙 추가
- [ ] `agent/__init__.py` 수정
- [ ] 테스트 작성
- [ ] 문서 업데이트
