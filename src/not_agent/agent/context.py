"""Context size management and compaction."""

import re
from typing import Any, TYPE_CHECKING

from .message import TextPart, ToolUsePart, ToolResultPart

if TYPE_CHECKING:
    from not_agent.config import Config
    from not_agent.provider import BaseProvider
    from .session import Session, Message


class ContextManager:
    """Context size management."""

    def __init__(
        self,
        config: "Config",
        provider: "BaseProvider",
        preserve_recent_messages: int = 3,
    ) -> None:
        self.config = config
        self.provider = provider
        self.limit = config.get("context_limit", 100_000)
        self.threshold = config.get("compact_threshold", 0.75)
        self.preserve_recent_messages = preserve_recent_messages

    def estimate_tokens(self, session: "Session") -> int:
        """Estimate token count of session."""
        text = str(session.to_api_format())
        # Rough estimate: 1 token per 4 characters
        return len(text) // 4

    def should_compact(self, session: "Session") -> bool:
        """Check if compaction is needed."""
        # Check minimum message count
        if len(session) <= self.preserve_recent_messages + 2:
            return False

        tokens = self.estimate_tokens(session)
        return tokens >= self.limit * self.threshold

    def get_usage_ratio(self, session: "Session") -> float:
        """Return context usage ratio."""
        return self.estimate_tokens(session) / self.limit

    def get_usage_info(self, session: "Session") -> dict[str, Any]:
        """Return context usage info."""
        token_count = self.estimate_tokens(session)
        percentage = (token_count / self.limit) * 100

        return {
            "current": token_count,
            "max": self.limit,
            "percentage": percentage,
            "messages": len(session),
        }

    def compact(
        self,
        session: "Session",
        system_prompt: str = "",
        debug_log: Any = None,
    ) -> None:
        """
        Perform session compaction.

        Summarize old messages with AI and replace with new session.
        """
        if debug_log:
            debug_log("[CONTEXT COMPACTION] Starting...")

        messages = session.messages
        original_count = len(messages)
        original_tokens = self.estimate_tokens(session)

        if debug_log:
            debug_log(f"[INFO] Current state: {original_count} messages, {original_tokens:,} tokens")
            debug_log(f"[INFO] Preserving recent {self.preserve_recent_messages} messages")

        # Find safe split point
        preserve_count = self._find_safe_split_point(messages)

        if debug_log:
            debug_log(f"[INFO] Safe preserve count: {preserve_count}")

        # Split messages
        messages_to_summarize = messages[:-preserve_count]
        recent_messages = messages[-preserve_count:]

        if debug_log:
            debug_log(f"[INFO] Summarizing {len(messages_to_summarize)} older messages...")

        # Generate summary with AI
        summary = self._generate_summary(messages_to_summarize, system_prompt)

        if debug_log:
            debug_log(f"[INFO] Summary generated ({len(summary)} characters)")

        # Build new message list (in API format)
        summary_message = {
            "role": "user",
            "content": f"[Previous conversation summary]\n\n{summary}"
        }
        new_messages = [summary_message] + [msg.to_api_format() for msg in recent_messages]

        # Update session
        session.set_messages(new_messages)

        # Log results
        if debug_log:
            new_count = len(session)
            new_tokens = self.estimate_tokens(session)
            reduction = ((original_tokens - new_tokens) / original_tokens) * 100

            debug_log(f"[SUCCESS] Compaction complete!")
            debug_log(f"[SUCCESS] Messages: {original_count} → {new_count}")
            debug_log(f"[SUCCESS] Tokens: {original_tokens:,} → {new_tokens:,} ({reduction:.1f}% reduction)")

    def _find_safe_split_point(self, messages: list["Message"]) -> int:
        """Find split point that doesn't break tool_use/tool_result pairs."""
        preserve_count = self.preserve_recent_messages

        if len(messages) <= preserve_count:
            return len(messages)

        # Check if first preserved message contains tool_result
        first_recent = messages[-preserve_count]
        if first_recent.role == "user":
            has_tool_result = any(
                isinstance(part, ToolResultPart)
                for part in first_recent.parts
            )
            if has_tool_result:
                # Also include previous message with tool_use
                preserve_count += 1

        return min(preserve_count, len(messages))

    def _generate_summary(
        self,
        messages_to_summarize: list["Message"],
        system_prompt: str,
    ) -> str:
        """Generate message summary using AI."""
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
            # Clean messages (simplify tool content, keep text)
            cleaned_messages = self._clean_messages_for_summary(messages_to_summarize)

            # Call AI
            response = self.provider.chat(
                messages=cleaned_messages + [
                    {"role": "user", "content": summary_prompt}
                ],
                system="You are a helpful assistant that creates concise summaries.",
                max_tokens=8 * 1024,
            )

            # Extract text from response
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )

            # Extract <summary> tag
            match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            else:
                return text.strip()

        except Exception as e:
            # Fallback: simple message
            return f"Previous conversation covered multiple topics. (Error: {e})"

    def _clean_messages_for_summary(
        self,
        messages: list["Message"],
    ) -> list[dict[str, Any]]:
        """Clean messages for summary (simplify tool-related content)."""
        cleaned = []

        for msg in messages:
            text_parts = []

            for part in msg.parts:
                if isinstance(part, TextPart):
                    text_parts.append(part.text)
                elif isinstance(part, ToolUsePart):
                    tool_input_str = str(part.tool_input)[:100]
                    text_parts.append(f"[Used tool: {part.tool_name} with {tool_input_str}...]")
                elif isinstance(part, ToolResultPart):
                    result_str = part.content[:200] if part.content else ""
                    text_parts.append(f"[Tool result: {result_str}...]")

            if text_parts:
                cleaned.append({
                    "role": msg.role,
                    "content": "\n".join(text_parts)
                })

        return cleaned
