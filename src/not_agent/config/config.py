"""Configuration management class."""

import json
import os
from pathlib import Path
from typing import Any

from .defaults import DEFAULT_CONFIG


class Config:
    """
    Hierarchical configuration loader.
    Priority: CLI override > Environment variables > Project config > Global config > Defaults
    """

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._load_defaults()
        self._load_global()
        self._load_project()
        self._load_env()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration for CLI override."""
        self._config[key] = value

    def __getitem__(self, key: str) -> Any:
        """Dictionary-style access."""
        return self._config[key]

    def __contains__(self, key: str) -> bool:
        """Support 'key in config'."""
        return key in self._config

    def _load_defaults(self) -> None:
        """Load defaults."""
        self._config.update(DEFAULT_CONFIG)

    def _load_global(self) -> None:
        """Load global config file (~/.not_agent/config.json)."""
        global_path = Path.home() / ".not_agent" / "config.json"
        if global_path.exists():
            try:
                with open(global_path) as f:
                    self._config.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass  # Ignore invalid config files

    def _load_project(self) -> None:
        """Load project config file (.not_agent.json)."""
        project_path = Path.cwd() / ".not_agent.json"
        if project_path.exists():
            try:
                with open(project_path) as f:
                    self._config.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass

    def _load_env(self) -> None:
        """Load environment variables (NOT_AGENT_*)."""
        prefix = "NOT_AGENT_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                self._config[config_key] = self._parse_value(value)

    def _parse_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Integer
        try:
            return int(value)
        except ValueError:
            pass

        # Float
        try:
            return float(value)
        except ValueError:
            pass

        # String
        return value

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()
