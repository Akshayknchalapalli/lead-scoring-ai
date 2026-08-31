# Lead Intelligence Platform — Blueprint Overview

Source: `lead-scoring-ai-2026-04-19-1647.excalidraw` (title on the board: **"LEAD INTELLIGENCE PLATFORM — Complete Blueprint: Problem → ML Solution → MLOps → LLM+RAG → Browser Extension → Deployment"**).

> From ~50,000 CRM leads across 3–4 tenants → AI-powered Hot / Warm / Cold scoring → Real-time browser extension → 99.96% gross margin SaaS feature.

This is the current data on hand: 50,000 rows, 49,830 unique `LeadId`s, 742 distinct `TenantId`s, top 4–5 tenants by volume used for a legible sample. Two things worth keeping in mind:

- Every "current dataset" statement in this folder (Section 1's problem framing, Section 3's raw data description) reflects **~50,000 leads / 3–4 tenants** — what's actually available today.
- Leadrat as a company has **1,500+ total clients**, so 3–4 tenants and 50,000 leads is a small slice of the addressable base. Anywhere a later section models cost or revenue at a larger scale (MLOps cost, RAG cost math, revenue projections), read that as an illustrative production target, not the current dataset — and treat it as a conservative floor, since the real ceiling across 1,500+ clients is materially larger.

This folder is a one-file-per-topic breakdown of that whiteboard. The board contains **15 numbered sections**, but two of them (14 and 15) are not independent topics — they are exhaustive reference appendices that back up sections 3 and 4. They have been merged into the section they support so each file is self-contained and reads as a complete unit.

## Evidence taxonomy

The claims in this documentation are not all the same kind of statement — some were measured, some are cited from outside research, some come from an actual model run on the real data, some are estimates for planning purposes, and some are the bet this project is proposing to test. Every file in this folder tags its claims with one of the five labels below, so a reader can tell the confidence level of any given number at a glance, audit assumptions easily, and know exactly which figure to replace once better data exists.

| Label | Meaning |
|---|---|
| **Observed** | Directly measured from the current CRM dataset or implementation. |
| **Industry** | Derived from published research or external benchmarks. |
| **Experiment** | Results produced during model training or evaluation. |
| **Projection** | Financial, operational, or scaling estimates based on stated assumptions. |
| **Hypothesis** | A claim the project intends to validate during implementation or rollout. |

**Where experiment results exist, they belong in separate evaluation/experiment-tracking records, not in this folder.** The architecture described here is intentionally independent of any single experimental run: this folder is not the place for AUC history, confusion matrices, or raw metrics dumps — those change every experiment, this folder shouldn't. [05-ml-model-training.md](05-ml-model-training.md) has the one exception worth reading: the model's promotion criteria — the bar any trained model has to clear, independent of which run produced it.

## How the sections were regrouped

| File | Board section(s) | Why grouped |
|---|---|---|
| [01-problem-statement.md](01-problem-statement.md) | Section 1 | Standalone — the business motivation everything else answers to. |
| [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) | Section 2 | Standalone — translates Section 1 into FR/NFR/use cases. |
| [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md) | Section 3 **+ Section 15** | Section 15 ("Real Data Architecture Revelation") is the ground-truth reverse-engineering of the *exact* database table Section 3 only describes at a high level — it belongs with it, not on its own. |
| [04-feature-engineering.md](04-feature-engineering.md) | Section 4 **+ Section 14** | Section 14 ("Feature Derivation Guide") is the row-by-row derivation logic for every feature Section 4 lists. One is the summary, the other is the recipe — they're one document. |
| [05-ml-model-training.md](05-ml-model-training.md) | Section 5 | Depends on Section 4's feature vector; stands on its own as the training pipeline + algorithm choice. |
| [06-mlops.md](06-mlops.md) | Section 6 | Depends on Section 5's model artifact; keeps it alive in production. |
| [07-llm-rag-layer.md](07-llm-rag-layer.md) | Section 7 | An optional add-on layer on top of the ML score from Section 5/6. |
| [08-scoring-service-architecture.md](08-scoring-service-architecture.md) | Section 8 | The backend that wires Sections 5–7 into callable APIs. |
| [09-browser-extension.md](09-browser-extension.md) | Section 9 | The client that consumes Section 8's API. |
| [10-tech-stack-and-deployment.md](10-tech-stack-and-deployment.md) | Section 10 **+ Section 11** | Section 11 (CI/CD) is the pipeline that ships Section 10's tech stack — deploying and the thing being deployed are one story. |
| [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md) | Section 12 | Ties back to Section 1's problem — the ROI case. |
| [12-delivery-timeline-and-ask.md](12-delivery-timeline-and-ask.md) | Section 13 | The project plan and business ask, referencing every prior section by week. |

## End-to-end dependency chain

