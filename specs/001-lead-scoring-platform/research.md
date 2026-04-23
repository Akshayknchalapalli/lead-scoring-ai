# Research: Lead Intelligence Scoring Platform

## Decision 1: Hybrid scoring pipeline
- **Decision**: Use event-triggered score refresh plus scheduled reconciliation jobs.
- **Rationale**: Meets freshness goals while recovering from delayed or missed events.
- **Tradeoffs accepted**: Additional operational complexity from running both streaming and scheduled paths.
- **Alternatives considered**:
  - Pure real-time only: weak resilience for delayed/out-of-order events.
  - Pure batch only: fails near-real-time freshness expectations.

## Decision 2: Persisted score as source of truth
- **Decision**: Persist all computed scores durably; use cache as read acceleration only.
- **Rationale**: Keeps results auditable and deterministic under cache churn.
- **Tradeoffs accepted**: Extra write load and storage overhead per recompute.
- **Alternatives considered**:
  - Cache-only authority: fragile and hard to audit.
  - Always live-compute reads: expensive under high read load.

## Decision 3: Global model with tenant-aware features
- **Decision**: Use a global model with tenant-scoped features and calibration.
- **Rationale**: Avoids sparse per-tenant model quality collapse while preserving tenant behavior signals.
- **Tradeoffs accepted**: Highly unique tenants may be underfit until sufficient data is available.
- **Alternatives considered**:
  - Per-tenant models: weak for low-volume tenants and high maintenance cost.
  - Global model without tenant context: lower personalization quality.

## Decision 4: Strict leakage prevention
- **Decision**: Enforce `event_ts <= feature_cutoff_ts`, exclude post-conversion fields from model inputs, and keep training/inference datasets separated.
- **Rationale**: Prevents inflated offline performance and production mismatch.
- **Tradeoffs accepted**: Additional validation layers and stricter data contracts in pipelines.
- **Alternatives considered**:
  - Convention-based controls only: too error-prone.
  - Masking post-conversion data: still leakage-prone.

## Decision 5: Threshold governance
- **Decision**: Use global default thresholds with controlled tenant overrides and governed A/B tuning.
- **Rationale**: Balances consistency and tenant-level optimization.
- **Tradeoffs accepted**: Governance overhead for approval and audit workflows.
- **Canonical policy source**: `spec.md` (`FR-021`) defines policy requirements; `plan.md` defines runtime application details.
- **Alternatives considered**:
  - Fixed global only: no adaptation.
  - Unrestricted tenant edits: inconsistent business outcomes.

## Decision 6: Missing-data strategy
- **Decision**: Standardize missing-data handling across tenants; use canonical defaults and prune persistently sparse non-critical features.
- **Rationale**: Keeps feature semantics stable and model behavior consistent.
- **Tradeoffs accepted**: Some edge-signal loss from pruning high-missing features.
- **Alternatives considered**:
  - Tenant-specific imputation logic: reduced comparability.
  - Blindly drop all high-missing fields: possible quality loss.

## Decision 7: Feature store architecture
- **Decision**: Use explicit `feature_store` system with `definitions`, `aggregations`, `online_store`, and `offline_store`, keyed by `(tenant_id, lead_id, feature_cutoff_ts)`.
- **Rationale**: Enables reuse for scoring and training with clear ownership boundaries.
- **Tradeoffs accepted**: Higher upfront implementation cost than direct per-request computation.
- **Alternatives considered**:
  - On-demand recomputation: unstable latency and reproducibility.
  - Raw DB joins for every score: weak maintainability at scale.

## Decision 8: Online/offline feature parity
- **Decision**: Share transformation code and feature metadata across online/offline paths, validated by parity tests on sampled tuples.
- **Rationale**: Reduces training-serving skew risk.
- **Tradeoffs accepted**: Slower feature iteration due to stricter compatibility requirements.
- **Alternatives considered**:
  - Independent implementations: faster iteration, high drift risk.

## Decision 9: Training pipeline and dataset source
- **Decision**: Implement dedicated training module; build datasets from offline snapshots only.
- **Rationale**: Improves reproducibility and leakage control.
- **Tradeoffs accepted**: Additional orchestration and storage lifecycle management.
- **Alternatives considered**:
  - Notebook-only training: poor repeatability.
  - Live-path data for training: increased reproducibility risk.

## Decision 10: Model service contract
- **Decision**: Centralize load, predict, and probability-to-category mapping in `services/model_service.py`.
- **Rationale**: Prevents scoring logic drift between workers and API.
- **Tradeoffs accepted**: Requires strict versioning and backward compatibility in one shared module.
- **Alternatives considered**:
  - Distributed inference logic: higher drift and bug risk.

