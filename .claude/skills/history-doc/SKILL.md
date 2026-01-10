---
name: history-doc
description: Manage project history documentation files with automatic sequential numbering. Use when creating new history files in the history/ directory to ensure correct sequential numbering (XXX_description.md format) and avoid duplicate numbers. This skill automatically finds the next available number and creates properly named history files.
---

# History Documentation

Manage project history files with automatic sequential numbering to maintain a clean, organized history directory.

## When to Use

Use this skill whenever you need to create a new history file in the `history/` directory. The skill ensures:
- Correct sequential numbering (001, 002, 003, ...)
- No duplicate numbers
- Consistent file naming format: `XXX_description.md`

## Quick Start

To create a new history file:

1. **Get the next number** using the script:
   ```bash
   python3 .claude/skills/history-doc/scripts/get_next_number.py
   ```

2. **Create the file** with the returned number:
   ```bash
   # Example: if script returns "010"
   touch history/010_my_new_document.md
   # or use Write tool
   ```

## Workflow

### Step 1: Determine Next Number

Always start by running the script to get the next available number:

```bash
python3 .claude/skills/history-doc/scripts/get_next_number.py
```

The script:
- Scans all files in `history/` directory
- Finds files matching pattern `XXX_*.md`
- Returns the next sequential number (e.g., "010")

### Step 2: Create the File

Use the returned number to create a properly named file:

```
history/XXX_description.md
```

Where:
- `XXX` = 3-digit zero-padded number (001, 002, ..., 010, ...)
- `description` = brief description in snake_case or kebab-case
- `.md` = Markdown file extension

**Naming conventions:**
- Use descriptive names: `010_approval_system_redesign_plan.md`
- Use underscores or hyphens: `phase1_complete` or `phase-1-complete`
- Keep it concise but clear

### Step 3: Write Content

Write the history document content following the project's documentation standards.

## Examples

### Example 1: Creating a Plan Document

```bash
# Get next number
$ python3 .claude/skills/history-doc/scripts/get_next_number.py
010

# Create file
history/010_approval_system_redesign_plan.md
```

### Example 2: Creating a Milestone Document

```bash
# Get next number
$ python3 .claude/skills/history-doc/scripts/get_next_number.py
011

# Create file
history/011_phase4_complete.md
```

### Example 3: Script Returns "001" for Empty Directory

```bash
# First history file
$ python3 .claude/skills/history-doc/scripts/get_next_number.py
001

# Create first file
history/001_project_start.md
```

## Script Reference

### get_next_number.py

**Location:** `scripts/get_next_number.py`

**Usage:**
```bash
python3 .claude/skills/history-doc/scripts/get_next_number.py [history_dir]
```

**Arguments:**
- `history_dir` (optional): Path to history directory (default: "history")

**Output:**
- Prints next available number as zero-padded string (e.g., "010")
- Returns exit code 0 on success

**Behavior:**
- Scans files matching pattern `^(\d{3})_.*`
- Finds maximum number
- Returns max + 1, zero-padded to 3 digits
- Returns "001" if no numbered files exist

## Common Issues

### Wrong Directory

If running from a subdirectory, specify the history path:

```bash
python3 ../.claude/skills/history-doc/scripts/get_next_number.py ../history
```

### Duplicate Numbers

If duplicate numbers exist, the script returns the next number after the highest found. Clean up duplicates manually:

```bash
# Find duplicates
ls history/ | grep -E '^[0-9]{3}_' | cut -d'_' -f1 | sort | uniq -d

# Rename duplicates manually
mv history/007_file.md history/009_file.md
```

## Integration with Project

This skill integrates with the project's history tracking system documented in CLAUDE.md. All major milestones, plans, and decisions should be recorded in the `history/` directory using this skill to ensure consistent numbering.
