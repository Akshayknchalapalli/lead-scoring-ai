# Section 6 — MLOps: Keeping the Model Alive in Production

**Depends on:** [05-ml-model-training.md](05-ml-model-training.md) — this is the lifecycle wrapper around the model artifact that section produces.
**Feeds into:** [08-scoring-service-architecture.md](08-scoring-service-architecture.md) — the Redis cache and model registry described here are the same components that appear in the backend architecture diagram.

## What this section will do

A trained model is not a finished product — it decays as tenant behaviour drifts, and it needs a serving path that's fast and cheap. This section defines the seven always-running pieces of infrastructure that keep the XGBoost model accurate, fast, and inexpensive in production, plus the cost discipline rule that governs the whole platform: ML stays always-on and near-free; the LLM (Section 7) is strictly on-demand.

## The seven MLOps components

| Component | Cadence | Tooling | Role | Monthly cost |
|---|---|---|---|---|
| **Data Pipeline** | Daily | Apache Airflow DAG | Pulls new lead events, does actor classification, excludes test leads | $0 (OSS) |
| **Online Feature Cache** | Real-time | Redis (ElastiCache), TTL 24h | Serves pre-computed feature vectors; invalidates on event; falls back to computing live on a cache miss | $13 |
| **Training Job** | Monthly (policy, not fixed — see below) | AWS c5.2xlarge spot, pulls a 90-day window | Retrains XGBoost with 5-fold cross-validation, runs the candidate through operational shadow validation (see below) — accuracy-based promotion is decided later, once labels exist | $0.68/run |
| **Model Registry** | Always | MLflow on EC2 (t3.nano) | Stores every model_v*.pkl with metrics per version; supports 1-click rollback | $5 |
| **Drift Monitor** | Hourly | Evidently AI (OSS), 30-day look-back | Tracks feature distribution (PSI score per feature); alerts if PSI > 0.2; sends tenant-level alerts — see "what happens when drift is detected" below | $0 (OSS) |
| **Accuracy Tracker** | Weekly | CloudWatch metrics | Checks whether hot leads actually converted; tracks precision/recall per tier and AUC on a rolling window, broken out per tenant — this is the delayed, outcome-based evaluation the promotion gate depends on | $3 |
| **Model Observability** | Real-time | CloudWatch metrics | Inference latency, cache hit ratio, scoring failures/errors, and which registry version is currently loaded — the operational health signals a backend on-call engineer checks, distinct from the Accuracy Tracker's business-quality signals | $0 (same CloudWatch account as Accuracy Tracker) |

**Naming note:** this component is called the **Online Feature Cache**, deliberately not "Feature Store" — it's an online cache for already-computed feature values, not a system that guarantees the offline (training) and online (serving) paths compute each feature identically. At today's scale, that's Redis. If the training-serving-skew concern in [04-feature-engineering.md](04-feature-engineering.md) ever needs solving for real, the natural next step is a full feature store (Feast/Tecton/SageMaker Feature Store) — that's a swap of *what's behind this component*, not a rename of the architecture around it.

