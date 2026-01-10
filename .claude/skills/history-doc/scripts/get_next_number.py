#!/usr/bin/env python3
"""
Get the next available history file number.
"""
import os
import sys
import re
from pathlib import Path


def get_next_history_number(history_dir: str = "history") -> str:
    """
    Find the next available history file number.

    Args:
        history_dir: Path to history directory (default: "history")

    Returns:
        Next number as zero-padded string (e.g., "009")
    """
    history_path = Path(history_dir)

    if not history_path.exists():
        return "001"

    # Find all files starting with numbers
    pattern = re.compile(r'^(\d{3})_')
    numbers = []

    for file in history_path.iterdir():
        if file.is_file():
            match = pattern.match(file.name)
            if match:
                numbers.append(int(match.group(1)))

    if not numbers:
        return "001"

    next_num = max(numbers) + 1
    return f"{next_num:03d}"


def main():
    """CLI interface"""
    if len(sys.argv) > 1:
        history_dir = sys.argv[1]
    else:
        history_dir = "history"

    next_num = get_next_history_number(history_dir)
    print(next_num)
    return 0


if __name__ == "__main__":
    sys.exit(main())
