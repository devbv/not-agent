"""설정 관리 클래스."""

import json
import os
from pathlib import Path
from typing import Any

from .defaults import DEFAULT_CONFIG


class Config:
    """
    계층적 설정 로더.
    우선순위: CLI 오버라이드 > 환경변수 > 프로젝트 설정 > 글로벌 설정 > 기본값
    """

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._load_defaults()
        self._load_global()
        self._load_project()
        self._load_env()

    def get(self, key: str, default: Any = None) -> Any:
        """설정값 조회."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """CLI 오버라이드용 설정."""
        self._config[key] = value

    def __getitem__(self, key: str) -> Any:
        """딕셔너리 스타일 접근."""
        return self._config[key]

    def __contains__(self, key: str) -> bool:
        """key in config 지원."""
        return key in self._config

    def _load_defaults(self) -> None:
        """기본값 로드."""
        self._config.update(DEFAULT_CONFIG)

    def _load_global(self) -> None:
        """글로벌 설정 파일 로드 (~/.not_agent/config.json)."""
        global_path = Path.home() / ".not_agent" / "config.json"
        if global_path.exists():
            try:
                with open(global_path) as f:
                    self._config.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass  # 잘못된 설정 파일은 무시

    def _load_project(self) -> None:
        """프로젝트 설정 파일 로드 (.not_agent.json)."""
        project_path = Path.cwd() / ".not_agent.json"
        if project_path.exists():
            try:
                with open(project_path) as f:
                    self._config.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass

    def _load_env(self) -> None:
        """환경변수 로드 (NOT_AGENT_*)."""
        prefix = "NOT_AGENT_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                self._config[config_key] = self._parse_value(value)

    def _parse_value(self, value: str) -> Any:
        """환경변수 값을 적절한 타입으로 파싱."""
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
        """설정을 딕셔너리로 반환."""
        return self._config.copy()
