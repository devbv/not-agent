"""도구 레지스트리 시스템."""

from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseTool


class ToolRegistry:
    """
    도구 등록 및 관리.

    싱글톤 패턴을 사용하여 전역 레지스트리 관리.
    """

    _tools: dict[str, Type["BaseTool"]] = {}
    _instances: dict[str, "BaseTool"] = {}
    _instance_kwargs: dict[str, dict] = {}  # 도구별 초기화 인자

    @classmethod
    def register(
        cls,
        tool_class: Type["BaseTool"],
        name: str | None = None,
    ) -> Type["BaseTool"]:
        """
        도구 클래스 등록.

        Args:
            tool_class: 등록할 도구 클래스
            name: 선택적 도구 이름 (없으면 클래스의 name 속성 사용)

        Returns:
            등록된 도구 클래스 (데코레이터 체이닝용)
        """
        tool_name = name or tool_class.name
        if not tool_name:
            raise ValueError(f"Tool class {tool_class.__name__} must have a 'name' attribute")

        cls._tools[tool_name] = tool_class
        return tool_class

    @classmethod
    def get(cls, name: str, **kwargs) -> "BaseTool":
        """
        이름으로 도구 인스턴스 조회.

        Args:
            name: 도구 이름
            **kwargs: 도구 초기화 인자 (TodoTool 등에 필요)

        Returns:
            도구 인스턴스
        """
        if name not in cls._tools:
            raise KeyError(f"Unknown tool: {name}. Available: {list(cls._tools.keys())}")

        # 캐시 키: 이름 + kwargs 해시
        cache_key = name
        if kwargs:
            # kwargs가 있으면 새 인스턴스 생성 (TodoManager 등)
            return cls._tools[name](**kwargs)

        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls._tools[name]()

        return cls._instances[cache_key]

    @classmethod
    def get_all(cls, **shared_kwargs) -> list["BaseTool"]:
        """
        모든 등록된 도구 인스턴스 반환.

        Args:
            **shared_kwargs: 모든 도구에 전달할 공통 인자

        Returns:
            도구 인스턴스 리스트
        """
        tools = []
        for name in cls._tools:
            try:
                tool = cls.get(name, **shared_kwargs)
                tools.append(tool)
            except TypeError:
                # kwargs가 필요 없는 도구
                tool = cls.get(name)
                tools.append(tool)
        return tools

    @classmethod
    def get_tool_class(cls, name: str) -> Type["BaseTool"]:
        """도구 클래스 조회 (인스턴스화 없이)."""
        if name not in cls._tools:
            raise KeyError(f"Unknown tool: {name}")
        return cls._tools[name]

    @classmethod
    def list_tools(cls) -> list[str]:
        """등록된 도구 이름 목록 반환."""
        return list(cls._tools.keys())

    @classmethod
    def clear(cls) -> None:
        """레지스트리 초기화 (테스트용)."""
        cls._tools.clear()
        cls._instances.clear()
        cls._instance_kwargs.clear()

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """도구 등록 여부 확인."""
        return name in cls._tools


def register_tool(cls: Type["BaseTool"]) -> Type["BaseTool"]:
    """
    도구 등록 데코레이터.

    사용 예:
        @register_tool
        class ReadTool(BaseTool):
            name = "read"
            ...
    """
    return ToolRegistry.register(cls)
