# Phase 4.2.4: 권한 시스템 개선 계획

**작성일**: 2026-01-11
**업데이트**: 2026-01-11 (현재 코드 상태 반영)
**우선순위**: 🔴 높음 (코드 생성/테스트 Phase 선행 조건)
**상태**: 📋 구현 예정

---

## 1. 현재 문제점

### 1.1 단순 y/n 승인만 지원

**현재 코드** (`approval.py`):
```python
class ApprovalManager:
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
- **코드 생성/테스트 시 반복적인 승인 요청으로 비효율적**

### 1.2 도구별 세분화 없음

- 안전한 도구 (read, glob, grep)도 승인 요청 가능
- 위험한 도구 (bash, write)에 대한 차별화 없음
- 테스트 파일 생성 시에도 매번 승인 필요

### 1.3 설정 파일 연동 없음

**현재 `defaults.py`**:
```python
DEFAULT_CONFIG = {
    # ...
    "approval_enabled": True,  # 전체 on/off만 가능
    # ...
}
```

- 세부 규칙 설정 불가
- 프로젝트별 권한 정책 적용 불가

---

## 2. 개선 목표

1. **규칙 기반 권한 평가**: 도구/경로/패턴별 규칙
2. **자동 승인/거부**: 규칙 매칭 시 사용자 입력 없이 처리
3. **설정 파일 연동**: config에서 규칙 로드
4. **하위 호환성**: 기존 ApprovalManager 인터페이스 유지
5. **코드 생성/테스트 최적화**: 테스트 파일, pytest 실행 등 자동 승인

---

## 3. 상세 설계

### 3.1 Permission Enum

```python
# agent/permissions.py

from enum import Enum, auto

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
    path_pattern: str | None = None   # "/tmp/*", "*.test.py", None
    command_pattern: str | None = None # "pytest*", "rm *", None

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
            if not path or not fnmatch.fnmatch(path, self.path_pattern):
                return False

        # 명령어 매칭 (bash 도구)
        if self.command_pattern:
            command = context.get("command")
            if not command or not fnmatch.fnmatch(command, self.command_pattern):
                return False

        return True
```

### 3.3 PermissionManager 클래스

```python
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
            priority=-100,
        ),
        PermissionRule(
            tool_pattern="grep",
            permission=Permission.ALLOW,
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
        self.enabled = enabled
        self.show_diff = show_diff
        self.rules: list[PermissionRule] = []

        if use_default_rules:
            self.rules.extend(self.DEFAULT_RULES)

        if rules:
            self.rules.extend(rules)

        # 우선순위로 정렬 (높은 것 먼저)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

        self.history: list[tuple[str, Permission]] = []
        self.pause_spinner: callable | None = None
        self.resume_spinner: callable | None = None

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

        # Permission.ASK
        return self._ask_user(tool_name, details, diff)

    @classmethod
    def from_config(cls, config: "Config") -> "PermissionManager":
        """설정에서 PermissionManager 생성."""
        enabled = config.get("approval_enabled", True)
        show_diff = config.get("show_diff", True)
        rules_data = config.get("permission_rules", [])
        rules = [PermissionRule.from_dict(r) for r in rules_data]

        return cls(enabled=enabled, rules=rules, show_diff=show_diff)
```

### 3.4 ApprovalManager 호환 래퍼

기존 코드와의 호환성을 위해 `ApprovalManager`를 유지하되, 내부적으로 `PermissionManager`를 사용합니다.

```python
# agent/approval.py (수정)

class ApprovalManager:
    """
    하위 호환성을 위한 래퍼.
    내부적으로 PermissionManager를 사용.
    """

    def __init__(self, enabled: bool = False, show_diff: bool = True):
        from .permissions import PermissionManager
        self._manager = PermissionManager(enabled=enabled, show_diff=show_diff)

    @property
    def enabled(self) -> bool:
        return self._manager.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._manager.enabled = value

    # ... 기존 인터페이스 유지 ...

    def request(self, tool_name: str, details: str, diff: str | None = None) -> bool:
        """기존 인터페이스 호환."""
        context = {"details": details}
        return self._manager.check(tool_name, details, context, diff)
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
      "path_pattern": "src/*.py",
      "permission": "allow",
      "description": "Allow writing source files",
      "priority": 20
    },
    {
      "tool_pattern": "bash",
      "command_pattern": "npm test*",
      "permission": "allow",
      "description": "Allow npm test",
      "priority": 10
    },
    {
      "tool_pattern": "bash",
      "command_pattern": "rm *",
      "permission": "deny",
      "description": "Block rm commands",
      "priority": 100
    }
  ]
}
```

---

## 5. 파일 변경 계획

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `agent/permissions.py` | **신규** | Permission, PermissionRule, PermissionManager |
| `agent/approval.py` | 수정 | PermissionManager 래퍼로 변경 |
| `agent/executor.py` | 수정 | PermissionManager 직접 지원, context 전달 |
| `agent/__init__.py` | 수정 | permissions 모듈 export 추가 |
| `config/defaults.py` | 수정 | permission_rules 기본값 추가 |

---

## 6. ToolExecutor 수정

```python
# agent/executor.py

