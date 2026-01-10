# Commit Message Examples

This file contains examples of good commit messages for reference.

## Feature Additions

### Adding New Tool

```
feat(tools): add WebSearch tool for web queries

Implement WebSearch tool using Claude API's web search capability.
Returns search results with source links formatted as markdown.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Adding New CLI Command

```
feat(cli): add 'run' command for single task execution

New command executes a single task with tool access and exits.
Useful for scripting and automation scenarios.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Adding Configuration

```
feat(config): support custom tool configurations

Add ability to enable/disable specific tools via config file.
Allows users to customize available tool set per project.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Bug Fixes

### Logic Error

```
fix(agent): handle empty responses from LLM

Add validation to check for empty or invalid LLM responses
before attempting to parse tool calls.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Edge Case

```
fix(tools): handle missing files gracefully in Read tool

Return clear error message instead of crashing when file
doesn't exist or lacks read permissions.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Refactoring

### Code Organization

```
refactor(tools): extract common file operations to utilities

Move shared file handling logic to utils module to reduce
duplication across Read, Write, and Edit tools.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Performance Improvement

```
perf(agent): cache LLM responses for identical prompts

Implement simple caching to avoid redundant API calls
when same prompt is sent multiple times in a session.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Documentation

### API Documentation

```
docs(tools): add docstrings to all tool classes

Complete API documentation for tool implementations
with parameter descriptions and usage examples.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### User Guide

```
docs: create user guide for agent mode

Add comprehensive guide covering tool usage, best practices,
and common workflows in agent mode.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Testing

### New Tests

```
test(tools): add unit tests for Grep tool

Cover basic search, regex patterns, and error cases.
All tests pass with 100% coverage for Grep tool.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Test Fixes

```
test(agent): fix flaky test in loop execution

Add proper mocking for LLM calls to ensure deterministic
test behavior in CI environment.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Build and Dependencies

### Dependency Updates

```
build(deps): upgrade anthropic SDK to v0.18.0

Update to latest SDK version for improved streaming support
and bug fixes. No breaking changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Build Configuration

```
build: add support for Python 3.12

Update pyproject.toml and CI to test against Python 3.12.
All tests pass on new version.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Chores

### Project Maintenance

```
chore: clean up unused imports and dead code

Remove deprecated code and optimize imports across project.
No functional changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Configuration Updates

```
chore(config): update .gitignore for IDE files

Add patterns for VSCode, PyCharm, and other common IDE
configuration directories.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Multi-Component Changes

### Phase Completion

```
feat: complete Phase 2 - core tools implementation

Implement all core tools: Read, Write, Edit, Glob, Grep, Bash.
Add comprehensive error handling and validation.
Update documentation with usage examples.

Tools included:
- Read: File reading with offset/limit support
- Write: File creation and overwriting
- Edit: In-place file modifications
- Glob: Pattern-based file searching
- Grep: Content search with regex
- Bash: Shell command execution

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Breaking Changes

```
feat(cli)!: redesign command structure

BREAKING CHANGE: CLI commands have been restructured.
Old 'not-agent chat' is now 'not-agent --mode chat'.
Old 'not-agent agent' is now the default behavior.

Update all scripts and documentation to use new command syntax.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```
