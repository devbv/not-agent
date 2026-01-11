"""Agent loop - Main agent execution loop."""

import time
from typing import Any, Callable, TYPE_CHECKING

from anthropic import RateLimitError, APIError
from anthropic.types import Message, ToolUseBlock, TextBlock
from rich.console import Console

from not_agent.config import Config
from not_agent.provider import get_provider, BaseProvider
from not_agent.tools import ToolResult, TodoManager, get_all_tools
from not_agent.core import (
    Event,
    EventBus,
    LoopStartedEvent,
    LoopCompletedEvent,
    TurnStartedEvent,
    TurnCompletedEvent,
    StateChangedEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    ToolExecutionStartedEvent,
    ToolExecutionCompletedEvent,
    ContextCompactionEvent,
)
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
        event_bus: EventBus | None = None,
        executor: ToolExecutor | None = None,
        todo_manager: TodoManager | None = None,
    ) -> None:
        # Config setup (create default if not provided)
        self.config = config or Config()

        # Event bus (optional)
        self.event_bus = event_bus

        # Provider setup
        self.provider: BaseProvider = get_provider(
            self.config.get("provider", "claude"),
            self.config
        )

        # Settings (loaded from Config)
        self.max_turns: int = self.config.get("max_turns", 20)
        self.max_output_length: int = self.config.get("max_output_length", 10_000)
        self.debug: bool = self.config.get("debug", False)

        # Create TodoManager instance (isolated per session)
        self.todo_manager = todo_manager or TodoManager()

        # Executor setup - inject TodoManager
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

        # Spinner callbacks (set in run())
        self.pause_spinner_callback: Any = None
        self.resume_spinner_callback: Any = None
        self.update_spinner_callback: Any = None

        # State management
        self.context = LoopContext(max_turns=self.max_turns)
        self._state_change_callbacks: list[Callable[[LoopState, LoopState], None]] = []

    # Debug formatting
    _SEP = "=" * 60

    def _debug_log(self, message: str) -> None:
        """Print debug message in dim style if debug mode is enabled."""
        if self.debug:
            _debug_console.print(f"[dim]{message}[/dim]")

    def _emit(self, event: Event) -> None:
        """Emit an event to the event bus if available."""
        if self.event_bus:
            self.event_bus.publish(event)

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
        """Change state and invoke callbacks."""
        old_state = self.context.state
        self.context.record_state(new_state)

        # Emit event
        self._emit(StateChangedEvent(
            old_state=old_state.name,
            new_state=new_state.name,
        ))

        # Invoke callbacks (legacy compatibility)
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                self._debug_log(f"[STATE] Callback error: {e}")

    def on_state_change(
        self, callback: Callable[[LoopState, LoopState], None]
    ) -> None:
        """Register state change callback.

        Args:
            callback: Callback function that receives (old_state, new_state)
        """
        self._state_change_callbacks.append(callback)

    def _check_termination(
        self,
        response: Any,
        tool_uses: list[ToolUseBlock],
    ) -> TerminationReason | None:
        """Check termination conditions.

        Args:
            response: LLM response
            tool_uses: Extracted list of tool calls

        Returns:
            Termination reason or None (continue)
        """
        # End if no tool calls
        if not tool_uses:
            return TerminationReason.END_TURN

        # Check stop_reason
        if hasattr(response, 'stop_reason'):
            if response.stop_reason == 'end_turn' and not tool_uses:
                return TerminationReason.STOP_REASON

        return None  # Continue

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

        # Initialize context
        self.context.reset()
        self.context.max_turns = self.max_turns
        self.context.start_time = time.time()

        try:
            # Receive input
            self._set_state(LoopState.RECEIVING_INPUT)
            self.session.add_user_message(user_message)

            # Loop started event
            self._emit(LoopStartedEvent(
                session_id=self.session.id,
                user_message=user_message[:100],
            ))

            for turn in range(self.max_turns):
                self.context.current_turn = turn + 1

                # Turn started event
                self._emit(TurnStartedEvent(
                    turn_number=turn + 1,
                    max_turns=self.max_turns,
                ))

                # Call LLM
                self._set_state(LoopState.CALLING_LLM)

                # LLM request event
                self._emit(LLMRequestEvent(
                    message_count=len(self.session.messages),
                    has_tools=bool(self.executor.get_tool_definitions()),
                ))

                llm_start_time = time.time()
                response = self._call_llm()
                llm_duration_ms = (time.time() - llm_start_time) * 1000
                self.context.total_llm_calls += 1

                # Analyze response
                self._set_state(LoopState.PROCESSING_RESPONSE)
                tool_uses = [
                    block for block in response.content if isinstance(block, ToolUseBlock)
                ]

                # LLM response event
                usage = getattr(response, 'usage', {}) or {}
                self._emit(LLMResponseEvent(
                    stop_reason=getattr(response, 'stop_reason', ''),
                    has_tool_use=bool(tool_uses),
                    input_tokens=usage.get('input_tokens', 0),
                    output_tokens=usage.get('output_tokens', 0),
                    duration_ms=llm_duration_ms,
                ))

                # Check termination conditions
                termination = self._check_termination(response, tool_uses)
                if termination:
                    self.context.termination_reason = termination
                    self._set_state(LoopState.COMPLETED)

                    # Extract text response
                    text_content = [
                        block.text
                        for block in response.content
                        if isinstance(block, TextBlock)
                    ]
                    text_response = "\n".join(text_content)

                    # Loop completed event
                    duration_ms = (time.time() - self.context.start_time) * 1000
                    self._emit(LoopCompletedEvent(
                        session_id=self.session.id,
                        termination_reason=termination.name,
                        total_turns=self.context.current_turn,
                        duration_ms=duration_ms,
                    ))
                    return text_response

                # Execute tools
                self._set_state(LoopState.EXECUTING_TOOLS)
                self.session.add_assistant_message(list(response.content))

                tool_results = []

                for tool_use in tool_uses:
                    tool_input = dict(tool_use.input)

                    # Tool execution started event
                    self._emit(ToolExecutionStartedEvent(
                        tool_name=tool_use.name,
                        tool_input=tool_input,
                    ))

                    # Pause spinner for ask_user to allow clean user input
                    if tool_use.name == "ask_user" and self.pause_spinner_callback:
                        self.pause_spinner_callback()

                    tool_start_time = time.time()
                    result = self.executor.execute(tool_use.name, tool_input)
                    tool_duration_ms = (time.time() - tool_start_time) * 1000
                    self.context.total_tool_calls += 1

                    # Resume spinner after ask_user
                    if tool_use.name == "ask_user" and self.resume_spinner_callback:
                        self.resume_spinner_callback()

                    # Tool execution completed event
                    self._emit(ToolExecutionCompletedEvent(
                        tool_name=tool_use.name,
                        success=result.success,
                        duration_ms=tool_duration_ms,
                        output_preview=result.output[:200] if result.output else "",
                    ))

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

                # Turn completed event
                self._emit(TurnCompletedEvent(
                    turn_number=turn + 1,
                    tool_calls_count=len(tool_uses),
                ))

                # Check context size
                self._set_state(LoopState.CHECKING_CONTEXT)
                self._check_context_size()

            # Max turns reached
            self.context.termination_reason = TerminationReason.MAX_TURNS
            self._set_state(LoopState.COMPLETED)

            # Loop completed event (max turns)
            duration_ms = (time.time() - self.context.start_time) * 1000
            self._emit(LoopCompletedEvent(
                session_id=self.session.id,
                termination_reason=TerminationReason.MAX_TURNS.name,
                total_turns=self.context.current_turn,
                duration_ms=duration_ms,
            ))
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
        self._debug_log(f"\n. [LLM REQUEST]")
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

            # Log LLM response
            self._debug_log(f"\n. [LLM RESPONSE]")
            for block in response.content:
                block_type = getattr(block, 'type', None)
                if block_type == 'text':
                    text = getattr(block, 'text', '')
                    preview = text[:300] + "..." if len(text) > 300 else text
                    self._debug_log(f"  [TEXT] {preview}")
                elif block_type == 'tool_use':
                    name = getattr(block, 'name', '?')
                    input_data = getattr(block, 'input', {})
                    input_str = str(input_data)
                    input_preview = input_str[:150] + "..." if len(input_str) > 150 else input_str
                    self._debug_log(f"  [TOOL_USE] {name}: {input_preview}")

            # Convert ProviderResponse to anthropic Message format (legacy code compatibility)
            # response.content is already in list format
            return type('Message', (), {
                'content': response.content,
                'stop_reason': response.stop_reason,
                'usage': response.usage,
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
        enable_auto_compaction = self.config.get("enable_auto_compaction", True)
        if enable_auto_compaction and self.context_manager.should_compact(self.session):
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
