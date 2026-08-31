# Section 12 — Outcomes, Success Metrics & Business Value

**Depends on:** [01-problem-statement.md](01-problem-statement.md) (this is the promised payoff for every pain point listed there) and [06-mlops.md](06-mlops.md)/[07-llm-rag-layer.md](07-llm-rag-layer.md) (the margin figure here is a direct consequence of the cost discipline enforced in those two sections).
**Feeds into:** [12-delivery-timeline-and-ask.md](12-delivery-timeline-and-ask.md) — "the ask" is justified by the numbers in this file.

## What this section will do

This section is the scorecard: it converts every earlier architectural decision into the metrics a salesperson, a tenant, and the business itself would actually measure after launch. It exists to close the loop back to Section 1 — proving, in numbers, that the six pain points identified there get fixed, and that the fix is financially attractive enough to build.

**Evidence note:** every row below is **[Projection]** or **[Hypothesis]** — nothing in this section has been measured post-launch, because there is no launch yet. The conversion-rate lift and model-quality rows specifically are targets framed against planning-time baselines; actual current standing against them belongs in separate evaluation records, addressed briefly below without repeating the numbers here.

## Outcomes, in three tiers

An earlier version of this section put dashboard-ready metrics and strategic arguments in one undifferentiated table — "AUC > 0.82" and "cited as the #1 reason not to leave" read as the same kind of claim even though only one of them will ever show up on a dashboard. Split by what kind of claim each one actually is, ordered roughly sales → tenant → business → model → product → strategy:

### Operational KPIs — dashboard metrics, tracked by existing instrumentation

| Metric | Target | Tracked by |
|---|---|---|
| Call-to-meeting rate (Sales) | 25–35% improvement | CRM activity data |
| Time spent on hot leads (Sales) | 40% → 75% | CRM activity data |
| Average deal cycle (Sales) | Shortened by 18 days | CRM activity data |
| Weekly active scoring users (Adoption) | — target TBD | Model Observability ([06-mlops.md](06-mlops.md)) |
| Badge click-through / explanation request rate (Adoption) | — target TBD | Model Observability, Explanation Service logs ([07-llm-rag-layer.md](07-llm-rag-layer.md)) |
| Model AUC | Launch: > 0.82 · 6 months: > 0.87 | Accuracy Tracker ([06-mlops.md](06-mlops.md)) |
| Model Precision (Hot) | > 65% | Accuracy Tracker |
| Model Recall (Hot) | > 70% | Accuracy Tracker |
| Model F1 score | > 0.67 | Accuracy Tracker |

**A launch objective and a promotion gate are not the same thing.** "AUC > 0.82 at launch" above is a product-level launch objective; the actual promotion gate a model has to clear before it ships is [05-ml-model-training.md](05-ml-model-training.md)'s full multi-criteria gate (AUC, precision, recall, calibration, drift, schema compatibility) plus [06-mlops.md](06-mlops.md)'s delayed accuracy confirmation once real outcomes exist. A model can clear the promotion gate at a slightly different AUC than this table's launch number and still be the right one to ship — the gate, not this table, is the actual go/no-go mechanism.

### Business KPIs — dashboard metrics, framed as projections until measured

| Metric | Target | Basis |
|---|---|---|
| Conversion rate lift (Tenant) | Industry baseline 3–8% → 5–12% | **[Projection]** — baseline is a planning figure, see below |
| Revenue per rep (Tenant) | +20–30% annually | **[Projection]** |
| Lead wastage reduction (Tenant) | −50% | **[Projection]** |
| Tenant churn (Retention) | −40% for tenants using scoring | **[Hypothesis]** |
| NPS (Retention) | +15 points from baseline | **[Hypothesis]** |
| MRR — illustrative business projections | Year 1: ₹14L · Year 2: ₹45L+ · Year 3: ₹1.2Cr | **[Projection]** |
| Gross margin | 99.96% | **[Projection]**, arithmetic — see below |

### Strategic hypotheses — not dashboard metrics, arguments for why this is worth building

