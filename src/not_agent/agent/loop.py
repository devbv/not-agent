"""Agent loop - Main agent execution loop."""

import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic, RateLimitError, APIError
from anthropic.types import Message, ToolUseBlock, TextBlock

from not_agent.tools import ToolResult
from .executor import ToolExecutor


class AgentLoop:
    """Main agent loop that handles conversation and tool execution."""

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        max_turns: int = 20,
        max_output_length: int = 10_000,
        max_context_tokens: int = 50_000,
        compaction_threshold: float = 0.75,
        preserve_recent_messages: int = 4,
        enable_auto_compaction: bool = True,
        executor: ToolExecutor | None = None,
    ) -> None:
        self.client = Anthropic()
        self.model = model
        self.max_turns = max_turns
        self.max_output_length = max_output_length
        self.max_context_tokens = max_context_tokens
        self.compaction_threshold = compaction_threshold
        self.preserve_recent_messages = preserve_recent_messages
        self.enable_auto_compaction = enable_auto_compaction
        self.executor = executor or ToolExecutor()
        self.messages: list[dict[str, Any]] = []
        self.system_prompt = self._get_system_prompt()
        # Track pending draft_write for auto-confirm
        self.pending_draft: dict[str, str] | None = None

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are a coding agent that takes action using tools.

IMPORTANT: You MUST use tools to complete tasks. Do NOT just explain how to do something - actually DO it using your tools.

WORKFLOW: You can use multiple turns:
- Turn 1: Use tools to gather information (read, glob, grep, etc.)
- Turn 2+: Use tools to take action (write, edit, bash, etc.)
- You are NOT required to use tools in every single turn if you need to process information first

Available tools:
- read: Read file contents
- draft_write: Declare intention to write a file (system will auto-save content in next turn)
- edit: Edit files by replacing text
- glob: Find files by pattern (e.g., "**/*.py")
- grep: Search file contents with regex
- bash: Execute shell commands
- WebSearch: Search the web for information
- WebFetch: Fetch URL content and convert HTML to plain text
- AskUserQuestion: Ask the user for clarification

RULES:
1. When asked to find/search something → USE the glob or grep tool immediately
2. When asked to read/show a file → USE the read tool immediately
3. When asked to create a file → USE draft_write + show content (system auto-saves)
4. When asked to modify a file → USE the edit tool immediately
5. When asked to run a command → USE the bash tool immediately
6. When asked about recent/latest information → USE WebSearch immediately
7. When asked to fetch/read a URL or web page → USE WebFetch to get the text, then analyze it
8. NEVER explain methods or options - just take action
9. After using tools, summarize what you found/did

CRITICAL: File Writing Content Format
When you receive "Draft registered for: <file_path>" feedback after calling draft_write:
- Your NEXT response must contain ONLY the file content itself
- DO NOT include meta-commentary like "Here's the content:" or "I will write:"
- DO NOT include explanations about what you're doing
- Start directly with the actual content that should be saved to the file
- The system will automatically save your entire text response to the file

Example WRONG:
"이제 2차 창작물의 내용을 작성하겠습니다:

# Story Title
..."

Example CORRECT:
"# Story Title
Once upon a time..."

