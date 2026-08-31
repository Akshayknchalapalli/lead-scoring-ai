# Section 7 — LLM + RAG: Intelligence Layer (Enterprise Tier Only)

**Depends on:** [05-ml-model-training.md](05-ml-model-training.md) / [06-mlops.md](06-mlops.md) — this layer only runs *after* the ML model has already produced a Hot/Warm/Cold score; it never scores leads itself.
**Feeds into:** [08-scoring-service-architecture.md](08-scoring-service-architecture.md)'s `POST /api/explanations/{leadId}` endpoint, and [09-browser-extension.md](09-browser-extension.md)'s "click badge for explanation" step (UC6).

## What this section will do

This section defines the optional, Enterprise-tier explanation layer: when a salesperson clicks "Why is this Hot?", an **Explanation Service** builds an answer — either directly from the model's own signals, or, when richer output is warranted, via a Retrieval-Augmented Generation call to an LLM — and returns a structured explanation plus a recommended next action. Its other job — arguably its more important one — is to draw a hard cost boundary: **ML scores every lead for free; the LLM only ever runs when a human explicitly asks for a reason.**

> ML handles scoring (always on, free). LLM handles explanation + next-action (on-demand, only when a salesperson clicks 'Why?').

## Three layers, not two: Prediction, Explanation, and the LLM Adapter

The board's own language ("Scoring Service" does prediction, a separate "explain" endpoint does explanation) already implies a split, but it's worth drawing explicitly and taking one step further than "explanation doesn't need the LLM" — the architecture here is **"the Explanation Service explains the score," not "the LLM explains the score."** The LLM is one implementation strategy the Explanation Service can call on, not the thing doing the explaining:

```
Lead
  │
  ▼
XGBoost (05-ml-model-training.md)
  │
  ├──────────────────┐
  ▼                   ▼
Probability      SHAP Values          ← both produced together, in the same inference call —
  │                   │                 SHAP is not something the LLM computes or requests later
  └─────────┬─────────┘
            ▼
   Explanation Service
     - can answer "top 3 signals for this score" directly from SHAP values,
       templated into plain language — no retrieval, no LLM call, near-zero
       latency and cost
            │
            ├───────────────────┬───────────────────┐
            ▼                   ▼
     SHAP-only path      LLM + RAG path  (via the LLM Adapter below)
     (free, always       (Enterprise-tier, on-demand — the rest of this file)
      available)
```

**The LLM Adapter is the abstraction that makes the model swappable.** The Explanation Service calls an adapter interface, not "GPT-4o-mini" directly — the prompt contract, retrieval logic, and output schema (see below) are all defined against that interface. Swapping GPT-4o-mini for Claude, Gemini, or a local Llama deployment later is an adapter change, not a rewrite of the Explanation Service or the API contract in [08-scoring-service-architecture.md](08-scoring-service-architecture.md). That's the actual point of separating these three layers, not just a tidiness preference.

The distinction also matters for cost tiering: a bare "why is this hot" signal list is cheap enough (SHAP only, no LLM) that it could reasonably be offered even on the Growth tier as a lighter-weight feature, while the natural-language writeup, lead comparison, and script suggestion below are the genuinely LLM-dependent, Enterprise-only value-add. The board keeps the whole explanation feature Enterprise-only; splitting the architecture this way is what would let that decision be revisited later without new modeling work — the SHAP values already exist as a free byproduct of every XGBoost prediction.

## What happens when the LLM is unavailable

A direct consequence of the layering above, worth stating explicitly rather than leaving implicit: if the LLM Adapter call times out, errors, or is rate-limited, the Explanation Service does **not** fail the request.

```
LLM Adapter call fails or times out
        │
        ▼
Explanation Service falls back to the SHAP-only path (already computed, no extra cost or latency)
        │
        ▼
Salesperson sees a signal-based explanation instead of the full natural-language writeup —
never an error message, never a blank panel
```

This is only possible because the SHAP-only path isn't a degraded stand-in for the LLM path — it's a complete, independent explanation source that happens to exist for free. An architecture where "explanation" meant "LLM call" would have no fallback here except an error.

## The explanation pipeline

| Stage | Detail |
|---|---|
| **Trigger** | Salesperson clicks the "Why is this Hot?" badge in the extension → `POST /api/explain {lead_id}` |
| **Structured context** | Pull the lead's own signals: call log summary, status trail, human-only notes, budget vs. project fit, and the SHAP feature-importance values already produced alongside the score (see the layering above) — no LLM involved yet, this is a data-assembly step |
| **Vector search** | pgvector similarity search for 3 similar *converted* leads — **scoped to the current tenant only.** A query never searches across tenants; comparing one builder's leads against another's would leak competitive data and produce comparisons that don't reflect that tenant's own market. Same isolation guarantee as NFR5, applied at the retrieval layer specifically. |
| **Prompt assembly** | A dedicated, deterministic step — not string concatenation. The prompt builder combines the structured context and the 3 retrieved leads into a request using a **versioned prompt template** (see below), enforcing the guardrails below before anything is sent to the LLM Adapter. |
| **LLM Adapter call** | Current implementation: GPT-4o-mini · Input: ~1,200 tokens · Output: ~300 tokens · Cost: $0.006/call · Latency: ~1.2 sec. Called through the adapter interface described above, not directly. |
| **Structured output** | The adapter returns JSON, not prose — see the schema below. The extension UI renders it as prose; the backend consumes it as data. |
| **Display** | Shown in a collapsible sidebar panel inside the extension — designed so the salesperson can act in under 30 seconds |

