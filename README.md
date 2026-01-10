# Not Agent

A coding agent built with Claude API, featuring tool-based automation and intelligent file operations.

## Features

### Core Tools
- **Read/Write/Edit**: File operations with smart editing
- **Glob/Grep**: Pattern-based file search and content search
- **Bash**: Shell command execution
- **WebSearch/WebFetch**: Web search and content retrieval

### Agent Capabilities
- Autonomous task execution with tool chaining
- Interactive agent mode with persistent conversation
- Intelligent file modification and code generation
- Debug logging for transparency

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/not-agent.git
cd not-agent

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Requirements
- Python 3.11+
- Claude API key (set as `ANTHROPIC_API_KEY` environment variable)

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

### Agent Mode (Default)
Interactive mode with full tool access:

```bash
not-agent agent
```

The agent can:
- Search and read files
- Modify code and create new files
- Execute shell commands
- Search the web for information
- Chain multiple operations autonomously

### Chat Mode
Simple conversation without tools:

```bash
not-agent chat
```

### Single Task
Execute a single task and exit:

```bash
not-agent run "Add error handling to main.py"
```

### Ask a Question
Get a quick answer without tools:

```bash
not-agent ask "What is the difference between lists and tuples?"
```

## Project Structure

```
not-agent/
├── src/
│   └── not_agent/
│       ├── agent/          # Agent loop and orchestration
│       │   └── loop.py     # Main agent loop with tool execution
│       ├── tools/          # Tool implementations
│       │   ├── read.py     # File reading
│       │   ├── write.py    # File writing
│       │   ├── edit.py     # File editing
│       │   ├── glob_tool.py # File pattern matching
│       │   ├── grep.py     # Content search
│       │   ├── bash.py     # Shell execution
│       │   ├── web_search.py  # Web search
│       │   └── web_fetch.py   # URL fetching
│       ├── llm/            # LLM integration
│       │   └── claude.py   # Claude API wrapper
│       └── cli/            # Command-line interface
│           └── main.py     # CLI entry point
├── .claude/                # Claude Code skills
│   └── skills/
│       └── commit/         # Automated commit workflow
└── history/                # Development history and decisions
```

## Skills

This project includes Claude Code skills for enhanced workflows:

### Commit Skill
Automated git commit workflow with:
- Conventional Commits format
- Security validation (secrets detection)
- Auto-commit on phase completion
- Co-Authored-By attribution

Load the skill:
```bash
# The commit.skill file can be imported into Claude Code
```

## Development

### Running Tests
```bash
pytest
```

### Type Checking
```bash
mypy src
```

### Linting
```bash
ruff check src
```

### Formatting
```bash
black src
```

## Configuration

The agent uses `claude-haiku-4-5-20251001` by default for cost efficiency. To change the model, modify `src/not_agent/agent/loop.py`:

```python
def __init__(
    self,
    model: str = "claude-sonnet-4-5-20250929",  # Change here
    max_turns: int = 20,
) -> None:
```

## Examples

### Code Generation
```bash
not-agent run "Create a FastAPI server with user authentication"
```

### Bug Fixing
```bash
not-agent agent
> Find and fix the bug in src/main.py where dates are formatted incorrectly
```

### Research
```bash
not-agent run "Search for the latest Python best practices for async/await"
```

### File Operations
```bash
not-agent run "Find all TODO comments in the codebase and create a summary"
```

## Architecture

The agent follows a tool-based architecture:

1. **User Input** → Agent receives task
2. **LLM Planning** → Claude decides which tools to use
3. **Tool Execution** → Tools perform operations (read, write, search, etc.)
4. **Result Feedback** → Results fed back to LLM
5. **Iteration** → Process repeats until task completion

Maximum 20 turns per conversation to prevent infinite loops.

## Contributing

See [CLAUDE.md](CLAUDE.md) for project context and development guidelines.

## License

MIT

## Roadmap

- [x] Phase 1: Basic infrastructure and LLM integration
- [x] Phase 2: Core tools (Read, Write, Edit, Glob, Grep, Bash)
- [x] Phase 2 Extension: Web tools (WebSearch, WebFetch)
- [ ] Phase 3: Advanced agent loop features
- [ ] Phase 4: Multi-agent collaboration
- [ ] Phase 5: Plugin system

See [history/](history/) for detailed development progress.
