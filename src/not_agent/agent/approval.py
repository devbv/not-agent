"""
Approval Manager Plugin

Tool 실행 전 사용자 승인을 받는 플러그인.
- Tool이 아님 (LLM이 호출하지 않음)
- Executor에 주입되어 모든 Tool 실행 전 실행됨
- Tool이 제공한 설명을 기반으로 y/n 확인
- diff 표시 지원 (opencode 스타일)
"""


class ApprovalManager:
    """Tool 실행 전 사용자 승인 플러그인"""

    def __init__(self, enabled: bool = False, show_diff: bool = True):
        """
        Args:
            enabled: 승인 기능 활성화 여부
            show_diff: diff 표시 여부 (기본: True)
        """
        self.enabled = enabled
        self.show_diff = show_diff
        self.history: list[tuple[str, bool]] = []  # (description, approved) 이력
        # Spinner control callbacks (set by CLI)
        self.pause_spinner: callable | None = None
        self.resume_spinner: callable | None = None

    def _format_diff(self, diff: str) -> str:
        """diff를 읽기 좋게 포맷팅 (색상 없이)

        Args:
            diff: unified diff 문자열

        Returns:
            포맷된 diff 문자열
        """
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

    def request(self, tool_name: str, details: str, diff: str | None = None) -> bool:
        """
        사용자에게 승인 요청 (y/n만 허용)

        Args:
            tool_name: 도구 이름
            details: 승인 요청 설명
            diff: 선택적 diff 문자열 (파일 변경 시)

        Returns:
            True: 승인
            False: 거부
        """
        if not self.enabled:
            return True

        # Pause spinner before showing prompt
        if self.pause_spinner:
            self.pause_spinner()

        print(f"\n⚠️  Permission required: {tool_name}")
        print(f"   {details}")

        # diff 표시 (활성화되어 있고, diff가 있을 경우)
        if self.show_diff and diff:
            print("\n   Changes:")
            print(self._format_diff(diff))
            print()

        try:
            while True:
                try:
                    response = input("   Approve? [y/n]: ").strip().lower()
                    if response in ["y", "yes"]:
                        self.history.append((f"{tool_name}: {details}", True))
                        return True
                    elif response in ["n", "no"]:
                        self.history.append((f"{tool_name}: {details}", False))
                        return False
                    else:
                        print("   Invalid input. Please enter 'y' or 'n'")
                except (EOFError, KeyboardInterrupt):
                    print("\n   Cancelled. Denying permission.")
                    self.history.append((f"{tool_name}: {details}", False))
                    return False
        finally:
            # Resume spinner after user input
            if self.resume_spinner:
                self.resume_spinner()

    def get_history(self) -> list[tuple[str, bool]]:
        """승인 이력 반환"""
        return self.history.copy()

    def clear_history(self) -> None:
        """승인 이력 초기화"""
        self.history.clear()
