# POC Implementation Tasks: Lead Intelligence Scoring Prototype

**Input**: `poc/spec.md`, `poc/data-findings.md`, `poc/design.md`
**Reuses**: existing `backend/src/models/entities.py`, `backend/src/config/`, `backend/src/observability/logging.py`, Alembic setup already in the repo.
**Does not build**: anything in the "Explicitly out of scope" list in `poc/spec.md`.
**Folder structure, DB schema, feature list, and encoding are locked in `poc/design.md` — do not redecide them mid-implementation.**

## Phase A0: Config & shared spec

- [X] A0a. `backend/config/poc.yaml` — CSV file list, data/model dirs, sqlite `database_url`, top tenants, threshold percentiles, model_version (per `design.md` §4).
- [X] A0b. `backend/src/poc/config.py` — `load_poc_config()` reading `poc.yaml`.
- [X] A0c. `backend/src/poc/feature_spec.py` — canonical feature list + dtype/encoding (per `design.md` §6), imported by `features.py`, `train.py`, and `explain.py` so the three never drift out of sync.

## Phase A: Data ETL (new, real-data-specific)

- [X] A1. `backend/src/poc/etl/versioned_json.py` — utility to parse a versioned-JSON cell (`{"1": "New", "2": "Pending"}`) and return `(current_value, transition_count)`; handle null/empty/malformed cells safely.
- [X] A2. `backend/src/poc/etl/load_csv.py` — load the 5 CSVs (path via `poc.yaml`, not hardcoded), concat, dedupe by `LeadId` keeping the row with the latest `ModifiedDate`. **Checkpoint: log and assert 49,830 unique leads.**
- [X] A3. `backend/src/poc/etl/label.py` — derive the conversion label per POC-FR-002 (parsed `BookedDate` present OR parsed `SoldPrice > 0`), excluding cancelled/reverted bookings per FR-011/FR-019. **Checkpoint: log and assert 158 positive labels (162 raw signal minus 4 cancelled/reverted, per FR-011/FR-019).**
- [X] A4. `backend/src/poc/etl/features.py` — build the flat feature table from `feature_spec.py`. Explicitly excludes the PII columns listed in POC-FR-010.
- [X] A5. `backend/src/poc/etl/build_dataset.py` — orchestrates A1-A4, writes `backend/data/poc/processed_dataset.parquet` (features + label) for the full dataset; demo tenant filtering happens at score/serve time, not at training time (global model per spec).

**Exit check**: running the ETL script produces `processed_dataset.parquet` with ~49,830 rows, a label column with 158 positives, and no PII columns present.

## Phase B: Model

- [X] B1. `backend/src/poc/training/train.py` — stratified train/test split, XGBoost classifier with native categorical support and imbalance handling (`scale_pos_weight`), fit on Phase A's feature table, writes `backend/models/poc/model_poc_v1.json`.
- [X] B2. `backend/src/poc/training/evaluate.py` — compute AUC, precision/recall at candidate thresholds; pick percentile-based Hot/Warm/Cold cutoffs (POC-FR-004); writes `metrics.json`, `thresholds.json`.
- [X] B3. `backend/src/poc/training/score_all.py` — score every lead, write `lead_scores.csv`.
- [X] B4. `backend/src/poc/training/explain.py` — per-lead top-3 contributions via `Booster.predict(pred_contribs=True)` (per `design.md` §8), mapped to plain-language signal names, plus a canned next-action string keyed by category + top feature.
- [X] B5. `backend/src/poc/db/seed.py` — writes `Lead`, `TenantScoringPolicy`, `ModelVersion`, `LeadFeatureSnapshot`, `LeadScore` rows into the sqlite DB from the Phase A/B outputs (per `design.md` §5 table). No new tables.

**Exit check**: `score_all.py` + `seed.py` run produces a persisted `LeadScore` row for every lead; `evaluate.py` output (AUC, category counts) is saved to a file for the CTO one-pager.

## Phase C: API (minimal, synchronous — no queue/cache)

- [X] C1. `backend/src/poc/api/app.py` — minimal FastAPI app (reuse `backend/src/config`/`observability` bootstrap already in repo).
- [X] C2. `backend/src/poc/api/lead_routes.py`: `GET /poc/leads?tenant_id=` — list leads for a tenant with `score_probability`, `score_category`; returns empty/hidden when tenant scoring is disabled (POC-FR-008).
- [X] C3. `backend/src/poc/api/lead_routes.py`: `GET /poc/leads/{lead_id}/score` — single lead score lookup; `POST /poc/leads/{lead_id}/explain` — calls `explain.py`, returns `{summary, top_signals, recommended_action}` (contract-compatible shape with full spec's `ScoreExplanation`).
- [X] C4. `backend/src/poc/api/tenant_routes.py`: `PATCH /poc/tenants/{tenant_id}/scoring-policy` — toggle `scoring_enabled` for a tenant, updates the `TenantScoringPolicy` row.

**Exit check**: all endpoints respond correctly against the scored demo data; toggling one tenant off doesn't affect another tenant's list.

## Phase D: Demo UI

- [X] D1. `ui/poc/index.html` — single-page UI (plain HTML/JS, served as a static file by FastAPI) — tenant dropdown, lead table with color-coded Hot/Warm/Cold badges, "Explain" button per row opening a panel with rationale + next action, and an enable/disable toggle for the selected tenant.

**Exit check**: clicking through the UI tells the full demo story end to end without touching curl/Postman.

## Phase E: CTO-facing packaging

- [X] E1. `backend/scripts/run_poc_pipeline.py` — one command that runs Phase A → B end to end from the 5 CSVs, so the pipeline is reproducible/re-runnable during the demo if asked.
- [X] E2. One-page summary (metrics + real vs simplified split, per POC-SC-005) — AUC, category distribution, tenant count used, and the "what's real / what's simplified for POC" list from `poc/spec.md`.

---

## Suggested order
A (ETL) → B (model) → C (API) → D (UI) → E (packaging). A and B are the highest-risk/most novel work given the versioned-JSON parsing and severe class imbalance — do those first and validate the numbers in `data-findings.md` hold before building anything on top.

## Rough effort
Phase A: ~0.5-1 day (versioned-JSON parsing is the fiddly part). Phase B: ~0.5 day. Phase C: ~0.5 day. Phase D: ~0.5 day. Phase E: ~0.25 day. **~2-3 days total.**
