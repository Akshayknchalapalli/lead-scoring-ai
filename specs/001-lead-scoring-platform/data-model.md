# Data Model: Lead Intelligence Scoring Platform

## Global Validation Notes
- Unless explicitly marked optional, all required fields are DB-enforced `NOT NULL`.
- `feature_snapshot_ref` canonical format: `{tenant_id}:{lead_id}:{feature_cutoff_ts}`.

## Entity: Lead
- **Description**: Canonical tenant-owned lead record used as scoring subject.
- **Key fields**:
  - `tenant_id` (string, required)
  - `lead_id` (string, required, unique within tenant)
  - `lifecycle_state` (enum: open, closed, archived)
  - `current_score_ts` (timestamp, optional; active-score pointer optimization)
  - `created_at` (timestamp, required)
  - `updated_at` (timestamp, required)
- **Validation**:
  - Uniqueness on `(tenant_id, lead_id)`
  - Scoring eligibility requires `lifecycle_state=open`
  - If `current_score_ts` is set, it must reference the latest valid `LeadScore.score_ts` for `(tenant_id, lead_id)`

## Entity: LeadEvent
- **Description**: Immutable event stream input for feature updates.
- **Key fields**:
  - `event_id` (string, required, globally unique)
  - `tenant_id` (string, required)
  - `lead_id` (string, required)
  - `event_type` (string, required)
  - `event_ts` (timestamp, required)
  - `ingested_at` (timestamp, required)
  - `payload` (object, required)
  - `event_version` (integer, optional)
- **Validation**:
  - Idempotency by `event_id`
  - `event_id` MUST be globally unique
  - Reject feature contribution when `event_ts > feature_cutoff_ts`
  - Pipeline MUST be replay-safe: duplicate or already-applied events are ignored
  - Pipeline MUST handle out-of-order arrival by ordering on `event_ts` during feature aggregation and reconciliation

## Entity: LeadFeatureSnapshot
- **Description**: Canonical feature vector snapshot at a specific scoring cutoff.
- **Key fields**:
  - `tenant_id` (string, required)
  - `lead_id` (string, required)
  - `feature_cutoff_ts` (timestamp, required)
  - `feature_vector` (object, required)
  - `feature_schema_version` (string, required)
  - `is_leakage_validated` (boolean, required)
  - `feature_snapshot_ref` (string, optional; lineage/debug reference identifier, format `{tenant_id}:{lead_id}:{feature_cutoff_ts}`)
- **Validation**:
  - Unique key `(tenant_id, lead_id, feature_cutoff_ts)`
  - `is_leakage_validated` must be true before scoring
  - Logical reference: `(tenant_id, lead_id)` must resolve to an existing `Lead`

## Entity: ModelVersion
- **Description**: Registry entry for model lifecycle management.
- **Key fields**:
  - `model_version` (string, required, unique)
  - `model_scope` (enum: global, tenant, segment, required)
  - `scope_key` (string, optional; null for global, tenant id for tenant scope, segment id for segment scope)
  - `trained_at` (timestamp, required)
  - `status` (enum: candidate, approved, active, rolled_back, retired)
  - `training_window` (object, required)
  - `metrics` (object, required)
  - `artifact_uri` (string, required)
- **Validation**:
  - `scope_key` MUST be null when `model_scope=global`
  - `scope_key` MUST match `tenant_id` of scoring context when `model_scope=tenant`
  - `scope_key` MUST match `segment_id` of scoring context when `model_scope=segment`
  - Only one `active` model per `(model_scope, scope_key)` tuple
  - Promotion requires validation checks passed

## Entity: LeadScore
- **Description**: Durable score record and source of truth for reads.
- **Key fields**:
  - `tenant_id` (string, required)
  - `lead_id` (string, required)
  - `score_probability` (float, required, [0,1])
  - `score_category` (enum: cold, warm, hot, required as derived snapshot)
  - `threshold_policy_version` (string, required)
  - `score_ts` (timestamp, required)
  - `model_version` (string, required)
  - `feature_cutoff_ts` (timestamp, required)
  - `feature_snapshot_ref` (string, optional; logical lineage reference to `LeadFeatureSnapshot`, format `{tenant_id}:{lead_id}:{feature_cutoff_ts}`)
  - `is_cold_start` (boolean, required)
  - `is_stale` (boolean, required)
  - `staleness_seconds` (integer, required)
