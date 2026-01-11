"""기본 설정값 정의."""

from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    # LLM 설정
    "provider": "claude",
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 16384,

    # 에이전트 설정
    "max_turns": 20,
    "max_output_length": 10_000,
    "context_limit": 100_000,
    "compact_threshold": 0.75,
    "preserve_recent_messages": 3,
    "enable_auto_compaction": True,

    # 권한/승인 설정
    "approval_enabled": True,
    "show_diff": True,
    "permission_rules": [],  # 사용자 정의 규칙 (PermissionRule.from_dict 형식)

    # 기능 설정
    "debug": False,
}
