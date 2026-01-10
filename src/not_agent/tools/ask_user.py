"""AskUserQuestion tool - Ask the user for clarification or confirmation."""

from typing import Any

from rich.console import Console
from rich.panel import Panel

from .base import BaseTool, ToolResult


console = Console()


class AskUserQuestionTool(BaseTool):
    """Tool for asking the user questions when clarification is needed."""

    name = "AskUserQuestion"
    description = (
        "Ask the user a question when you need clarification, confirmation, "
        "or have to choose between multiple approaches. "
        "Use this when you're unsure about requirements or need user input."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "question": {
                "type": "string",
                "description": "The question to ask the user. Be clear and specific.",
                "required": True,
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of choices for the user to select from (2-10 options). "
                    "If provided, user will pick one. If omitted, user can answer freely."
                ),
                "required": False,
            },
        }

    def execute(
        self, question: str, options: list[str] | None = None
    ) -> ToolResult:
        """Ask the user a question and return their answer."""
        try:
            # Display the question prominently
            console.print()
            console.print(
                Panel(
                    f"[bold yellow]❓ Agent Question[/bold yellow]\n\n{question}",
                    border_style="yellow",
                )
            )

            if options:
                # Validate options
                if len(options) < 2:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Must provide at least 2 options for a choice question",
                    )

                if len(options) > 10:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Too many options (max 10)",
                    )

                # Show options in terminal (simpler than dialog)
                console.print("\n[dim]Please select an option (enter number):[/dim]")
                for i, opt in enumerate(options, 1):
                    console.print(f"  [cyan]{i}[/cyan]. {opt}")

                # Get user input
                while True:
                    try:
                        choice = input(f"\n→ Enter choice (1-{len(options)}): ").strip()

                        if not choice:
                            console.print("[yellow]Please enter a number[/yellow]")
                            continue

                        choice_num = int(choice)
                        if 1 <= choice_num <= len(options):
                            selected_option = options[choice_num - 1]
                            console.print(f"[green]→[/green] You selected: {selected_option}\n")

                            return ToolResult(
                                success=True,
                                output=f"User selected: {selected_option}",
                            )
                        else:
                            console.print(f"[yellow]Please enter a number between 1 and {len(options)}[/yellow]")
                    except ValueError:
                        console.print("[yellow]Please enter a valid number[/yellow]")
                    except KeyboardInterrupt:
                        return ToolResult(
                            success=False,
                            output="",
                            error="User cancelled the question",
                        )

            else:
                # Free-form question
                console.print("[dim]Please type your answer:[/dim]")

                answer = input("→ ").strip()

                if not answer:
                    return ToolResult(
                        success=False,
                        output="",
                        error="User provided no answer",
                    )

                console.print()

                return ToolResult(
                    success=True,
                    output=f"User answered: {answer}",
                )

        except KeyboardInterrupt:
            return ToolResult(
                success=False,
                output="",
                error="User interrupted (Ctrl+C)",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error asking question: {str(e)}",
            )
