---
name: commit
description: "Automated git commit workflow with Conventional Commits format, security validation, and auto-commit on phase completion. Use when: (1) User requests to create a commit or run /commit, (2) A plan/phase is completed and changes should be committed, (3) Significant work is done and needs to be saved to git. Handles commit message generation, Co-Authored-By attribution, secrets detection, and proper git workflow."
---

# Commit

Automated git commit workflow following Conventional Commits format with built-in security validation.

## When to Use This Skill

Use this skill in these scenarios:

1. **User explicitly requests commit**: User says "create a commit", "commit these changes", or runs `/commit`
2. **Phase/plan completion**: After completing a significant phase or plan with multiple changes
3. **Significant work completed**: After implementing a feature, fixing bugs, or making substantial changes
4. **Before switching tasks**: To checkpoint work before moving to a different task

**Auto-commit behavior**: When a plan or phase is completed (marked as done in todo list), automatically trigger commit workflow.

## Commit Workflow

Follow this sequence for every commit:

### 1. Gather Git Information

Run `auto_commit.py` to collect:
- Git status (untracked and modified files)
- Git diff (both staged and unstaged changes)
- Recent commits (to learn project commit style)

```bash
python3 scripts/auto_commit.py
```

### 2. Validate Security

Run `validate_commit.py` to check for:
- Sensitive file names (.env, credentials.json, etc.)
- API keys, tokens, passwords in content
- Private keys and certificates

```bash
python3 scripts/validate_commit.py
```

**If validation fails**: Review issues and either:
- Unstage sensitive files: `git reset <file>`
- Remove sensitive content from files
- Get user approval if files are intentionally committed

### 3. Analyze Changes

Review the git diff output to understand:
- What was added/modified/deleted
- Which components/modules are affected
- The purpose and impact of changes

Categorize changes:
- **feat**: New features or capabilities
- **fix**: Bug fixes
- **docs**: Documentation updates
- **refactor**: Code restructuring without behavior change
- **test**: Test additions or modifications
- **chore**: Maintenance, dependencies, configuration

### 4. Generate Commit Message

Create message following Conventional Commits format:

```
<type>(<scope>): <subject>

<body>

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Subject guidelines**:
- Use imperative mood ("add" not "added")
- Keep under 50 characters
- No period at end
- Lowercase first letter

**Body guidelines**:
- Explain what and why (not how)
- Provide context for the changes
- Reference related issues or PRs if applicable
- List major changes if multiple components affected

**Always include**: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>` at the end

See [commit_guidelines.md](references/commit_guidelines.md) for detailed format rules.
See [examples.md](references/examples.md) for good commit message examples.

### 5. Stage and Commit

Stage all relevant files and create the commit:

```bash
git add <files>
git commit -m "$(cat <<'EOF'
<commit message here>
EOF
)"
```

**Important**:
- Use HEREDOC format for multi-line messages
- Never use `--no-verify` flag unless explicitly requested
- Check git status after commit to verify success

### 6. Handle Pre-commit Hooks

If pre-commit hook fails:
- Review the error output
- Fix the issues (formatting, linting, etc.)
- Create a NEW commit (don't amend unless hook auto-modified files)
- Never skip hooks with `--no-verify` without user approval

### 7. Verify Success

After commit:
```bash
git status
git log -1 --pretty=format:"%h - %s"
```

Confirm the commit was created and message is correct.

## Auto-commit on Phase Completion

When a phase/plan is marked as completed in the todo list:

1. Check if there are uncommitted changes (`git status`)
2. If changes exist, automatically trigger commit workflow
3. Generate commit message based on phase/plan description
4. Use scope that matches the phase (e.g., if phase was about tools, use `feat(tools)`)
5. Include summary of phase accomplishments in body

Example auto-commit message for phase completion:

```
feat(tools): complete Phase 2 - core tools implementation

Implement six core tools: Read, Write, Edit, Glob, Grep, Bash.
Add error handling, validation, and comprehensive documentation.

Tools included:
- Read: File reading with offset/limit support
- Write: File creation and overwriting
- Edit: In-place string replacement
- Glob: Pattern-based file search
- Grep: Content search with regex
- Bash: Shell command execution

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## Security Validation Details

The `validate_commit.py` script checks for:

**Sensitive file patterns**:
- `.env`, `.env.local`, `.env.production`
- `credentials.json`, `secrets.json`
- `id_rsa`, `id_dsa`, `.pem`, `.key`

**Sensitive content patterns**:
- API keys: `api_key = "..."`
- Passwords: `password = "..."`
- Tokens: `token = "..."`
- AWS credentials: `aws_access_key_id = "..."`
- Private keys: `-----BEGIN PRIVATE KEY-----`

**If secrets detected**: Warn user and request confirmation before committing.

## Common Scenarios

### Scenario 1: Simple feature addition

```
User: "Commit the changes"

1. Run auto_commit.py - see new file added
2. Run validate_commit.py - no issues
3. Analyze: New feature file for web search
4. Generate message:

feat(tools): add WebSearch tool

Implement web search capability using Claude API.
Returns formatted results with source links.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

5. Stage and commit
6. Verify success
```

### Scenario 2: Bug fix

```
User: "Fix the error and commit"

1. Gather git info - see modified file
2. Validate security - no issues
3. Analyze: Fixed null pointer error in agent loop
4. Generate message:

fix(agent): handle None response from LLM

Add validation to check for None before parsing response.
Prevents crash when API returns empty response.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

5. Stage and commit
```

### Scenario 3: Phase completion (auto-commit)

```
Todo: "Phase 2 complete" marked as completed

1. Detect phase completion
2. Check git status - changes exist
3. Auto-trigger commit workflow
4. Analyze all changes in phase
5. Generate comprehensive message
6. Create commit automatically
```

### Scenario 4: Pre-commit hook failure

```
Commit attempt fails due to formatting issues

1. Read hook error output
2. Fix formatting issues (black, ruff)
3. Stage fixed files
4. Create NEW commit (don't amend)
5. Verify success
```

## Resources

- **scripts/auto_commit.py**: Gathers git status, diff, and recent commits
- **scripts/validate_commit.py**: Validates for secrets and sensitive info
- **references/commit_guidelines.md**: Full Conventional Commits specification
- **references/examples.md**: Real commit message examples

## Best Practices

1. **One commit per logical change**: Don't mix unrelated changes
2. **Clear subject lines**: Should complete "This commit will..."
3. **Informative bodies**: Explain reasoning, not just what changed
4. **Security first**: Always validate before committing
5. **Consistent style**: Follow Conventional Commits format
6. **Proper attribution**: Always include Co-Authored-By
7. **Never skip hooks**: Only use --no-verify with explicit approval
