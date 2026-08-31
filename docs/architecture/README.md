# Lead Intelligence Platform — Architecture Blueprint

This is the **architecture document**: what's being built and why, intended to stay stable across experiments. It's a detailed markdown breakdown of `lead-scoring-ai-2026-04-19-1647.excalidraw` (the 15-section whiteboard titled "LEAD INTELLIGENCE PLATFORM — Complete Blueprint"). Each file below explains what its section does, in detail, and how it depends on the sections around it. Start with [00-overview.md](00-overview.md) for the full dependency map and the reasoning behind how the 15 board sections were regrouped into these 13 files.

**This folder is not an experiment log.** Actual experiment results — dataset statistics, AUC/precision/recall, leakage investigations, calibration status — belong in separate, run-specific evaluation records, expected to change with every run. This folder should not need to change just because a new experiment landed; if you're looking for current model performance, look there instead of here.

| # | File | Board section(s) covered |
|---|---|---|
| 00 | [Overview & dependency map](00-overview.md) | — |
| 01 | [Problem Statement](01-problem-statement.md) | Section 1 |
| 02 | [Requirements & Use Cases](02-requirements-and-use-cases.md) | Section 2 |
| 03 | [Data Architecture & Real Schema](03-data-architecture-and-schema.md) | Section 3 + Section 15 |
| 04 | [Feature Engineering](04-feature-engineering.md) | Section 4 + Section 14 |
| 05 | [ML Model: Training Pipeline](05-ml-model-training.md) | Section 5 |
| 06 | [MLOps](06-mlops.md) | Section 6 |
| 07 | [LLM + RAG Layer](07-llm-rag-layer.md) | Section 7 |
| 08 | [Scoring Service Architecture](08-scoring-service-architecture.md) | Section 8 |
| 09 | [Browser Extension](09-browser-extension.md) | Section 9 |
| 10 | [Tech Stack & Deployment](10-tech-stack-and-deployment.md) | Section 10 + Section 11 |
| 11 | [Outcomes & Business Value](11-outcomes-and-business-value.md) | Section 12 |
| 12 | [Delivery Timeline & The Ask](12-delivery-timeline-and-ask.md) | Section 13 |

Sections 14 and 15 from the original board are not separate files — they are exhaustive reference appendices (a 74-feature derivation guide and a full real-database-schema reverse-engineering, respectively) that only make sense attached to the sections they back up, so they were merged into files 04 and 03. See [00-overview.md](00-overview.md) for the full reasoning.

Related existing doc: [`docs/lead_ai_scoring.md`](../lead_ai_scoring.md) is an earlier, shorter text companion to a prior version of this board — it predates Sections 10–15 and the Section 15 schema correction, so treat the files in this folder as the current source of truth.

**Current data scale:** the database export in hand is **~50,000 leads across 3–4 tenants**, a small slice of Leadrat's **1,500+ total clients**. See [00-overview.md](00-overview.md) for which downstream cost/revenue figures are illustrative production targets vs. the real current sample.

**Evidence taxonomy:** every claim in this folder is tagged **[Observed]** / **[Industry]** / **[Experiment]** / **[Projection]** / **[Hypothesis]**, defined in [00-overview.md](00-overview.md#evidence-taxonomy). Where an experiment result exists, this folder points to separate evaluation records rather than restating the number — see [00-overview.md](00-overview.md#evidence-taxonomy) for why that split is deliberate.
