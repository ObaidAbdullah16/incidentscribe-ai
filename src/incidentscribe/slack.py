"""Post a summary to Slack through an incoming webhook (stdlib only)."""
from __future__ import annotations

import json
import urllib.request
from typing import Any

SEV_EMOJI = {"SEV1": ":red_circle:", "SEV2": ":large_orange_circle:", "SEV3": ":large_yellow_circle:", "SEV4": ":white_circle:"}


def blocks(result: dict[str, Any]) -> list[dict[str, Any]]:
    s = result["summary"]
    meta = result.get("meta", {})
    lines = [
        f"{SEV_EMOJI.get(s['severity'], '')} *{s['severity']}* - *{s['title']}*",
        f"*Service:* {s['service'] or 'unknown'}   *Runbook:* {s['runbook_id'] or '-'}   *Confidence:* {s['confidence']}",
        "",
        s["summary"],
    ]
    out: list[dict[str, Any]] = [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)[:2900]}}]
    if s["likely_causes"]:
        out.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Likely causes*\n" + "\n".join(f"- {c}" for c in s["likely_causes"])}})
    if s["next_steps"]:
        out.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Next steps*\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(s["next_steps"], 1))}})
    cost = meta.get("cost_usd")
    footer = f"{result['incident_id']} - model {meta.get('model')} - " + (f"${cost:.5f}" if isinstance(cost, (int, float)) else "no AI cost")
    out.append({"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]})
    return out


def post(webhook_url: str, result: dict[str, Any], timeout: float = 5.0) -> int:
    body = json.dumps({"text": f"{result['summary']['severity']}: {result['summary']['title']}", "blocks": blocks(result)}).encode()
    req = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL comes from our own SSM parameter
        return resp.status
