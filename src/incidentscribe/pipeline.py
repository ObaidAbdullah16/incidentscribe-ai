"""alert -> normalise -> redact -> retrieve runbooks -> budget check -> model -> store -> Slack."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .budget import Budget
from .incident import Incident, normalize
from .llm import SYSTEM_PROMPT, FakeLLM, LLMResult, Pricing, build_user_message, fallback_answer
from .rag import Index, default_index
from .redact import redact


@dataclass
class Deps:
    llm: Any = field(default_factory=FakeLLM)
    index: Index = field(default_factory=default_index)
    pricing: Pricing = field(default_factory=Pricing)
    budget: Budget | None = None
    store: Any = None                 # DynamoDB Table or None
    slack: Any = None                 # callable(result) or None
    max_tokens: int = 500
    guardrail: bool = False
    id_prefix: str = ""               # e.g. "WEB-": public API records can't overwrite alarm records


def redact_incident(inc: Incident) -> dict[str, int]:
    counts: dict[str, int] = {}
    for attr in ("title", "service", "severity_hint", "description", "started_at"):   # every text field that reaches the prompt
        cleaned, c = redact(getattr(inc, attr))
        setattr(inc, attr, cleaned)
        for k, v in c.items():
            counts[k] = counts.get(k, 0) + v
    if inc.signals:
        import json
        cleaned, c = redact(json.dumps(inc.signals, default=str))
        try:
            inc.signals = json.loads(cleaned)          # placeholders inside strings keep the JSON valid
        except json.JSONDecodeError:
            inc.signals = {"redacted": cleaned}        # e.g. a redacted bare number broke the JSON
        for k, v in c.items():
            counts[k] = counts.get(k, 0) + v
    return counts


def process(payload: dict[str, Any], deps: Deps) -> dict[str, Any]:
    t0 = time.monotonic()
    inc = normalize(payload)
    inc.id = deps.id_prefix + inc.id
    redactions = redact_incident(inc)
    query = " ".join([inc.title, inc.service, inc.description, str(inc.signals.get("metrics", "")), str(inc.signals.get("alertname", ""))])
    hits = deps.index.search(query, k=3)
    user = build_user_message(inc, hits)

    llm_used, reason, cost = False, "", 0.0
    res: LLMResult
    estimate = deps.pricing.estimate(len(SYSTEM_PROMPT) + len(user), deps.max_tokens, deps.guardrail)
    decision = deps.budget.check(estimate) if deps.budget else None
    if decision is not None and not decision.allowed:
        reason = decision.reason
        res = LLMResult(data=fallback_answer(inc, hits, reason), model="none")
    else:
        res = deps.llm.complete(SYSTEM_PROMPT, user, inc, hits, deps.max_tokens)
        llm_used = res.model not in ("offline", "none")   # "none" = the call failed, nothing was billed
        guard_chars = len(SYSTEM_PROMPT) + len(user) + len(res.raw) if deps.guardrail else 0
        cost = deps.pricing.cost(res.input_tokens, res.output_tokens, guard_chars) if llm_used else 0.0
        if deps.budget and llm_used:
            deps.budget.record(cost)
        reason = "; ".join(res.notes)

    result = {
        "incident_id": inc.id,
        "source": inc.source,
        "summary": res.data,
        "meta": {
            "model": res.model,
            "llm_used": llm_used,
            "fallback_reason": reason,
            "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens,
            "cost_usd": round(cost, 6),
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "redactions": redactions,
            "guardrail": res.guardrail,
            "retrieved": [{"id": h.runbook.id, "title": h.runbook.title, "score": h.score} for h in hits],
            "budget": None if decision is None else {"spent_today_usd": round(decision.spent_today, 4),
                                                     "spent_month_usd": round(decision.spent_month, 4)},
        },
    }
    if deps.store is not None:
        _store(deps.store, result)
    if deps.slack is not None:
        try:
            deps.slack(result)
            result["meta"]["slack"] = "sent"
        except Exception as e:  # noqa: BLE001 - Slack being down must not lose the summary
            result["meta"]["slack"] = f"failed: {e.__class__.__name__}"
    return result


def _store(table: Any, result: dict[str, Any]) -> None:
    import json
    from decimal import Decimal
    now = int(time.time())
    table.put_item(Item={
        "pk": result["incident_id"],
        "created_at": Decimal(now),
        "expires_at": Decimal(now + 30 * 86400),
        "severity": result["summary"]["severity"],
        "title": result["summary"]["title"],
        "body": json.dumps(result),
    })
