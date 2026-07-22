# Feature Specification: Lead Intelligence Scoring Platform

**Feature Branch**: `[001-lead-scoring-platform]`  
**Created**: 2026-04-23  
**Status**: Draft  
**Input**: User description: "docs/lead_ai_scoring.md file"

## Clarifications

### Session 2026-04-23

- Q: How is conversion defined? → A: A lead is converted when `BookedDate` exists or `SoldPrice` is greater than zero.
- Q: How are cancelled or reverted bookings handled? → A: Cancelled or reverted bookings are treated as not converted unless a later valid booking event occurs.
- Q: What cutoff strategy should be used for features? → A: Use a strict feature cutoff timestamp per scoring event, with no signals beyond that cutoff.
- Q: How is leakage prevented from outcome fields? → A: Outcome and post-conversion fields are excluded from model inputs and only used for labels or offline evaluation.
- Q: What scoring mode is used? → A: Hybrid mode with event-driven refresh, periodic reconciliation, and cache-assisted reads.
- Q: What is the source of truth for score values? → A: Persisted latest computed score is the source of truth; cache is a performance layer.
- Q: Global or per-tenant model? → A: Use a global model with tenant-aware features; low-data tenants rely on shared patterns.
- Q: Are source-quality rates tenant specific? → A: Yes, compute source-quality rates at tenant scope with fallback to global priors for sparse data.
- Q: How is missing data handled? → A: Use standardized missing-data policies across tenants, including explicit unknown/default categories for attribution fields.
- Q: Evaluation strategy and primary metric? → A: Use time-based validation, optimize for AUC as primary ranking metric, and monitor precision/recall and business lift.
- Q: Should training and inference datasets be separated? → A: Yes, maintain separate training and inference views with the same cutoff enforcement policy.
- Q: When is LLM explanation used? → A: Trigger only on explicit explanation request, with optional short-lived caching for repeated queries.

### Session 2026-04-23 (Extended)

- Q: Should partial or staged bookings count as conversion? → A: No, partial or staged bookings are not conversion until final booking validity criteria are met.
- Q: What is the exact `feature_cutoff_ts` definition? → A: `feature_cutoff_ts` is the effective scoring-time boundary for each lead score evaluation event.
- Q: Are all feature events timestamped and cutoff-validated? → A: Yes, all feature events must carry event time and pass cutoff validation before feature inclusion.
- Q: What scoring mode is selected? → A: Hybrid operation is required: event-driven score refresh plus scheduled reconciliation for consistency.
- Q: What if scoring computation is delayed? → A: Return last valid persisted score with staleness indicator, and trigger prioritized recomputation.
- Q: What are category thresholds? → A: Default thresholds are Cold `<0.40`, Warm `0.40-<0.80`, Hot `>=0.80`.
- Q: Are thresholds tenant configurable? → A: Thresholds are globally defaulted with controlled tenant-level override capability.
- Q: Is threshold experimentation supported? → A: Yes, controlled threshold tuning and A/B evaluation are supported under governance.
- Q: What is maximum acceptable score staleness? → A: Score staleness target is 5 minutes maximum for visible leads in enabled tenants.
- Q: How are stale scores handled? → A: Show last known score with freshness metadata and queue immediate refresh when stale.
- Q: How are tenant-specific behaviors represented in a global model? → A: Encode tenant-sensitive behavior via tenant-scoped aggregate features and calibration policies.
- Q: How are low-data tenants handled? → A: Use global priors and shared model behavior until tenant data sufficiency thresholds are met.
- Q: How are high-missing columns handled? → A: Columns with persistently extreme missingness can be excluded from training features unless they provide validated business value.
- Q: What attribution defaults are used? → A: Missing attribution values default to canonical categories such as `Unknown` and `Direct`.
- Q: How are features stored and refreshed? → A: Features are maintained as incrementally updated snapshots with one canonical feature-vector source per lead-time boundary.
- Q: How are out-of-order/late events handled? → A: Late events are ingested idempotently, ordered by event time, and can trigger recomputation when materially impactful.
- Q: How is post-deployment performance tracked? → A: Track discrimination, calibration, and business impact metrics continuously with alerting thresholds.
- Q: Retraining strategy? → A: Use scheduled retraining with drift-triggered early retrain capability.
- Q: Model validation and rollback? → A: Validate candidate models before promotion and support safe rollback to prior approved versions.
- Q: Model version metadata in scores? → A: Every persisted score includes model version and score timestamp metadata.
- Q: Cold-start strategy for new leads/tenants? → A: Use global priors and conservative default categorization until sufficient interaction evidence exists.
- Q: Failure behavior and observability? → A: Scoring and explanation failures must degrade gracefully, be logged, monitored, and surfaced through service health metrics.
- Q: Security/privacy constraints? → A: Exclude direct PII from model features, anonymize logs, and sanitize explanation outputs to avoid sensitive data exposure.
- Q: KPI ownership and cadence? → A: Product, sales, and data teams jointly own KPI review on a regular operating cadence.
- Q: How is scoring-write idempotency enforced? → A: Score persistence uses an idempotency key on tenant, lead, cutoff, and model version.
- Q: What is cold-start behavior for leads with no events? → A: Apply a conservative default category until minimum interaction evidence is available.
- Q: Is compute usage tracked and throttled by cost? → A: Yes, per-tenant compute usage is tracked and cost-aware throttling can be applied to non-critical paths.
- Q: What is data retention policy? → A: Events, feature snapshots, and scores follow explicit retention windows with archive and compliance exceptions.
- Q: How are SLA violations enforced operationally? → A: SLA breaches trigger alerting, autoscaling/reprioritization actions, and degraded-mode safeguards for non-critical paths.
- Q: Is chaos testing required for reliability validation? → A: Yes, periodic chaos scenarios validate fallback behavior for cache, queue, and scoring-path failures.
- Q: What happens to historical leads when model version changes? → A: Model upgrades include governed historical re-scoring backfill with version-tagged outputs.
- Q: How is feature schema/version managed by operators? → A: Feature registry entries are managed through a controlled workflow with human review and versioned metadata updates.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prioritize High-Intent Leads (Priority: P1)

