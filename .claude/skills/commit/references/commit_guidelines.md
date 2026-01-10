# Commit Message Guidelines

## Conventional Commits Format

All commits should follow the Conventional Commits specification:

```
<type>(<scope>): <subject>

<body>

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Type

Must be one of:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning (formatting, white-space)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvement
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes to build system or dependencies
- **ci**: Changes to CI configuration files and scripts
- **chore**: Other changes that don't modify src or test files

## Scope

Optional. Should be the affected module/component:

- `agent` - Agent core logic
- `tools` - Tool implementations
- `cli` - CLI interface
- `llm` - LLM integration
- `config` - Configuration
- `deps` - Dependencies

## Subject

- Use imperative mood ("add" not "added" or "adds")
- Don't capitalize first letter
- No period at the end
- Keep under 50 characters

## Body

- Separate from subject with a blank line
- Explain what and why (not how)
- Wrap at 72 characters
- Can include multiple paragraphs
- Include motivation for the change
- Contrast with previous behavior

## Co-Authored-By

ALWAYS include at the end:

```
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Breaking Changes

If introducing breaking changes, add:

```
BREAKING CHANGE: description of what breaks
```

## Examples

### Feature Addition

```
feat(tools): add WebSearch and WebFetch tools

Implement web search and fetch capabilities using Claude API.
WebSearch performs web searches and returns results with sources.
WebFetch retrieves and analyzes web page content.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Bug Fix

```
fix(agent): prevent duplicate tool calls in loop

Check for identical consecutive tool calls and skip execution
to avoid infinite loops when LLM repeats the same action.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Documentation

```
docs: update phase 2 completion notes

Add documentation for WebSearch and WebFetch tools in history.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Refactoring

```
refactor(cli): extract command handlers to separate module

Move command logic from main CLI file to dedicated handlers
for better organization and testability.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```
