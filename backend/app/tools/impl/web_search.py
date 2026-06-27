"""web_search (Level 1): keyless search via DuckDuckGo's Instant Answer API.

Returns results as untrusted DATA. No API key required; if the network is
unavailable the tool returns a clear error rather than fabricating results.
"""

from __future__ import annotations

from app.tools.impl.web_fetch import detect_injection
from app.tools.schema import ToolResult


def make_web_search(*, max_results: int = 5, timeout: float = 10.0):
    async def _impl(args: dict) -> ToolResult:
        query = (args.get("query") or "").strip()
        if not query:
            return ToolResult(tool_name="web_search", level=1, status="error",
                              error="web_search requires a 'query'")
        import httpx

        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                resp = await c.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1},
                    headers={"User-Agent": "ApexMind/0.1"},
                )
            data = resp.json()
            results: list[dict] = []
            if data.get("AbstractText"):
                results.append({"title": data.get("Heading", ""),
                                "snippet": data["AbstractText"],
                                "url": data.get("AbstractURL", "")})
            for topic in data.get("RelatedTopics", []):
                if "Text" in topic and len(results) < max_results:
                    results.append({"title": topic.get("Text", "")[:80],
                                    "snippet": topic.get("Text", ""),
                                    "url": topic.get("FirstURL", "")})
            joined = " ".join(r["snippet"] for r in results)
            return ToolResult(
                tool_name="web_search", level=1, status="ok",
                result={"query": query, "results": results, "untrusted": True,
                        "content": joined,
                        "injection_flags": detect_injection(joined)},
            )
        except Exception as exc:
            return ToolResult(tool_name="web_search", level=1, status="error",
                              error=f"{type(exc).__name__}: {exc}")

    return _impl
