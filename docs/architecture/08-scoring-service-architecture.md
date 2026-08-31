# Section 8 — Scoring Service Architecture (Backend)

**Depends on:** [05-ml-model-training.md](05-ml-model-training.md), [06-mlops.md](06-mlops.md), and [07-llm-rag-layer.md](07-llm-rag-layer.md) — this is the backend that wires all three into a callable API surface.
**Feeds into:** [09-browser-extension.md](09-browser-extension.md) — the extension is a pure client of the endpoints defined here.

## What this section will do

This section is the backend blueprint: the eight components that sit between the browser extension and the model/LLM, and the concrete REST API contract the extension is built against. It's the integration point where every earlier section (feature extraction, the trained model, the cache, the LLM) becomes one coherent service.

**Evidence note:** per the taxonomy in [00-overview.md](00-overview.md#evidence-taxonomy), this file is almost entirely **[Hypothesis]** — an architecture design, not something built or measured yet. Any prototype pipeline that exists elsewhere is a separate batch ETL → train → score process, not this live service. Latency/size figures below (0.8ms inference, 30MB model) are **[Projection]** carried over from [05-ml-model-training.md](05-ml-model-training.md)'s planning-time estimates, not measurements of this service.

## Component architecture

**The Scoring API is an orchestration layer, not "everything."** An earlier version of this table had the Scoring API doing scoring, explanation, and everything else in one undifferentiated box. [07-llm-rag-layer.md](07-llm-rag-layer.md) already established a distinct **Explanation Service** — that separation belongs in this component table too, not just in the LLM section:

| Component | Role |
|---|---|
| **Browser Extension** | `content.js` reads row-id attributes, batch-POSTs to the API, injects badges — same code across all 4 browsers |
| **API Gateway** | Nginx reverse proxy — rate limiting, tenant auth check, SSL termination, request routing |
| **Scoring API (FastAPI)** | Orchestration only: routes score requests to the ML Model Service, explain requests to the Explanation Service, and handles tenant/health endpoints directly. See "API endpoint specifications" below for the exact routes. |
| **Feature Extractor** | Pulls lead history, computes the 60 features from [04-feature-engineering.md](04-feature-engineering.md), applies actor classification and test-lead filtering, and applies the same versioned feature transformations (encoders, imputers, EDA-derived tiers) recorded in the model artifact — see the note below on why this isn't independent normalisation logic |
| **ML Model Service** | XGBoost loaded in memory (30MB), 0.8ms inference, batch scoring, version-aware — polls the Model Registry ([06-mlops.md](06-mlops.md)) and atomically swaps in a new version without a restart; see "how a new model version actually loads" below |
| **Explanation Service** | Wraps the SHAP-only path and the LLM Adapter ([07-llm-rag-layer.md](07-llm-rag-layer.md)) behind one interface; the Scoring API calls this, never the LLM Adapter directly |
| **Redis Cache** | Score cache TTL 24h, feature cache TTL 1h, tenant flags, session tokens — invalidates on event; see the invalidation sequence below |
| **Postgres DB** | Leads table, history table, score history, tenant config, feature flags |

```
Browser Extension
        │
        ▼
API Gateway  (auth, rate limiting, SSL)
        │
        ▼
Scoring API  —  orchestration only
        │
        ├── score request  ────────▶  Feature Extractor  ──▶  ML Model Service  ──▶  Redis Cache
        │
        └── explain request  ──────▶  Explanation Service  ──▶  SHAP-only path, or the
                                                                  LLM Adapter (07-llm-rag-layer.md)
```

The request path is cache-first: a batch score request hits Redis first; on a miss it falls back to the Feature Extractor → ML Model Service live-compute path, then writes the result back to cache. This is what satisfies NFR2 (badge render < 500ms) from [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) on the common path, while still supporting fresh computation for leads that changed since the last cache write.

### Why "normalises" isn't quite right for the Feature Extractor

[05-ml-model-training.md](05-ml-model-training.md) deliberately moved every global statistic (encoders, imputers, EDA-derived tiers) into the training pipeline, fit on the training split only, and bundled into the model artifact specifically so training and serving never compute a transformation two different ways. If the Feature Extractor did its own independent normalisation, that guarantee would be broken the first time someone tweaked one side and not the other. So the Feature Extractor doesn't normalise in any independent sense — it **applies the exact versioned transformations shipped inside the model artifact it's currently serving**, the same ones [06-mlops.md](06-mlops.md)'s "schema compatibility" promotion check verifies match what this component expects.

### Cache invalidation, made explicit

"Invalidates on event" above is the summary; the actual sequence:

```
Lead Updated (new call logged, status changed, etc.)
        │
        ▼
Invalidate — the cached score/feature entry for that lead is dropped, not just marked stale
        │
        ▼
Recompute — Feature Extractor + ML Model Service run the live-compute path for that one lead
        │
        ▼
Write-through — the fresh result is written back into Redis before the response returns
        │
        ▼
Serve — this request, and every subsequent one, gets the fresh cached result
```

This is the same online-scoring path described in "Offline batch scoring vs. online real-time scoring" below — cache invalidation is what *triggers* that path, not a separate mechanism.

### How a new model version actually loads

[06-mlops.md](06-mlops.md) describes the Model Registry's version pointer changing on promotion or rollback; here's the other half, inside the ML Model Service itself:

```
Model Registry — "active" version pointer changes
        │
        ▼
ML Model Service polls (or subscribes to) that pointer
        │
        ▼
New version detected → load the new model artifact into memory
        │
        ▼
Atomic swap — the new version becomes "current" in one step; no request is ever served
  by a half-loaded model, and no request is dropped during the swap
        │
        ▼
Continue serving — subsequent requests use the new version; the old one is released
```

This closes the loop [06-mlops.md](06-mlops.md) started: a registry rollback isn't real until *this* mechanism actually picks it up.

## Offline batch scoring vs. online real-time scoring

That cache-first path only works if the cache is usually warm — which means the backend actually needs **two separate scoring triggers**, not one. This wasn't drawn as two paths on the board, but it's how the pieces above already have to work together:

**Offline batch scoring (nightly)**
- A scheduled job (same Airflow family as the "Data Pipeline" DAG in [06-mlops.md](06-mlops.md)) scores every open lead, across every tenant, once a day — outside business hours.
- Every result is written into the Redis score cache (24h TTL) ahead of time, so the overwhelming majority of daytime `GET /api/scores/{leadId}` / `POST /api/scores/batch` calls are pure cache hits. This is the main reason NFR2's < 500ms badge render is achievable at all — the live-compute path is the exception, not the rule.
- One large batch-inference pass against the in-memory XGBoost model is also far cheaper per-lead than thousands of individual live calls would be.

**Online real-time scoring**
- Triggered by an event: a new lead is created, or an existing lead's history changes — this is FR2, "update scores in real-time as lead history changes."
- The Feature Extractor recomputes just that one lead's 60 features, the ML Model Service scores it in 0.8ms, and the result overwrites the cached value immediately — so a lead doesn't sit with a stale badge until the next nightly batch.
- This is the same live-compute path used as a cache-miss fallback (e.g. a new tenant's first day, per UC5, before its first nightly batch has run).

Both paths write to the same Redis cache and read from whichever model version is currently registered as live ([06-mlops.md](06-mlops.md)'s Model Registry) — there's one source of truth for "the current score," just two different triggers for computing it.

## API endpoint specifications

**Naming convention, applied consistently below:** `/api/{resource}` for collection-style actions, `/api/{resource}/{id}` for a single item, plural resource names throughout. An earlier draft mixed `GET /score/:lead_id` with `POST /scores/batch` and `GET /explain/:id` — three different singular/plural and path-param conventions in three endpoints. Fixed so every endpoint follows the same shape.

### `POST /api/scores/batch`
- **Headers:** `X-Tenant-Id`, `X-Auth-Token`
- **Body:** `{lead_ids: [uuid, ...]}` — **no `tenant_id` field.** See "why tenant identity isn't in the body" below.
- **Returns:** `{lead_id: {label, probability, cached, timestamp}}`

### `GET /api/scores/{leadId}`
- **Headers:** `X-Tenant-Id`, `X-Auth-Token`
- **Returns:** `{label: 'hot', probability: 0.82, features_snapshot, last_updated}`

### `POST /api/explanations/{leadId}`
- **Headers:** `X-Tenant-Id`, `X-Auth-Token`
- Triggers the Explanation Service ([07-llm-rag-layer.md](07-llm-rag-layer.md)). **Enterprise tier only.**
- **Returns:** `{explanation, topSignals, nextAction, callWindow, script}` — the exact structured-output schema from Section 7, not a different shape re-derived at the API layer.
- **Failure behaviour:** if the LLM Adapter is unavailable (timeout, error, rate-limited), this still returns **HTTP 200** with the SHAP-only explanation (`topSignals` populated from feature importance; `nextAction` present; `callWindow`/`script` omitted). An LLM outage is not a scoring-service outage — see [07-llm-rag-layer.md](07-llm-rag-layer.md)'s fallback design.

### `GET /api/tenants/{tenantId}/scoring`
- **Headers:** `X-Auth-Token`
- **Returns:** `{enabled: bool, tier: 'growth'|'enterprise'}`
- Read counterpart to the `PUT` below, same resource — this is what the extension calls on load (per [09-browser-extension.md](09-browser-extension.md)'s enable/disable flow) to check whether scoring is currently on for its tenant.

### `PUT /api/tenants/{tenantId}/scoring`
- **Headers:** `X-Auth-Token`
- **Body:** `{enabled: bool, tier: 'growth'|'enterprise'}` — no `tenant_id` field; it's already the path parameter.
- Updates the tenant's feature flag. All of that tenant's users see (or lose) badges within 60 seconds — this is the backend half of FR7 and UC3 from [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md), completed on the client side in [09-browser-extension.md](09-browser-extension.md)'s tenant enable/disable flow.

### `GET /api/health`
- No auth required. Returns model version, **registry version currently loaded** (making a rollback trivially verifiable — "is the registry's active pointer actually what this instance is serving"), cache hit rate, and uptime.
- Used by the load balancer's health checks; returns 200 if all services are healthy — this is what NFR4 (99.9% uptime SLA) is measured against.

### Why tenant identity isn't in the request body

An earlier draft had `POST /api/scores/batch` take both an `X-Tenant-Id` header (for auth) and a `tenant_id` field in the body (for the query). Two sources of truth for the same fact invite an obvious question: which one wins if they disagree? Tenant identity now comes from exactly one place — the authenticated request context (`X-Tenant-Id` + `X-Auth-Token`) — and every endpoint that used to accept it in the body no longer does. The tenant-scoring endpoint's `{tenantId}` is the one exception, and it's a path parameter identifying *which tenant's policy to change*, not a duplicate of the caller's own identity — those are different facts, so it's not the same ambiguity.

## Why this shape

- Batch scoring (not per-lead calls) is what makes FR8 ("handle 1L+ leads with sub-second badge rendering") feasible — the extension fetches scores for a whole visible page of rows in one call.
- The explain endpoint is deliberately routed to a separate Explanation Service and gated to Enterprise tier, keeping the cost boundary from [07-llm-rag-layer.md](07-llm-rag-layer.md) enforced at the architecture layer, not just by API convention.
- The tenant-scoring toggle being a single `PUT` with a 60-second propagation window is what makes FR3/FR7 (multi-tenant isolation, one-click enable/disable) operationally simple rather than requiring a redeploy per tenant.

## Three logical services, one deployable unit for now

The Feature Extractor, ML Model Service, and Explanation Service above are three distinct logical services, coordinated by the Scoring API's orchestration — not three responsibilities buried inside one FastAPI endpoint. Nothing here requires deploying them as three separate processes from day one; a single container running all three is a perfectly reasonable v1. What this separation buys is *optionality*: if the Explanation Service's LLM calls need to scale independently of the Model Service's inference load, or the Feature Extractor becomes expensive enough to warrant its own autoscaling, splitting them apart later is an infrastructure change, not an architecture rewrite. The alternative — one endpoint that does feature extraction, inference, and explanation inline — would make that same future split much more expensive.
