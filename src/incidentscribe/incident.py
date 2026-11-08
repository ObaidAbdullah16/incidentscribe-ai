"""Turn different alert formats into one Incident."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

MAX_TEXT = 4000


@dataclass
class Incident:
    id: str
    source: str              # cloudwatch | alertmanager | api
    title: str
    service: str = ""
    severity_hint: str = ""  # from the alert, if any
    description: str = ""
    signals: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""

    def text(self) -> str:
        parts = [f"Title: {self.title}"]
        if self.service:
            parts.append(f"Service: {self.service}")
        if self.severity_hint:
            parts.append(f"Alert severity: {self.severity_hint}")
        if self.started_at:
            parts.append(f"Started: {self.started_at}")
        if self.signals:
            parts.append("Signals: " + json.dumps(self.signals, sort_keys=True, default=str)[:800])
        if self.description:
            parts.append(f"Details: {self.description}")
        return "\n".join(parts)[:MAX_TEXT]


def _id(*parts: str) -> str:
    return "INC-" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:10].upper()


def from_cloudwatch(event: dict[str, Any]) -> Incident:
    d = event.get("detail", {})
    state = d.get("state", {})
    cfg = d.get("configuration", {}) or {}
    metrics = []
    for m in cfg.get("metrics", []) or []:
        metric = (m.get("metricStat") or {}).get("metric") or {}
        if metric:
            metrics.append({"namespace": metric.get("namespace"), "name": metric.get("name"),
                            "dimensions": metric.get("dimensions")})
    name = d.get("alarmName", "unknown-alarm")
    dims = metrics[0]["dimensions"] if metrics and metrics[0].get("dimensions") else {}
    service = next((str(v) for k, v in (dims or {}).items() if k in ("ServiceName", "FunctionName", "DBInstanceIdentifier",
                                                                       "LoadBalancer", "QueueName", "InstanceId")), "")
    return Incident(
        id=_id(name, state.get("timestamp", event.get("time", ""))),
        source="cloudwatch",
        title=f"{name} in ALARM",
        service=service,
        description=" ".join(x for x in [cfg.get("description", ""), state.get("reason", "")] if x),
        # The account ID is left out on purpose: the model doesn't need it, and a 12-digit
        # number looks like an Aadhaar number to the redactor (a false positive).
        signals={"metrics": metrics, "region": event.get("region")},
        started_at=state.get("timestamp", event.get("time", "")),
    )


def from_alertmanager(body: dict[str, Any]) -> Incident:
    alerts = [a for a in body.get("alerts", []) if a.get("status", "firing") == "firing"] or body.get("alerts", [])
    first = alerts[0] if alerts else {}
    labels = {**body.get("commonLabels", {}), **first.get("labels", {})}
    ann = {**body.get("commonAnnotations", {}), **first.get("annotations", {})}
    title = labels.get("alertname", "alert")
    return Incident(
        id=_id(title, first.get("startsAt", ""), labels.get("service", "")),
        source="alertmanager",
        title=ann.get("summary") or title,
        service=labels.get("service") or labels.get("job") or labels.get("namespace", ""),
        severity_hint=labels.get("severity", ""),
        description=ann.get("description", ""),
        signals={"alertname": title, "labels": labels, "firing": len(alerts)},
        started_at=first.get("startsAt", ""),
    )


def from_api(body: dict[str, Any]) -> Incident:
    title = str(body.get("title") or body.get("summary") or "untitled incident")[:200]
    logs = body.get("logs") or []
    desc = str(body.get("description", ""))
    if logs:
        desc += "\nLog lines:\n" + "\n".join(str(x)[:300] for x in logs[:20])
    return Incident(
        id=str(body.get("id") or _id(title, desc[:200]))[:64],
        source="api",
        title=title,
        service=str(body.get("service", ""))[:100],
        severity_hint=str(body.get("severity", ""))[:20],
        description=desc[:MAX_TEXT],
        signals=body.get("signals") if isinstance(body.get("signals"), dict) else {},
        started_at=str(body.get("started_at", ""))[:40],
    )


def normalize(payload: dict[str, Any]) -> Incident:
    if payload.get("source") == "aws.cloudwatch" or payload.get("detail-type") == "CloudWatch Alarm State Change":
        return from_cloudwatch(payload)
    if "alerts" in payload and isinstance(payload["alerts"], list):
        return from_alertmanager(payload)
    return from_api(payload)
