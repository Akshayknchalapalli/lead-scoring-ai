# Lead Scoring POC — One-Pager

**What this is**: a working prototype that classifies real historical leads as Hot/Warm/Cold, with a per-lead explanation, isolated per tenant — built to validate the idea in `specs/001-lead-scoring-platform/spec.md` before committing to the full production build.

## The data (real, not synthetic)
- 50,000 CRM lead export rows → **49,830 unique leads** across **742 tenants**, spanning ~3.5 years (2022-12 to 2026-04).
- Conversion label (booking/sale, per the spec's own rule) is real and rare: **158 positives (0.317%)**.
- Demo uses the 5 highest-volume tenants: `blissrealty`, `propmart`, `lifespacepropertysolution`, `prdblack`, `assettrustservices`.

## The model
- XGBoost classifier, global model with tenant as a feature (per the spec's global-model decision), class-imbalance handling for the ~1:315 label ratio.
- **AUC: 0.75** on a held-out stratified test set — modest but real, driven by genuine engagement signals (`tenant_id`, meeting scheduled, site visit done, picked-up status, lead source).
- **Caught and fixed two real bugs during development** (full writeup in `poc/data-findings.md` and `poc/production-readiness-improvements.md`): (1) an earlier pass that included the lead's current CRM status as a feature scored AUC 0.99 — the status field ("Booked"/"Invoiced") turned out to be a near-restatement of the label itself (target leakage); removing it dropped AUC to an honest 0.699. (2) a data-quality bug where empty-string CRM sentinel values (`{"1": ""}`) were slipping through as their own category instead of being treated as "unknown" — fixing it improved AUC further to 0.751, from cleaner features alone, no architecture change. Both are concrete demonstrations of the leakage-control and data-quality discipline the full spec's FR-009/FR-012/SC-006 call for, not just policy on paper.
- Hot/Warm/Cold thresholds are percentile-based (top 10% hot, next 30% warm), not the full spec's fixed 0.40/0.80 cutoffs — those assume far more positive examples than this data has. Current run: **5,022 hot / 14,911 warm / 29,897 cold**.
- Explanations use business-language sentences per feature (not raw feature names/numbers) and are direction-aware — see `poc/production-readiness-improvements.md`.

## What's real vs. simplified in this POC
| Real | Simplified for POC |
|---|---|
| Actual CRM lead data, actual bookings | No live event stream — batch pipeline over the CSV export |
| Actual multi-tenant structure (742 tenants) | No Redis cache / queue / hybrid reconciliation |
| Actual trained model, actual AUC | No SHAP (uses XGBoost's built-in per-lead contribution output — same underlying algorithm) |
| Real tenant enable/disable isolation | No drift detection, retraining automation, or chaos testing |
| Same DB schema as the full spec (`entities.py`, reused as-is) | Thresholds are provisional, pending business sign-off |

## How to run it
```
cd backend
PYTHONPATH=src python scripts/run_poc_pipeline.py   # ETL -> train -> evaluate -> score -> seed DB (~90s)
PYTHONPATH=src python -m uvicorn poc.api.app:app --port 8811
# open http://127.0.0.1:8811
```

## Recommendation
The core idea holds up on real data: leads separate meaningfully by predicted conversion likelihood using signals that are available before conversion, tenant isolation works, and the platform correctly avoids the model's most tempting leakage trap. The honest next questions for a production build are (1) whether a 0.75 AUC lift is worth the investment given how rare bookings are, and (2) what business-approved Hot/Warm/Cold thresholds should replace the provisional percentile cutoffs used here.
