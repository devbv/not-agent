"""
Approval Manager - Backward compatibility wrapper.

Maintains the existing ApprovalManager interface while
internally using PermissionManager.

For new code, use PermissionManager directly.
"""

from typing import Callable

from .permissions import Permission, PermissionManager


class ApprovalManager:
    """
    User approval plugin for tool execution.

    Internally uses PermissionManager for rule-based permission evaluation.
    Maintained for backward compatibility with existing interface.
    """

    def __init__(self, enabled: bool = False, show_diff: bool = True):
        """
        Args:
            enabled: Whether approval feature is enabled
            show_diff: Whether to show diff (default: True)
        """
        self._manager = PermissionManager(
            enabled=enabled,
            show_diff=show_diff,
        )

    @property
    def enabled(self) -> bool:
        """Whether approval feature is enabled."""
        return self._manager.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._manager.enabled = value

    @property
    def show_diff(self) -> bool:
        """Whether to show diff."""
        return self._manager.show_diff

    @show_diff.setter
    def show_diff(self, value: bool) -> None:
        self._manager.show_diff = value

    @property
    def pause_spinner(self) -> Callable[[], None] | None:
        """Spinner pause callback."""
        return self._manager.pause_spinner

    @pause_spinner.setter
    def pause_spinner(self, value: Callable[[], None] | None) -> None:
        self._manager.pause_spinner = value

    @property
    def resume_spinner(self) -> Callable[[], None] | None:
        """Spinner resume callback."""
        return self._manager.resume_spinner

    @resume_spinner.setter
    def resume_spinner(self, value: Callable[[], None] | None) -> None:
        self._manager.resume_spinner = value

    def request(self, tool_name: str, details: str, diff: str | None = None) -> bool:
        """
        Request approval from user (legacy interface compatible).

        Internally calls PermissionManager.check().
        Attempts to extract context info from details.

        Args:
            tool_name: Tool name
            details: Approval request description
            diff: Optional diff string (for file changes)

        Returns:
            True: approved, False: denied
        """
        # Try to extract context from details
        context = {"details": details}

        return self._manager.check(tool_name, details, context, diff)

    def get_history(self) -> list[tuple[str, bool]]:
        """
        Return approval history (legacy format: bool).

        Returns:
            List of (description, approved) tuples
        """
        return [
            (desc, perm == Permission.ALLOW)
            for desc, perm in self._manager.get_history()
        ]

    def clear_history(self) -> None:
        """Clear approval history."""
        self._manager.clear_history()