As a sales representative, I can see each open lead classified as Hot, Warm, or Cold so I can focus first on leads most likely to convert.

**Why this priority**: This directly improves daily rep efficiency and conversion outcomes by reducing time spent on low-intent leads.

**Independent Test**: Can be fully tested by loading a list of open leads and confirming each lead displays exactly one score category, allowing reps to reorder outreach by category without any other feature enabled.

**Acceptance Scenarios**:

1. **Given** a tenant with open leads and scoring enabled, **When** a rep opens the lead list, **Then** each open lead shows exactly one category badge: Hot, Warm, or Cold.
2. **Given** a lead with newly recorded interaction history, **When** the lead list is refreshed, **Then** the displayed category reflects the latest lead state.
3. **Given** scoring is disabled for a tenant, **When** a rep opens the lead list, **Then** no scoring badge is shown for that tenant.

---

### User Story 2 - Understand Why a Lead Is Scored (Priority: P2)

As a sales representative, I can request an explanation for a lead score so I can make a better next action decision.

**Why this priority**: Explanation increases trust in scoring and improves rep action quality after prioritization is complete.

**Independent Test**: Can be fully tested by selecting one lead score and requesting an explanation, then confirming the response contains rationale and a recommended next step.

**Acceptance Scenarios**:

1. **Given** a scored lead, **When** a rep requests "Why this score?", **Then** the system returns a clear reason summary based on recent lead behavior.
2. **Given** an explanation response, **When** a rep reviews it, **Then** they also receive at least one suggested next best action.
3. **Given** explanation cannot be generated for a lead, **When** a rep requests it, **Then** the system provides a fallback message and preserves normal lead list behavior.

---

### User Story 3 - Control Scoring Per Tenant (Priority: P3)

As a tenant admin, I can enable or disable lead scoring for my organization so I can control rollout and operational usage.

**Why this priority**: Tenant control is required for safe adoption, phased rollout, and contractual flexibility across customers.

**Independent Test**: Can be fully tested by toggling scoring on and off for one tenant and validating that only that tenant's users are affected.

**Acceptance Scenarios**:

1. **Given** an admin user in Tenant A, **When** they enable scoring, **Then** users in Tenant A can see score categories on eligible leads.
2. **Given** Tenant A scoring is enabled and Tenant B is disabled, **When** users from both tenants access leads, **Then** only Tenant A sees scoring output.
3. **Given** an admin disables scoring, **When** users refresh lead views, **Then** scoring output is hidden without affecting access to lead records.

---

### Edge Cases