## Decision 11: Explainability strategy
- **Decision**: Use SHAP TreeExplainer for XGBoost and cache explanations separately from score cache.
- **Rationale**: Improves trust with defensible feature attributions while isolating expensive path behavior.
- **Tradeoffs accepted**: Higher compute/latency cost for uncached explanation requests.
- **Alternatives considered**:
  - Heuristic-only explanations: lower trust and diagnostics.

## Decision 12: Queue and scheduler baseline
- **Decision**: Use Redis-backed queue workers plus scheduled reconciliation (`workers/scheduler.py`).
- **Rationale**: Supports both immediacy and consistency.
- **Tradeoffs accepted**: Queue and scheduler operations increase platform complexity.
- **Alternatives considered**:
  - Queue-only: missed-event reconciliation gaps.
  - Scheduler-only: weaker burst handling.

## Decision 13: Queue degradation policy
- **Decision**: Prioritize recent/high-value lead updates during backlog spikes and expose freshness degradation alerts.
- **Rationale**: Maintains business impact during incident windows.
- **Tradeoffs accepted**: Lower-priority leads may see delayed refresh.
- **Alternatives considered**:
  - Strict FIFO only: predictable ordering, poorer business responsiveness.

## Decision 14: Drift detection and retraining gates
- **Decision**: Use PSI/KL drift checks with monthly baseline retraining and early retrain triggers; gate promotions with AUC and non-regression checks.
- **Rationale**: Converts retraining policy into measurable controls.
- **Tradeoffs accepted**: Increased monitoring and evaluation workload.
- **Alternatives considered**:
  - Manual drift review only: slow and subjective.

## Decision 15: Progressive rollout strategy
- **Decision**: Roll out new models via shadow -> canary -> progressive tenant ramp -> full release.
- **Rationale**: Reduces blast radius and catches regressions early.
- **Tradeoffs accepted**: Longer time to full deployment.
- **Alternatives considered**:
  - Immediate full cutover: faster rollout, higher risk.

## Decision 16: Runtime fallback policy
- **Decision**: Define hard fallbacks for Redis, inference, and explanation failures using persisted score and deterministic fallback behavior.
- **Rationale**: Preserves user-facing availability under dependency failure.
- **Tradeoffs accepted**: Temporary reliance on stale scores during incidents.
- **Alternatives considered**:
  - Fail-fast dependency behavior: unacceptable user disruption.

## Decision 17: Event schema and evolution policy
- **Decision**: Standardize `LeadEvent` envelope with versioned schema and dead-letter invalid events.
- **Rationale**: Stabilizes ingestion and supports forward-compatible changes.
- **Tradeoffs accepted**: Additional validation and schema governance overhead.
- **Alternatives considered**:
  - Unstructured payload-only events: brittle integrations.

## Decision 18: Observability baseline
- **Decision**: Instrument latency, queue lag, freshness, drift, and per-tenant error metrics with enforceable alert thresholds and tracing.
- **Rationale**: Enables proactive incident detection and SLO management.
- **Tradeoffs accepted**: Higher telemetry volume and storage cost.
- **SLA enforcement mechanism**: sustained SLA breaches trigger automated mitigation (autoscaling and workload reprioritization), then controlled degradation for non-critical workloads if breaches persist.
- **Alternatives considered**:
  - Minimal logging-only approach: weak operational visibility.

## Decision 19: Tenant isolation enforcement
- **Decision**: Enforce tenant-scoped auth, mandatory tenant predicates, row-level guards, and tenant-scoped cache/queue keys.
- **Rationale**: Converts isolation principles into enforceable controls.
- **Tradeoffs accepted**: Additional implementation and testing overhead for every data path.
- **Alternatives considered**:
  - Best-effort app-layer checks only: unsafe in multi-tenant systems.

## Decision 20: Storage/index strategy
- **Decision**: Use tenant-aware composite indexes and time partitioning aligned with read/reconciliation patterns.
- **Rationale**: Maintains predictable latency under growth.
- **Tradeoffs accepted**: More complex migration and maintenance operations.
- **Alternatives considered**:
  - Reactive indexing after incidents: delayed reliability improvements.

## Decision 21: Scoring idempotency
- **Decision**: Enforce unique score idempotency key `(tenant_id, lead_id, feature_cutoff_ts, model_version)`.
- **Rationale**: Prevents duplicate score rows from retries and race conditions.
- **Tradeoffs accepted**: Upsert conflict handling complexity in high-concurrency paths.
- **Alternatives considered**:
  - Event-idempotency only: insufficient for duplicate score compute paths.

