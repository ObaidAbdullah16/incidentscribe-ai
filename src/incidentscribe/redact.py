"""Remove personal data and secrets from alert text before it reaches a model.

Deterministic regexes run first (free, testable, no data leaves the function);
Bedrock Guardrails is a second layer. Each match becomes a typed placeholder
like [EMAIL] so the model still understands the sentence.
"""
from __future__ import annotations

import re
from collections import Counter

# Order matters: more specific patterns first.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("AWS_SECRET_KEY", re.compile(r"(?i)\b(?:aws_secret_access_key|secret_access_key|secretkey)\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("SLACK_WEBHOOK", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+")),
    ("PASSWORD", re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*\S+")),
    ("CONN_STRING_CREDS", re.compile(r"\b([a-z][a-z0-9+]*://)[^/\s:@]+:[^/\s@]+@")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b")),
    ("PHONE", re.compile(r"(?<![\w.])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}\b|(?<![\w.])\+\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}\b")),
    ("IP", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
]


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def redact(text: str) -> tuple[str, Counter]:
    """Return (redacted text, counts by type)."""
    counts: Counter = Counter()
    if not text:
        return text, counts
    out = text
    for kind, rx in PATTERNS:
        def repl(m: re.Match[str], kind: str = kind) -> str:
            if kind == "CARD" and not _luhn_ok(m.group(0)):
                return m.group(0)          # a long number that is not a card (e.g. a request id)
            counts[kind] += 1
            if kind == "PASSWORD":
                return f"{m.group(1)}=[PASSWORD]"
            if kind == "CONN_STRING_CREDS":
                return f"{m.group(1)}[CREDENTIALS]@"
            return f"[{kind}]"
        out = rx.sub(repl, out)
    return out, counts