- What happens when a lead has insufficient interaction history to infer strong intent?
- How does the system behave when multiple lead updates occur in quick succession before a user refreshes the list?
- What happens if a lead transitions to a closed state after being scored as open?
- How does the system respond when score retrieval is temporarily unavailable?
- What happens when a tenant has newly onboarded leads with no historical activity?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST classify every eligible open lead into exactly one intent category: Hot, Warm, or Cold.
- **FR-002**: The system MUST recompute lead category outcomes when relevant lead history changes.
- **FR-003**: The system MUST enforce tenant-level data and scoring isolation so one tenant cannot view or infer another tenant's lead scoring information.
- **FR-004**: The system MUST allow authorized users to request a score explanation for an individual lead.
- **FR-005**: The system MUST include at least one recommended next action in the explanation response for a scored lead.
- **FR-006**: The system MUST allow tenant administrators to enable or disable scoring for their tenant.
- **FR-007**: The system MUST hide scoring output when tenant-level scoring is disabled.
- **FR-008**: The system MUST support score availability for newly onboarded tenants without requiring manual per-lead setup.
- **FR-009**: The system MUST prevent scoring input from using post-conversion outcome data in a way that would invalidate predictive integrity.
- **FR-010**: The system MUST provide a graceful fallback response when score or explanation retrieval is temporarily unavailable.
- **FR-011**: The system MUST label a lead as converted only when a booking timestamp exists or closed-sale value is positive, and MUST treat cancelled or reverted bookings as non-converted unless a later valid booking occurs.
- **FR-012**: The system MUST enforce event-time cutoff controls so only data available at or before the scoring cutoff contributes to score inputs.
- **FR-013**: The system MUST keep score generation and score retrieval decoupled by using persisted computed scores as source of truth and cache only as a read accelerator.
- **FR-014**: The system MUST support hybrid scoring operations that combine event-driven updates with periodic reconciliation to maintain freshness and consistency.
- **FR-015**: The system MUST compute tenant-sensitive behavioral rate features using tenant-level data with standardized sparse-data fallback behavior.
- **FR-016**: The system MUST apply a standardized missing-data policy across tenants to ensure consistent feature semantics.
- **FR-017**: The system MUST maintain separate training and inference datasets under the same leakage-control and cutoff policy.
- **FR-018**: The system MUST restrict explanation generation to explicit user requests and include only decision-relevant, non-sensitive lead context in explanation prompts.
- **FR-019**: The system MUST treat partial or staged bookings as non-converted until final conversion validity criteria are satisfied.
- **FR-020**: The system MUST attach freshness metadata to returned scores and indicate when a score exceeds staleness targets.
- **FR-021**: The system MUST provide default category-threshold mapping for Cold, Warm, and Hot, with governed support for tenant-level threshold overrides.
- **FR-022**: The system MUST support controlled threshold experimentation and comparative evaluation without exposing conflicting outcomes to end users.
- **FR-023**: The system MUST use a canonical feature-vector snapshot source for each lead and scoring cutoff boundary.
- **FR-024**: The system MUST process late or out-of-order events idempotently and trigger recomputation when those events materially affect score inputs.
- **FR-025**: The system MUST include model-version and `score_ts` metadata in every persisted score record and score API response.
- **FR-026**: The system MUST support scheduled retraining, drift-triggered retraining, pre-promotion validation, and rollback to a previously approved model version.
- **FR-027**: The system MUST apply a defined cold-start policy for new leads and new tenants using conservative defaults until sufficient data is available.
- **FR-028**: The system MUST exclude direct personally identifiable fields from model input features, anonymize operational logs, and sanitize explanation outputs.
- **FR-029**: The system MUST expose score responses containing lead identifier, category, score value, model version, `score_ts`, and freshness indicator.
- **FR-030**: The system MUST enforce monitoring for model drift, prediction drift, and scoring-service failures with actionable alerting thresholds.
- **FR-031**: The system MUST enforce idempotent score persistence using a deterministic key derived from tenant, lead, feature cutoff, and model version.
- **FR-032**: The system MUST apply a documented cold-start scoring policy for leads without sufficient interaction history.
- **FR-033**: The system MUST track per-tenant scoring and explanation compute usage and support policy-based throttling for high-cost requests.
- **FR-034**: The system MUST implement explicit retention and archival rules for events, feature snapshots, and persisted scores, including compliance overrides.
- **FR-035**: The system MUST execute defined operational responses for SLA breaches, including alerting, autoscaling or work reprioritization, and controlled degradation of non-critical workflows.
- **FR-036**: The system MUST execute periodic chaos tests covering Redis outage, queue lag spike, and scoring dependency failure scenarios, and MUST verify fallback behavior outcomes.
- **FR-037**: The system MUST support governed historical re-scoring backfill after approved model upgrades, preserving both prior and new model-version lineage.
- **FR-038**: The system MUST provide a versioned feature registry management workflow, including human-reviewed schema updates and compatibility status tracking for online and offline pipelines.

