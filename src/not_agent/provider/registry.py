"""프로바이더 레지스트리."""

from typing import Type, TYPE_CHECKING

from .base import BaseProvider
from .claude import ClaudeProvider

if TYPE_CHECKING:
    from not_agent.config import Config


# 등록된 프로바이더들
PROVIDERS: dict[str, Type[BaseProvider]] = {
    "claude": ClaudeProvider,
}


def get_provider(name: str, config: "Config") -> BaseProvider:
    """
    이름으로 프로바이더 인스턴스 생성.

    Args:
        name: 프로바이더 이름 (예: "claude")
        config: 설정 객체

    Returns:
        BaseProvider: 프로바이더 인스턴스

    Raises:
        ValueError: 알 수 없는 프로바이더 이름
    """
    if name not in PROVIDERS:
        available = list(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {name}. Available: {available}")

    return PROVIDERS[name](config)


def register_provider(name: str, provider_class: Type[BaseProvider]) -> None:
    """
    프로바이더 등록 (확장용).

    Args:
        name: 프로바이더 이름
        provider_class: BaseProvider를 상속한 클래스
    """
    PROVIDERS[name] = provider_class


def list_providers() -> list[str]:
    """등록된 프로바이더 이름 목록 반환."""
    return list(PROVIDERS.keys())
