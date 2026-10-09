from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from interview_demo.data import ACTIONS, LEADS, SIGNALS
from interview_demo.prompts import PROMPT_VERSION, SYSTEM_PROMPT

Provider = Callable[[dict], dict]

class State(TypedDict, total=False):
    tenant_id: str
    lead_id: str
    request: str
    lead: dict | None
    action: str
    evidence_ids: list[str]
    status: str
    attempts: int
    trace: list[dict]


def policy(lead: dict) -> str:
    if not lead["signals"]:
        return "human_review"
    if lead["meeting"]:
        return "confirm_meeting"
    return {"hot": "prioritize_outreach", "warm": "follow_up", "cold": "nurture"}[lead["category"]]


def deterministic_provider(payload: dict) -> dict:
    """Offline test double, NOT an LLM. Same output contract as live mode."""
    return {"action": payload["policy_action"], "evidence_ids": payload["signals"]}


def ollama_provider(payload: dict) -> dict:
    """Optional real inference with a locally running Ollama model."""
    body = json.dumps({
        "model": os.getenv("OLLAMA_MODEL", "qwen3:4b"),
        "stream": False, "format": "json",
        "options": {"temperature": 0},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": json.dumps(payload)}],
    }).encode()
    endpoint = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    req = urllib.request.Request(endpoint + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.load(response)
    return json.loads(result["message"]["content"])


def build_graph(provider: Provider):
    def retrieve(state):
        # Composite tenant+lead key: a lead ID alone never authorizes a lookup.
        lead = LEADS.get((state["tenant_id"], state["lead_id"]))
        return {"lead": lead, "trace": [{"node": "retrieve", "outcome": "found" if lead else "unavailable"}]}

    def advise(state):
        lead = state["lead"]
        expected = policy(lead)
        trace = list(state["trace"])
        if expected == "human_review":
            trace.append({"node": "advise", "outcome": "insufficient_evidence"})
            return {"action": expected, "evidence_ids": [], "status": "human_review", "attempts": 0, "trace": trace}
        payload = {"signals": list(lead["signals"]), "category": lead["category"],
                   "policy_action": expected, "request": state["request"]}
        for attempt in range(1, 3):
            try:
                candidate = provider(payload)
                if not isinstance(candidate, dict) or set(candidate) != {"action", "evidence_ids"}:
                    raise ValueError("invalid schema")
                ids = candidate["evidence_ids"]
                if (candidate["action"] != expected or not isinstance(ids, list)
                    or not all(isinstance(i, str) for i in ids)
                    or len(ids) != len(set(ids)) or set(ids) != set(lead["signals"])):
                    raise ValueError("ungrounded response")
                trace.append({"node": "advise", "attempt": attempt, "outcome": "validated"})
                return {"action": expected, "evidence_ids": sorted(ids), "status": "completed", "attempts": attempt, "trace": trace}
            except Exception as exc:
                # Record error class only; upstream messages may contain sensitive text.
                trace.append({"node": "advise", "attempt": attempt, "outcome": "rejected", "error_type": type(exc).__name__})
        return {"action": "human_review", "evidence_ids": [], "status": "human_review", "attempts": 2, "trace": trace}

    def unavailable(state):
        return {"action": "unavailable", "status": "unavailable", "evidence_ids": [], "attempts": 0,
                "trace": state["trace"] + [{"node": "unavailable", "outcome": "scope_or_missing"}]}

    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve)
    graph.add_node("advise", advise)
    graph.add_node("unavailable", unavailable)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges("retrieve", lambda s: "advise" if s["lead"] else "unavailable")
    graph.add_edge("advise", END)
    graph.add_edge("unavailable", END)
    return graph.compile()


def run_agent(tenant_id: str, lead_id: str, request: str = "Explain the next step", *,
              provider: Provider | None = None, evidence_dir: Path | None = None) -> dict:
    mode = os.getenv("DEMO_PROVIDER", "offline")
    if mode not in {"offline", "ollama"}:
        raise ValueError("DEMO_PROVIDER must be offline or ollama")
    provider_name = "injected-test-double" if provider is not None else mode
    selected = provider if provider is not None else (ollama_provider if mode == "ollama" else deterministic_provider)
    started = time.perf_counter()
    state = build_graph(selected).invoke({"tenant_id": tenant_id, "lead_id": lead_id, "request": request})
    evidence = [{"id": i, "fact": SIGNALS[i]} for i in state["evidence_ids"]]
    result = {
        "run_id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_version": "lead-advisor-1", "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        "input_sha256": hashlib.sha256(json.dumps([tenant_id, lead_id, request]).encode()).hexdigest(),
        "provider": provider_name, "model": os.getenv("OLLAMA_MODEL", "qwen3:4b") if provider_name == "ollama" else None,
        "status": state["status"], "action": state["action"], "summary": ACTIONS[state["action"]],
        "evidence": evidence, "attempts": state["attempts"], "trace": state["trace"],
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "scoring_source": "synthetic fixture; not a trained prediction",
    }
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        path = evidence_dir / (result["run_id"] + ".json")
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
