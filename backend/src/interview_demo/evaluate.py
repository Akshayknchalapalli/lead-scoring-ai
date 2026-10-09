"""Scenario runner: nonzero exit on failure, JSON and Markdown evidence reports."""
import argparse
import hashlib
import json
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

from interview_demo.agent import run_agent
from interview_demo.prompts import PROMPT_VERSION

SCENARIOS = Path(__file__).with_name("scenarios.json")

def evaluate(output: Path) -> dict:
    results = []
    for case in json.loads(SCENARIOS.read_text()):
        run = run_agent(case["tenant_id"], case["lead_id"], case["request"], evidence_dir=output / "runs")
        expected_nodes = ["retrieve", "unavailable" if case["expected_action"] == "unavailable" else "advise"]
        checks = {
            "action": run["action"] == case["expected_action"],
            "trace": list(dict.fromkeys(t["node"] for t in run["trace"])) == expected_nodes,
            "prompt_version": run["prompt_version"] == PROMPT_VERSION,
            "evidence": bool(run["evidence"]) if run["status"] == "completed" else run["evidence"] == [],
        }
        results.append({"scenario": case["id"], "passed": all(checks.values()), "checks": checks, "run_id": run["run_id"]})
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        revision, dirty = "unknown", None
    report = {"suite": "lead-advisor-regression-v1", "git_revision": revision, "working_tree_dirty": dirty,
              "scenario_sha256": hashlib.sha256(SCENARIOS.read_bytes()).hexdigest(),
              "runtime": {"python": platform.python_version(), "langgraph": version("langgraph")},
              "total": len(results), "passed": sum(r["passed"] for r in results), "results": results}
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2))
    rows = ["# Lead Advisor Regression Report", "", f"Passed: {report['passed']}/{report['total']}", "",
            "| Scenario | Result | Run ID |", "|---|---|---|"]
    rows += [f"| {r['scenario']} | {'PASS' if r['passed'] else 'FAIL'} | {r['run_id']} |" for r in results]
    (output / "report.md").write_text("\n".join(rows) + "\n")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/regression"))
    args = parser.parse_args()
    report = evaluate(args.output)
    print(f"Regression scenarios: {report['passed']}/{report['total']} passed; evidence: {args.output}")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
