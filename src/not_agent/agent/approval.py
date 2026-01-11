"""
Approval Manager - 하위 호환성을 위한 래퍼

기존 ApprovalManager 인터페이스를 유지하면서
내부적으로 PermissionManager를 사용합니다.

새 코드에서는 PermissionManager를 직접 사용하세요.
"""

from typing import Callable

from .permissions import Permission, PermissionManager


class ApprovalManager:
    """
    Tool 실행 전 사용자 승인 플러그인.

    내부적으로 PermissionManager를 사용하여 규칙 기반 권한 평가를 수행합니다.
    기존 인터페이스와의 호환성을 위해 유지됩니다.
    """

    def __init__(self, enabled: bool = False, show_diff: bool = True):
        """
        Args:
            enabled: 승인 기능 활성화 여부
            show_diff: diff 표시 여부 (기본: True)
        """
        self._manager = PermissionManager(
            enabled=enabled,
            show_diff=show_diff,
        )

    @property
    def enabled(self) -> bool:
        """승인 기능 활성화 여부."""
        return self._manager.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._manager.enabled = value

    @property
    def show_diff(self) -> bool:
        """diff 표시 여부."""
        return self._manager.show_diff

    @show_diff.setter
    def show_diff(self, value: bool) -> None:
        self._manager.show_diff = value

    @property
    def pause_spinner(self) -> Callable[[], None] | None:
        """스피너 일시정지 콜백."""
        return self._manager.pause_spinner

    @pause_spinner.setter
    def pause_spinner(self, value: Callable[[], None] | None) -> None:
        self._manager.pause_spinner = value

    @property
    def resume_spinner(self) -> Callable[[], None] | None:
        """스피너 재개 콜백."""
        return self._manager.resume_spinner

    @resume_spinner.setter
    def resume_spinner(self, value: Callable[[], None] | None) -> None:
        self._manager.resume_spinner = value

    def request(self, tool_name: str, details: str, diff: str | None = None) -> bool:
        """
        사용자에게 승인 요청 (기존 인터페이스 호환).

        내부적으로 PermissionManager.check()를 호출합니다.
        details에서 context 정보를 추출하려 시도합니다.

        Args:
            tool_name: 도구 이름
            details: 승인 요청 설명
            diff: 선택적 diff 문자열 (파일 변경 시)

        Returns:
            True: 승인, False: 거부
        """
        # details에서 context 추출 시도
        context = {"details": details}

        return self._manager.check(tool_name, details, context, diff)

    def get_history(self) -> list[tuple[str, bool]]:
        """
        승인 이력 반환 (기존 형식: bool).

        Returns:
            (description, approved) 튜플 리스트
        """
        return [
            (desc, perm == Permission.ALLOW)
            for desc, perm in self._manager.get_history()
        ]

    def clear_history(self) -> None:
        """승인 이력 초기화."""
        self._manager.clear_history()
