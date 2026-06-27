"""Built-in tool registry: tool name -> required permission level.

The DB table `tool_registry` is the persistent source of truth (seeded from this
map); this in-code default keeps the system runnable before seeding and documents
the levels in one place.

Levels:
  0  read-only / pure compute, no side effects
  1  outbound read (web_search, web_fetch) — untrusted DATA only
  2  sandboxed code execution (network-less, resource-limited)
  3  side effects requiring approval (e.g. write to a user resource)
  4  sensitive actions requiring approval
  5  never permitted
"""

from __future__ import annotations

BUILTIN_TOOL_LEVELS: dict[str, int] = {
    "web_search": 1,
    "web_fetch": 1,
    "code_exec": 2,
}


def level_for(tool_name: str, registry: dict[str, int] | None = None) -> int | None:
    return (registry or BUILTIN_TOOL_LEVELS).get(tool_name)
