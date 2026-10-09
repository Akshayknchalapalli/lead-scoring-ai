import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from interview_demo.agent import deterministic_provider, run_agent
from interview_demo import api
from interview_demo.evaluate import SCENARIOS, evaluate

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEMO_PROVIDER", "offline")

@pytest.mark.parametrize("case", json.loads(SCENARIOS.read_text()), ids=lambda c: c["id"])
def test_scenario(case):
    result = run_agent(case["tenant_id"], case["lead_id"], case["request"])
    assert result["action"] == case["expected_action"]
    assert result["attempts"] <= 2
    assert result["provider"] == "offline"

@pytest.mark.parametrize("bad", [None, {}, {"action": "send_message", "evidence_ids": []},
    {"action": "prioritize_outreach", "evidence_ids": ["invented"]},
    {"action": "prioritize_outreach", "evidence_ids": ["recent_reply", "site_visit", "site_visit"]},
    {"action": "prioritize_outreach", "evidence_ids": ["recent_reply", "site_visit"], "email": "private"}])
def test_reject_bad_output(bad):
    result = run_agent("demo-a", "hot-1", provider=lambda _: bad)
    assert result["status"] == "human_review"
    assert result["attempts"] == 2
    assert result["evidence"] == []

def test_timeout_fallback():
    def timeout(_):
        raise TimeoutError("private request body")
    result = run_agent("demo-a", "hot-1", provider=timeout)
    assert result["action"] == "human_review"
    assert result["attempts"] == 2
    assert "private request body" not in json.dumps(result)

def test_retry_recovery():
    calls = []
    def transient(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise TimeoutError()
        return deterministic_provider(payload)
    result = run_agent("demo-a", "hot-1", provider=transient)
    assert result["status"] == "completed"
    assert result["attempts"] == 2

def test_missing_data_skips_provider():
    def forbidden(_):
        pytest.fail("Provider must not receive absent or unscoped lead data")
    for tenant, lead in [("demo-b", "meeting-1"), ("demo-a", "empty-1")]:
        assert run_agent(tenant, lead, provider=forbidden)["attempts"] == 0

def test_evidence_persistence(tmp_path):
    result = run_agent("demo-a", "hot-1", request="email@example.com", evidence_dir=tmp_path)
    saved = (tmp_path / (result["run_id"] + ".json")).read_text()
    assert json.loads(saved) == result
    assert "email@example.com" not in saved
    assert len(result["prompt_sha256"]) == 64
    assert [t["node"] for t in result["trace"]] == ["retrieve", "advise"]

def test_regression_evidence(tmp_path):
    report = evaluate(tmp_path)
    assert report["passed"] == report["total"] == 10
    assert len(list((tmp_path / "runs").glob("*.json"))) == 10
    assert (tmp_path / "report.md").exists()

def test_api_and_input_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "EVIDENCE_DIR", tmp_path)
    with TestClient(api.app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/demo").text == client.get("/").text
        response = client.post("/demo/run", json={"lead_id": "meeting-1"})
        assert response.status_code == 200
        assert response.json()["action"] == "confirm_meeting"
        assert client.post("/demo/run", json={"request": "x" * 1001}).status_code == 422
        assert client.post("/demo/run", json={"tenant_id": ""}).status_code == 422

def test_ollama_adapter_contract(monkeypatch):
    from interview_demo.agent import ollama_provider
    from interview_demo.prompts import SYSTEM_PROMPT
    observed = {}
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps({"message": {"content": json.dumps({"action": "nurture", "evidence_ids": ["low_engagement"]})}}).encode()
    def fake_open(req, timeout):
        observed.update(url=req.full_url, payload=json.loads(req.data), timeout=timeout)
        return Response()
    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    assert ollama_provider({"policy_action": "nurture"})["action"] == "nurture"
    assert observed["url"].endswith("/api/chat")
    assert observed["timeout"] == 20
    assert observed["payload"]["messages"][0]["content"] == SYSTEM_PROMPT
    assert observed["payload"]["stream"] is False
    assert observed["payload"]["format"] == "json"

def test_report_detects_policy_regression(monkeypatch, tmp_path):
    from interview_demo import agent
    original = agent.policy
    # Reproduce a category-first bug: a scheduled meeting is incorrectly nurtured.
    monkeypatch.setattr(agent, "policy", lambda lead: "nurture" if lead["meeting"] else original(lead))
    report = evaluate(tmp_path)
    failing = [r["scenario"] for r in report["results"] if not r["passed"]]
    assert failing == ["meeting-precedence"]

def test_advisor_routes_precede_original_dashboard_mount(tmp_path, monkeypatch):
    pytest.importorskip("sqlalchemy", reason="Full POC integration requires pip install -e backend")
    pytest.importorskip("pandas", reason="Full POC integration requires pip install -e backend")
    pytest.importorskip("xgboost", reason="Full POC integration requires pip install -e backend")
    from poc.api.app import create_app
    monkeypatch.setattr(api, "EVIDENCE_DIR", tmp_path)
    with TestClient(create_app()) as client:
        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert '<h1>Lead Scoring POC</h1>' in dashboard.text
        assert 'href="/demo"' in dashboard.text
        assert client.get("/demo").text == api.home()
        response = client.post("/demo/run", json={"lead_id": "meeting-1"})
        assert response.status_code == 200
        assert response.json()["action"] == "confirm_meeting"
