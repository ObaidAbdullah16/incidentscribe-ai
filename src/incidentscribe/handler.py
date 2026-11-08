"""AWS Lambda entry point.

Triggers:
  - EventBridge "CloudWatch Alarm State Change" (state ALARM)  -> summarise + Slack
  - API Gateway HTTP API:  GET /health, GET /samples, POST /incidents
  - Direct invoke with an Alertmanager webhook or {"title": ..., "description": ...}
"""
from __future__ import annotations

import base64
import json
import os
import time
from functools import cache
from importlib import resources
from typing import Any

from .budget import Budget
from .llm import BedrockLLM, FakeLLM, Pricing
from .pipeline import Deps, process
from .slack import post as slack_post

MAX_BODY = 8 * 1024
_SLACK: dict[str, Any] = {"url": None, "at": 0.0}


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@cache
def boto(service: str) -> Any:
    import boto3
    if service == "bedrock-runtime":
        from botocore.config import Config
        # botocore waits 60 s by default, longer than the 30 s Lambda timeout: a slow model call
        # would kill the function (and be retried and billed again). Fail inside the timeout
        # instead, so the fallback summary still goes out.
        return boto3.client(service, config=Config(connect_timeout=3, read_timeout=20, retries={"total_max_attempts": 1, "mode": "standard"}))
    return boto3.client(service)


@cache
def samples() -> dict[str, dict[str, Any]]:
    data = json.loads(resources.files("incidentscribe").joinpath("samples.json").read_text(encoding="utf-8"))
    return {s["id"]: s for s in data}


def slack_url() -> str | None:
    name = env("SLACK_PARAM")
    if not name:
        return None
    if time.time() - _SLACK["at"] > 300:   # cache for 5 minutes
        try:
            value = boto("ssm").get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
        except Exception:  # noqa: BLE001
            value = ""
        _SLACK["url"] = value if value.startswith("https://hooks.slack.com/") else None
        _SLACK["at"] = time.time()
    return _SLACK["url"]


def deps(send_slack: bool) -> Deps:
    model = env("MODEL_ID", "offline")
    guardrail_id = env("GUARDRAIL_ID")
    llm = FakeLLM() if model == "offline" else BedrockLLM(boto("bedrock-runtime"), model, guardrail_id, env("GUARDRAIL_VERSION"))
    budget = None
    if env("BUDGET_TABLE"):
        import boto3
        budget = Budget(boto3.resource("dynamodb").Table(env("BUDGET_TABLE")),
                        float(env("DAILY_CAP_USD", "0.15")), float(env("MONTHLY_CAP_USD", "4.50")))
    store = None
    if env("INCIDENTS_TABLE"):
        import boto3
        store = boto3.resource("dynamodb").Table(env("INCIDENTS_TABLE"))
    url = slack_url() if send_slack else None
    pricing = Pricing(float(env("PRICE_IN_PER_MTOK", "0.037")), float(env("PRICE_OUT_PER_MTOK", "0.148")))
    return Deps(llm=llm, pricing=pricing, budget=budget, store=store,
                slack=(lambda r: slack_post(url, r)) if url else None,
                max_tokens=int(env("MAX_TOKENS", "500")), guardrail=bool(guardrail_id))


def http(status: int, body: Any) -> dict[str, Any]:
    return {"statusCode": status, "headers": {"content-type": "application/json", "cache-control": "no-store"},
            "body": json.dumps(body, default=str)}


def handle_http(event: dict[str, Any]) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    if method == "GET" and path.endswith("/health"):
        return http(200, {"ok": True, "model": env("MODEL_ID", "offline"), "guardrail": bool(env("GUARDRAIL_ID"))})
    if method == "GET" and path.endswith("/samples"):
        return http(200, [{"id": s["id"], "title": s["title"], "kind": s["kind"], "incident": s["incident"]} for s in samples().values()])
    if method == "POST" and path.endswith("/incidents"):
        raw = event.get("body") or ""
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8", errors="replace")
        if len(raw) > MAX_BODY:
            return http(413, {"error": f"body larger than {MAX_BODY} bytes"})
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return http(400, {"error": "body must be JSON"})
        if not isinstance(body, dict):
            return http(400, {"error": "body must be a JSON object"})
        if "sample_id" in body:
            sample = samples().get(str(body["sample_id"]))
            if not sample:
                return http(404, {"error": "unknown sample_id"})
            body = sample["incident"]
        elif env("ALLOW_CUSTOM_TEXT", "true") != "true":
            return http(403, {"error": "custom incidents are disabled on this demo; use sample_id"})
        body = {k: v for k, v in body.items() if k != "id"}   # visitors don't choose record keys
        public = deps(send_slack=False)   # public demo endpoint: never post visitor input to Slack
        public.id_prefix = "WEB-"         # and keep its records apart from real alarm records
        return http(200, process(body, public))
    return http(404, {"error": "not found"})


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    if "requestContext" in event and "http" in event.get("requestContext", {}):
        return handle_http(event)
    if event.get("source") == "aws.cloudwatch" and event.get("detail", {}).get("state", {}).get("value") != "ALARM":
        return {"skipped": "not an ALARM transition"}
    result = process(event, deps(send_slack=True))
    print(json.dumps({"incident_id": result["incident_id"], "severity": result["summary"]["severity"],
                      "llm_used": result["meta"]["llm_used"], "cost_usd": result["meta"]["cost_usd"],
                      "redactions": result["meta"]["redactions"]}))
    return result
