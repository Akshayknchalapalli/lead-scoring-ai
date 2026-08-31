# POC Data Findings: Real Lead Export (5 CSVs, 50,000 rows)

**Source files** (user-provided, not checked into repo):
`data-1776891244155.csv`, `data-1776891157362.csv`, `data-1776891100282.csv`, `data-1776891037923.csv`, `data-1776713795562.csv`

These are five ~10,000-row pages of what is effectively one export (49,830 unique `LeadId`s, 170 duplicates across pages), not five distinct tenant datasets. 160 columns, matching a Leadrat-style CRM lead record.

## Key facts that shape the POC

1. **Multi-tenant, real**: 742 distinct `TenantId` values, heavily long-tailed (median 21 leads/tenant, top tenant `blissrealty` has 3,346). For a legible demo, use the **top 4-5 tenants by volume** (`blissrealty`, `propmart`, `lifespacepropertysolution`, `prdblack`, `assettrustservices`) — consistent with `plan.md`'s stated scale target ("initial 100k+ leads across 3-4 tenants").

2. **Versioned-JSON fields (the main engineering surprise)**: most mutable columns are not flat values — they're JSON objects keyed by an incrementing version number, e.g.
   - `BaseLeadStatus = {"1": "New", "2": "Pending"}`
   - `BookedDate = {"1": null}` or `{"1": null, "4": "2025-12-29T21:41:56Z"}`
   - Same pattern for: `SubLeadStatus`, `Rating`, `LeadSource`, `SubSource`, `IsHotLead`/`IsWarmLead`/`IsColdLead`, `IsPicked`, `IsEscalated`, `IsHighlighted`, `IsAboutToConvert`, `EnquiredFor`, `SaleType`, `BasePropertyType`, `ShareCount`, `IsArchived`, `IsMeetingDone`, `IsSiteVisitDone`, `ScheduledDate`, `RevertDate`, `PickedDate`, `LowerBudget`, `UpperBudget`, `SoldPrice`, `ModifiedDate`, `ContactRecords`.
   - **The "current" value is the value at the last key.** `CurrentVersion` (mean 11, max 712) roughly tracks total edit count across all versioned fields, not any single field's version.
   - **No per-version timestamps exist inside these blobs.** We only have overall `CreatedDate`, `ModifiedDate`, and the `CurrentVersion` counter. Precise event-time cutoff enforcement (as `spec.md` FR-012 assumes) is not reconstructable from this export at per-field granularity — a POC has to use `ModifiedDate`/transition-count as a proxy, and this limitation should be stated plainly, not hidden.
   - **Do not trust a naive `notna()` check on these columns.** Every row has a non-null JSON string (even when the real value is null), so `BookedDate.notna()` reports 42,553/50,000 — the correct number, after parsing, is **156**.

3. **Conversion label is real and very rare.** Using the spec's raw rule (FR-011: `BookedDate` present or `SoldPrice > 0`, after JSON-parsing):
   - **162 / 49,830 unique leads (0.32%) have a booking/sale signal.**
   - Label sanity-check against status text: current `BaseLeadStatus = "Booked"` → 121 with-signal vs 14 without; `"Booking Cancel"` → 4 with-signal vs 33 without.
   - Applying the full FR-011/FR-019 rule (cancelled/reverted bookings are non-converted unless a later valid booking occurred) removes those 4 `"Booking Cancel"` leads that still carry a stale `BookedDate`/`SoldPrice` from before cancellation — since current status *is* "Booking Cancel", no later valid booking exists, so these must not count as converted. **Final POC label: 158 / 49,830 positives (0.317%).** (Implemented in `backend/src/poc/etl/label.py`.)
   - This is a heavy class imbalance (~1:315). A POC model needs class-weighting (e.g. XGBoost `scale_pos_weight`) and should not use the spec's default 0.40/0.80 probability thresholds as-is (those assume a different label prevalence) — POC will derive Hot/Warm/Cold cutoffs from score percentiles instead, and flag this as a business decision to revisit, not a finished calibration.

4. **PII columns present, must be excluded from model features / explanation text** (per FR-028): `Name`, `Email`, `ContactNo`, `AlternateContactNo`, `ReferralContactNo`, `ReferralName`, `LandLine`, `DateOfBirth`, `ConfidentialNotes`, free-text `Notes`.

5. **Usable behavioral/engagement signals** (real, non-PII):
   - `PickedDate` present for ~65% (lead has been opened/claimed by an agent)
   - `ScheduledDate` present for ~20% (meeting scheduled)
   - `IsMeetingDone` / `IsSiteVisitDone` present for <3% but real when present
   - `ContactRecords` (per-version contact-outcome map, e.g. `{"4":1,"5":1,"6":0}`) — usable as a contact-attempt/success count
   - `LowerBudget`/`UpperBudget` (numeric after JSON parse; mostly 0/unset, real values up to ~1.5B — mixed currency, see `Currency` column)
   - `BasePropertyType`, `BHKType`/`NoOfBHK`, `EnquiredCity`/`EnquiredState`, `LeadSource` (opaque numeric code, no decode legend in this export — treat as categorical), `SaleType`, `EnquiredFor`
   - Status-transition count (number of keys in `BaseLeadStatus` / `CurrentVersion`) as an activity-volume proxy.

6. **`Rating`, `IsHotLead`/`IsWarmLead`/`IsColdLead` are not usable as ground truth** for the model to predict — they're almost universally unset/false (e.g. `IsHotLead` true for only 7 rows) and represent ad hoc manual tags on a handful of leads, not a consistent taxonomy across tenants. The POC model must derive its own Hot/Warm/Cold from predicted booking probability, independent of these fields.

## Implementation finding: `current_status` is target leakage, not a feature
First training pass included the lead's current status text (`BaseLeadStatus`, last value) as a
categorical feature and got a suspiciously high AUC (0.988). Feature importance showed why:
`current_status` alone accounted for 84% of the model's decisions, and its values are near-synonymous
with the label — `"Booking Done"`/`"Invoiced"` are 100% converted, `"Booked"` is 89.6% converted. The
model was mostly just reading the outcome back off a differently-named copy of itself, not predicting
intent. Removed `current_status`/`current_sub_status` from model inputs (kept as display-only fields
for the API/UI, per `feature_spec.py`'s `DISPLAY_ONLY_FEATURES`); retrained AUC dropped to a much more
credible **0.699**, driven by real engagement signals instead (`tenant_id`, `has_scheduled_meeting`,
`is_site_visit_done`, `is_picked`, `is_meeting_done`, `lead_source_code`). This is exactly the kind of
leakage the full spec's FR-009/FR-012/SC-006 are designed to prevent — worth mentioning in the CTO
demo as a concrete example of the leakage-control discipline working, not just a policy on paper.

## Implication for POC architecture
The dataset is a historical snapshot, not a live event stream. The POC is a **batch ETL → train → score → serve** pipeline, not the event-driven/queue/cache architecture in the full `plan.md`. That's the correct scope cut, not a shortcut — see `poc/spec.md`.
