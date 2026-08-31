# Section 9 — Browser Extension: Cross-Browser Implementation

**Depends on:** [08-scoring-service-architecture.md](08-scoring-service-architecture.md) — every action the extension takes is a call to that API.
**Feeds into:** [10-tech-stack-and-deployment.md](10-tech-stack-and-deployment.md) — the extension's build/store-submission steps are one of the parallel tracks in the CI/CD pipeline there.

## What this section will do

This section defines the client the salesperson actually sees: a browser extension (not a CRM code change, per FR6) that injects Hot/Warm/Cold badges onto the existing CRM UI. It covers the file structure of the extension itself, the end-to-end flow from a tenant admin enabling the feature to a badge appearing on screen, and the browser-by-browser rollout plan.

**Evidence note:** **[Hypothesis]** in full — this is a design, not a build. The repo's `extension/` directory exists (`extension/src/`, `extension/tests/`) but is currently empty scaffolding; nothing described below has been implemented yet.

## Extension file structure

**Networking belongs to `background.js`, not `content.js`.** An earlier version of this file had `content.js` batch-fetching scores directly — that puts API calls, auth, and retry logic in the one script with direct DOM access, which is both the wrong separation of concerns for a browser extension and unnecessarily broad use of host permissions. The corrected split:

| File | Role |
|---|---|
| `manifest.json` | Declares permissions, host_permissions (CRM domain + API domain), content_scripts, background service_worker, popup action |
| `content.js` | **DOM only.** Queries `[row-id]` elements, renders badge placeholders and updates, runs the `MutationObserver` for virtually-scrolled rows. Never calls the Scoring API directly — it messages `background.js` and waits for a response. |
| `background.js` | **All networking.** Owns authentication (token storage/refresh in `chrome.storage.local`), every Scoring API call, retries, scheduled refreshes, and the messaging bridge to `content.js`. Never touches the DOM. |
| `popup.html` / `popup.js` | The extension-icon UI — enable/disable toggle, current tenant, score stats, link to settings |
| `styles.css` | `.li-score-hot` (red pill), `.li-score-warm` (amber pill), `.li-score-cold` (blue pill) — injected into the CRM page |
| `build.sh` | Webpack bundles for Chrome/Edge (MV3), Firefox (compatibility layer), Safari (`xcrun` convert) — one source tree, four browser packages |

### Why this split, specifically

```
content.js                    background.js                  Scoring API
    │                              │                               │
    │  "score these leadIds"       │                               │
    ├─────────────────────────────▶│                               │
    │                              │  POST /api/scores/batch       │
    │                              ├──────────────────────────────▶│
    │                              │◀──────────────────────────────┤
    │  scores for those leadIds    │  (auth, retry-on-failure,     │
    │◀─────────────────────────────┤   cache logic all live here)  │
    ▼                              │                               │
Render badges                      ▼                               ▼
```

`content.js` runs in the CRM page's context and needs the DOM permissions that implies; `background.js` is the only place that needs the API host permission, the auth token, and retry state. Centralizing networking in one script — rather than splitting it across whichever content script happened to need a score — is what keeps the extension's permission surface minimal and its API-calling logic testable independent of any particular CRM page's DOM shape.

## Tenant enable/disable flow (end to end)

