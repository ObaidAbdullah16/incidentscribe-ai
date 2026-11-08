"""Runbook retrieval with BM25 - the "R" in RAG.

Why BM25 and not embeddings + a vector database: 12 runbooks fit in memory,
retrieval is deterministic and testable, it costs $0, and the cheapest managed
vector store (OpenSearch Serverless) has a monthly minimum far above this
project's $5 budget. The interface (search -> ranked runbooks) stays the same if
embeddings are added later.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from importlib import resources

STOP = set("""a an and are as at be by for from has have in into is it its of on or that the this to was
were will with when which who why how what not no but if then than so do does did can could should would
our your their there here up down out over under about after before during per via vs""".split())
TOKEN = re.compile(r"[a-z0-9]+")

# A few synonyms make short alert titles match runbook vocabulary.
SYNONYMS = {
    "5xx": "5xx 500 502 503 504 error errors", "502": "502 5xx", "503": "503 5xx", "504": "504 5xx timeout",
    "oom": "oom oomkilled memory", "oomkilled": "oomkilled oom memory crashloopbackoff",
    "latency": "latency slow p95 p99", "slow": "slow latency",
    "cert": "cert certificate tls ssl expiry", "ssl": "ssl tls certificate", "tls": "tls ssl certificate",
    "disk": "disk storage space full", "sqs": "sqs queue backlog", "lag": "lag backlog queue",
    "bill": "bill cost spend budget", "cost": "cost spend budget bill", "budget": "budget cost spend",
    "throttle": "throttle throttles throttling", "throttles": "throttles throttle throttling",
    "connections": "connections connection pool", "cpu": "cpu cpuutilization load",
    "crash": "crash crashloop stopped exit", "restarting": "restarting restarts crashloop",
}


def tokenize(text: str, expand: bool = False) -> list[str]:
    toks = [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]
    if expand:
        extra: list[str] = []
        for t in toks:
            if t in SYNONYMS:
                extra.extend(SYNONYMS[t].split())
        toks += extra
    return toks


@dataclass
class Runbook:
    id: str
    title: str
    text: str


@dataclass
class Hit:
    runbook: Runbook
    score: float


class Index:
    def __init__(self, runbooks: list[Runbook], k1: float = 1.4, b: float = 0.75, title_boost: int = 3):
        self.runbooks = runbooks
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize((r.title + " ") * title_boost + r.text)) for r in runbooks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / max(1, len(self.lengths))
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 3) -> list[Hit]:
        q = Counter(tokenize(query, expand=True))
        scores = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for term, qf in q.items():
                f = d.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg)
                s += self.idf.get(term, 0) * f * (self.k1 + 1) / denom * (1 + 0.1 * (qf - 1))
            scores.append(s)
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
        return [Hit(self.runbooks[i], round(scores[i], 3)) for i in ranked[:k] if scores[i] > 0]


def load_runbooks() -> list[Runbook]:
    out = []
    for f in sorted(resources.files("incidentscribe").joinpath("runbooks").iterdir(), key=lambda p: p.name):
        if not f.name.endswith(".md"):
            continue
        text = f.read_text(encoding="utf-8")
        first = text.splitlines()[0].lstrip("# ").strip()
        rid, _, title = first.partition(":")
        out.append(Runbook(id=rid.strip(), title=title.strip(), text=text))
    return out


_INDEX: Index | None = None


def default_index() -> Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(load_runbooks())
    return _INDEX


def excerpt(runbook: Runbook, max_chars: int = 1800) -> str:
    """The runbook sections most useful to the model, trimmed to a budget."""
    keep = []
    for section in re.split(r"\n(?=## )", runbook.text):
        if section.startswith("## Escalate") or section.startswith("## Mitigate") or section.startswith("## Diagnose") \
                or section.startswith("## Likely causes") or section.startswith("# "):
            keep.append(section.strip())
    text = "\n\n".join(keep)
    return text[:max_chars]
