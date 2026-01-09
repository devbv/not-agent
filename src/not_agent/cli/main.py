"""CLI entry point."""

import os
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

from not_agent.agent import AgentLoop
from not_agent.llm.claude import ClaudeClient


console = Console()


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

            with console.status("[bold green]Thinking...[/bold green]"):
                response = client.chat(user_input)

            console.print()
            console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit[/dim]")
        except EOFError:
            break


@cli.command()
def agent() -> None:
    """Start an interactive agent session with tools."""
    check_api_key()

    console.print(
        Panel(
            "[bold blue]Not Agent[/bold blue] - Agent Mode (with Tools)\n"
            "Type [bold]exit[/bold] or [bold]quit[/bold] to end the session.\n"
            "Type [bold]reset[/bold] to clear conversation history.",
            title="Welcome",
        )
    )

    agent_loop = AgentLoop()
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

            with console.status("[bold green]Thinking...[/bold green]"):
                response = agent_loop.run(user_input)

            console.print()
            console.print(Markdown(response))

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

    with console.status("[bold green]Thinking...[/bold green]"):
        response = client.chat(message)

    console.print(Markdown(response))


@cli.command()
@click.argument("message")
def run(message: str) -> None:
    """Run agent with a single task (with tools)."""
    check_api_key()

    agent_loop = AgentLoop()

    with console.status("[bold green]Working...[/bold green]"):
        response = agent_loop.run(message)

    console.print(Markdown(response))


if __name__ == "__main__":
    cli()