### Prompt versioning

The prompt template used in the "Prompt assembly" stage is a production artifact, the same way the model and its calibration are (05-ml-model-training.md, 06-mlops.md) — changing one sentence in it changes production behaviour just as surely as retraining the model does. **Prompt templates are version-controlled and deployed alongside application releases**, not edited ad hoc in a config panel. This is what makes "why did the explanation change" a traceable question instead of a mystery.

### Structured output schema

The LLM Adapter's contract is JSON, not free text — this is what lets the Explanation Service treat the LLM path and the SHAP-only path as interchangeable inputs to the same display layer:

```json
{
  "explanation": "This lead is scored Hot (top 12% of leads). Site visit completed...",
  "topSignals": [
    "Site visit completed — one of the strongest pre-booking signals",
    "3 successful contact attempts out of 4",
    "Budget matches an active project listing"
  ],
  "nextAction": "Call within the next hour — engagement is high and recent.",
  "callWindow": "Weekday mornings, 10–11am (based on this lead's answer pattern)",
  "script": "Hi [name], following up on your visit to..."
}
```

The extension renders this as prose; nothing about the contract changes if the rendering later becomes a card layout, a voice summary, or something else — the schema, not the presentation, is what the backend and the LLM Adapter agree on.

## RAG use cases available in the extension

| Use case | What it does |
|---|---|
| **Score Explanation** | Why is this lead hot? — the top 3 signals pulled from actual history data |
| **Call Summary** | Auto-summarises call logs into a 2-line salesperson note |
| **Next Best Action** | What to do next, based on what similar converted leads did |
| **Script Suggestion** | An opening line for the next call, tailored to this lead's behaviour |
| **Best Time to Call** | Analyses answer patterns across history to predict the best call window |
| **Lead Comparison** | Shows the 3 most similar leads that converted, and why they did |

## Cost — correct usage vs. wrong usage

This is the section's central argument, made with numbers that are **[Industry]** at the unit-price level (published OpenAI API pricing) but **[Projection]** at the monthly-total level (built on an illustrative adoption assumption and lead volume, not measured usage):

**Correct usage — RAG on-demand [Industry unit price → Projection total]:**
GPT-4o-mini at $0.00015/1K input + $0.0006/1K output (published pricing) → ~$0.006 per explanation. *Assuming*, as an illustrative adoption assumption rather than a measured click-through rate, that 10% of the ~1L daily leads get a click (10K/day, a projected volume — not the ~50,000-lead current sample): $60/day = **$1,800/month (₹1,49,400/month)**.

**Wrong usage — scoring every lead with an LLM [Industry unit price → Projection total]:**
GPT-4 Turbo at $0.013/lead (published pricing) × 1L leads/day (projected volume) = $1,300/day = $39,000/month = **₹32,37,000/month = ₹3.88 Crore/year**.

**Conclusion, verbatim from the board:** *"Never use LLM for bulk scoring. Use ML. Use LLM only for explanations."* This single decision is what makes the platform's 99.96% gross margin in [11-outcomes-and-business-value.md](11-outcomes-and-business-value.md) possible — swapping the always-on scorer from XGBoost to any LLM would turn a ₹1,826/month infra bill into a multi-crore one, as also shown in the algorithm comparison's GPT-4 row in [05-ml-model-training.md](05-ml-model-training.md).

## Guardrails — the prompt builder is a deterministic component, not string concatenation

NFR6 from [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) — "PDPA/GDPR compliant, no PII sent to LLM APIs" — is the guardrail already named on this layer, but it's one of four the prompt assembly stage has to enforce before anything reaches the LLM Adapter:

| Guardrail | What it enforces |
|---|---|
| **PII removal** | NFR6 — no name, phone number, email, or other personally-identifying raw field reaches the prompt, regardless of how useful it might seem for context. |
| **Tenant isolation** | The retrieved comparison leads, and every field pulled into structured context, come from the requesting lead's own tenant only — see the vector-search scoping above. Same guarantee as NFR5, enforced here specifically. |
| **Maximum context size** | A hard cap on assembled prompt size (tokens), so a lead with an unusually long history can't silently balloon cost or latency, or exceed the model's context window. |
| **Prompt schema** | The assembled prompt itself follows a fixed structure (matching the versioned template above) rather than ad hoc formatting — this is what makes prompt changes reviewable as a diff, the same way a code change is. |

Framing these four together, and enforcing them in one place (the prompt builder), is what keeps this stage a deterministic, testable component rather than a string-concatenation function that happens to also need to remember not to leak PII.