```
1. Problem Statement
        │
        ▼
2. Requirements & Use Cases
        │
        ▼
3. Data Architecture  ──(reverse-engineered by)──  Section 15 appendix
        │  (raw fields available)
        ▼
   3A. Data Pipeline — ingestion, validation, dedup, missing values, schema evolution
        │  (clean rows)
        ▼
4. Feature Engineering  ──(derived row-by-row by)──  Section 14 appendix
        │  (60-feature vector; future: a shared Feature Store to prevent training/serving skew)
        ▼
5. ML Model Training (XGBoost)
        │
        ▼
   Evaluation & Promotion Gate — AUC/Precision/Recall (offline) → Drift & Compatibility Checks → Shadow Validation (operational) → Provisional Promotion → delayed Business-metrics Confirmation → Approve
        │  (promoted model artifact: model + feature schema + encoders + calibration + thresholds + metadata)
        ▼
   Model Registry (MLflow) — versioning, rollback, lineage, metadata, reproducibility
        │  (registered model artifact)
        ▼
6. MLOps (offline batch + online serving, retraining, drift)  ──┐
        │  (live score + SHAP feature importance)               │
        ▼                                                        │
7. LLM + RAG explanation layer                                   │
   (SHAP → cheap always-on "why" · LLM+RAG → optional enrichment)┤ (both feed the backend)
        │                                                        │
        ▼                                                        ▼
8. Scoring Service Architecture (FastAPI backend)
        │  Offline batch scoring (nightly) + Online scoring (real-time)  →  REST API
        ▼
9. Browser Extension (Chrome/Edge/Firefox/Safari)
        │
        ▼
10. Tech Stack + 11. CI/CD Deployment Pipeline  (cuts across all of the above)
        │
        ▼
12. Outcomes & Business Value  ──(answers back to)──  Section 1's problem
        │
        ▼
13. 8-Week Delivery Timeline & The Ask
```

**A note on what's original vs. added:** the 15 numbered sections and their content are the whiteboard's own. The items above that aren't numbered — 3A Data Pipeline, the Feature Store note, the explicit Evaluation & Promotion Gate, the Model Registry write-up, the offline/online scoring split, and the SHAP/LLM explanation split — are production-hardening additions layered on top, each marked inline in its file as a recommended addition rather than board content:

| Addition | Where it lives | Why it's not on the original board |
|---|---|---|
| **3A. Data Pipeline** (ingestion/validation/dedup/missing-values/schema evolution as its own stage) | [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md) | The board goes straight from raw data to features; in production this cleanup step is usually substantial enough to be its own stage. |
| **Feature Store** (shared feature definitions for training + serving) | [04-feature-engineering.md](04-feature-engineering.md) | Not needed at today's scale, but flagged because the current design computes features twice (training pipeline + live extractor), which can drift. |
| **Evaluation & Promotion Gate** (offline AUC/Precision/Recall → drift/schema checks → operational shadow validation → provisional promotion → delayed accuracy confirmation → Approve, as one explicit chain, plus a defined model-artifact bundle) | [05-ml-model-training.md](05-ml-model-training.md) | The board has the shadow test scattered across two files, and originally implied it could compare AUC on live traffic (it can't — no labels exist yet); this makes it one continuous, auditable, two-phase gate that separates what's checkable immediately from what can only be confirmed once outcomes arrive. |
| **Model Registry write-up** (versioning, rollback, lineage, metadata, reproducibility) | [06-mlops.md](06-mlops.md) | The board lists MLflow as a $5/month line item; the five properties it actually buys are worth naming explicitly. |
| **Offline batch vs. online real-time scoring** | [08-scoring-service-architecture.md](08-scoring-service-architecture.md) | The board implies one cache-first path; real-estate CRMs benefit from a nightly full-base batch pass *and* real-time scoring of new/changed leads. |
| **SHAP-based prediction/explanation split, behind an LLM Adapter abstraction** | [07-llm-rag-layer.md](07-llm-rag-layer.md) | The board treats "explanation" as inherently LLM-only; a cheap SHAP-based "top signals" tier is available with zero LLM cost, the LLM is an optional enrichment behind a swappable adapter interface (not a hardcoded GPT-4o-mini call), and an LLM outage now has a defined fallback instead of an undefined failure. |

## Key numbers referenced throughout

- **Scale [Observed]:** ~50,000 leads across 3–4 real-estate tenants (out of Leadrat's 1,500+ total clients).
- **Conversion rate [Industry]:** "3–8%" — a planning-time range used to frame the problem; the exact measured figure on the current export is a dataset statistic tracked separately, not in this architecture doc.
- **Model [Hypothesis target]:** XGBoost, AUC > 0.80 (NFR3). Current standing against this target is tracked in separate evaluation records, not in this architecture doc — see [05-ml-model-training.md](05-ml-model-training.md)'s promotion criteria.
- **Cost discipline [Projection]:** ML scoring is always-on and near-free (~₹830/year); LLM is on-demand only for explanations (~₹1.49L/month if 10% of leads request one) — using an LLM to score every lead instead would cost ~₹3.93 Crore/year. These are cost-model estimates, not yet measured against a live deployment.
- **Business case [Projection]:** Year 1 ₹14L MRR at 99.96% gross margin, against ~₹1,826/month infrastructure cost.
- **Delivery [Hypothesis]:** 8 weeks, 1 engineer — the project's proposed plan, not a tracked-to-date estimate.

See each linked file for the full detail behind these numbers, and each file's own evidence labels for exactly what's measured vs. assumed. Actual experiment results are tracked separately from this blueprint.
