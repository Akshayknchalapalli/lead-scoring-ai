# Tasks: Lead Intelligence Scoring Platform

**Input**: Design documents from `/specs/001-lead-scoring-platform/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/scoring-api.yaml`, `quickstart.md`

**Tests**: Critical correctness and reliability tests are explicitly included in this task list.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no direct dependency)
- **[Story]**: User story label for story-phase tasks only
- All tasks include concrete file paths

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize backend and extension structure, dependencies, and baseline runtime configuration.

- [X] T001 Create backend and extension skeleton directories per plan in `backend/` and `extension/`
- [ ] T002 Initialize Python backend project dependencies in `backend/pyproject.toml`
- [ ] T003 [P] Add environment profiles in `backend/config/dev.yaml` and `backend/config/prod.yaml`
- [ ] T004 [P] Create base application entrypoint and wiring in `backend/src/api/app.py`
- [ ] T005 [P] Add queue/runtime bootstrap configuration in `backend/src/config/runtime.py`
- [ ] T006 [P] Add observability bootstrap scaffolding in `backend/src/observability/bootstrap.py`
- [ ] T068 [P] Add local/dev seed data loader for leads and events in `backend/scripts/seed_data.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement core persistence, schema, feature-store skeleton, and shared services required by all stories.

**⚠️ CRITICAL**: No user story implementation begins before this phase completes.

- [ ] T007 Define core ORM entities from `data-model.md` in `backend/src/models/entities.py`
- [ ] T008 Create database migration for core entities and constraints in `backend/src/models/migrations/0001_initial.sql`
- [ ] T009 [P] Implement repository base with mandatory tenant predicates in `backend/src/services/repositories/base_repository.py`
- [ ] T010 [P] Implement model registry service for scope/version resolution in `backend/src/services/model_registry_service.py`
- [ ] T011 [P] Implement feature registry metadata model and loader in `backend/src/feature_store/definitions/registry.py`
- [ ] T012 [P] Implement shared feature transformation utilities in `backend/src/feature_store/aggregations/transforms.py`
- [ ] T013 Implement online/offline parity checker job in `backend/src/feature_store/parity/parity_checker.py`
- [ ] T014 Implement event envelope validator and dead-letter writer in `backend/src/workers/event_validation_worker.py`
- [ ] T015 Implement idempotent score-write helper using `(tenant_id, lead_id, feature_cutoff_ts, model_version)` key in `backend/src/services/score_write_service.py`
- [ ] T016 Implement SLA policy and mitigation trigger manager in `backend/src/services/sla_enforcement_service.py`
- [ ] T017 Implement retention-policy scheduler scaffolding in `backend/src/workers/retention_scheduler.py`
- [ ] T018 Implement authenticated tenant context middleware in `backend/src/api/middleware/tenant_context.py`
- [ ] T019 Implement feature build pipeline orchestrator in `backend/src/feature_store/pipelines/feature_build_pipeline.py`
- [ ] T020 Implement end-to-end scoring pipeline wiring in `backend/src/pipelines/scoring_pipeline.py`

**Checkpoint**: Foundational platform ready; user stories can proceed.

**Definition of Done (Phase 2)**:
- Core schemas, constraints, and tenant guards are implemented.
- Feature build orchestration and scoring pipeline wiring compile and run in dry mode.
- Idempotent score-write helper and SLA/retention scaffolding are callable by workers.

### Phase 2 -> 3 Handoff Debug Checklist (First Integration Pass)

**Purpose**: De-risk the initial end-to-end wiring (`T019`, `T020` -> US1) by validating a minimal, deterministic vertical slice before scaling coverage.

#### Scope: Thin Vertical Slice Only

Start with one event type -> one feature set -> one score -> one API read.

- Single `tenant_id`, single `lead_id`
- 2-3 deterministic events (fixed timestamps)
- One model version (stubbed or simple deterministic model)
- One feature snapshot window (for example, `7d` only)

#### Deterministic Seed Dataset

Use `T068` seed loader to insert:

- `lead_id = "lead_1"`
- `tenant_id = "tenant_1"`

Events:

- `type: email_open, event_ts: T1`
- `type: link_click, event_ts: T2`

Expected outputs (predefined):

- `feature_vector` (exact values)
- `score_probability` (fixed or stubbed)
- `score_category` (based on known thresholds)
- `score_ts` and `feature_cutoff_ts` (controlled)

#### Instrumentation (temporary but high-signal)

Add logs/traces around:

- Enqueue/Dequeue:
  - `event_id`, `tenant_id`, `lead_id`, `event_ts`
- Feature Build (`T019`):
  - `feature_cutoff_ts`
  - computed `feature_vector` (hash plus key fields)
- Score Write (`T015`):
  - idempotency key `(tenant_id, lead_id, feature_cutoff_ts, model_version)`
  - upsert result (`insert` vs `no-op`)
- Cache Layer (`T029`/`T032`):
  - cache hit/miss
  - fallback path (DB read)
- API Read (`T031`):
  - response payload plus `is_stale`, `staleness_seconds`

Prefer structured logs with a shared `request_id` or `trace_id`.

#### Validation Checklist

Event handling:

- Duplicate event (same `event_id`) does not create duplicate effects
- Out-of-order events still produce correct feature snapshot (ordered by `event_ts`)

Feature consistency:

- Online snapshot matches expected deterministic values
- If available, offline parity check produces identical vector

Scoring:

- Exactly one `LeadScore` row per idempotency key
- Re-running pipeline is idempotent (no new row, no drift)

API contract:

- Response matches OpenAPI (fields and types)
- `score_category` matches thresholds
- `score_ts` and `feature_cutoff_ts` are correct and consistent

Cache behavior:

- First read -> miss -> DB fallback
- Subsequent read -> hit
- Cache value equals DB value

Staleness:

- Fresh score returns `is_stale=false`
- Artificially advance time -> `is_stale=true` and recompute path works

#### Failure Injection (quick checks)

- Redis down -> API returns DB-backed score, logs fallback
- Model failure -> last known score served (or safe fallback), no crash
- Queue backlog (simulated delay) -> reconciliation (`T033`) eventually corrects state

#### Exit Criteria (must pass before expanding)

- End-to-end path runs without manual intervention
- Idempotency verified under retries
- Feature snapshot is deterministic and stable
- API responses match contract exactly
- Cache and fallback paths behave as designed

#### Then Expand

Only after passing all checks:

- Add more event types
- Add additional feature windows (`30d`, `lifetime`)
- Enable full model (replace stub)
- Increase concurrency and tenants

---

## Phase 3: User Story 1 - Prioritize High-Intent Leads (Priority: P1) 🎯 MVP

**Goal**: Deliver tenant-safe Hot/Warm/Cold score availability with fresh persisted scores and cache-first read path.

**Independent Test**: A tenant user can fetch lead scores that are category-mapped, freshness-aware, and isolated per tenant with no explanation dependency.

- [ ] T021 [P] [US1] Implement lead-event ingestion endpoint and enqueue path in `backend/src/api/routes/event_ingest.py`
- [ ] T022 [P] [US1] Implement queue consumer for incremental scoring triggers in `backend/src/workers/event_worker.py`
- [ ] T023 [P] [US1] Implement feature aggregation windows (7d/30d/lifetime) in `backend/src/feature_store/aggregations/window_aggregations.py`
- [ ] T024 [US1] Implement online feature snapshot writer in `backend/src/feature_store/online_store/snapshot_writer.py`
- [ ] T025 [US1] Implement offline snapshot persistence for training reuse in `backend/src/feature_store/offline_store/snapshot_archive.py`
- [ ] T026 [US1] Implement model inference service (`load/predict`) in `backend/src/services/model_service.py`
- [ ] T027 [US1] Implement threshold and policy-based category resolver in `backend/src/services/category_service.py`
- [ ] T028 [US1] Implement persisted score source-of-truth repository in `backend/src/services/repositories/lead_score_repository.py`
- [ ] T029 [US1] Implement Redis cache read/write service for lead scores in `backend/src/services/score_cache_service.py`
- [ ] T030 [US1] Implement latest-score lookup optimization with `current_score_ts` pointer maintenance in `backend/src/services/current_score_pointer_service.py`
- [ ] T031 [US1] Implement `GET /score/{lead_id}` and `POST /scores/batch` routes from contract in `backend/src/api/routes/scores.py`
- [ ] T032 [US1] Implement stale-score fallback and degraded freshness response behavior in `backend/src/services/score_read_service.py`
- [ ] T033 [US1] Implement scheduled reconciliation worker for stale/missed lead recompute in `backend/src/workers/scheduler.py`

**Checkpoint**: US1 is independently functional and can be validated via score-read and refresh behavior.

**Definition of Done (Phase 3 / US1)**:
- Score API returns category, freshness metadata, and `score_ts` per contract.
- Cache-hit and DB-fallback behavior is verified.
- Idempotent score persistence and tenant isolation rules are enforced.

---

## Phase 4: User Story 2 - Understand Why a Lead Is Scored (Priority: P2)

**Goal**: Provide on-demand explanation with safe context, caching, quotas, and graceful fallback.

**Independent Test**: A tenant user can request an explanation for a scored lead and receive rationale plus recommended action without affecting score availability.

- [ ] T034 [P] [US2] Implement explanation context builder with non-sensitive feature filtering in `backend/src/services/explanation_context_service.py`
- [ ] T035 [P] [US2] Implement SHAP attribution service for XGBoost scores in `backend/src/services/shap_explanation_service.py`
- [ ] T036 [US2] Implement explanation cache service (separate from score cache) in `backend/src/services/explanation_cache_service.py`
- [ ] T037 [US2] Implement explanation quota and cost-aware throttling checks in `backend/src/services/explanation_quota_service.py`
- [ ] T038 [US2] Implement `POST /explain/{lead_id}` route from contract in `backend/src/api/routes/explanations.py`
- [ ] T039 [US2] Implement fallback explanation response path for failures/timeouts in `backend/src/services/explanation_fallback_service.py`
- [ ] T040 [US2] Implement explanation uniqueness enforcement `(tenant_id, lead_id, score_ts)` in `backend/src/services/repositories/score_explanation_repository.py`

**Checkpoint**: US2 works independently on top of existing scores and degrades gracefully.

**Definition of Done (Phase 4 / US2)**:
- Explanation response matches contract fields (`summary`, `top_signals`, `recommended_action`, `cached`).
- Quota and cost-aware throttling apply without degrading score-read path.
- Explanation fallback path works under dependency failures.

---

## Phase 5: User Story 3 - Control Scoring Per Tenant (Priority: P3)

**Goal**: Enable tenant admins to control scoring activation and policy while preserving isolation and governance.

**Independent Test**: Tenant admin can enable/disable scoring and adjust allowed thresholds for only their tenant without impacting other tenants.

- [ ] T041 [P] [US3] Implement tenant scoring policy repository in `backend/src/services/repositories/tenant_policy_repository.py`
- [ ] T042 [P] [US3] Implement threshold policy validation and governance checks in `backend/src/services/tenant_policy_service.py`
- [ ] T043 [US3] Implement `PATCH /tenant/scoring-policy` route from contract in `backend/src/api/routes/tenant_policy.py`
- [ ] T044 [US3] Implement tenant policy change audit logger in `backend/src/observability/audit_policy_logger.py`
- [ ] T045 [US3] Implement scoring enable/disable enforcement guard in score-read and score-write services in `backend/src/services/scoring_gate_service.py`

**Checkpoint**: US3 independently supports tenant-scoped control and auditability.

**Definition of Done (Phase 5 / US3)**:
- Tenant policy updates are isolated to caller tenant scope.
- Threshold validation and audit logs are persisted.
- Scoring enable/disable gates are enforced in both read and write paths.

---

## Phase 6: Model Lifecycle, Backfill, and Reliability Hardening

**Purpose**: Implement cross-cutting controls for retraining, rollout, backfill, chaos, retention, and operational governance.

- [ ] T046 Implement training dataset builder from offline snapshots in `backend/src/training/dataset_builder.py`
- [ ] T047 [P] Implement model training and evaluation pipeline (AUC + non-regression gates) in `backend/src/training/train_pipeline.py`
- [ ] T048 [P] Implement model promotion workflow (shadow/canary/ramp/full) in `backend/src/training/promotion_workflow.py`
- [ ] T049 Implement historical re-score backfill workflow for promoted model versions in `backend/src/workers/model_backfill_worker.py`
- [ ] T050 [P] Implement drift monitors (PSI/KL/prediction drift) in `backend/src/observability/drift_monitor.py`
- [ ] T051 [P] Implement SLA breach mitigation automation hooks in `backend/src/observability/sla_mitigation_runner.py`
- [ ] T052 Implement chaos scenario runner (Redis outage, queue lag, model failure) in `backend/src/observability/chaos_runner.py`
- [ ] T053 Implement retention and archival execution jobs in `backend/src/workers/retention_jobs.py`
- [ ] T054 Implement feature-registry change workflow (review/compatibility/staged activation) in `backend/src/feature_store/definitions/registry_workflow.py`
- [ ] T055 [P] Implement tenant-scoped metrics dashboards data export in `backend/src/observability/metrics_exporter.py`
- [ ] T056 Run end-to-end validation checklist from `specs/001-lead-scoring-platform/quickstart.md` and record results in `specs/001-lead-scoring-platform/quickstart-validation.md`

**Definition of Done (Phase 6)**:
- Model lifecycle workflows run with promotion gates and rollback readiness.
- Backfill, retention, and chaos jobs execute with auditable outcomes.
- Drift and SLA mitigation telemetry is emitted and actionable.

---

## Phase 7: Verification & Test Hardening

**Purpose**: Validate correctness, contract compliance, idempotency, tenant isolation, and failure behavior before build/deploy.

- [ ] T057 [US1] Add integration test for end-to-end scoring flow in `backend/tests/integration/test_scoring_end_to_end.py`
- [ ] T058 [US1] Add tenant isolation test for score read/write in `backend/tests/integration/test_tenant_isolation_scores.py`
- [ ] T059 [US2] Add explanation correctness and fallback test in `backend/tests/integration/test_explanation_fallback.py`
- [ ] T060 Add OpenAPI contract validation tests for scoring routes in `backend/tests/contract/test_scoring_api.py`
- [ ] T061 Add idempotency test for duplicate events and duplicate score writes in `backend/tests/integration/test_idempotency_events_scores.py`
- [ ] T062 Add Redis failure fallback behavior test in `backend/tests/integration/test_redis_fallback.py`
- [ ] T063 Add model failure fallback behavior test in `backend/tests/integration/test_model_failure_fallback.py`
- [ ] T064 Add queue backlog degradation handling test in `backend/tests/integration/test_queue_backlog_degradation.py`
- [ ] T065 Add stale-score recomputation and freshness-target test in `backend/tests/integration/test_staleness_recompute.py`
- [ ] T066 Add reconciliation loop correctness test in `backend/tests/integration/test_reconciliation_loop.py`
- [ ] T067 Add SLA breach mitigation trigger test in `backend/tests/integration/test_sla_enforcement.py`
- [ ] T069 Add CI workflow gate to run Phase 7 contract/integration/failure-path tests before merge in `.github/workflows/ci.yml`
- [ ] T070 Add route naming alignment check (`/score`, `/scores/batch`, `/explain`, `/tenant/scoring-policy`) against OpenAPI contract in `backend/tests/contract/test_route_naming_alignment.py`

**Definition of Done (Phase 7)**:
- Contract, integration, and failure-path tests pass in CI.
- Fallback behaviors are verified for Redis, model, and queue-degradation scenarios.
- Idempotency and tenant-isolation guarantees are continuously test-enforced.
- CI merge gate blocks changes when Phase 7 verification tests fail.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: starts immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; blocks all user stories.
- **Phase 3 (US1)**: depends on Phase 2; defines MVP.
- **Phase 4 (US2)**: depends on Phase 2 and US1 score availability.
- **Phase 5 (US3)**: depends on Phase 2; can proceed in parallel with later US2 tasks once policy repository is ready.
- **Phase 6 (Hardening)**: depends on completion of US1, US2, and US3 core paths.
- **Phase 7 (Verification)**: depends on Phases 3-6 implementation tasks.

### User Story Dependencies

- **US1 (P1)**: no dependency on other stories after foundational completion.
- **US2 (P2)**: depends on US1 score generation/read path only.
- **US3 (P3)**: independent of US2; integrates with US1 services for policy enforcement.

### Within-Story Ordering

- Data/repository and service tasks before API route exposure.
- Idempotency, tenant checks, and fallback behavior before operational validation.

---

## Parallel Opportunities

- **Setup**: T003-T006 parallel.
- **Foundational**: T009-T012 and T017-T018 parallel.
- **US1**: T019-T021 parallel; T024-T025 parallel; T027-T028 parallel after core persistence.
- **US2**: T032-T033 parallel; T034-T035 parallel.
- **US3**: T039-T040 parallel.
- **Hardening**: T047/T048/T050/T051/T055 parallel after pipeline baseline exists.
- **Verification**: T057-T067 and T070 largely parallel once implementation stabilizes.

---

## Parallel Example: User Story 1

```bash
# Parallel feature/event foundations
Task: "Implement lead-event ingestion endpoint in backend/src/api/routes/event_ingest.py"
Task: "Implement queue consumer in backend/src/workers/event_worker.py"
Task: "Implement aggregation windows in backend/src/feature_store/aggregations/window_aggregations.py"

