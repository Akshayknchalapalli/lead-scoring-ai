# Section 2 — Requirements & Use Cases

**Depends on:** [01-problem-statement.md](01-problem-statement.md) — every requirement below is a direct, numbered answer to one of the six pain points listed there.
**Feeds into:** every other section. FRs/NFRs act as acceptance criteria checked against later sections (e.g. NFR1's 2ms budget is verified in [05-ml-model-training.md](05-ml-model-training.md); NFR6's privacy rule constrains [07-llm-rag-layer.md](07-llm-rag-layer.md)).

## What this section will do

This is the translation layer between "here's the business problem" (Section 1) and "here's what we're going to build" (everything after). It converts the six pain points into three concrete, testable artifacts: a functional requirements list (what the system must do), a non-functional requirements list (how well it must do it), and six concrete user journeys (who uses it and how). Nothing downstream should exist without a line item here justifying it.

## Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | Score every open lead as Hot / Warm / Cold automatically |
| FR2 | Update lead scores automatically within minutes of meaningful lead-history changes |
| FR3 | Work across all tenants with isolated data and thresholds |
| FR4 | Explain WHY a lead is scored hot/warm/cold on demand |
| FR5 | Suggest next best action for each salesperson per lead |
| FR6 | Integrate as a browser extension — no CRM code changes |
| FR7 | Tenant admin can enable/disable the feature with one click |
| FR8 | Handle 1L+ leads with sub-second badge rendering *(a production-scale target — the current dataset is ~50,000 leads across 3–4 tenants; Leadrat's 1,500+ total clients means real volume will exceed 1L as more tenants onboard)* |

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR1 | Scoring latency < 2ms per lead (ML inference) |
| NFR2 | Badge render < 500ms after page load (cached scores) |
| NFR3 | Model accuracy: AUC > 0.80 on held-out test set |
| NFR4 | System uptime: 99.9% SLA for scoring API |
| NFR5 | Data isolation: zero cross-tenant data leakage |
| NFR6 | PDPA/GDPR compliant — no PII sent to LLM APIs |
| NFR7 | Horizontal scale: handles 10x lead volume without re-architecture |
| NFR8 | Monthly auto-retraining with zero-downtime deployment |

**A note on evidence tagging for this file:** FRs and NFRs are targets/decisions, not measured claims, so they aren't tagged with the [Observed]/[Industry]/[Experiment]/[Projection]/[Hypothesis] taxonomy from [00-overview.md](00-overview.md#evidence-taxonomy) the way factual statements are elsewhere in this folder. Current standing against NFR3 specifically (and every other model-quality requirement) is tracked against promotion criteria in [05-ml-model-training.md](05-ml-model-training.md), with the actual experiment results maintained separately in run-specific evaluation records — that's not a reason to lower the requirement, just where the up-to-date number lives.

## Key Use Cases

| ID | Actor | Journey |
|---|---|---|
| UC1 | Sales Rep | Opens CRM → sees Hot badge → calls hot leads first → conversion rate up |
| UC2 | Manager | Views team dashboard → identifies which reps have the most hot leads |
| UC3 | Tenant Admin | Enables scoring in Settings → all users see badges instantly |
| UC4 | Re-enquiry | Lead re-enquires via portal → score updates within minutes |
| UC5 | New Tenant | Onboards → global model scores leads from Day 1 automatically |
| UC6 | Explanation | Rep clicks badge → RAG explains why + next best action shown |

## How the requirements map forward

- **FR1, FR8, NFR1, NFR3** are the acceptance criteria for the model itself — see [05-ml-model-training.md](05-ml-model-training.md) (algorithm choice, calibration) and [04-feature-engineering.md](04-feature-engineering.md) (the inputs the model needs).
- **FR2, NFR2, NFR8** drive the caching, retraining, and drift-monitoring design in [06-mlops.md](06-mlops.md).
- **FR3, FR7, NFR5** drive the tenant feature-flag design in [08-scoring-service-architecture.md](08-scoring-service-architecture.md) and the enable/disable flow in [09-browser-extension.md](09-browser-extension.md).
- **FR4, FR5, UC6, NFR6** drive the LLM+RAG explanation boundary in [07-llm-rag-layer.md](07-llm-rag-layer.md) — note NFR6 is why that layer is explicitly scoped to explanations only, never bulk scoring.
- **FR6, NFR7** drive the decision to ship as a browser extension rather than modify the CRM — see [09-browser-extension.md](09-browser-extension.md).
- **UC1–UC5** are used as the walkthrough script for the end-to-end flow described in [09-browser-extension.md](09-browser-extension.md)'s tenant enable/disable and scoring flow.
