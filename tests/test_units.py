import datetime as dt
import json

import boto3
import pytest
from botocore.stub import Stubber
from moto import mock_aws

from incidentscribe.budget import Budget
from incidentscribe.incident import from_alertmanager, from_cloudwatch, normalize
from incidentscribe.llm import BedrockLLM, Pricing, fallback_answer, parse_answer
from incidentscribe.pipeline import Deps, process, redact_incident
from incidentscribe.rag import default_index, load_runbooks
from incidentscribe.redact import redact

NOW = dt.datetime(2026, 10, 24, 12, tzinfo=dt.UTC)


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")


# ------------------------------------------------------------------ redaction
@pytest.mark.parametrize("text,kind,secret", [
    ("mail ravi.k@example.org now", "EMAIL", "ravi.k@example.org"),
    ("call +91 98765 43210", "PHONE", "98765 43210"),
    ("call 9876543210", "PHONE", "9876543210"),
    ("from 10.20.30.40", "IP", "10.20.30.40"),
    ("key AKIAIOSFODNN7EXAMPLE leaked", "AWS_ACCESS_KEY", "AKIAIOSFODNN7EXAMPLE"),
    ("token ghp_abcdefghijklmnopqrstuvwxyz0123", "GITHUB_TOKEN", "ghp_abcdefghijklmnopqrstuvwxyz0123"),
    ("card 4111-1111-1111-1111", "CARD", "4111-1111-1111-1111"),
    ("aadhaar 2345 6789 0123", "AADHAAR", "2345 6789 0123"),
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", "JWT", "eyJhbGciOiJIUzI1NiJ9"),
    ("DATABASE_URL=postgres://app:pw123@db:5432/x", "CONN_STRING_CREDS", "pw123"),
    ("password: Sup3r!", "PASSWORD", "Sup3r!"),
])
def test_redact_types(text, kind, secret):
    out, counts = redact(text)
    assert counts[kind] >= 1, (out, counts)
    assert secret not in out


def test_redact_keeps_normal_ops_text():
    text = "orders-db CPUUtilization 96 > 80 at 2026-10-20T10:15:00Z, request id 1234567890123456, task exit code 137"
    out, counts = redact(text)
    assert out == text and not counts   # long request id fails the Luhn check, so it is not a card


# ------------------------------------------------------------------ retrieval
def test_runbooks_load_and_search():
    books = load_runbooks()
    assert len(books) == 12 and books[0].id == "RB-01"
    idx = default_index()
    assert idx.search("pods OOMKilled crashloopbackoff")[0].runbook.id == "RB-09"
    assert idx.search("certificate expires soon")[0].runbook.id == "RB-10"
    assert idx.search("zzzz qqqq") == []


# ------------------------------------------------------------------ normalisers
def test_cloudwatch_and_alertmanager_normalisers():
    cw = {"source": "aws.cloudwatch", "detail-type": "CloudWatch Alarm State Change", "region": "ap-south-1", "time": "t",
          "detail": {"alarmName": "db-cpu", "state": {"value": "ALARM", "reason": "CPU 95 > 80", "timestamp": "ts"},
                     "configuration": {"metrics": [{"metricStat": {"metric": {"namespace": "AWS/RDS", "name": "CPUUtilization",
                                                                              "dimensions": {"DBInstanceIdentifier": "orders-db"}}}}]}}}
    inc = normalize(cw)
    assert inc.source == "cloudwatch" and inc.service == "orders-db" and "CPU 95" in inc.description
    am = {"alerts": [{"status": "firing", "labels": {"alertname": "X", "severity": "critical", "service": "pay"},
                      "annotations": {"summary": "pay down"}, "startsAt": "s"}]}
    inc2 = normalize(am)
    assert inc2.source == "alertmanager" and inc2.title == "pay down" and inc2.severity_hint == "critical"
    assert from_cloudwatch(cw).id == from_cloudwatch(cw).id      # stable ids
    assert from_alertmanager(am).id.startswith("INC-")


# ------------------------------------------------------------------ model output
GOOD = {"title": "t", "severity": "sev2", "service": "s", "summary": "Something broke.", "likely_causes": ["a", "b", "c", "d"],
        "next_steps": ["1"], "runbook_id": "RB-01", "confidence": "high"}


def test_parse_answer_validates_and_trims():
    data = parse_answer("Sure! ```json\n" + json.dumps(GOOD) + "\n```")
    assert data["severity"] == "SEV2" and len(data["likely_causes"]) == 3
    with pytest.raises(ValueError):
        parse_answer(json.dumps({**GOOD, "severity": "P1"}))
    with pytest.raises(ValueError):
        parse_answer("no json here")


def test_pricing_math():
    p = Pricing(0.037, 0.148, 0.00025)
    assert p.cost(1_000_000, 0) == pytest.approx(0.037)
    assert p.cost(0, 0, guardrail_chars=2500) == pytest.approx(3 * 0.00025)
    assert p.estimate(4000, 500, guardrail=True) > p.estimate(4000, 500, guardrail=False)


def _converse_response(text, stop="end_turn"):
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}, "stopReason": stop,
            "usage": {"inputTokens": 900, "outputTokens": 150, "totalTokens": 1050}, "metrics": {"latencyMs": 400}}


