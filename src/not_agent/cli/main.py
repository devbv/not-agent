"""CLI entry point."""

import os
import sys
from typing import TYPE_CHECKING

import click
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

from anthropic import RateLimitError, APIError

from not_agent.agent import AgentLoop
from not_agent.agent.approval import ApprovalManager
from not_agent.agent.executor import ToolExecutor
from not_agent.llm.claude import ClaudeClient
from not_agent.tools import TodoManager, get_all_tools


console = Console()


class TodoSpinner:
    """Spinner that shows todo list and current task using Rich Live display."""

    def __init__(self, console: Console, todo_manager: TodoManager):
        self.console = console
        self.todo_manager = todo_manager
        self._live: Live | None = None

    def _build_display(self) -> Group:
        """Build the complete display with todo list and spinner."""
        parts = []

        # Todo list
        todos = self.todo_manager.get_todos()
        if todos:
            status_icons = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}
            summary = self.todo_manager.get_summary()

            # Header
            parts.append(Text(f"📋 Tasks ({summary['completed']}/{summary['total']})"))

            # Todo items
            for todo in todos:
                status = todo.get("status", "pending")
                icon = status_icons.get(status, "⬜")
                content = todo.get("content", "")

                if status == "completed":
                    parts.append(Text(f"  {icon} {content}", style="strike"))
                elif status == "in_progress":
                    parts.append(Text(f"  {icon} {content}", style="bold"))
                else:
                    parts.append(Text(f"  {icon} {content}"))

            # Spacing
            parts.append(Text(""))

        # Spinner line with actual Spinner object
        current_task = self.todo_manager.get_current_task()

        if current_task:
            summary = self.todo_manager.get_summary()
            progress = f"({summary['completed']}/{summary['total']})"

            # Truncate long task names
            max_len = 50
            if len(current_task) > max_len:
                current_task = current_task[:max_len-3] + "..."

            spinner_text = f"[bold green]Thinking...[/bold green] [dim]|[/dim] [yellow]🔄 {current_task}[/yellow] [dim]{progress}[/dim]"
        else:
            spinner_text = "[bold green]Thinking...[/bold green]"

        # Use Spinner directly as renderable
        parts.append(Spinner("dots", text=spinner_text, style="green"))

        return Group(*parts)

    def start(self) -> None:
        """Start the live display."""
        if self._live is None:
            self._live = Live(
                self._build_display(),
                console=self.console,
                refresh_per_second=10,
                transient=True,  # Remove when stopped
            )
            self._live.start()
        else:
            self._live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self._live:
            self._live.stop()

    def update(self) -> None:
        """Update the live display with current todo state."""
        if self._live:
            self._live.update(self._build_display())


def show_todo_panel(todo_manager: TodoManager) -> None:
    """Show the current todo list as a panel."""
    todos = todo_manager.get_todos()
    if not todos:
        return  # 할 일이 없으면 표시하지 않음

    summary = todo_manager.get_summary()

    # 상태별 아이콘
    status_icons = {
        "completed": "[green]✅[/green]",
        "in_progress": "[yellow]🔄[/yellow]",
        "pending": "[dim]⬜[/dim]",
    }

    # Todo 항목 포맷팅
    lines = []
    for todo in todos:
        status = todo.get("status", "pending")
        icon = status_icons.get(status, "⬜")
        content = todo.get("content", "")

        # 상태에 따라 텍스트 스타일 적용
        if status == "completed":
            lines.append(f"{icon} [dim strikethrough]{content}[/dim strikethrough]")
        elif status == "in_progress":
            lines.append(f"{icon} [bold]{content}[/bold]")
        else:
            lines.append(f"{icon} {content}")

    # 패널 제목
    title = f"📋 Tasks ({summary['completed']}/{summary['total']} completed)"

    console.print(Panel(
        "\n".join(lines),
        title=title,
        border_style="blue",
    ))


