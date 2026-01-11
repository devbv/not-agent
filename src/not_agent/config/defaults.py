"""Default configuration values."""

from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    # LLM settings
    "provider": "claude",
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 16384,

    # Agent settings
    "max_turns": 20,
    "max_output_length": 10_000,
    "context_limit": 100_000,
    "compact_threshold": 0.75,
    "preserve_recent_messages": 3,
    "enable_auto_compaction": True,

    # Permission/approval settings
    "approval_enabled": True,
    "show_diff": True,
    "permission_rules": [],  # Custom rules (PermissionRule.from_dict format)

    # Feature settings
    "debug": False,
}