def test_bedrock_converse_request_and_parsing(aws_env):
    client = boto3.client("bedrock-runtime", region_name="ap-south-1")
    stub = Stubber(client)
    stub.add_response("converse", _converse_response(json.dumps(GOOD)), {
        "modelId": "apac.amazon.nova-micro-v1:0", "system": [{"text": "sys"}],
        "messages": [{"role": "user", "content": [{"text": "user"}]}],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.2},
        "guardrailConfig": {"guardrailIdentifier": "gr-1", "guardrailVersion": "2", "trace": "disabled"},
    })
    with stub:
        inc = normalize({"title": "x"})
        res = BedrockLLM(client, "apac.amazon.nova-micro-v1:0", "gr-1", "2").complete("sys", "user", inc, [], 300)
    assert res.data["severity"] == "SEV2" and res.guardrail == "passed" and res.input_tokens == 900


def test_bedrock_guardrail_intervention_falls_back(aws_env):
    client = boto3.client("bedrock-runtime", region_name="ap-south-1")
    stub = Stubber(client)
    stub.add_response("converse", _converse_response("Sorry, blocked.", stop="guardrail_intervened"))
    with stub:
        inc = normalize({"title": "Disk full", "severity": "high"})
        res = BedrockLLM(client, "m", "gr-1", "1").complete("s", "u", inc, default_index().search("disk full"), 300)
    assert res.guardrail == "intervened" and res.data["runbook_id"] == "RB-08" and res.data["confidence"] == "low"


def test_bad_model_output_falls_back(aws_env):
    client = boto3.client("bedrock-runtime", region_name="ap-south-1")
    stub = Stubber(client)
    stub.add_response("converse", _converse_response("I think it is fine."))
    with stub:
        res = BedrockLLM(client, "m").complete("s", "u", normalize({"title": "x"}), [], 300)
    assert res.notes and res.data["confidence"] == "low"


# ------------------------------------------------------------------ budget + pipeline
@pytest.fixture
def budget_table(aws_env):
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")
        t = ddb.create_table(TableName="budget", KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
        yield t


def test_budget_caps(budget_table):
    b = Budget(budget_table, daily_cap_usd=0.01, monthly_cap_usd=1.0, now=NOW)
    assert b.check(0.004).allowed
    b.record(0.004)
    b.record(0.004)
    d = b.check(0.004)
    assert not d.allowed and "daily" in d.reason and d.spent_today == pytest.approx(0.008)
    item = budget_table.get_item(Key={"pk": "day#2026-10-24"})["Item"]
    assert int(item["calls"]) == 2


class CountingLLM:
    model_id = "test-model"

    def __init__(self):
        self.calls = 0

    def complete(self, system, user, inc, hits, max_tokens):
        from incidentscribe.llm import LLMResult
        self.calls += 1
        assert "<incident>" in user and "[EMAIL]" in user and "someone@example.org" not in user
        return LLMResult(data=fallback_answer(inc, hits, "test"), model=self.model_id, input_tokens=1000, output_tokens=200, raw="{}")


def test_pipeline_redacts_before_the_model_and_respects_budget(budget_table):
    llm = CountingLLM()
    deps = Deps(llm=llm, budget=Budget(budget_table, 0.00015, 1.0, now=NOW), pricing=Pricing(0.037, 0.148))
    payload = {"title": "500 errors for someone@example.org", "service": "web", "description": "HTTP 500 on checkout"}
    first = process(payload, deps)
    assert first["meta"]["llm_used"] and first["meta"]["redactions"] == {"EMAIL": 1} and llm.calls == 1
    assert first["meta"]["cost_usd"] == pytest.approx(1000 * 0.037e-6 + 200 * 0.148e-6, abs=1e-6)
    second = process(payload, deps)   # cap is tiny: the second call must not reach the model
    assert llm.calls == 1 and not second["meta"]["llm_used"] and "budget" in second["meta"]["fallback_reason"]
    assert second["summary"]["runbook_id"] == "RB-01"


def test_slack_failure_does_not_lose_the_summary():
    def boom(_):
        raise TimeoutError("slack down")
    res = process({"title": "queue backlog growing", "description": "SQS ApproximateAgeOfOldestMessage high"}, Deps(slack=boom))
    assert res["meta"]["slack"].startswith("failed") and res["summary"]["runbook_id"] == "RB-11"


def test_bedrock_error_falls_back_and_costs_nothing(aws_env):
    client = boto3.client("bedrock-runtime", region_name="ap-south-1")
    stub = Stubber(client)
    stub.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    with stub:
        res = process({"title": "queue backlog growing", "description": "SQS ApproximateAgeOfOldestMessage high"},
                      Deps(llm=BedrockLLM(client, "m")))
    meta = res["meta"]
    assert not meta["llm_used"] and meta["cost_usd"] == 0 and "ThrottlingException" in meta["fallback_reason"]
    assert res["summary"]["runbook_id"] == "RB-11" and res["summary"]["confidence"] == "low"


def test_real_account_ids_are_not_redacted_and_signals_keep_their_shape():
    from importlib import resources
    alarm = json.loads((resources.files("incidentscribe") / "samples.json").read_text())[0]["incident"]
    alarm["account"] = "234567890123"            # starts with 2-9: looked like an Aadhaar number before
    inc = normalize(alarm)
    counts = redact_incident(inc)
    assert not counts and inc.signals["metrics"] and "account" not in inc.signals
    dims = {"metrics": [{"dimensions": {"InstanceId": "i-1", "PrivateIp": "10.1.2.3"}}]}
    inc2 = normalize({"title": "x", "signals": dims})
    assert redact_incident(inc2) == {"IP": 1} and inc2.signals["metrics"][0]["dimensions"]["PrivateIp"] == "[IP]"


def test_every_prompt_field_is_redacted():
    inc = normalize({"title": "x", "severity": "a@b.io", "started_at": "call +91 98765 43210 " + "z" * 100})
    counts = redact_incident(inc)
    assert counts == {"EMAIL": 1, "PHONE": 1} and "a@b.io" not in inc.text() and len(inc.started_at) <= 40
