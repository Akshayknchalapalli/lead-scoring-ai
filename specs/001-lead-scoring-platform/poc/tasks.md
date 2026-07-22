# POC Implementation Tasks: Lead Intelligence Scoring Prototype

**Input**: `poc/spec.md`, `poc/data-findings.md`
**Reuses**: existing `backend/src/models/entities.py`, `backend/src/config/`, `backend/src/observability/logging.py`, Alembic setup already in the repo.
**Does not build**: anything in the "Explicitly out of scope" list in `poc/spec.md`.

## Phase A: Data ETL (new, real-data-specific)

- [ ] A1. `backend/src/poc/etl/versioned_json.py` — utility to parse a versioned-JSON cell (`{"1": "New", "2": "Pending"}`) and return `(current_value, transition_count)`; handle null/empty/malformed cells safely.
- [ ] A2. `backend/src/poc/etl/load_csv.py` — load the 5 CSVs (path via config/env, not hardcoded), concat, dedupe by `LeadId` keeping the row with the latest `ModifiedDate`.
- [ ] A3. `backend/src/poc/etl/label.py` — derive the conversion label per POC-FR-002 (parsed `BookedDate` present OR parsed `SoldPrice > 0`), excluding cancelled/reverted bookings per FR-011/FR-019.
- [ ] A4. `backend/src/poc/etl/features.py` — build the flat feature table: property type, BHK type/count, budget range, city/state, lead source code, sale type, enquired-for, picked/meeting/site-visit flags, contact-record engagement count, status-transition count, days-since-created, days-since-modified, tenant_id. Explicitly excludes the PII columns listed in POC-FR-010.
- [ ] A5. `backend/src/poc/etl/build_dataset.py` — orchestrates A1-A4, writes a processed feature table (parquet/CSV or directly into a `lead_feature_snapshot`-shaped table) plus the label column, for the top 4-5 tenants by volume (demo set) and the full dataset (model training set).

**Exit check**: running the ETL script produces a feature table with ~49,830 rows, a label column with ~162 positives, and no PII columns present.

## Phase B: Model

- [ ] B1. `backend/src/poc/training/train.py` — stratified train/test split, XGBoost classifier with imbalance handling (`scale_pos_weight`), fit on Phase A's feature table.
- [ ] B2. `backend/src/poc/training/evaluate.py` — compute AUC, precision/recall at candidate thresholds; pick percentile-based Hot/Warm/Cold cutoffs (POC-FR-004) and record them alongside the metrics.
- [ ] B3. `backend/src/poc/training/score_all.py` — score every lead in the demo tenant set, write one row per lead into a `LeadScore`-shaped table (`tenant_id`, `lead_id`, `score_probability`, `score_category`, `model_version="poc-v1"`, `scored_at`).
- [ ] B4. `backend/src/poc/training/explain.py` — for a given lead, return top 3 contributing features (via model feature importances / per-row contribution) mapped to plain-language signal names, plus a canned next-action string keyed by category + top feature.

**Exit check**: `score_all.py` run produces a persisted score for every demo-tenant lead; `evaluate.py` output (AUC, category counts) is saved to a file for the CTO one-pager.

## Phase C: API (minimal, synchronous — no queue/cache)

- [ ] C1. `backend/src/poc/api/app.py` — minimal FastAPI app (reuse `backend/src/config`/`observability` bootstrap already in repo).
- [ ] C2. `GET /poc/leads?tenant_id=` — list leads for a tenant with `score_probability`, `score_category`; returns empty/hidden when tenant scoring is disabled (POC-FR-008).
- [ ] C3. `GET /poc/leads/{lead_id}/score` — single lead score lookup.
- [ ] C4. `POST /poc/leads/{lead_id}/explain` — calls `explain.py`, returns `{summary, top_signals, recommended_action}` (contract-compatible shape with full spec's `ScoreExplanation`).
- [ ] C5. `PATCH /poc/tenants/{tenant_id}/scoring-policy` — toggle `scoring_enabled` for a tenant (simple table/in-memory dict is fine for POC).

**Exit check**: all 4 endpoints respond correctly against the scored demo data; toggling one tenant off doesn't affect another tenant's list.

## Phase D: Demo UI

- [ ] D1. Single-page UI (plain HTML/JS served by FastAPI, or a small React page if time allows) — tenant dropdown, lead table with color-coded Hot/Warm/Cold badges, "Explain" button per row opening a panel with rationale + next action, and an enable/disable toggle for the selected tenant.

**Exit check**: clicking through the UI tells the full demo story end to end without touching curl/Postman.

## Phase E: CTO-facing packaging

- [ ] E1. `backend/scripts/run_poc_pipeline.py` — one command that runs Phase A → B end to end from the 5 CSVs, so the pipeline is reproducible/re-runnable during the demo if asked.
- [ ] E2. One-page summary (metrics + real vs simplified split, per POC-SC-005) — AUC, category distribution, tenant count used, and the "what's real / what's simplified for POC" list from `poc/spec.md`.

---

## Suggested order
A (ETL) → B (model) → C (API) → D (UI) → E (packaging). A and B are the highest-risk/most novel work given the versioned-JSON parsing and severe class imbalance — do those first and validate the numbers in `data-findings.md` hold before building anything on top.

## Rough effort
Phase A: ~0.5-1 day (versioned-JSON parsing is the fiddly part). Phase B: ~0.5 day. Phase C: ~0.5 day. Phase D: ~0.5 day. Phase E: ~0.25 day. **~2-3 days total.**
