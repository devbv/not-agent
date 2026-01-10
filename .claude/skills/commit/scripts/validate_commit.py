#!/usr/bin/env python3
"""
Validate commits for security issues and sensitive information.
"""
import re
import subprocess
from pathlib import Path


# Patterns for sensitive information
SENSITIVE_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})', "API Key"),
    (r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})', "Password/Secret"),
    (r'(?i)(token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})', "Token"),
    (r'(?i)(aws_access_key_id|aws_secret_access_key)\s*[:=]\s*["\']?([^\s"\']+)', "AWS Credentials"),
    (r'(?i)(private[_-]?key)\s*[:=]', "Private Key"),
    (r'-----BEGIN (RSA |DSA )?PRIVATE KEY-----', "Private Key Block"),
]

# Files that commonly contain secrets
SENSITIVE_FILES = [
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_dsa",
    ".pem",
    ".key",
]


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False
    )
    return [f.strip() for f in result.stdout.split("\n") if f.strip()]


def get_staged_content() -> str:
    """Get content of staged changes."""
    result = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        check=False
    )
    return result.stdout


def check_sensitive_files(files: list[str]) -> list[str]:
    """Check for sensitive file names."""
    issues = []
    for file in files:
        filename = Path(file).name
        if any(sens in filename for sens in SENSITIVE_FILES):
            issues.append(f"Sensitive file detected: {file}")
    return issues


def check_sensitive_content(content: str) -> list[str]:
    """Check for sensitive patterns in content."""
    issues = []
    for pattern, desc in SENSITIVE_PATTERNS:
        matches = re.finditer(pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append(f"Potential {desc} at line {line_num}")
    return issues


def validate() -> tuple[bool, list[str]]:
    """
    Validate staged changes for security issues.
    Returns (is_safe, list_of_issues)
    """
    issues = []

    # Check staged files
    files = get_staged_files()
    if not files:
        return True, []

    # Check file names
    file_issues = check_sensitive_files(files)
    issues.extend(file_issues)

    # Check content
    content = get_staged_content()
    content_issues = check_sensitive_content(content)
    issues.extend(content_issues)

    return len(issues) == 0, issues


def main():
    """Main validation function."""
    is_safe, issues = validate()

    if is_safe:
        print("✅ No security issues detected")
        return 0
    else:
        print("⚠️  Security issues detected:")
        for issue in issues:
            print(f"  - {issue}")
        return 1


if __name__ == "__main__":
    exit(main())