### Key Entities *(include if feature involves data)*

- **Lead**: A tenant-owned prospect record that includes status, contact progression, intent indicators, and lifecycle state.
- **LeadScore**: The current categorical intent outcome (Hot/Warm/Cold) assigned to a lead, with update timestamp and scoring context.
- **TenantScoringPolicy**: Tenant-level control object representing whether scoring is enabled and applicable visibility rules.
- **ScoreExplanation**: Human-readable rationale and next-action guidance associated with a specific lead score request.
- **LeadInteractionSnapshot**: Time-bounded summary of lead interactions and status changes used to determine lead intent at evaluation time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of eligible open leads displayed to users in enabled tenants show one valid score category.
- **SC-002**: At least 95% of lead history updates result in refreshed score visibility to users within 5 seconds of data refresh.
- **SC-003**: At least 90% of pilot sales users report that score explanations are clear enough to guide their next action decisions.
- **SC-004**: Teams using scoring increase call-to-meeting conversion rate by at least 15% within the first full operating quarter compared with their baseline.
- **SC-005**: 0 confirmed cross-tenant scoring data exposure incidents occur in production during the first 6 months post-launch.
- **SC-006**: 100% of production scoring runs pass automated leakage validation checks for cutoff compliance and outcome-field exclusion.
- **SC-007**: At least 95% of leads affected by new events receive refreshed persisted scores within 60 seconds.
- **SC-008**: At least 99% of score API responses for enabled tenants return within 500 ms on the cache-served path.
- **SC-009**: At least 95% of scoring updates triggered by new eligible events are persisted within 5 seconds under normal operating load.
- **SC-010**: 100% of production score records include model-version and `score_ts` metadata.
- **SC-011**: 100% of model promotions are preceded by validation gates, and 100% of incidents requiring rollback complete rollback to last approved model within the operational runbook target.
- **SC-012**: 100% of periodic privacy audits confirm no direct PII usage in model features and no unsanitized sensitive content in explanation responses.
- **SC-013**: 100% of duplicate scoring attempts with the same idempotency key resolve to a single persisted score record.
- **SC-014**: 100% of configured data retention jobs execute successfully on schedule, with compliance-exempt records preserved according to policy.
- **SC-015**: 100% of sustained SLA breaches trigger the configured incident workflow within 5 minutes, including alert emission and at least one automated mitigation action.
- **SC-016**: 100% of scheduled chaos-test scenarios execute at planned cadence and confirm expected fallback paths without unresolved critical findings.
- **SC-017**: 100% of approved model-upgrade backfill runs complete lineage tagging for old and new model versions, with no tenant data-mixing incidents.
- **SC-018**: 100% of promoted feature-schema changes pass compatibility checks for both online scoring and offline training pipelines before activation.

## Assumptions

- Tenant administrators are responsible for deciding whether scoring is active for their organization.
- Lead intent categories are only applied to open leads; closed or archived leads are out of scoring scope.
- Existing lead history and interaction records are available and sufficiently reliable for intent categorization.
- Explanation access is only available to users who can already view the underlying lead.
- Phase-one rollout prioritizes lead-level scoring and explanation over manager analytics dashboards.
- Explanation requests may reuse recently generated responses for a short period when lead state has not changed.
- Validation and retraining assessments use time-ordered evaluation to reflect real production behavior.
- Score category thresholds start with global defaults and can be adjusted through governed configuration.
- KPI accountability is shared across product, sales, and data stakeholders with recurring reviews.
- Cold-start leads use conservative default scoring until minimum behavioral signals are available.

## Future Enhancements *(out of current scope)*

- Self-serve feature registry UI for non-engineering operational workflows.
- Automated experiment platform for threshold/model experiments with approval pipelines.
- Cost observability dashboards for per-tenant compute usage, budget trends, and optimization alerts.
