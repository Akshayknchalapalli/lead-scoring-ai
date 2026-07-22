# POC Requirements: Lead Intelligence Scoring (Data-Driven Prototype)

**Parent feature**: `specs/001-lead-scoring-platform/spec.md`
**Purpose**: A scoped-down, demoable prototype for a CTO review — built on the real 50,000-row lead export, not synthetic data. See `poc/data-findings.md` for the data grounding behind every decision below.

This is **not** a subset of the full spec's task list — several full-spec requirements (event-driven refresh, Redis cache, hybrid reconciliation, SHAP, drift/retrain automation, chaos testing, retention/archival, feature registry governance) are explicitly out of scope here because the input is a historical CSV snapshot, not a live event stream. Full spec.md remains authoritative for production scope.

## Goal
Show that real historical lead data can be turned into a trustworthy Hot/Warm/Cold classification with an explainable rationale, isolated per tenant, in a form a sales rep or CTO can click through.

## In scope

- **POC-FR-001**: Ingest the 5 provided CSV exports, flatten the versioned-JSON fields (see data-findings.md) to current-value + transition-count features, and dedupe by `LeadId` (keep latest by `ModifiedDate`).
- **POC-FR-002**: Label each lead as converted using the spec's own rule — `BookedDate` present or `SoldPrice > 0` (post JSON-parse) — and exclude cancelled/reverted bookings unless a later valid booking exists (FR-011/FR-019, validated against real data in data-findings.md).
- **POC-FR-003**: Train one global classifier (tenant_id as a feature, per spec's global-model-with-tenant-aware-features decision) on the flattened, PII-free feature set to predict conversion probability.
- **POC-FR-004**: Map each lead's predicted probability to exactly one category (Hot/Warm/Cold) using percentile-derived thresholds (not the full spec's default 0.40/0.80 cutoffs — label prevalence here is 0.32%, so fixed cutoffs would put almost every lead in "Cold"). Thresholds are a documented placeholder for business sign-off, not a final policy.
- **POC-FR-005**: Persist one score record per lead (`tenant_id`, `lead_id`, `score_probability`, `score_category`, `model_version`, `scored_at`) — reusing the existing `LeadScore`/`Lead` ORM entities where they fit.
- **POC-FR-006**: Expose a read API: list leads with category badges (filterable by tenant), get a single lead's score, and request an explanation.
- **POC-FR-007**: Explanation = top 3 contributing features (by model feature-importance/contribution for that lead) + a canned recommended next action mapped from category + top feature. No SHAP/live LLM required, but response shape should match the full spec's contract (`summary`, `top_signals`, `recommended_action`) so it's a drop-in upgrade later.
- **POC-FR-008**: Tenant scoring toggle — a simple enabled/disabled flag per tenant; disabling hides scores for that tenant's leads in the list/read API. Demonstrated using the top 4-5 real tenants by lead volume.
- **POC-FR-009**: A minimal browser UI showing the lead list with category badges, a tenant selector, and an "explain" action per lead — this is what gets demoed, not raw API responses.
- **POC-FR-010**: PII fields (`Name`, `Email`, `ContactNo`, `AlternateContactNo`, `ReferralName`, `ReferralContactNo`, `LandLine`, `DateOfBirth`, `ConfidentialNotes`, `Notes`) are excluded from model features and from any explanation text.

## Explicitly out of scope for POC
- Event ingestion API / queue / worker (no live events exist in this dataset)
- Redis cache layer, hybrid event-driven + reconciliation scoring
- SHAP explainability (feature-importance-based rationale is the POC stand-in)
- Drift detection, scheduled/drift-triggered retraining, model promotion/rollback governance
- Chaos testing, SLA enforcement automation, rate limiting/throttling
- Retention/archival jobs, feature registry governance workflow, historical re-score backfill lineage
- Precise event-time cutoff enforcement per feature (not reconstructable from this export — see data-findings.md point 2)

## Model & threshold approach
- Algorithm: XGBoost binary classifier (already the intended stack per plan.md), `scale_pos_weight` or equivalent to handle ~1:300 class imbalance.
- Split: stratified train/test split on the full ~49,830-lead dataset (time-ordered by `CreatedDate` where feasible; strict time-based validation as in full spec is a post-POC hardening item, not a blocker here given the small positive count).
- Primary metric: AUC, reported alongside precision/recall at the chosen thresholds — consistent with the full spec's evaluation strategy (Q&A in spec.md).
- Thresholds: percentile-based (e.g., top ~10% of scores → Hot, next ~30% → Warm, remainder → Cold) chosen to produce a visually meaningful category split for the demo; explicitly flagged in the demo as provisional, pending business threshold governance (FR-021/FR-022 in full spec).

## Success criteria for the CTO demo
- **POC-SC-001**: Every lead in the demo tenant list shows exactly one Hot/Warm/Cold badge.
- **POC-SC-002**: Switching the tenant selector changes the visible lead set; disabling scoring for one tenant hides its badges without affecting other tenants.
- **POC-SC-003**: Clicking "explain" on any lead returns a rationale (top signals) and a recommended next action within a couple seconds.
- **POC-SC-004**: The trained model's AUC and category distribution are presented as real numbers from the real dataset, not illustrative placeholders.
- **POC-SC-005**: A one-page summary clearly separates "real in this POC" (data, labels, tenants, model) from "simplified for this POC" (no live events, no cache/queue infra, provisional thresholds) so the CTO can evaluate the idea and the production gap separately.

## Assumptions
- The 5 CSVs are a representative, if noisy, sample of production lead data; POC does not require additional cleansing beyond the versioned-JSON flattening and PII exclusion described above.
- A local Postgres or SQLite instance is acceptable for the POC; no requirement to stand up Redis/queue infra.
- Demo runs against a static, pre-scored snapshot — re-running the pipeline (not live refresh) is how "new data" would be shown if needed during the demo.
