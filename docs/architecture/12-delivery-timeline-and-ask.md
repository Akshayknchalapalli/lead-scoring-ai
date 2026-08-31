# Section 13 — 8-Week Delivery Timeline & The Ask

**Depends on:** every prior section — this is the schedule for building them, in order.
**Feeds into:** nothing further on the board — this is the closing slide, the concrete commitment the rest of the blueprint has been building a case for.

## What this section will do

This is the project plan and the pitch, compressed into one week-by-week schedule and a single closing ask. It exists to answer the last remaining question after 12 sections of design: *how long, with whom, and for what return.*

**Evidence note:** the whole plan and ask below are **[Hypothesis]**/**[Projection]** — a proposal, not a tracked-to-date estimate.

## 8-week plan

**The schedule is dependency-driven, not date-driven.** Each phase below starts only once the contracts the downstream phases rely on are stable — the weeks are a readable projection of that dependency graph, not the thing actually gating the order. If Weeks 1–2 run long, everything after them shifts with them; the plan doesn't assume a fixed calendar so much as a fixed sequence.

| Week(s) | Focus | Deliverables |
|---|---|---|
| **1–2** | Data & Model | Clean the ~50,000 leads currently available across 3–4 tenants, exclude test leads, apply actor classification, run feature engineering ([04-feature-engineering.md](04-feature-engineering.md)), train XGBoost, validate against the promotion gate ([05-ml-model-training.md](05-ml-model-training.md)) |
| **3** | API Backend | FastAPI scoring service, batch score endpoint, Redis cache layer, tenant feature flags, Settings-page toggle ([08-scoring-service-architecture.md](08-scoring-service-architecture.md)) |
| **4** | MLOps Setup | Airflow pipeline, MLflow registry, GitHub Actions CI/CD, staging environment, drift monitoring ([06-mlops.md](06-mlops.md), [10-tech-stack-and-deployment.md](10-tech-stack-and-deployment.md)) |
| **5–6** | Browser Extension | `content.js` (row-id detection), badge injection logic, auth token handling, Chrome + Edge + Firefox builds, store submissions ([09-browser-extension.md](09-browser-extension.md)) — this phase depends on Week 3's API contract being stable, which is why it isn't scheduled earlier |
| **7** | Parallel work: Safari submission + RAG implementation | Two independent workstreams, not one bundled deliverable: (a) Xcode Safari conversion + App Store submission, and (b) the RAG pipeline (LangChain), explanation endpoint, Enterprise-tier UI ([07-llm-rag-layer.md](07-llm-rag-layer.md)). Running them in parallel is what keeps Apple's review latency off the pilot's critical path. |
| **8** | Pilot Launch | Onboard 1 Growth-tier tenant. **Immediately**: monitor operational health (latency, errors, cache hit rate — Model Observability, [06-mlops.md](06-mlops.md)) and collect rep feedback. **Starting now, resolving later**: begin collecting the business-outcome data (conversions, rep behaviour) that will feed the Accuracy Tracker once labels exist, per Section 6's operational-vs-delayed-validation split — accuracy confirmation is not a Week 8 deliverable, it's a Week 8 *start*. |

Note how the schedule mirrors the board's own section order almost exactly — data/model first because everything downstream depends on it, extension work deliberately held until weeks 5–6 after the backend contract is stable, and the highest-latency external dependency (Apple's Safari review) is started in week 7 rather than week 8 so it doesn't block the pilot.

### Pilot success criteria (what "done" means at the end of Week 8)

- Pilot deployed to the chosen Growth-tier tenant.
- One tenant fully onboarded — scoring enabled, badges live, tenant admin has used the enable/disable toggle at least once.
- Production scoring running against real, current leads for that tenant — not a demo dataset.
- A KPI dashboard is live and collecting baseline data for the metrics defined in [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md)'s Operational and Business KPI tables — the dashboard existing and collecting a baseline is the Week 8 deliverable; the KPI *targets* in that table are evaluated later, once enough data has accumulated.

## The ask

**[Projection]** — every dollar figure below is a cost/revenue model, not a measured outcome; see [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md) for which of these are framed against planning-time baselines that real measured data should eventually replace.

> **Approve 8 weeks of 1 engineer's time.** Use data we already own (~50,000 leads, 3–4 tenants). Zero changes to core CRM.
>
> **Illustrative Year 1 projection:** ₹14L MRR at 99.96% margin (see [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md)).
> **Infrastructure:** ₹1,826/month (see [06-mlops.md](06-mlops.md)).
> **ML cost:** ₹830/year for all scoring.
> **LLM alternative (rejected):** ₹3.93 Crore/year, if an LLM were used to score every lead instead of the ML/LLM split in [07-llm-rag-layer.md](07-llm-rag-layer.md).
>
> **We avoid an estimated ₹3.93 Crore/year serving cost by using ML for prediction and reserving the LLM for explanations — while building a moat no competitor can copy.**

The "we avoid a cost" framing above is more precise than "we save" — nothing is being cut from an existing bill; a more expensive alternative architecture (LLM-for-everything) is being avoided in favor of this one. This closing line ties directly back to the two numbers established earlier: the LLM-for-everything cost is the same ₹3.88–3.93 Crore/year figure computed independently in both [05-ml-model-training.md](05-ml-model-training.md) (algorithm comparison) and [07-llm-rag-layer.md](07-llm-rag-layer.md) (RAG cost math), and the "moat" is the same tenant-specific training-data argument made in [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md).

**On risk:** the pilot is deliberately scoped to limit both engineering and commercial exposure — one Growth-tier tenant, zero core-CRM changes, and a feature-flag toggle that can disable scoring for that tenant within 60 seconds ([09-browser-extension.md](09-browser-extension.md)) if anything goes wrong. The architecture is validated against real production conditions before any broader rollout decision is made.

**On scale:** the infrastructure, ML, and LLM-alternative costs above are modeled at a larger production scale than the ~50,000-lead sample in hand today. Since Leadrat has 1,500+ total clients against the 3–4 in this sample, treat these figures as a conservative floor — real production volume, and the case for building this now, only gets stronger as more tenants onboard. The same applies in the other direction: **model quality and cost assumptions should both be revisited as production adoption grows** — the promotion-gate targets in [05-ml-model-training.md](05-ml-model-training.md) and the cost model in [06-mlops.md](06-mlops.md) were built for today's data volume and tenant count, not a permanent ceiling.

## Beyond the pilot

The objective of this proposal is not simply to deploy an AI feature, but to establish a reusable intelligence platform that compounds in value as more tenants, more historical outcomes, and more validated models accumulate. The pilot in Week 8 is a deliberately small first step through an architecture — the six stable contracts in [10-tech-stack-and-deployment.md](10-tech-stack-and-deployment.md), the evidence discipline in [00-overview.md](00-overview.md#evidence-taxonomy), the operational-vs-delayed-validation separation in [06-mlops.md](06-mlops.md) — built to outlast any single tenant, any single model version, and any single tool choice in [10](10-tech-stack-and-deployment.md)'s tables. What's being approved is 8 weeks of engineering time; what's being built is the foundation the next 1,500 tenants get scored against.