class ToolExecutor:
    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        permission_manager: "PermissionManager | None" = None,
        approval_manager: "ApprovalManager | None" = None,  # 하위 호환
    ) -> None:
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}

        # PermissionManager 우선
        if permission_manager:
            self.permission = permission_manager
        elif approval_manager:
            self.permission = approval_manager._manager
        else:
            self.permission = None

    def _execute_sync(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        # ...

        if self.permission and self.permission.enabled:
            approval_desc = tool.get_approval_description(**tool_input)

            if approval_desc:
                # context 구성 (도구 입력 전체)
                context = dict(tool_input)

                # diff 생성
                diff = None
                if tool.name == "write" and hasattr(tool, "generate_diff"):
                    diff = tool.generate_diff(
                        tool_input.get("file_path", ""),
                        tool_input.get("content", ""),
                    )

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

def test_permission_rule_tool_matching():
    """도구 이름 매칭 테스트."""
    rule = PermissionRule(tool_pattern="write", permission=Permission.ALLOW)

    assert rule.matches("write", {})
    assert not rule.matches("read", {})

def test_permission_rule_path_matching():
    """경로 패턴 매칭 테스트."""
    rule = PermissionRule(
        tool_pattern="write",
        path_pattern="*.test.py",
        permission=Permission.ALLOW,
    )

    assert rule.matches("write", {"file_path": "test_example.test.py"})
    assert not rule.matches("write", {"file_path": "example.py"})

def test_permission_rule_command_matching():
    """명령어 패턴 매칭 테스트."""
    rule = PermissionRule(
        tool_pattern="bash",
        command_pattern="pytest*",
        permission=Permission.ALLOW,
    )

    assert rule.matches("bash", {"command": "pytest tests/"})
    assert not rule.matches("bash", {"command": "rm -rf /"})

def test_permission_manager_priority():
    """우선순위 테스트."""
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

    assert manager.evaluate("read", {}) == Permission.ALLOW
    assert manager.evaluate("write", {}) == Permission.ASK

def test_default_rules_for_testing():
    """테스트 관련 기본 규칙 테스트."""
    manager = PermissionManager(enabled=True)

    # 테스트 파일 쓰기: 허용
    assert manager.evaluate("write", {"file_path": "test_example.py"}) == Permission.ALLOW

    # pytest 실행: 허용
    assert manager.evaluate("bash", {"command": "pytest tests/"}) == Permission.ALLOW

    # 일반 파일 쓰기: ASK
    assert manager.evaluate("write", {"file_path": "main.py"}) == Permission.ASK

def test_from_config():
    """설정 파일 로드 테스트."""
    config = Config()
    config.set("permission_rules", [
        {"tool_pattern": "bash", "command_pattern": "npm*", "permission": "allow"}
    ])

    manager = PermissionManager.from_config(config)
    assert manager.evaluate("bash", {"command": "npm test"}) == Permission.ALLOW
```

---

## 8. 구현 순서

1. `agent/permissions.py` 생성
   - Permission enum
   - PermissionRule dataclass
   - PermissionManager 클래스

2. `agent/approval.py` 수정
   - PermissionManager 래퍼로 변경
   - 기존 인터페이스 유지

3. `agent/executor.py` 수정
   - PermissionManager 직접 지원
   - context 전달 로직 추가

4. `agent/__init__.py` 수정
   - permissions 모듈 export

5. `config/defaults.py` 수정
   - show_diff 기본값 추가

6. 테스트 작성

7. 문서 업데이트

---

## 9. 체크리스트

- [ ] `agent/permissions.py` 생성
  - [ ] Permission enum
  - [ ] PermissionRule dataclass (matches, to_dict, from_dict)
  - [ ] PermissionManager 클래스
  - [ ] DEFAULT_RULES (테스트/린팅 최적화)
- [ ] `agent/approval.py` 수정
  - [ ] PermissionManager 래퍼로 변경
  - [ ] 기존 인터페이스 유지
- [ ] `agent/executor.py` 수정
  - [ ] PermissionManager 직접 지원
  - [ ] context 전달
- [ ] `agent/__init__.py` 수정
- [ ] `config/defaults.py` 수정
- [ ] 테스트 작성 (`tests/test_permissions.py`)
- [ ] 기존 테스트 통과 확인
- [ ] 수동 테스트 (agent 모드에서 확인)

---

## 10. 예상 효과

| 시나리오 | 현재 | 개선 후 |
|---------|------|--------|
| 테스트 파일 생성 | 매번 y/n | 자동 승인 |
| pytest 실행 | 매번 y/n | 자동 승인 |
| ruff/mypy 실행 | 매번 y/n | 자동 승인 |
| 일반 코드 수정 | y/n | y/n (유지) |
| rm -rf 명령 | y/n | 자동 거부 |
| /tmp 파일 쓰기 | y/n | 자동 승인 |

**코드 생성/테스트 워크플로우가 크게 개선됩니다.**
