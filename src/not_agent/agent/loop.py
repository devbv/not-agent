"""Agent loop - Main agent execution loop."""

import time
from typing import Any, Callable, TYPE_CHECKING

from anthropic import RateLimitError, APIError
from anthropic.types import Message, ToolUseBlock, TextBlock
from rich.console import Console

from not_agent.config import Config
from not_agent.provider import get_provider, BaseProvider
from not_agent.tools import ToolResult, TodoManager, get_all_tools
from .executor import ToolExecutor
from .session import Session
from .context import ContextManager
from .states import LoopState, TerminationReason, LoopContext

if TYPE_CHECKING:
    pass

# Debug console (shared instance)
_debug_console = Console()


class AgentLoop:
    """Main agent loop that handles conversation and tool execution."""

    def __init__(
        self,
        config: Config | None = None,
        # Legacy parameters (하위 호환성)
        model: str | None = None,
        max_turns: int | None = None,
        max_output_length: int | None = None,
        max_context_tokens: int | None = None,
        compaction_threshold: float | None = None,
        preserve_recent_messages: int | None = None,
        enable_auto_compaction: bool | None = None,
        executor: ToolExecutor | None = None,
        todo_manager: TodoManager | None = None,
        debug: bool | None = None,
    ) -> None:
        # Config 설정 (없으면 기본값 생성)
        self.config = config or Config()

        # Legacy parameters로 Config 오버라이드
        if model is not None:
            self.config.set("model", model)
        if max_turns is not None:
            self.config.set("max_turns", max_turns)
        if max_output_length is not None:
            self.config.set("max_output_length", max_output_length)
        if max_context_tokens is not None:
            self.config.set("context_limit", max_context_tokens)
        if compaction_threshold is not None:
            self.config.set("compact_threshold", compaction_threshold)
        if preserve_recent_messages is not None:
            self.config.set("preserve_recent_messages", preserve_recent_messages)
        if enable_auto_compaction is not None:
            self.config.set("enable_auto_compaction", enable_auto_compaction)
        if debug is not None:
            self.config.set("debug", debug)

        # Provider 설정
        self.provider: BaseProvider = get_provider(
            self.config.get("provider", "claude"),
            self.config
        )

        # 설정값 캐싱 (자주 사용됨)
        self.max_turns = self.config.get("max_turns", 20)
        self.max_output_length = self.config.get("max_output_length", 10_000)
        self.debug = self.config.get("debug", False)

        # TodoManager 인스턴스 생성 (세션별 격리)
        self.todo_manager = todo_manager or TodoManager()

        # Executor 설정 - TodoManager 주입
        if executor:
            self.executor = executor
        else:
            tools = get_all_tools(todo_manager=self.todo_manager)
            self.executor = ToolExecutor(tools=tools)

        # Session & Context Manager
        self.session = Session()
        self.context_manager = ContextManager(
            config=self.config,
            provider=self.provider,
            preserve_recent_messages=self.config.get("preserve_recent_messages", 3),
        )

        self.system_prompt = self._get_system_prompt()

        # Spinner callbacks (run()에서 설정됨)
        self.pause_spinner_callback: Any = None
        self.resume_spinner_callback: Any = None
        self.update_spinner_callback: Any = None

        # 상태 관리
        self.context = LoopContext(max_turns=self.max_turns)
        self._state_change_callbacks: list[Callable[[LoopState, LoopState], None]] = []

    # --- Legacy compatibility properties ---
    @property
    def messages(self) -> list[dict[str, Any]]:
        """Legacy: 직접 messages 접근 지원."""
        return self.session.to_api_format()

    @messages.setter
    def messages(self, value: list[dict[str, Any]]) -> None:
        """Legacy: messages 직접 설정 지원."""
        self.session.set_messages(value)

    @property
    def max_context_tokens(self) -> int:
        """Legacy property."""
        return self.config.get("context_limit", 100_000)

    @property
    def preserve_recent_messages(self) -> int:
        """Legacy property."""
        return self.config.get("preserve_recent_messages", 3)

    @property
    def enable_auto_compaction(self) -> bool:
        """Legacy property."""
        return self.config.get("enable_auto_compaction", True)

    # Debug formatting
    _SEP = "=" * 60

    def _debug_log(self, message: str) -> None:
        """Print debug message in dim style if debug mode is enabled."""
        if self.debug:
            _debug_console.print(f"[dim]{message}[/dim]")

    def _debug_box(
        self,
        title: str,
        messages: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Print a formatted debug box."""
        lines = [f"\n{self._SEP}", title, self._SEP]
        if messages:
            lines.extend(f"[ERROR] {m}" for m in messages)
        if suggestions:
            lines.append("\n[SUGGESTION] Please try one of the following:")
            lines.extend(f"  {i}. {s}" for i, s in enumerate(suggestions, 1))
        lines.append(f"{self._SEP}\n")
        self._debug_log("\n".join(lines))

    # --- State management ---

    def _set_state(self, new_state: LoopState) -> None:
        """상태 변경 및 콜백 호출."""
        old_state = self.context.state
        self.context.record_state(new_state)

        self._debug_log(f"[STATE] {old_state.name} -> {new_state.name}")

        # 콜백 호출 (이벤트 시스템 연동 포인트)
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                self._debug_log(f"[STATE] Callback error: {e}")

    def on_state_change(
        self, callback: Callable[[LoopState, LoopState], None]
    ) -> None:
        """상태 변경 콜백 등록.

        Args:
            callback: (old_state, new_state)를 받는 콜백 함수
        """
        self._state_change_callbacks.append(callback)

    def _check_termination(
        self,
        response: Any,
        tool_uses: list[ToolUseBlock],
    ) -> TerminationReason | None:
        """종료 조건 확인.

        Args:
            response: LLM 응답
            tool_uses: 추출된 도구 호출 목록

        Returns:
            종료 사유 또는 None (계속 진행)
        """
        # 도구 호출이 없으면 종료
        if not tool_uses:
            return TerminationReason.END_TURN

        # stop_reason 확인
        if hasattr(response, 'stop_reason'):
            if response.stop_reason == 'end_turn' and not tool_uses:
                return TerminationReason.STOP_REASON

        return None  # 계속 진행

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent.

        Note: Tool-specific details are in each tool's description.
        This prompt focuses only on agent behavior and workflow.
        """
        return """You are a coding agent that completes tasks using tools.

CRITICAL: Take action immediately. Do NOT explain how to do something - DO it.

WORKFLOW:
1. Gather information first (read, glob, grep)
2. Then take action (write, edit, bash)
3. Summarize what you did

When unsure about requirements, use ask_user."""

    def run(
        self,
        user_message: str,
        pause_spinner_callback: Any = None,
        resume_spinner_callback: Any = None,
        update_spinner_callback: Any = None,
    ) -> str:
        """Run the agent loop with a user message.

        Args:
            user_message: The user's input message
            pause_spinner_callback: Optional callback to pause spinner during user input
            resume_spinner_callback: Optional callback to resume spinner after user input
            update_spinner_callback: Optional callback to update spinner with new todo status

        Returns:
            Agent's text response

        Note:
            After run() completes, check self.context for execution statistics:
            - context.termination_reason: Why the loop ended
            - context.total_llm_calls: Number of LLM API calls
            - context.total_tool_calls: Number of tool executions
            - context.duration_ms(): Total execution time in milliseconds
        """
        self.pause_spinner_callback = pause_spinner_callback
        self.resume_spinner_callback = resume_spinner_callback
        self.update_spinner_callback = update_spinner_callback

        # 컨텍스트 초기화
        self.context.reset()
        self.context.max_turns = self.max_turns
        self.context.start_time = time.time()

        try:
            # 입력 수신
            self._set_state(LoopState.RECEIVING_INPUT)
            self.session.add_user_message(user_message)

            self._debug_box(f"[AGENT LOOP] Starting with user message: {user_message[:100]}...")

            for turn in range(self.max_turns):
                self.context.current_turn = turn + 1

                self._debug_box(f"[TURN {turn + 1}/{self.max_turns}]")

                # LLM 호출
                self._set_state(LoopState.CALLING_LLM)
                response = self._call_llm()
                self.context.total_llm_calls += 1

                # 응답 분석
                self._set_state(LoopState.PROCESSING_RESPONSE)
                tool_uses = [
                    block for block in response.content if isinstance(block, ToolUseBlock)
                ]

                # 종료 조건 확인
                termination = self._check_termination(response, tool_uses)
                if termination:
                    self.context.termination_reason = termination
                    self._set_state(LoopState.COMPLETED)

                    # 텍스트 응답 추출
                    text_content = [
                        block.text
                        for block in response.content
                        if isinstance(block, TextBlock)
                    ]
                    text_response = "\n".join(text_content)
                    self._debug_log(f"\n[COMPLETE] {termination.name}")
                    return text_response

                # 도구 실행
                self._set_state(LoopState.EXECUTING_TOOLS)
                self.session.add_assistant_message(list(response.content))

                self._debug_log(f"\n[TOOL EXECUTION] Executing {len(tool_uses)} tool(s)...")

                tool_results = []

                for idx, tool_use in enumerate(tool_uses):
                    self._debug_log(f"\n  Tool {idx + 1}: {tool_use.name}")

                    tool_input = dict(tool_use.input)

                    # Show input for debugging
                    input_str = str(tool_input)
                    if len(input_str) > 150:
                        self._debug_log(f"    Input: {input_str[:150]}...")
                    else:
                        self._debug_log(f"    Input: {input_str}")

                    # Pause spinner for ask_user to allow clean user input
                    if tool_use.name == "ask_user" and self.pause_spinner_callback:
                        self.pause_spinner_callback()

                    result = self.executor.execute(tool_use.name, tool_input)
                    self.context.total_tool_calls += 1

                    # Resume spinner after ask_user
                    if tool_use.name == "ask_user" and self.resume_spinner_callback:
                        self.resume_spinner_callback()

                    self._debug_log(f"    Success: {result.success}")
                    if result.success:
                        output_preview = result.output[:200] if result.output else "(empty)"
                        self._debug_log(f"    Output: {output_preview}...")
                    else:
                        self._debug_log(f"    Error: {result.error}")

                    # Update spinner with new todo status (live display)
                    if tool_use.name == "todo_write" and result.success:
                        if self.update_spinner_callback:
                            self.update_spinner_callback()

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": self._format_tool_result(result),
                        }
                    )

                self.session.add_tool_results(tool_results)
                self._debug_log(f"\n[FEEDBACK] Tool results added to conversation")

                # 컨텍스트 크기 확인
                self._set_state(LoopState.CHECKING_CONTEXT)
                self._check_context_size()

            # 최대 턴 도달
            self.context.termination_reason = TerminationReason.MAX_TURNS
            self._set_state(LoopState.COMPLETED)

            self._debug_box(f"[MAX TURNS] Reached maximum turns ({self.max_turns})")
            return "Max turns reached. Please continue with a new message."

        except KeyboardInterrupt:
            self.context.termination_reason = TerminationReason.USER_INTERRUPT
            self._set_state(LoopState.ERROR)
            return "Interrupted by user."

        except Exception as e:
            self.context.last_error = e
            self.context.termination_reason = TerminationReason.ERROR
            self._set_state(LoopState.ERROR)
            raise

        finally:
            self.context.end_time = time.time()

    def _call_llm(self) -> Message:
        """Call the LLM with current messages."""
        messages = self.session.to_api_format()

        # Show LLM request
        self._debug_log(f"\n[LLM REQUEST]")
        for i, msg in enumerate(messages, 1):
            role = msg['role']
            content = msg['content']

            if isinstance(content, str):
                preview = content[:150] + "..." if len(content) > 150 else content
                self._debug_log(f"  #{i} {role.upper()}: {preview}")
            elif isinstance(content, list):
                # Check if it's tool results or assistant content
                if all(isinstance(item, dict) and item.get('type') == 'tool_result' for item in content):
                    self._debug_log(f"  #{i} {role.upper()}: [Tool Results x{len(content)}]")
                    for j, item in enumerate(content[:2], 1):
                        result_preview = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
                        self._debug_log(f"      Result {j}: {result_preview}")
                    if len(content) > 2:
                        self._debug_log(f"      ... and {len(content) - 2} more")
                else:
                    # Assistant message with mixed content
                    for item in content:
                        # Handle both SDK objects (hasattr) and dicts
                        item_type = getattr(item, 'type', None) or (item.get('type') if isinstance(item, dict) else None)
                        if item_type == 'tool_use':
                            name = getattr(item, 'name', None) or item.get('name', '?')
                            input_data = getattr(item, 'input', None) or item.get('input', {})
                            self._debug_log(f"  #{i} {role.upper()}: Tool={name}, Input={str(input_data)[:80]}...")
                        elif item_type == 'text':
                            text = getattr(item, 'text', None) or item.get('text', '')
                            self._debug_log(f"  #{i} {role.upper()}: {text[:100]}...")

        try:
            response = self.provider.chat(
                messages=messages,
                system=self.system_prompt,
                tools=self.executor.get_tool_definitions(),
                max_tokens=self.config.get("max_tokens", 16 * 1024),
            )

            # ProviderResponse -> anthropic Message 형식으로 변환 (기존 코드 호환)
            # response.content는 이미 리스트 형태
            return type('Message', (), {
                'content': response.content,
                'stop_reason': response.stop_reason,
            })()

        except RateLimitError as e:
            self._debug_box(
                "[API ERROR] Rate Limit Exceeded",
                messages=["Claude API rate limit reached.", str(e)],
                suggestions=[
                    "Wait a few moments and try again",
                    "Use 'reset' to clear conversation history",
                    "Reduce the size of your request",
                ],
            )
            raise
        except APIError as e:
            self._debug_box(
                "[API ERROR] Claude API Error",
                messages=["Failed to communicate with Claude API.", str(e)],
                suggestions=[
                    "Your internet connection",
                    "API key is valid (ANTHROPIC_API_KEY)",
                    "Anthropic API status: https://status.anthropic.com",
                ],
            )
            raise
        except Exception as e:
            self._debug_box("[ERROR] Unexpected Error", messages=[str(e)])
            raise

    def _format_tool_result(self, result: ToolResult) -> str:
        """Format a tool result for the LLM."""
        if result.success:
            output = result.output
            if len(output) > self.max_output_length:
                truncated_chars = len(output) - self.max_output_length
                output = (
                    output[: self.max_output_length]
                    + f"\n\n... (output truncated, {truncated_chars:,} characters omitted)"
                )
            return output
        else:
            error_output = f"Error: {result.error}\n{result.output}".strip()
            if len(error_output) > self.max_output_length:
                truncated_chars = len(error_output) - self.max_output_length
                error_output = (
                    error_output[: self.max_output_length]
                    + f"\n\n... (error output truncated, {truncated_chars:,} characters omitted)"
                )
            return error_output

    def _check_context_size(self) -> None:
        """Check and warn if context is getting large."""
        # Auto-compact if threshold reached
        if self.enable_auto_compaction and self.context_manager.should_compact(self.session):
            self.context_manager.compact(
                session=self.session,
                system_prompt=self.system_prompt,
                debug_log=self._debug_log if self.debug else None,
            )
            return

        # Warnings
        usage = self.context_manager.get_usage_info(self.session)
        token_count = usage["current"]
        max_tokens = usage["max"]

        if token_count > max_tokens:
            self._debug_log(f"\n[WARNING] Context size ({token_count:,} tokens) exceeds limit ({max_tokens:,} tokens)")
            self._debug_log(f"[WARNING] Consider using 'reset' command to clear history")
        elif token_count > max_tokens * 0.8:
            self._debug_log(f"\n[INFO] Context size: {token_count:,} / {max_tokens:,} tokens (80%+)")

    def get_context_usage(self) -> dict[str, Any]:
        """Get current context usage information."""
        return self.context_manager.get_usage_info(self.session)

    def reset(self) -> None:
        """Reset the conversation history."""
        self.session.clear()

    # --- Legacy methods for backward compatibility ---
    def _count_messages_tokens(self) -> int:
        """Legacy: 토큰 수 추정."""
        return self.context_manager.estimate_tokens(self.session)

    def _should_compact(self) -> bool:
        """Legacy: 컴팩션 필요 여부."""
        return self.context_manager.should_compact(self.session)

    def _compact_context(self) -> None:
        """Legacy: 컨텍스트 컴팩션."""
        self.context_manager.compact(
            session=self.session,
            system_prompt=self.system_prompt,
            debug_log=self._debug_log if self.debug else None,
        )
