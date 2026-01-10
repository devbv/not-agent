"""
Approval Manager Plugin

Tool 실행 전 사용자 승인을 받는 플러그인.
- Tool이 아님 (LLM이 호출하지 않음)
- Executor에 주입되어 모든 Tool 실행 전 실행됨
- Tool이 제공한 설명을 기반으로 y/n 확인
"""


class ApprovalManager:
    """Tool 실행 전 사용자 승인 플러그인"""

    def __init__(self, enabled: bool = False):
        """
        Args:
            enabled: 승인 기능 활성화 여부
        """
        self.enabled = enabled
        self.history: list[tuple[str, bool]] = []  # (description, approved) 이력

    def request(self, tool_name: str, details: str) -> bool:
        """
        사용자에게 승인 요청 (y/n만 허용)

        Args:
            tool_name: 도구 이름
            details: 승인 요청 설명

        Returns:
            True: 승인
            False: 거부
        """
        if not self.enabled:
            return True

        print(f"\n⚠️  Permission required: {tool_name}")
        print(f"   {details}")

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

    def get_history(self) -> list[tuple[str, bool]]:
        """승인 이력 반환"""
        return self.history.copy()

    def clear_history(self) -> None:
        """승인 이력 초기화"""
        self.history.clear()
