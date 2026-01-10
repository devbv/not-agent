"""CLI entry point."""

import os
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

from anthropic import RateLimitError, APIError

from not_agent.agent import AgentLoop
from not_agent.agent.approval import ApprovalManager
from not_agent.agent.executor import ToolExecutor
from not_agent.llm.claude import ClaudeClient


console = Console()


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
def agent(approval: bool) -> None:
    """Start an interactive agent session with tools."""
    check_api_key()

    # Create approval manager if enabled
    approval_manager = ApprovalManager(enabled=approval) if approval else None

    # Create executor with approval plugin
    executor = ToolExecutor(approval_manager=approval_manager)

    # Create agent loop with executor
    agent_loop = AgentLoop(executor=executor)

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
                # Use a status object that can be stopped and restarted
                status = console.status("[bold green]Thinking...[/bold green]")
                status.start()

                try:
                    # Pass callbacks to stop/start spinner during AskUserQuestion
                    response = agent_loop.run(
                        user_input,
                        pause_spinner_callback=status.stop,
                        resume_spinner_callback=status.start
                    )
                finally:
                    # Ensure spinner is stopped
                    status.stop()

                console.print()
                console.print(Markdown(response))

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
def run(message: str, approval: bool) -> None:
    """Run agent with a single task (with tools)."""
    check_api_key()

    # Create approval manager if enabled
    approval_manager = ApprovalManager(enabled=approval) if approval else None

    # Create executor with approval plugin
    executor = ToolExecutor(approval_manager=approval_manager)

    # Create agent loop with executor
    agent_loop = AgentLoop(executor=executor)

    if approval:
        console.print("[green]✓ Approval mode enabled[/green]")
        console.print("[dim]You will be asked before file modifications[/dim]\n")
    else:
        console.print("[yellow]⚠️  Approval mode disabled[/yellow]")
        console.print("[dim]Files will be modified without confirmation[/dim]\n")

    try:
        with console.status("[bold green]Working...[/bold green]"):
            response = agent_loop.run(message)

        console.print(Markdown(response))
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