# Parallel score-serving accelerators
Task: "Implement score cache service in backend/src/services/score_cache_service.py"
Task: "Implement current score pointer service in backend/src/services/current_score_pointer_service.py"
```

---

## Implementation Strategy

### Execution Discipline (Mandatory)

1. Complete **Phase 1 + Phase 2** before starting any user story tasks.
2. Treat **Phase 2 -> 3 Handoff Debug Checklist** as a hard gate:
   - no phase advancement until all exit criteria pass.
3. Build **US1 end-to-end** before starting US2/US3 expansion:
   - ingestion -> feature build -> model inference -> score persistence -> API read.
4. Only expand scope after US1 passes:
   - contract checks
   - fallback-path checks
   - idempotency and tenant-isolation checks

### MVP First (US1 Only)

1. Finish Phase 1 and Phase 2.
2. Complete Phase 3 (US1) end-to-end.
3. Validate independent US1 behavior before moving on.

### Incremental Delivery

1. Add US2 explanations once US1 is stable.
2. Add US3 tenant controls without blocking US2.
3. Add Phase 6 hardening and lifecycle automation.
4. Complete Phase 7 verification before release sign-off.

### Team Parallelization

1. Core platform team: Phase 1-2.
2. After Phase 2:
   - Engineer A: US1 core scoring path
   - Engineer B: US2 explanation path
   - Engineer C: US3 policy controls
3. Reliability/MLOps team executes Phase 6 in parallel with late-story stabilization.

---

## Notes

- Tasks marked `[P]` are parallelizable by design.
- Story labels `[US1]`, `[US2]`, `[US3]` preserve traceability to independent user outcomes.
- Task IDs are execution-ordered (`T001` ... `T070`) and immediately actionable.
