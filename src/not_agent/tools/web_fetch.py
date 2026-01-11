"""WebFetch tool for fetching and converting web content to plain text."""

from typing import Any
from urllib.parse import urlparse

from .base import BaseTool, ToolResult
from .registry import register_tool

try:
    import requests
    from bs4 import BeautifulSoup

    HAS_WEB_DEPS = True
except ImportError:
    HAS_WEB_DEPS = False


@register_tool
class WebFetchTool(BaseTool):
    """Tool for fetching content from URLs and converting HTML to plain text."""

    name = "WebFetch"
    description = """Fetches content from a specified URL and converts HTML to plain text.
Takes a URL as input and returns the text content with HTML tags removed.

Usage notes:
- The URL must be a fully-formed valid URL
- HTTP URLs will be automatically upgraded to HTTPS
- Returns plain text content with HTML tags, scripts, and styles removed
- Results may be truncated if the content is very large (max 50,000 characters)
- This tool is read-only and does not modify any files"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "url": {
                "type": "string",
                "description": "The URL to fetch content from",
                "required": True,
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute web fetch and convert HTML to text."""
        if not HAS_WEB_DEPS:
            return ToolResult(
                success=False,
                output="",
                error="Web dependencies not installed. Run: pip install requests beautifulsoup4",
            )

        url = kwargs.get("url", "")
        if not url:
            return ToolResult(
                success=False,
                output="",
                error="URL parameter is required",
            )

        # Validate and upgrade URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
            elif parsed.scheme == "http":
                url = url.replace("http://", "https://", 1)
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid URL: {str(e)}",
            )

        try:
            # Fetch URL content
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; NotAgent/1.0)",
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Convert HTML to text
            soup = BeautifulSoup(response.content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            # Limit content size
            max_chars = 50000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[Content truncated...]"

            # Format output with URL info
            output = f"Content from {url}:\n\n{text}"

            return ToolResult(
                success=True,
                output=output,
            )

        except requests.RequestException as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to fetch URL: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Web fetch failed: {str(e)}",
            )
