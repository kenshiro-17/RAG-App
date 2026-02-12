from __future__ import annotations

import re

INJECTION_PATTERNS = [
    re.compile(r"ignore (all|previous) instructions", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"developer message", re.IGNORECASE),
    re.compile(r"assistant:", re.IGNORECASE),
    re.compile(r"disregard.*policy", re.IGNORECASE),
    re.compile(r"reveal.*(secret|key|token|password)", re.IGNORECASE),
    re.compile(r"execute (shell|command|script)", re.IGNORECASE),
]


def sanitize_retrieved_text(text: str) -> str:
    lines = text.splitlines()
    safe_lines: list[str] = []
    for line in lines:
        if any(pattern.search(line) for pattern in INJECTION_PATTERNS):
            continue
        safe_lines.append(line)
    sanitized = "\n".join(safe_lines).strip()
    return sanitized if sanitized else "[Filtered potentially malicious content]"


def maybe_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)


def injection_risk_score(text: str) -> float:
    if not text.strip():
        return 1.0

    hits = sum(1 for pattern in INJECTION_PATTERNS if pattern.search(text))
    density = min(len(text) / 2000, 1.0)
    score = min(1.0, (hits / max(len(INJECTION_PATTERNS), 1)) * 0.8 + 0.2 * density)
    return score