## Decision 22: Cold-start strategy
- **Decision**: Use conservative prior-based scoring for no-signal leads and transition once minimum signals are observed.
- **Rationale**: Keeps scoring available without overconfident early classification.
- **Tradeoffs accepted**: Early predictions may be less personalized.
- **Alternatives considered**:
  - No-score behavior for cold starts: weaker UX and prioritization continuity.

## Decision 23: Cost-aware governance
- **Decision**: Track per-tenant compute usage and apply budget-aware throttling on expensive non-critical paths.
- **Rationale**: Improves cost predictability while protecting core score-read traffic.
- **Tradeoffs accepted**: Potentially delayed explanation responses for high-usage tenants.
- **Alternatives considered**:
  - Unlimited usage: cost spikes and abuse risk.

## Decision 24: Data retention and archival
- **Decision**: Define explicit retention windows for events, snapshots, scores, and explanation cache with auditable jobs and compliance holds.
- **Rationale**: Balances analytics value, cost, and compliance posture.
- **Tradeoffs accepted**: Long-horizon backtesting may require archive restoration workflows.
- **Canonical policy source**: `spec.md` (`FR-034`, `SC-014`) defines retention obligations; `plan.md` defines initial operational window values.
- **Alternatives considered**:
  - Indefinite retention: cost and privacy/compliance risk.

## Decision 25: Environment separation
- **Decision**: Maintain separate runtime profiles (`config/dev.yaml`, `config/prod.yaml`) with isolated tuning and secret handling.
- **Rationale**: Reduces accidental production misconfiguration.
- **Tradeoffs accepted**: Configuration drift risk if profile parity checks are not automated.
- **Alternatives considered**:
  - Single shared config: simpler, less safe operationally.

## Decision 26: Chaos testing reliability program
- **Decision**: Introduce scheduled chaos scenarios for Redis outage, queue lag spikes, and model-service degradation to continuously validate fallback behavior.
- **Rationale**: Converts reliability assumptions into regularly verified operational evidence.
- **Tradeoffs accepted**: Additional test infrastructure and controlled-failure operational overhead.
- **Alternatives considered**:
  - Incident-driven validation only: too reactive and incomplete.

## Decision 27: Model-upgrade historical backfill
- **Decision**: After approved model promotion, run tenant-scoped historical re-score backfill with dual-version lineage preservation.
- **Rationale**: Keeps historical analytics and downstream consumers consistent with upgraded scoring semantics.
- **Tradeoffs accepted**: Temporary extra compute/storage load and longer upgrade completion windows.
- **Alternatives considered**:
  - No backfill after upgrade: lower cost but inconsistent historical comparability.

## Decision 28: Feature registry version governance surface
- **Decision**: Manage `feature_schema_version` through a controlled human workflow with review, compatibility checks, staged activation, and version history visibility.
- **Rationale**: Reduces accidental schema drift and improves operational clarity for online/offline feature consumers.
- **Tradeoffs accepted**: Slower schema-change throughput due to governance checkpoints.
- **Alternatives considered**:
  - Code-only implicit registry updates: faster but high coordination risk.

## Decision 29: Phase-2 self-serve registry UI
- **Decision**: Plan a self-serve UI for feature-registry lifecycle operations after core platform stabilization.
- **Rationale**: Reduces operator friction and broadens safe operational ownership.
- **Tradeoffs accepted**: Additional product/UI investment outside core scoring delivery.
- **Alternatives considered**:
  - CLI-only operations long-term: lower build cost, poorer accessibility for non-engineering operators.

## Decision 30: Automated experiment platform
- **Decision**: Plan experiment orchestration tooling for model/threshold tests with standardized evaluation and guardrails.
- **Rationale**: Speeds controlled optimization while reducing manual analysis variance.
- **Tradeoffs accepted**: Added orchestration and governance complexity.
- **Alternatives considered**:
  - Manual experiments only: slower iteration and inconsistent rigor.

## Decision 31: Cost dashboarding
- **Decision**: Plan cost dashboards for per-tenant compute/explanation consumption and budget risk monitoring.
- **Rationale**: Improves financial visibility and proactive optimization.
- **Tradeoffs accepted**: Additional telemetry and reporting infrastructure overhead.
- **Alternatives considered**:
  - Ad-hoc reporting: lower implementation effort, weaker continuous cost control.