def show_context_status(agent_loop: 'AgentLoop') -> None:
    """Show context usage status with a progress bar."""
    usage = agent_loop.get_context_usage()
    percentage = usage['percentage']
    current = usage['current']
    max_tokens = usage['max']
    messages = usage['messages']

    # Choose color based on usage
    if percentage >= 75:
        color = "red"
        status = "⚠️  High"
    elif percentage >= 50:
        color = "yellow"
        status = "⚡ Medium"
    else:
        color = "green"
        status = "✓ Good"

    # Create a simple text-based progress bar
    bar_width = 30
    # Cap at 100% for visual representation
    display_percentage = min(percentage, 100)
    filled = int(bar_width * display_percentage / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    console.print(
        f"\n[dim]Context: [{color}]{bar}[/{color}] "
        f"{percentage:.1f}% ({current:,}/{max_tokens:,} tokens, {messages} msgs) {status}[/dim]"
    )


def check_api_key() -> None:
    """Check if API key is set."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "[red]Error:[/red] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.\n"
            "다음 명령어로 설정하세요:\n"
            "  [bold]export ANTHROPIC_API_KEY='your-api-key'[/bold]"
        )
        sys.exit(1)


@click.group()
@click.version_option()
def cli() -> None:
    """Not Agent - A coding agent similar to Claude Code."""
    pass


@cli.command()
def chat() -> None:
    """Start an interactive chat session (simple mode, no tools)."""
    check_api_key()

    console.print(
        Panel(
            "[bold blue]Not Agent[/bold blue] - Simple Chat Mode\n"
            "Type [bold]exit[/bold] or [bold]quit[/bold] to end the session.",
            title="Welcome",
        )
    )

    client = ClaudeClient()
    history = FileHistory(".not_agent_history")

    while True:
        try:
            user_input = prompt(
                "\n> ",
                history=history,
                multiline=False,
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                console.print("[dim]Goodbye![/dim]")
                break

            try:
                with console.status("[bold green]Thinking...[/bold green]"):
                    response = client.chat(user_input)

                console.print()
                console.print(Markdown(response))

            except RateLimitError:
                console.print("\n[red bold]⚠️  Rate Limit Exceeded[/red bold]")
                console.print("[yellow]Please wait a moment before trying again.[/yellow]")
            except APIError as e:
                console.print("\n[red bold]⚠️  API Error[/red bold]")
                console.print(f"[yellow]{str(e)}[/yellow]")
                console.print("[dim]Please check your connection and API key.[/dim]")

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit[/dim]")
        except EOFError:
            break


@cli.command()
@click.option(
    "--approval/--no-approval",
    default=True,
    help="Require approval for file modifications (default: enabled)",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug output (shows LLM requests, tool executions, etc.)",
)
def agent(approval: bool, debug: bool) -> None:
    """Start an interactive agent session with tools."""
    check_api_key()

    # Create TodoManager (세션별 인스턴스)
    todo_manager = TodoManager()

    # Create approval manager if enabled
    approval_manager = ApprovalManager(enabled=approval) if approval else None

    # Create executor with approval plugin and TodoManager
    tools = get_all_tools(todo_manager=todo_manager)
    executor = ToolExecutor(tools=tools, approval_manager=approval_manager)

    # Create agent loop with executor and TodoManager
    agent_loop = AgentLoop(executor=executor, todo_manager=todo_manager, debug=debug)

    # Show welcome message
    welcome_msg = (
        "[bold blue]Not Agent[/bold blue] - Agent Mode (with Tools)\n"
        "Type [bold]exit[/bold] or [bold]quit[/bold] to end the session.\n"
        "Type [bold]reset[/bold] to clear conversation history.\n"
        "Type [bold]status[/bold] to show context usage.\n"
        "Type [bold]compact[/bold] to manually compress context."
    )

    if approval:
        welcome_msg += "\n\n[green]✓ Approval mode enabled[/green]\n[dim]You will be asked before file modifications[/dim]"
    else:
        welcome_msg += "\n\n[yellow]⚠️  Approval mode disabled[/yellow]\n[dim]Files will be modified without confirmation (use --approval to enable)[/dim]"

    if debug:
        welcome_msg += "\n[cyan]🔍 Debug mode enabled[/cyan]"

    console.print(Panel(welcome_msg, title="Welcome"))

    history = FileHistory(".not_agent_history")

    while True:
        try:
            user_input = prompt(
                "\n> ",
                history=history,
                multiline=False,
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "reset":
                agent_loop.reset()
                console.print("[dim]Conversation history cleared.[/dim]")
                continue

            if user_input.lower() == "status":
                show_context_status(agent_loop)
                continue

            if user_input.lower() == "compact":
                # Force manual compaction
                if len(agent_loop.messages) <= agent_loop.preserve_recent_messages + 2:
                    console.print("[yellow]Not enough messages to compact.[/yellow]")
                    console.print(f"[dim]Need at least {agent_loop.preserve_recent_messages + 3} messages.[/dim]")
                else:
                    agent_loop._compact_context()
                continue

            try:
                # Create TodoSpinner that shows task list + spinner
                spinner = TodoSpinner(console, todo_manager)
                spinner.start()

                # Set spinner callbacks on approval manager for user input prompts
                if approval_manager:
                    approval_manager.pause_spinner = spinner.stop
                    approval_manager.resume_spinner = spinner.start

                try:
                    # Pass callbacks to stop/start spinner during AskUserQuestion
                    # Also pass update callback to refresh todo display
                    response = agent_loop.run(
                        user_input,
                        pause_spinner_callback=spinner.stop,
                        resume_spinner_callback=spinner.start,
                        update_spinner_callback=spinner.update
                    )
                finally:
                    # Ensure spinner is stopped
                    spinner.stop()

                console.print()
                console.print(Markdown(response))

                # Show todo panel if there are todos (final state)
                show_todo_panel(todo_manager)

                # Show context usage after each response
                show_context_status(agent_loop)

            except RateLimitError:
                console.print("\n[red bold]⚠️  Rate Limit Exceeded[/red bold]")
                console.print("[yellow]Please wait a moment before trying again.[/yellow]")
                console.print("[dim]Tip: You can use 'reset' to reduce context size.[/dim]")
            except APIError as e:
                console.print("\n[red bold]⚠️  API Error[/red bold]")
                console.print(f"[yellow]{str(e)}[/yellow]")
                console.print("[dim]Please check your connection and API key.[/dim]")

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit[/dim]")
        except EOFError:
            break


@cli.command()
@click.argument("message")
def ask(message: str) -> None:
    """Ask a single question and get a response."""
    check_api_key()

    client = ClaudeClient()

    try:
        with console.status("[bold green]Thinking...[/bold green]"):
            response = client.chat(message)

        console.print(Markdown(response))
    except RateLimitError:
        console.print("\n[red bold]⚠️  Rate Limit Exceeded[/red bold]")
        console.print("[yellow]Please wait a moment before trying again.[/yellow]")
        sys.exit(1)
    except APIError as e:
        console.print("\n[red bold]⚠️  API Error[/red bold]")
        console.print(f"[yellow]{str(e)}[/yellow]")
        console.print("[dim]Please check your connection and API key.[/dim]")
        sys.exit(1)


@cli.command()
@click.argument("message")
@click.option(
    "--approval/--no-approval",
    default=True,
    help="Require approval for file modifications (default: enabled)",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug output (shows LLM requests, tool executions, etc.)",
)
def run(message: str, approval: bool, debug: bool) -> None:
    """Run agent with a single task (with tools)."""
    check_api_key()

    # Create TodoManager (세션별 인스턴스)
    todo_manager = TodoManager()

    # Create approval manager if enabled
    approval_manager = ApprovalManager(enabled=approval) if approval else None

    # Create executor with approval plugin and TodoManager
    tools = get_all_tools(todo_manager=todo_manager)
    executor = ToolExecutor(tools=tools, approval_manager=approval_manager)

    # Create agent loop with executor and TodoManager
    agent_loop = AgentLoop(executor=executor, todo_manager=todo_manager, debug=debug)

    if approval:
        console.print("[green]✓ Approval mode enabled[/green]")
        console.print("[dim]You will be asked before file modifications[/dim]\n")
    else:
        console.print("[yellow]⚠️  Approval mode disabled[/yellow]")
        console.print("[dim]Files will be modified without confirmation[/dim]\n")

    if debug:
        console.print("[cyan]🔍 Debug mode enabled[/cyan]\n")

    # Add spacing before spinner
    console.print()

    try:
        # Create TodoSpinner that shows task list + spinner
        spinner = TodoSpinner(console, todo_manager)
        spinner.start()

        # Set spinner callbacks on approval manager for user input prompts
        if approval_manager:
            approval_manager.pause_spinner = spinner.stop
            approval_manager.resume_spinner = spinner.start

        try:
            response = agent_loop.run(
                message,
                pause_spinner_callback=spinner.stop,
                resume_spinner_callback=spinner.start,
                update_spinner_callback=spinner.update
            )
        finally:
            spinner.stop()

        console.print(Markdown(response))

        # Show todo panel if there are todos (final state)
        show_todo_panel(todo_manager)

    except RateLimitError:
        console.print("\n[red bold]⚠️  Rate Limit Exceeded[/red bold]")
        console.print("[yellow]Please wait a moment before trying again.[/yellow]")
    except APIError as e:
        console.print("\n[red bold]⚠️  API Error[/red bold]")
        console.print(f"[yellow]{str(e)}[/yellow]")
        console.print("[dim]Please check your connection and API key.[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