1. Tenant admin → CRM Settings → Add-ons → Lead Intelligence.
2. Admin clicks "Enable Lead Scoring" → selects tier (Growth / Enterprise).
3. Backend flips `is_scoring_enabled=true` for that `tenant_id` in the `feature_flags` table — this is the `PUT /api/tenants/{tenantId}/scoring` call from [08-scoring-service-architecture.md](08-scoring-service-architecture.md).
4. Sales users visit the Chrome Web Store / Firefox Add-ons / Edge Add-ons / Safari App Store and install the extension.
5. On first load, `background.js` **derives the tenant context from the authenticated CRM session** — the exact mechanism (a cookie, a JWT claim, a bootstrap endpoint, `localStorage`) is a CRM-integration implementation detail, not an architectural commitment. Tenant identity arriving this way, rather than being hardcoded to one storage mechanism, mirrors the same principle [08-scoring-service-architecture.md](08-scoring-service-architecture.md) applies server-side: tenant identity comes from the authenticated context, not a value the client invents or a specific browser API the architecture locks itself to.
6. `background.js` calls `GET /api/tenants/{tenantId}/scoring` → receives `{enabled: true}` (same resource as the `PUT` above, read instead of written).
7. `content.js` detects the visible lead rows and messages `background.js` with their IDs; `background.js` makes the batch API call — see "why this split" above. `content.js` never calls the API directly.
8. Scores come back from the Redis cache (<1ms) or are computed live (~5ms) if not cached; `background.js` relays them back to `content.js`.
9. Badges render — see "badge rendering lifecycle" below for the exact sequence, including what the rep sees before the API responds.
10. A `MutationObserver` in `content.js` watches the DOM and requests scores (via `background.js`) for newly-rendered rows as the user scrolls (handles virtualized/infinite-scroll lead lists).
11. A rep clicks a badge for an explanation — see "explain interaction" below.
12. `background.js` runs a **scheduled background refresh** (cadence is a deployment policy, not a fixed clock time — see [06-mlops.md](06-mlops.md)'s "retraining cadence is a policy, not a hard limit," applied the same way here) that re-checks the tenant's scoring-enabled flag, refreshes the auth token, and re-pulls scores — not scores alone.
13. If the admin disables scoring, the flag flips and the extension goes silent within 60 seconds — the client-side mirror of Step 3.

This flow is the direct implementation of UC1, UC3, and UC5 from [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md): a rep sees a badge with zero CRM changes, an admin controls it with one click, and a new tenant gets scores from day one because the flag check happens on every load rather than requiring a manual per-tenant deploy.

### Badge rendering lifecycle

Step 9 above is itself a sequence, not an instant swap — worth making explicit because it's what determines what a rep sees on a slow network, not just on a fast one:

```
Rows detected (content.js, on page load or MutationObserver trigger)
        │
        ▼
Placeholder badge rendered immediately (a neutral/loading state, not blank)
        │
        ▼
background.js's API call resolves (cache hit: <1ms, live compute: ~5ms, or slower under load)
        │
        ▼
Badge updates to the real Hot/Warm/Cold state
        │
        ▼
MutationObserver continues watching for newly-rendered rows
```

The placeholder step matters specifically because it gives the rep immediate visual feedback that scoring is active, rather than a lead row that looks unscored for however long the network round-trip takes.

### Explain interaction

The flow above ends at a badge appearing; [07-llm-rag-layer.md](07-llm-rag-layer.md) and [08-scoring-service-architecture.md](08-scoring-service-architecture.md)'s `POST /api/explanations/{leadId}` are what a badge click actually does, end to end:

```
Rep clicks a Hot/Warm/Cold badge
        │
        ▼
Loading indicator shown in the sidebar panel
        │
        ▼
background.js calls POST /api/explanations/{leadId}
        │
        ▼
Sidebar opens with the structured explanation (explanation, topSignals, nextAction,
  callWindow, script — 07-llm-rag-layer.md's schema) — or the SHAP-only fallback
  version of that same schema if the LLM Adapter was unavailable, per Section 7/8's
  designed failure mode. Either way the sidebar opens; the rep never sees an error
  for this specific failure.
```

### What the extension does not store

Worth stating explicitly, since it's a real privacy property and not just an omission: the extension does not persist lead history, and does not persist scores beyond the current page session. `chrome.storage.local` holds the auth token and lightweight tenant/settings state (the enabled flag, tier) — nothing lead-specific. Explanations, if cached at all, live only in memory for the current session, not written to disk. If the extension is uninstalled or the browser profile is cleared, no lead data leaves a trace in it — the CRM and the backend remain the only systems of record.

### Failure behavior — a down API degrades gracefully, it doesn't break the CRM

If `background.js`'s call to the Scoring API fails (timeout, 5xx, network error):

```
API call fails
        │
        ▼
Badge shows a neutral/grey state (or no badge at all) — never a broken UI element,
  never an error surfaced on the CRM page itself
        │
        ▼
background.js retries on its own schedule (exponential backoff, not a tight loop)
        │
        ▼
No disruption to the underlying CRM — the extension is additive UI; if it can't reach
  the API, the CRM page underneath it works exactly as it did before the extension existed
```

This is the same principle as [07-llm-rag-layer.md](07-llm-rag-layer.md)'s LLM-unavailable fallback, one layer up: a failure in an additive feature should never take down or visibly break the thing it's additive to.

## Browser-by-browser support

| Browser | Manifest | Store | Cost | Review time | Notes |
|---|---|---|---|---|---|
| **Chrome + Edge** | Manifest V3, same exact codebase | Chrome Web Store / Edge Add-ons | $5 one-time (Chrome) / free (Edge) | 1–3 days | Largest user base — ship first |
| **Firefox** | Manifest V2/V3 via a `browser.*` **compatibility layer** (named for what it does, not tied to today's specific polyfill — manifest support across browsers keeps evolving) | Firefox Add-ons | Free | 1–7 days | Minor tweak only; good developer user base |
| **Safari** | `safari-web-extension-converter` (Xcode) | Mac App Store | $99/yr (Apple Developer) | 1–2 weeks | Do this last — longest review, extra tooling |
| **Mobile (future)** | iOS Safari Extension / Android Chrome extension | — | — | — | Not MVP scope — roadmap item; a native CRM-app badge is the likely alternative |

The "Chrome+Edge first, Firefox next, Safari last" order isn't arbitrary — it's sequenced by review-time risk and matches the Week 5–7 breakdown in [12-delivery-timeline-and-ask.md](12-delivery-timeline-and-ask.md), where Safari conversion is deliberately scheduled alongside the RAG pipeline work rather than blocking the initial pilot.

## The extension is a thin client

Worth stating as an explicit architectural property, not just an implementation detail: nothing in this file defines business logic. Scoring, thresholds, explanation, and tenant policy all live server-side, per [05](05-ml-model-training.md)–[08](08-scoring-service-architecture.md). What's described here is a client that renders what the backend contracts return — `content.js` renders DOM state, `background.js` calls defined API contracts and relays responses, and neither script makes a decision the server hasn't already made. That's deliberate: it means the extension's four browser builds are a rendering and packaging problem, not four places business rules could quietly drift apart from each other or from the server.