"""

    def run(self, user_message: str, pause_spinner_callback: Any = None, resume_spinner_callback: Any = None) -> str:
        """Run the agent loop with a user message.

        Args:
            user_message: The user's input message
            pause_spinner_callback: Optional callback to pause spinner during user input
            resume_spinner_callback: Optional callback to resume spinner after user input
        """
        self.pause_spinner_callback = pause_spinner_callback
        self.resume_spinner_callback = resume_spinner_callback
        self.messages.append({"role": "user", "content": user_message})

        print(f"\n{'='*60}")
        print(f"[AGENT LOOP] Starting with user message: {user_message[:100]}...")
        print(f"{'='*60}\n")

        for turn in range(self.max_turns):
            print(f"\n{'─'*60}")
            print(f"[TURN {turn + 1}/{self.max_turns}]")
            print(f"{'─'*60}")

            # Don't force tool use - let LLM decide when it's ready
            # Forcing tools can cause incomplete parameters (e.g., write without content)
            response = self._call_llm(force_tool=False)

            # Check if there are tool calls
            tool_uses = [
                block for block in response.content if isinstance(block, ToolUseBlock)
            ]

            if not tool_uses:
                # No tool calls - check if we need to auto-confirm a pending draft
                text_content = [
                    block.text
                    for block in response.content
                    if isinstance(block, TextBlock)
                ]
                text_response = "\n".join(text_content)

                if self.pending_draft and text_response.strip():
                    # Auto-confirm the pending draft write
                    file_path = self.pending_draft["file_path"]
                    print(f"\n[AUTO-CONFIRM] Detected draft content, auto-confirming write to {file_path}")
                    print(f"[AUTO-CONFIRM] Content length: {len(text_response)} chars")

                    # Pause spinner during approval prompt
                    if self.pause_spinner_callback:
                        self.pause_spinner_callback()

                    # Get approval from user
                    approved = True
                    if self.executor.approval and self.executor.approval.enabled:
                        lines = len(text_response.split("\n"))
                        path = Path(file_path)
                        exists = path.exists()

                        if exists:
                            approval_desc = f"Overwrite {file_path} ({lines} lines)"
                        else:
                            approval_desc = f"Write {lines} lines to {file_path} (new file)"

                        approved = self.executor.approval.request("confirm_write", approval_desc)

                    # Resume spinner
                    if self.resume_spinner_callback:
                        self.resume_spinner_callback()

                    # Execute write if approved
                    if approved:
                        try:
                            path = Path(file_path)
                            path.parent.mkdir(parents=True, exist_ok=True)

                            with open(path, "w", encoding="utf-8") as f:
                                f.write(text_response)

                            result_msg = f"Successfully wrote {len(text_response)} characters to {file_path}"
                            print(f"[AUTO-CONFIRM] {result_msg}")

                            # Clear pending draft
                            self.pending_draft = None

                            # Continue to next turn
                            self.messages.append({"role": "assistant", "content": response.content})
                            self.messages.append({
                                "role": "user",
                                "content": f"File successfully written. {result_msg}"
                            })
                            continue

                        except Exception as e:
                            error_msg = f"Error writing file: {e}"
                            print(f"[AUTO-CONFIRM] Error: {error_msg}")

                            # Clear pending draft on error
                            self.pending_draft = None

                            # Continue with error message
                            self.messages.append({"role": "assistant", "content": response.content})
                            self.messages.append({
                                "role": "user",
                                "content": f"Failed to write file. {error_msg}"
                            })
                            continue
                    else:
                        # User denied approval
                        print(f"[AUTO-CONFIRM] User denied permission")

                        # Clear pending draft
                        self.pending_draft = None

                        # Continue with denial message
                        self.messages.append({"role": "assistant", "content": response.content})
                        self.messages.append({
                            "role": "user",
                            "content": "User denied permission for this action. Please ask what they would like to do instead."
                        })
                        continue

                # No pending draft, return text response
                print(f"\n[COMPLETE] No tool calls, returning text response")
                return text_response

            # Process tool calls
            self.messages.append({"role": "assistant", "content": response.content})

            print(f"\n[TOOL EXECUTION] Executing {len(tool_uses)} tool(s)...")

            tool_results = []

            # Extract text from current response for confirm_write auto-fill
            text_blocks = [
                block.text for block in response.content if isinstance(block, TextBlock)
            ]
            current_response_text = "\n".join(text_blocks)

            for idx, tool_use in enumerate(tool_uses):
                print(f"\n  Tool {idx + 1}: {tool_use.name}")

                # Special handling for confirm_write: auto-fill content from current response
                tool_input = dict(tool_use.input)  # Make a copy

                if tool_use.name == "confirm_write" and "content" not in tool_input:
                    if current_response_text.strip():
                        print(f"    [AUTO-FILL] confirm_write missing content, using current response text ({len(current_response_text)} chars)")
                        tool_input["content"] = current_response_text
                    else:
                        print(f"    [ERROR] confirm_write missing content and no text in current response")

                # Show input for debugging
                input_str = str(tool_input)
                if len(input_str) > 150:
                    print(f"    Input: {input_str[:150]}...")
                else:
                    print(f"    Input: {input_str}")

                # Pause spinner for AskUserQuestion to allow clean user input
                if tool_use.name == "AskUserQuestion" and self.pause_spinner_callback:
                    self.pause_spinner_callback()

                result = self.executor.execute(tool_use.name, tool_input)

                # Resume spinner after AskUserQuestion
                if tool_use.name == "AskUserQuestion" and self.resume_spinner_callback:
                    self.resume_spinner_callback()

                # Track draft_write for auto-confirm in next turn
                if tool_use.name == "draft_write" and result.success:
                    self.pending_draft = {"file_path": tool_input["file_path"]}
                    print(f"    [PENDING] Draft registered for auto-confirm: {tool_input['file_path']}")

                print(f"    Success: {result.success}")
                if result.success:
                    print(f"    Output: {result.output[:200]}...")
                else:
                    print(f"    Error: {result.error}")

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": self._format_tool_result(result),
                    }
                )

            self.messages.append({"role": "user", "content": tool_results})
            print(f"\n[FEEDBACK] Tool results added to conversation")

            # Check context size after each turn
            self._check_context_size()

        print(f"\n{'='*60}")
        print(f"[MAX TURNS] Reached maximum turns ({self.max_turns})")
        print(f"{'='*60}\n")
        return "Max turns reached. Please continue with a new message."

    def _call_llm(self, force_tool: bool = False) -> Message:
        """Call the LLM with current messages."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": self.system_prompt,
            "tools": self.executor.get_tool_definitions(),
            "messages": self.messages,
        }

        # Force tool use on first turn to encourage action
        if force_tool:
            kwargs["tool_choice"] = {"type": "any"}

        # Show LLM request
        print(f"\n[LLM REQUEST]")
        for i, msg in enumerate(self.messages, 1):
            role = msg['role']
            content = msg['content']

            if isinstance(content, str):
                preview = content[:150] + "..." if len(content) > 150 else content
                print(f"  #{i} {role.upper()}: {preview}")
            elif isinstance(content, list):
                # Check if it's tool results or assistant content
                if all(isinstance(item, dict) and item.get('type') == 'tool_result' for item in content):
                    print(f"  #{i} {role.upper()}: [Tool Results x{len(content)}]")
                    for j, item in enumerate(content[:2], 1):  # Show first 2 tool results
                        result_preview = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
                        print(f"      Result {j}: {result_preview}")
                    if len(content) > 2:
                        print(f"      ... and {len(content) - 2} more")
                else:
                    # Assistant message with mixed content
                    for item in content:
                        if hasattr(item, 'type'):
                            if item.type == 'tool_use':
                                print(f"  #{i} {role.upper()}: Tool={item.name}, Input={str(item.input)[:80]}...")
                            elif item.type == 'text':
                                print(f"  #{i} {role.upper()}: {item.text[:100]}...")

        try:
            response = self.client.messages.create(**kwargs)
        except RateLimitError as e:
            print(f"\n{'='*60}")
            print(f"[API ERROR] Rate Limit Exceeded")
            print(f"{'='*60}")
            print(f"[ERROR] Claude API rate limit reached.")
            print(f"[ERROR] {str(e)}")
            print(f"\n[SUGGESTION] Please try one of the following:")
            print(f"  1. Wait a few moments and try again")
            print(f"  2. Use 'reset' to clear conversation history")
            print(f"  3. Reduce the size of your request")
            print(f"{'='*60}\n")
            raise
        except APIError as e:
            print(f"\n{'='*60}")
            print(f"[API ERROR] Claude API Error")
            print(f"{'='*60}")
            print(f"[ERROR] Failed to communicate with Claude API.")
            print(f"[ERROR] {str(e)}")
            print(f"\n[SUGGESTION] Please check:")
            print(f"  1. Your internet connection")
            print(f"  2. API key is valid (ANTHROPIC_API_KEY)")
            print(f"  3. Anthropic API status: https://status.anthropic.com")
            print(f"{'='*60}\n")
            raise
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"[ERROR] Unexpected Error")
            print(f"{'='*60}")
            print(f"[ERROR] {str(e)}")
            print(f"{'='*60}\n")
            raise

        # Show LLM response
        print(f"\n[LLM RESPONSE]")
        for i, block in enumerate(response.content, 1):
            if isinstance(block, ToolUseBlock):
                print(f"  #{i} ToolUse: {block.name}")
                print(f"      Input: {str(block.input)[:150]}...")
            elif isinstance(block, TextBlock):
                print(f"  #{i} Text: {block.text[:150]}...")

        return response

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

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Simple estimation: ~4 characters per token on average
        return len(text) // 4

    def _count_messages_tokens(self) -> int:
        """Count total tokens in message history."""
        total = 0

        for msg in self.messages:
            content = msg.get("content", "")

            if isinstance(content, str):
                total += self._estimate_tokens(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        # Tool result or structured content
                        item_str = str(item.get("content", ""))
                        total += self._estimate_tokens(item_str)
                    elif hasattr(item, "text"):
                        # TextBlock
                        total += self._estimate_tokens(item.text)

        # Add system prompt tokens
        total += self._estimate_tokens(self.system_prompt)

        return total

    def _check_context_size(self) -> None:
        """Check and warn if context is getting large."""
        token_count = self._count_messages_tokens()

        # Auto-compact if threshold reached
        if self._should_compact():
            self._compact_context()
            return  # Exit after compaction

        # Warnings if not compacting
        if token_count > self.max_context_tokens:
            print(f"\n[WARNING] Context size ({token_count:,} tokens) exceeds limit ({self.max_context_tokens:,} tokens)")
            print(f"[WARNING] Consider using 'reset' command to clear history")
        elif token_count > self.max_context_tokens * 0.8:
            print(f"\n[INFO] Context size: {token_count:,} / {self.max_context_tokens:,} tokens (80%+)")

    def get_context_usage(self) -> dict[str, any]:
        """Get current context usage information."""
        token_count = self._count_messages_tokens()
        percentage = (token_count / self.max_context_tokens) * 100

        return {
            "current": token_count,
            "max": self.max_context_tokens,
            "percentage": percentage,
            "messages": len(self.messages),
        }

    def reset(self) -> None:
        """Reset the conversation history."""
        self.messages = []

    def _should_compact(self) -> bool:
        """Check if context compaction is needed."""
        if not self.enable_auto_compaction:
            return False

        # Need at least preserve_recent_messages + 2 to have something to compact
        if len(self.messages) <= self.preserve_recent_messages + 2:
            return False

        token_count = self._count_messages_tokens()
        threshold = int(self.max_context_tokens * self.compaction_threshold)

        return token_count >= threshold

    def _generate_summary(self, messages_to_summarize: list[dict[str, Any]]) -> str:
        """Generate a summary of messages using AI."""
        summary_prompt = """You have been assisting the user but the conversation is getting long.
Create a concise summary that preserves essential information for continuing the work.

Include in your summary:

1. **Task Overview**
   - User's main request and goals
   - Any constraints or requirements

2. **Work Completed**
   - Files read, created, or modified (with exact paths)
   - Commands executed successfully
   - Key findings or outputs

3. **Important Context**
   - Variable names, function names, class names mentioned
   - Technical decisions made and reasons
   - Errors encountered and how they were resolved
   - User preferences or style requirements

4. **Current State**
   - What needs to be done next
   - Any blockers or open questions

Keep the summary concise (under 1000 words) but preserve ALL critical details.
Focus on facts, not process. Include specific names (files, variables, etc.).
Wrap your entire summary in <summary></summary> tags."""

        try:
            # Clean messages to remove tool content (only keep text for summary)
            # This avoids passing tool_use/tool_result to the summary API
            cleaned_messages = []
            for msg in messages_to_summarize:
                role = msg.get("role")
                content = msg.get("content")

                if isinstance(content, str):
                    # Simple text message - keep as is
                    cleaned_messages.append(msg)
                elif isinstance(content, list):
                    # Mixed content - extract only text parts
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "tool_use":
                                tool_name = item.get("name", "unknown")
                                tool_input = str(item.get("input", {}))[:100]
                                text_parts.append(f"[Used tool: {tool_name} with {tool_input}...]")
                            elif item.get("type") == "tool_result":
                                result = str(item.get("content", ""))[:200]
                                text_parts.append(f"[Tool result: {result}...]")
                        elif hasattr(item, "text"):
                            text_parts.append(item.text)

                    if text_parts:
                        cleaned_messages.append({
                            "role": role,
                            "content": "\n".join(text_parts)
                        })

            # Call Claude API for summarization
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="You are a helpful assistant that creates concise summaries.",
                messages=cleaned_messages + [
                    {"role": "user", "content": summary_prompt}
                ],
            )

            # Extract text from response
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )

            # Extract summary from tags
            import re
            match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            else:
                return text.strip()

        except Exception as e:
            print(f"[ERROR] Failed to generate summary: {e}")
            # Fallback: simple concatenation
            return "Previous conversation covered multiple topics. Context preserved."

    def _replace_with_summary(self, summary: str) -> None:
        """Replace old messages with summary."""
        # Extract recent messages
        recent_messages = self.messages[-self.preserve_recent_messages:]

        # IMPORTANT: Validate that we don't break tool_use/tool_result pairs
        # If the first recent message is a tool_result, we need to include the previous tool_use
        if recent_messages and recent_messages[0].get("role") == "user":
            content = recent_messages[0].get("content", [])
            # Check if content is a list of tool results
            if isinstance(content, list) and any(
                isinstance(item, dict) and item.get("type") == "tool_result"
                for item in content
            ):
                # Need to find the corresponding tool_use in the previous message
                # Include one more message (the assistant message with tool_use)
                if len(self.messages) > self.preserve_recent_messages:
                    recent_messages = self.messages[-(self.preserve_recent_messages + 1):]
                    print(f"[INFO] Extended recent messages to preserve tool_use/tool_result pairs")

        # Create summary message
        summary_message = {
            "role": "user",
            "content": f"[Previous conversation summary]\n\n{summary}"
        }

        # Replace history
        self.messages = [summary_message] + recent_messages

    def _compact_context(self) -> None:
        """Perform context compaction by summarizing old messages."""
        print(f"\n{'='*60}")
        print(f"[CONTEXT COMPACTION] Starting...")
        print(f"{'='*60}")

        # Pre-compaction stats
        original_count = len(self.messages)
        original_tokens = self._count_messages_tokens()

        print(f"[INFO] Current state: {original_count} messages, {original_tokens:,} tokens")
        print(f"[INFO] Preserving recent {self.preserve_recent_messages} messages")

        # Find safe split point (don't break tool_use/tool_result pairs)
        preserve_count = self.preserve_recent_messages

        # Check if we need to extend to preserve tool pairs
        if len(self.messages) > preserve_count:
            first_recent = self.messages[-preserve_count]

            # If first recent message is a tool_result, include the previous tool_use
            if first_recent.get("role") == "user":
                content = first_recent.get("content", [])
                if isinstance(content, list) and any(
                    isinstance(item, dict) and item.get("type") == "tool_result"
                    for item in content
                ):
                    preserve_count += 1
                    print(f"[INFO] Extended preserve count to {preserve_count} to keep tool pairs intact")

        # Split messages at safe point
        messages_to_summarize = self.messages[:-preserve_count]

        print(f"[INFO] Summarizing {len(messages_to_summarize)} older messages...")

        # Generate summary (clean messages without tool_result orphans)
        summary = self._generate_summary(messages_to_summarize)

        print(f"[INFO] Summary generated ({len(summary)} characters)")

        # Replace history (using updated preserve_count)
        recent_messages = self.messages[-preserve_count:]
        summary_message = {
            "role": "user",
            "content": f"[Previous conversation summary]\n\n{summary}"
        }
        self.messages = [summary_message] + recent_messages

        # Post-compaction stats
        new_count = len(self.messages)
        new_tokens = self._count_messages_tokens()
        reduction = ((original_tokens - new_tokens) / original_tokens) * 100

        print(f"[SUCCESS] Compaction complete!")
        print(f"[SUCCESS] Messages: {original_count} → {new_count}")
        print(f"[SUCCESS] Tokens: {original_tokens:,} → {new_tokens:,} ({reduction:.1f}% reduction)")
        print(f"{'='*60}\n")
