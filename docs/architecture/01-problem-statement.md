# Section 1 — Problem Statement

**Depends on:** nothing (the root motivation).
**Feeds into:** [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) (every FR/NFR traces back to a pain point here) and [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md) (the ROI case is the mirror image of this section's costs).

## What this section will do

This is the business-case slide of the blueprint. Before any data, model, or architecture is discussed, the board first establishes *why* a lead-scoring feature is worth building at all — in numbers a non-technical stakeholder can act on. Its job is to give every later technical decision (which model, which latency target, which tier gets the LLM) a reason to exist: each one is a direct answer to a pain point listed here.

## Evidence behind this section

Tagged using the taxonomy defined in [00-overview.md](00-overview.md#evidence-taxonomy) (Observed / Industry / Experiment / Projection / Hypothesis).

**[Observed]** — measured from the current export, or a fact about the business as it stands today
- ~50,000 leads across 3–4 real-estate tenants — the current export from the database.
- No existing mechanism scores or prioritizes leads today — salespeople work the pipeline in creation-date or gut-feel order.
- Leadrat as a company has **1,500+ total clients** — this 3–4-tenant sample is a small slice of that base.

**[Industry]** — external benchmarks, cited but not measured against Leadrat's own leads
- "Baseline conversion: 3–8%" — a typical real-estate lead-to-sale range, used at planning time to frame the problem. The exact measured conversion rate on the current export is a dataset statistic, not an architecture concern — it's tracked separately, along with the class-imbalance implications it has for training in [05-ml-model-training.md](05-ml-model-training.md).
- 78% of customers buy from the first business that responds to their enquiry.

**[Hypothesis]** — what this project is proposing to validate, not yet measured
- AI-driven prioritization will measurably improve sales efficiency and conversion.
- Surfacing intent signals that already exist in the CRM (but aren't currently read) will let reps act faster on the leads most likely to convert.
- Several of the pain-point framings below are internal estimates meant to dramatize the problem, not measured statistics — each is labelled with its basis in the table below so that distinction stays visible.

## The six pain points it documents

Each is a distinct failure mode in how leads are currently handled, and each maps to a later fix. The **Basis** column is the honest answer to "how do we know this is true" — most of these are reasonable, well-understood failure modes in unscored CRM pipelines, but they haven't been measured against Leadrat's own data yet, so they're marked as estimates/hypotheses rather than facts:

| Pain point | Basis | What's actually happening | What later section fixes it |
|---|---|---|---|
| **~60% Wasted Sales Time** | **[Hypothesis]** — internal estimate, not measured against this dataset; treat as directional, not exact | Salespeople call leads that never convert; no way to prioritize; pure guesswork daily. | Scoring model (Section 5) ranks leads so reps call hot ones first. |
| **Zero Visibility into Intent** | **[Observed]** | The CRM already holds call logs, visit history, budget, and source — but nobody reads all of it. | Feature engineering (Section 4) turns that buried history into a usable signal. |
| **Hot Leads Go Cold** | **[Hypothesis]** — plausible pattern, not yet measured | A lead answers once, shows interest, then gets ignored because the rep is busy with others. | Real-time re-scoring (NFR2, Section 6 retraining/serving) keeps badges current. |
| **No Data-Driven Follow-up** | **[Observed]** | Reps rely on gut feel — no system tells them who to call, when, or why. | The LLM+RAG explanation layer (Section 7) supplies a "why" and a next best action. |
| **Revenue Lost Every Day** | **[Industry]** — 78% first-responder stat, not Leadrat-specific | Every delay in responding is, per that benchmark, a direct revenue loss. | Sub-second badge rendering (NFR2/FR8) and always-on scoring close that response gap. |
| **Management Blind Spots** | **[Observed]** | Managers can't see which leads are hot across the full pipeline; forecasting is broken. | Dashboards/use cases in Section 2 (UC2 — manager view) and the per-tenant metrics in Section 12. |

## Target product outcome

The stated goal, in one line: **real-time Hot / Warm / Cold lead scoring on the CRM UI, with on-demand actionable guidance, delivered as a multi-tenant, low-cost, high-margin add-on capability.**

That single sentence is effectively the spec for the rest of the board:
- "Real-time … on the CRM UI" → drives the browser-extension architecture (Section 9) instead of a CRM rewrite.
- "Hot / Warm / Cold" → drives the 3-bucket calibration/thresholding step in model training (Section 5).
- "On-demand actionable guidance" → drives the strict ML-always-on / LLM-only-on-click cost boundary (Section 7).
- "Multi-tenant" → drives tenant isolation requirements (NFR5) and per-tenant threshold calibration (Section 5, Step 8).
- "Low-cost, high-margin" → drives the MLOps cost accounting (Section 6) and the final business case (Section 12), which reports 99.96% gross margin.

**Why a browser extension specifically:** delivering the capability this way avoids touching each tenant's underlying CRM deployment — there's no per-tenant code change, migration, or coordinated release to schedule. That's what makes incremental, tenant-by-tenant rollout possible (UC3, UC5 in [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md)) instead of a single big-bang launch across all of Leadrat's 1,500+ clients. See [09-browser-extension.md](09-browser-extension.md) for how that's implemented.

## How success will be measured

**[Hypothesis]** — a short preview of what "this worked" will actually look like, before the full numbers show up in [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md). None of these are measured yet; they're the metrics this project commits to moving, measured against whatever the real baseline turns out to be (see current evaluation records, not the 3–8% industry figure used for framing above):

- Increase in lead-to-sale conversion rate.
- Reduction in average first-response time to new leads.
- Increase in calls made specifically to Hot-tagged leads (not just call volume).
- Improvement in salesperson productivity — time spent on leads that convert vs. leads that don't.
- Improvement in manager forecast accuracy, from better pipeline visibility.

Each of these is a direct answer to one of the six pain points above — this list is the bridge between "here's the problem" on this page and "here's what we measured" in [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md)'s stakeholder outcome tables.