- **Validation**:
  - Unique idempotency key `(tenant_id, lead_id, feature_cutoff_ts, model_version)`
  - `score_category` is a derived snapshot from `score_probability` using `threshold_policy_version` at write time
  - Current-category views MUST be recomputed at read time if active threshold policy changed since `threshold_policy_version`
  - Category mapping from thresholds:
    - cold `<0.40`
    - warm `>=0.40 and <0.80`
    - hot `>=0.80`
  - Logical references:
    - `(tenant_id, lead_id)` must resolve to an existing `Lead`
    - `model_version` must resolve to an existing `ModelVersion`

## Entity: TenantScoringPolicy
- **Description**: Tenant-level controls and threshold overrides.
- **Key fields**:
  - `tenant_id` (string, required, unique)
  - `scoring_enabled` (boolean, required)
  - `threshold_cold_max` (float, required)
  - `threshold_hot_min` (float, required)
  - `override_enabled` (boolean, required)
  - `policy_version` (string, required)
- **Validation**:
  - `threshold_cold_max < threshold_hot_min`
  - Override allowed only when governance checks pass

## Entity: ScoreExplanation
- **Description**: On-demand explanation output for a specific score context.
- **Key fields**:
  - `explanation_id` (string, required, unique)
  - `tenant_id` (string, required)
  - `lead_id` (string, required)
  - `score_ts` (timestamp, required)
  - `summary` (string, required)
  - `top_signals` (array[string], required)
  - `recommended_action` (string, required)
  - `expires_at` (timestamp, optional)
- **Validation**:
  - Unique key `(tenant_id, lead_id, score_ts)` to avoid duplicate explanations for the same scored state
  - Explanation request authorized by lead access scope
  - Prompt context excludes direct PII and sensitive free text

## Relationships
- `Lead` 1..* `LeadEvent`
- `Lead` 1..* `LeadFeatureSnapshot`
- `LeadFeatureSnapshot` 1..* `LeadScore` (multiple model versions can score the same snapshot cutoff)
- `ModelVersion` 1..* `LeadScore`
- `TenantScoringPolicy` 1..* `LeadScore`
- `LeadScore` 0..* `ScoreExplanation`

## Logical Constraint Enforcement
- Foreign-key style constraints SHOULD be enforced in the database where supported.
- If DB-level FK enforcement is unavailable for selected paths, service-layer validation is mandatory before writes.
- Minimum service-layer checks:
  - `LeadScore.model_version` -> `ModelVersion.model_version`
  - `LeadScore.(tenant_id, lead_id)` -> `Lead.(tenant_id, lead_id)`
  - `LeadFeatureSnapshot.(tenant_id, lead_id)` -> `Lead.(tenant_id, lead_id)`

## Active Score Pointer Optimization (Optional)
- Optimization options:
  - Add `Lead.current_score_ts` as denormalized latest-score pointer, or
  - Use separate `LeadCurrentScore(tenant_id, lead_id, score_ts)` table for pointer isolation.
- Benefit:
  - O(1)-style latest-score lookup for high-volume reads.
- Tradeoff:
  - Additional write-path complexity to maintain pointer consistency on score updates/replays.
- Safety rule:
  - Pointer updates must be transactional with `LeadScore` writes or protected by idempotent reconciliation repair jobs.

## State Transitions
- **LeadScore freshness**:
  - `fresh` -> `stale` when `now - score_ts > staleness_target`
  - `staleness_target` source is tenant policy when configured; otherwise global default config
  - `stale` -> `fresh` after recomputation persisted
- **Model lifecycle**:
  - `candidate` -> `approved` -> `active`
  - `active` -> `rolled_back` (incident path)
  - `active` or `rolled_back` -> `retired`

## Indexing Strategy
- **LeadScore**
  - `(tenant_id, lead_id)` for lead score lookup
  - `(tenant_id, lead_id, score_ts DESC)` for latest-score-per-lead retrieval
  - `(tenant_id, score_ts DESC)` for latest score retrieval
  - `(tenant_id, is_stale, score_ts)` for reconciliation scans
  - unique `(tenant_id, lead_id, feature_cutoff_ts, model_version)` for idempotent writes
- **LeadFeatureSnapshot**
  - `(tenant_id, lead_id, feature_cutoff_ts DESC)` for nearest snapshot lookup
- **LeadEvent**
  - `(tenant_id, lead_id, event_ts)` for ordered replay and aggregation
  - unique `(event_id)` for event deduplication
