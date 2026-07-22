# Quickstart: Lead Intelligence Scoring Platform

## Objective
Validate the end-to-end scoring flow from event ingestion to score retrieval and explanation, including leakage controls and tenant isolation.

## Prerequisites
- Python 3.11 runtime
- Running PostgreSQL and Redis
- Seeded tenant and lead data
- Feature branch `001-lead-scoring-platform`

## 1) Initialize environment
1. Create and activate Python virtual environment.
2. Install backend and worker dependencies.
3. Select environment profile (`config/dev.yaml` or `config/prod.yaml`).
4. Configure environment variables for DB, Redis, model artifact store, and service auth.

## 2) Apply schema and seed data
1. Apply database migrations for entities described in `data-model.md`.
2. Seed:
   - at least two tenants
   - open leads for each tenant
   - one low-data tenant profile for cold-start validation

## 3) Start services
1. Start API service.
2. Start queue broker and worker consumers.
3. Start feature store update worker.
4. Start reconciliation scheduler (`workers/scheduler.py`).
5. Verify `services/model_service.py` has loaded active model artifact.

## 4) Validate scoring flow
1. Publish lead events with increasing timestamps.
2. Confirm queue consumption and idempotent event handling.
3. Confirm feature snapshots are created in feature store with `feature_cutoff_ts`.
4. Verify score records persist with:
   - `score_probability`
   - `score_category`
   - `model_version`
   - freshness metadata
5. Verify API read path: Redis cache hit or DB fallback.

## 5) Validate API contracts
1. Call score read endpoint for tenant-scoped leads.
2. Confirm response shape matches `contracts/scoring-api.yaml`.
3. Validate no cross-tenant data visibility.

## 6) Validate explanation boundary
1. Trigger explanation only via explicit explain endpoint.
2. Confirm response includes rationale and next action.
3. Verify explanation falls back gracefully if unavailable.

## 7) Validate leakage controls
1. Run pipeline checks enforcing `event_ts <= feature_cutoff_ts`.
2. Ensure post-conversion fields are absent from model inputs.
3. Confirm training and inference datasets remain separated.

## 8) Validate resilience
1. Simulate scoring delay and confirm last persisted score is returned with staleness metadata.
2. Simulate explanation service failure and confirm fallback response.
3. Confirm errors are logged with operational metrics.

## 9) Validate training pipeline
1. Run training workflow from `training/` module on approved extraction window.
2. Confirm AUC evaluation output and model validation gate checks.
3. Confirm approved model artifact is saved to object storage with version metadata.
