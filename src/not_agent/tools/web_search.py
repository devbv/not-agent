"""WebSearch tool for searching the web via Google."""

from typing import Any
from urllib.parse import quote_plus

from .base import BaseTool, ToolResult
from .registry import register_tool

try:
    import requests
    from bs4 import BeautifulSoup

    HAS_WEB_DEPS = True
except ImportError:
    HAS_WEB_DEPS = False


@register_tool
class WebSearchTool(BaseTool):
    """Tool for searching the web using Google search scraping."""

    name = "web_search"
    description = (
        "Search the web for up-to-date information. "
        "Use when: user asks about current events, recent data, or anything beyond knowledge cutoff. "
        "Returns top search results with titles, URLs, and snippets."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "query": {
                "type": "string",
                "description": "The search query to use",
                "required": True,
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute web search by scraping Google search results."""
        if not HAS_WEB_DEPS:
            return ToolResult(
                success=False,
                output="",
                error="Web dependencies not installed. Run: pip install requests beautifulsoup4",
            )

        query = kwargs.get("query", "")
        if not query:
            return ToolResult(
                success=False,
                output="",
                error="Query parameter is required",
            )

        try:
            # Use DuckDuckGo HTML search (simpler, no JS required)
            encoded_query = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            # Set headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }

            # Fetch search results
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract search results from DuckDuckGo
            results = []
            result_divs = soup.find_all("div", class_="result")

            for div in result_divs[:10]:  # Limit to top 10 results
                try:
                    # Extract title and URL
                    title_elem = div.find("a", class_="result__a")
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    url_result = title_elem.get("href", "")

                    # Extract snippet/description
                    snippet = ""
                    snippet_elem = div.find("a", class_="result__snippet")
                    if snippet_elem:
                        snippet = snippet_elem.get_text(strip=True)

                    if title and url_result:
                        results.append(
                            {"title": title, "url": url_result, "snippet": snippet}
                        )

                except Exception:
                    # Skip malformed results
                    continue

            if not results:
                return ToolResult(
                    success=False,
                    output="",
                    error="No search results found. DuckDuckGo may be blocking requests or the page structure changed.",
                )

            # Format results
            output_lines = [f"검색 쿼리: {query}\n", "검색 결과:\n"]

            for idx, result in enumerate(results, 1):
                output_lines.append(f"{idx}. {result['title']}")
                output_lines.append(f"   URL: {result['url']}")
                if result["snippet"]:
                    output_lines.append(f"   설명: {result['snippet']}")
                output_lines.append("")

            # Add sources section
            output_lines.append("Sources:")
            for result in results:
                output_lines.append(f"- [{result['title']}]({result['url']})")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
            )

        except requests.RequestException as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to fetch search results: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Web search failed: {str(e)}",
            )
