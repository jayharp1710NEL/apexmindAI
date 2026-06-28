"""web_fetch (Level 1): GET a URL and return its text as untrusted DATA.

Content fetched from the web is DATA, never instructions. We strip HTML to text,
truncate, and flag any embedded prompt-injection-looking phrases so downstream steps
(and the Step-11 prescreen) can treat it with suspicion. We never act on it.
"""

from __future__ import annotations

import re

from app.tools.schema import ToolResult

_INJECTION_PATTERNS = [
    r"ignore (all|any|previous|prior) (instructions|prompts)",
    r"disregard (the )?(above|previous|system)",
    r"you are now",
    r"system prompt",
    r"reveal your (instructions|system prompt)",
    r"act as",
]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    return _WS_RE.sub(" ", text).strip()


def detect_injection(text: str) -> list[str]:
    flags = []
    low = text.lower()
    for pat in _INJECTION_PATTERNS:
        if re.search(pat, low):
            flags.append(pat)
    return flags


def make_web_fetch(*, max_chars: int = 8000, timeout: float = 10.0):
    async def _impl(args: dict) -> ToolResult:
        url = (args.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return ToolResult(tool_name="web_fetch", level=1, status="error",
                              error="web_fetch requires an http(s) url")
        import httpx

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as c:
                resp = await c.get(url, headers={"User-Agent": "ApexMind/0.1"})
            text = _strip_html(resp.text)[:max_chars]
            flags = detect_injection(text)
            return ToolResult(
                tool_name="web_fetch", level=1, status="ok",
                result={"url": url, "status_code": resp.status_code,
                        "content": text, "untrusted": True,
                        "injection_flags": flags},
            )
        except Exception as exc:
            return ToolResult(tool_name="web_fetch", level=1, status="error",
                              error=f"{type(exc).__name__}: {exc}")

    return _impl
