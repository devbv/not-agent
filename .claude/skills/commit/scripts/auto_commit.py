#!/usr/bin/env python3
"""
Automated git commit helper that analyzes changes and creates commits.
"""
import subprocess
import sys
from pathlib import Path


def run_git_command(args: list[str]) -> tuple[str, int]:
    """Run git command and return output and exit code."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout + result.stderr, result.returncode
    except Exception as e:
        return str(e), 1


def get_git_status() -> str:
    """Get git status output."""
    output, _ = run_git_command(["status", "--short"])
    return output


def get_git_diff() -> str:
    """Get both staged and unstaged diffs."""
    staged, _ = run_git_command(["diff", "--cached"])
    unstaged, _ = run_git_command(["diff"])
    return f"=== Staged Changes ===\n{staged}\n\n=== Unstaged Changes ===\n{unstaged}"


def get_recent_commits(count: int = 5) -> str:
    """Get recent commit messages to learn the style."""
    output, _ = run_git_command(["log", f"-{count}", "--pretty=format:%s"])
    return output


def stage_all_changes() -> bool:
    """Stage all changes."""
    _, code = run_git_command(["add", "."])
    return code == 0


def create_commit(message: str) -> tuple[bool, str]:
    """Create a commit with the given message."""
    output, code = run_git_command(["commit", "-m", message])
    return code == 0, output


def main():
    """Main function to gather git information."""
    print("=== GIT STATUS ===")
    print(get_git_status())
    print("\n=== GIT DIFF ===")
    print(get_git_diff())
    print("\n=== RECENT COMMITS ===")
    print(get_recent_commits())


if __name__ == "__main__":
    main()
