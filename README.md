# Lead Scoring AI

The existing ML POC lives under `backend/src/poc/` and requires customer CSVs and generated model artifacts. Its XGBoost scoring and feature-contribution explanations are separate from the new interview demo.

## Run the interview demo (no customer data needed)

Use Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-demo.lock.txt
export PYTHONPATH=backend/src
export DEMO_PROVIDER=offline
uvicorn interview_demo.api:app --host 127.0.0.1 --port 8000
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`, then set `$env:PYTHONPATH="backend/src"` and `$env:DEMO_PROVIDER="offline"`.

Open http://127.0.0.1:8000. Select a tenant and lead, run the advisor, inspect its trace, and download JSON evidence. The API explorer is at http://127.0.0.1:8000/docs.

**Offline mode uses a deterministic test double, not an LLM. Scores are synthetic fixtures, not trained predictions.** The workflow itself uses LangGraph in both modes. This is a bounded, read-only workflow with code-enforced actions; the model does not autonomously choose tools or modify CRM records.

### Real local model mode (optional)

Install Ollama and download a model you can run on your laptop, for example:

```bash
ollama pull qwen3:4b
export DEMO_PROVIDER=ollama
export OLLAMA_MODEL=qwen3:4b
uvicorn interview_demo.api:app --host 127.0.0.1 --port 8000
```

Ollama must be running at http://127.0.0.1:11434; `OLLAMA_BASE_URL` can override it. Restart the demo after changing modes. The adapter sends a versioned system prompt and scoped signals to `/api/chat`, validates the JSON output, and permits at most two attempts. Invalid output or a timeout routes to a human-review recommendation. Real model inference was **not** validated in the development environment; rehearse it locally before presenting it. Offline tests demonstrate workflow behavior, not prompt quality on a real model.

### Run regression checks

In another terminal, with the same environment activated:

```bash
export PYTHONPATH=backend/src
export DEMO_PROVIDER=offline
pytest backend/tests -q --junitxml=artifacts/junit.xml
python -m interview_demo.evaluate --output artifacts/regression
```

Tests check expected actions, tenant boundaries, invalid outputs, bounded retries, evidence persistence, and API validation. The scenario runner writes a Markdown report, a JSON report, and per-run JSON evidence. Failures return a nonzero exit code. CI uploads these artifacts and no longer suppresses pytest failures.

To evaluate the actual model, run the same scenario runner with `DEMO_PROVIDER=ollama`. Compare failures and run evidence before revising a prompt; do not interpret offline passes as proof of model robustness.

## Documentation

- [Interview preparation, role mapping, and demo script](docs/interview-preparation.md)
- [Agent requirements and acceptance criteria](docs/interview-agent-requirements.md)
- [Existing ML POC code walkthrough](docs/poc-code-walkthrough.md)
- [Architecture](docs/architecture/README.md)

Run the demo on localhost with synthetic data. Tenant selection tests lookup scoping; it is **not authentication**. Production integration needs authenticated tenant context, persistent access-controlled audit storage, and an adapter to the actual scoring service. The current demo does not claim RAG, autonomous tool calling, production readiness, or measured conversion uplift.