**[Projection] Illustrative deployment cost: ~$22/month (~₹1,826/month) at a ~1,00,000-lead scale, for this specific stack (Airflow + Redis + MLflow + Evidently + CloudWatch on modest AWS instances).** This is a cost model built on published pricing for one reasonable infrastructure choice, not a bill anyone has actually paid, and not a claim that production always costs $22/month regardless of stack — swap in EKS, GPU inference, or Aurora instead of the components above and the number moves accordingly. The architectural point this number supports is the *relative* one below (ML-always-on stays cheap; see the cost-discipline boundary), not the absolute figure. See [00-overview.md](00-overview.md#evidence-taxonomy) for the evidence taxonomy this file follows.

## How a retrain actually gets promoted

**[Hypothesis]** — this whole mechanism is designed, not yet running; no retrain has actually happened in production.

**A shadow test cannot compute AUC.** An earlier version of this section said the shadow test compares AUC at 20% traffic — that's not something shadow traffic can actually measure. AUC needs a prediction *and* a ground-truth outcome, and for this system the ground truth ("did this lead book?") doesn't exist yet at scoring time — it only shows up weeks or months later, if at all. What shadow traffic *can* validate immediately is purely operational: does the candidate run without errors, at acceptable latency, producing a score distribution that isn't wildly different from the incumbent's. Whether it's actually *more accurate* is a question that can only be answered once real outcomes have had time to arrive. This is a two-phase gate, not one:

```
Candidate Model (from 05-ml-model-training.md's training pipeline)
        │
        ▼
Shadow Traffic — operational validation (immediate, no labels needed)
  Latency            — inference time comparable to the incumbent
  Errors             — no crashes, no malformed outputs
  Prediction stability — score distribution isn't wildly different from the incumbent's
  Feature drift        — same PSI mechanism as the Drift Monitor below
  Calibration stability — probabilities aren't systematically shifted vs. the incumbent
        │
        ▼
Limited rollout — candidate takes a small slice of real traffic (e.g. 20%) if operational
  checks pass; both models' predictions are logged, but neither's accuracy is known yet
        │
        ▼
        ⋯ weeks or months later — real outcomes (booked / lost) arrive for leads scored during
          the rollout, per the label rule in 03-data-architecture-and-schema.md's 15G ⋯
        │
        ▼
Accuracy Tracker (below) computes AUC, Precision, Recall, Calibration
  on the candidate's shadow predictions now that ground truth exists — compared
  against the incumbent's performance over that same period
        │
        ▼
Keep the candidate / Roll back to the incumbent / Trigger a retrain
  — the accuracy-based decision from 05-ml-model-training.md's promotion criteria is
    made here, not at shadow-traffic time
```

This changes what "promoted" means: a candidate that passes the operational shadow test starts serving a slice of live traffic *provisionally* — the accuracy-based promote/rollback decision from [05-ml-model-training.md](05-ml-model-training.md)'s promotion gate is only finalized once labels exist. If a provisionally-promoted candidate later underperforms once real outcomes come in, that's a rollback, not a rare edge case — it's the expected mechanism for a system where predictive quality can only be measured with a delay. This is what satisfies NFR8 ("monthly auto-retraining with zero-downtime deployment") from [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) — there's no window where scoring stops, and a candidate that fails *either* phase never fully replaces the incumbent.

**Retraining cadence is a deployment policy, not a hard technical limit.** "Monthly" above is a reasonable default, not an architectural constraint — a tenant with fast-moving inventory might warrant weekly retraining, while a low-volume tenant might only need quarterly. Nothing about this pipeline requires a single global cadence.

## What happens when drift is detected

The Drift Monitor's role above stops at "alerts if PSI > 0.2" — that describes detection, not response. An alert with no defined next step is just noise. The response chain:

```
PSI Alert (per-feature or per-tenant)
        │
        ▼
Investigation — is this real behavioural change (a tenant's lead mix genuinely shifted) or a
  data-quality problem (a schema change, an upstream bug, a new test-lead pattern slipping through
  3A's pipeline in 03-data-architecture-and-schema.md)?
        │
        ├── Data-quality cause found  →  fix the pipeline; no model change needed
        │
        ├── Genuine behavioural shift, model still performing  →  no action; keep monitoring
        │
        └── Genuine behavioural shift, Accuracy Tracker also shows degradation
                        │
                        ▼
                Trigger an out-of-cycle retrain (doesn't wait for the next scheduled
                monthly/weekly run) — the new candidate goes through the same shadow
                validation → limited rollout → delayed accuracy evaluation gate above
```

A PSI alert alone never auto-triggers a retrain — it triggers investigation. Only a *confirmed* behavioural shift that's also degrading measured accuracy (from the Accuracy Tracker, once labels exist) justifies an out-of-cycle retrain; otherwise this would retrain on every seasonal wobble in tenant behaviour.

## What the Model Registry is actually for

MLflow is listed above as a $5/month line item, which undersells it — a model registry is what turns "we have a pickle file on a server" into a production practice. Specifically, it's the one component responsible for:

- **Versioning** — every retrain produces a new `model_v*.pkl`, never overwriting the previous one.
- **Rollback** — if a newly-promoted model regresses in production (caught by the Accuracy Tracker below), reverting to the prior version is a registry lookup, not a redeploy from a backup.
- **Lineage** — which training run, which feature-engineering code version, and which data window produced this exact model artifact.
- **Metadata** — the metrics (AUC, precision/recall per tier, Brier score) attached to each version, which is what the promotion gate in [05-ml-model-training.md](05-ml-model-training.md) actually compares against.
- **Reproducibility** — anyone can pull `model_v7`'s exact training config and re-run it, rather than the model's behaviour depending on tribal knowledge of "how it was trained that one time."

None of this needs to be a heavyweight platform on day one — a lightweight MLflow instance on a t3.nano gives you all five properties for $5/month. The point of naming them explicitly here is that "model registry" isn't just a rollback button; it's the thing that makes the whole retrain → shadow-validate → provisionally-promote → accuracy-confirm loop above auditable instead of ad hoc.

**How a rollback actually reaches the Scoring Service.** "Reverting to the prior version is a registry lookup" above is easy to read as a manual step. It isn't:

```
Model Registry — the "active" version pointer changes (rollback or a newly-confirmed promotion)
        │
        ▼
Scoring Service (08-scoring-service-architecture.md) polls or subscribes to that pointer
        │
        ▼
On change, the service reloads the model artifact (model + feature schema + encoders +
calibration + thresholds — the full bundle from 05-ml-model-training.md) into memory
        │
        ▼
New requests use the new version. No redeploy, no restart, no code change.
```

This is what makes "1-click rollback" true in practice rather than aspirational — the rollback is a registry write, and the Scoring Service picking it up is an existing polling/subscription mechanism, not a human SSHing into a box.

## Serving happens on two cadences, not one

The components above (the Online Feature Cache, Model Registry) are shared infrastructure for **both** of the serving paths detailed in [08-scoring-service-architecture.md](08-scoring-service-architecture.md): a nightly **offline batch** pass that (re-)scores the entire lead base, and a **real-time online** path that scores a lead the moment it's created or its history changes. The Accuracy Tracker's weekly precision/recall check and the Drift Monitor's hourly PSI check apply to whichever model version is currently live across both paths — there's only ever one "current model," just two different ways of calling it. Concretely: the offline path scores everybody, the online path scores one lead at a time, but **both read the exact same model artifact, the same per-tenant thresholds, and the same calibration** — there is no separate "batch model" and "real-time model" to keep in sync.

## The cost-discipline boundary

**[Projection]** — all dollar figures in this section are cost-model estimates from published pricing, not measured spend. This section states the platform's central economic rule directly: **keep ML scoring always-on and cheap; keep LLM usage strictly on-demand for explanations.** This is why the MLOps cost above (~₹1,826/month) is nearly two orders of magnitude smaller than what LLM-based scoring would cost — see [07-llm-rag-layer.md](07-llm-rag-layer.md) for the side-by-side cost comparison that this rule is protecting against, and [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md) for how this cost discipline turns directly into the platform's 99.96% gross margin.
