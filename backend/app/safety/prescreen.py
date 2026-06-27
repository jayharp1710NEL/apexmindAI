"""Safety pre-screen for requests and tool calls.

Goals (from the ground rules):
  * Refuse CLEAR harm (weapons of mass destruction, CSAM, obvious malware-for-harm).
  * ALLOW benign look-alikes — "kill a process", "explain how ransomware works to
    defend", security education, fiction.
  * Treat instructions embedded in fetched/tool content as untrusted DATA: never
    follow them, but flag them.

Deterministic and rule-based so it is fully unit-testable without a model. An
optional LLM safety agent can refine borderline cases, but the spine here never
depends on it. Errs toward allowing benign work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.tools.impl.web_fetch import detect_injection

Decision = Literal["allow", "refuse", "escalate"]


@dataclass
class PrescreenResult:
    decision: Decision
    category: str
    reason: str
    injection_detected: bool = False
    flags: list[str] = field(default_factory=list)


# (pattern, category, allow_benign_override)
# Hard rules (override=False) cannot be excused by an educational/fiction framing.
_HARM_RULES: list[tuple[str, str, bool]] = [
    (r"\b(make|build|construct|synthesi[sz]e|create)\b.{0,40}\b"
     r"(bomb|explosive|ied|grenade|nerve agent|sarin|vx|bioweapon|"
     r"chemical weapon|dirty bomb|nuclear weapon)\b", "weapons", False),
    (r"\b(child (porn|sexual|sex)|csam|minor)\b.{0,20}\b(sexual|porn|nude)\b",
     "csam", False),
    (r"\bhow to (kill|murder|poison)\b.{0,20}\b(a |the )?"
     r"(person|people|someone|him|her|them|my \w+)\b", "violence", False),
    # Malware/intrusion FOR harm — benign override allowed (defense/education).
    (r"\bwrite\b.{0,30}\b(ransomware|keylogger|spyware|rootkit|computer virus|"
     r"malware|trojan|botnet)\b", "cyber_harm", True),
    (r"\b(ddos|denial of service)\b.{0,20}\battack\b", "cyber_harm", True),
    (r"\bhow to (hack|break) into\b.{0,30}\b(account|email|phone|network|"
     r"server|wifi|someone)\b", "cyber_harm", True),
    (r"\b(steal|exfiltrate|dump)\b.{0,20}\b(credentials|passwords|credit cards)\b",
     "cyber_harm", True),
]

# Signals that a cyber/look-alike request is benign (defensive / educational / fiction).
_BENIGN_OVERRIDES = [
    r"\b(defend|protect|detect|mitigat\w*|prevent|secure|harden|remediat\w*)\b",
    r"\b(how does|how do|explain|understand|what is|overview|learn|education|"
    r"awareness|research|analy[sz]e)\b",
    r"\b(novel|fiction|story|movie|screenplay|game|fictional)\b",
    r"\b(authori[sz]ed|pentest|penetration test|ctf|lab|my own)\b",
]


def _has_benign_override(text: str) -> bool:
    return any(re.search(p, text) for p in _BENIGN_OVERRIDES)


def prescreen_request(text: str) -> PrescreenResult:
    low = text.lower()
    flags = detect_injection(low)
    for pattern, category, overridable in _HARM_RULES:
        if re.search(pattern, low):
            if overridable and _has_benign_override(low):
                return PrescreenResult(
                    "allow", f"benign_{category}",
                    "matched a harmful pattern but with a clearly benign framing",
                    injection_detected=bool(flags), flags=flags,
                )
            return PrescreenResult(
                "refuse", category,
                f"request matches a clear-harm pattern ({category})",
                injection_detected=bool(flags), flags=flags,
            )
    return PrescreenResult("allow", "benign", "no clear-harm pattern matched",
                           injection_detected=bool(flags), flags=flags)


def prescreen_tool_content(text: str) -> PrescreenResult:
    """Screen content fetched by tools. Such content is DATA: we never refuse the
    user's task because of it, but we DO flag embedded instructions so downstream
    code keeps treating it as untrusted.
    """
    flags = detect_injection(text or "")
    return PrescreenResult(
        decision="allow",
        category="tool_content",
        reason="fetched content treated as untrusted data",
        injection_detected=bool(flags),
        flags=flags,
    )


REFUSAL_MESSAGE = (
    "I can't help with that — it appears to request clear harm. If your intent is "
    "defensive, educational, or fictional, please rephrase with that context and I'll "
    "do my best to help."
)
