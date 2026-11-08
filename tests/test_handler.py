import json

import pytest

from incidentscribe import handler


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for k in ("BUDGET_TABLE", "INCIDENTS_TABLE", "SLACK_PARAM", "GUARDRAIL_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MODEL_ID", "offline")


def http_event(method, path, body=None):
    return {"version": "2.0", "rawPath": path, "requestContext": {"http": {"method": method, "path": path}},
            "body": json.dumps(body) if body is not None else None, "isBase64Encoded": False}


def test_health_and_samples():
    r = handler.lambda_handler(http_event("GET", "/health"))
    assert r["statusCode"] == 200 and json.loads(r["body"])["model"] == "offline"
    samples = json.loads(handler.lambda_handler(http_event("GET", "/samples"))["body"])
    assert len(samples) == 8 and all(s["title"] for s in samples)


def test_post_sample_and_custom():
    r = handler.lambda_handler(http_event("POST", "/incidents", {"sample_id": "DEMO-28"}))
    body = json.loads(r["body"])
    assert r["statusCode"] == 200 and body["meta"]["redactions"]["EMAIL"] == 1
    assert "priya.sharma" not in r["body"]
    r = handler.lambda_handler(http_event("POST", "/incidents", {"title": "Lambda throttles", "description": "Task timed out"}))
    assert json.loads(r["body"])["summary"]["runbook_id"] == "RB-07"


def test_http_errors(monkeypatch):
    assert handler.lambda_handler(http_event("POST", "/incidents", {"sample_id": "nope"}))["statusCode"] == 404
    big = http_event("POST", "/incidents", {"description": "x" * 9000})
    assert handler.lambda_handler(big)["statusCode"] == 413
    bad = http_event("POST", "/incidents")
    bad["body"] = "not json"
    assert handler.lambda_handler(bad)["statusCode"] == 400
    monkeypatch.setenv("ALLOW_CUSTOM_TEXT", "false")
    assert handler.lambda_handler(http_event("POST", "/incidents", {"title": "x"}))["statusCode"] == 403
    assert handler.lambda_handler(http_event("GET", "/nope"))["statusCode"] == 404


def test_cloudwatch_event_and_ok_transition_skipped():
    alarm = json.loads((handler.resources.files("incidentscribe") / "samples.json").read_text())[0]["incident"]
    out = handler.lambda_handler(alarm)
    assert out["summary"]["runbook_id"] == "RB-01" and out["source"] == "cloudwatch"
    ok = json.loads(json.dumps(alarm))
    ok["detail"]["state"]["value"] = "OK"
    assert handler.lambda_handler(ok) == {"skipped": "not an ALARM transition"}


def test_public_api_cannot_choose_record_ids():
    r = handler.lambda_handler(http_event("POST", "/incidents", {"id": "INC-REAL-ALARM", "title": "disk full on web-1"}))
    body = json.loads(r["body"])
    assert body["incident_id"].startswith("WEB-INC-") and "REAL-ALARM" not in body["incident_id"]


def test_bedrock_client_fails_inside_the_lambda_timeout(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    handler.boto.cache_clear()
    cfg = handler.boto("bedrock-runtime").meta.config
    assert cfg.read_timeout + cfg.connect_timeout < 30 and cfg.retries["total_max_attempts"] == 1