- **Product positioning:** scoring becomes cited as the #1 reason a tenant doesn't leave. This is a qualitative retention argument, not something that gets a number on a dashboard the way churn % does.
- **Competitive moat:** the model is trained on *this company's own* tenant conversion data — competitors can't replicate it without years of the same history. More tenants → better model → a compounding data flywheel. **The advantage comes from proprietary historical outcomes, not proprietary algorithms** — the algorithm (XGBoost) is off-the-shelf and replaceable, exactly as [05-ml-model-training.md](05-ml-model-training.md)'s algorithm comparison and [10-tech-stack-and-deployment.md](10-tech-stack-and-deployment.md)'s contracts-over-tools framing already establish; what a competitor can't buy or copy is years of this specific company's outcome data.

## Where each number comes from

- The **40→75% time-on-hot-leads** and **call-to-meeting rate** figures are the direct payoff of fixing "60% Wasted Sales Time" and "Hot Leads Go Cold" from [01-problem-statement.md](01-problem-statement.md), via the always-on scoring badge from [08-scoring-service-architecture.md](08-scoring-service-architecture.md) / [09-browser-extension.md](09-browser-extension.md). Both source pain points are themselves labelled Hypothesis there — this row inherits that uncertainty.
- **The adoption metrics are new** — earlier versions of this file jumped straight from "deployment" to "revenue" with nothing measuring whether anyone actually uses the badge or clicks "why," even though [09-browser-extension.md](09-browser-extension.md)'s badge lifecycle and [07-llm-rag-layer.md](07-llm-rag-layer.md)'s explanation flow both produce events that could drive exactly this metric. No target is set for these yet — they need a baseline pilot before a number means anything.
- **The tenant-business row is framed against a planning-time baseline, not a measured one.** "3–8% → 5–12%" assumes a starting conversion rate that is an [Industry] figure (see [01-problem-statement.md](01-problem-statement.md)), not something measured on Leadrat's own leads. The actual current conversion rate is a dataset statistic tracked in separate evaluation records — once that number is in hand, this row's lift target should be reframed against it rather than against "3–8%."
- **The model quality targets have a tracked, open gap against the promotion criteria in [05-ml-model-training.md](05-ml-model-training.md).** Current standing (AUC, precision, recall) against those criteria is maintained in separate evaluation records, not restated here — these targets are not wrong to hold, but closing the gap to them is active work, not a footnote.
- The **99.96% gross margin** is arithmetic on top of the cost model, not aspiration: ₹14L/month **[Projection]** revenue against ~₹1,826/month **[Projection]** MLOps infrastructure ([06-mlops.md](06-mlops.md)) plus modest on-demand LLM spend ([07-llm-rag-layer.md](07-llm-rag-layer.md)). The arithmetic is sound *given* those inputs; neither input is measured yet. This margin only holds *because* the ML-always-on / LLM-on-demand cost boundary from those two sections is enforced — the "wrong usage" LLM-for-everything cost of ₹3.88 Crore/year would erase it entirely.
- The **competitive moat** claim is the strategic argument for building this at all rather than buying/reselling a generic scoring tool: the training data (this company's own tenant history, as reverse-engineered in [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md)) is not something a competitor can acquire. This argument holds regardless of current model quality — it's about data ownership, not accuracy.

## Closing this section — and the blueprint's traceability chain

The purpose of the architecture in [03](03-data-architecture-and-schema.md) through [10](10-tech-stack-and-deployment.md) is not technical elegance for its own sake — it's to deliver the outcomes above while keeping operations simple and unit economics sustainable. Every major decision in this blueprint now traces both backward and forward: a **pain point** ([01](01-problem-statement.md)) became a **requirement** ([02](02-requirements-and-use-cases.md)), which shaped an **architecture** ([03](03-data-architecture-and-schema.md)–[09](09-browser-extension.md)), which was given a concrete **implementation** ([10](10-tech-stack-and-deployment.md)), which ships through a **deployment pipeline** (also 10), which is what makes the **outcomes** on this page achievable rather than aspirational. That chain — Pain Point → Requirement → Architecture → Implementation → Deployment → Outcome — is the thing worth checking before adding anything new to this blueprint: does it trace back to a real pain point, and forward to a measurable outcome, or is it a component looking for a justification.
