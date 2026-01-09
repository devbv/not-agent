# Not Agent

A coding agent similar to Claude Code.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Usage

```bash
# Interactive chat
not-agent chat

# Single question
not-agent ask "Write a hello world in Python"
```

## Development

```bash
# Run tests
pytest

# Type check
mypy src

# Lint
ruff check src

# Format
black src
```
