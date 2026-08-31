# Section 3 — Data Architecture & Real Schema (+ Section 15 appendix)

**Depends on:** [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) (FR3 tenant isolation, NFR5 zero leakage frame what "raw data sources" must support).
**Feeds into:** [04-feature-engineering.md](04-feature-engineering.md) — every feature there is derived from a column documented in this file.

> This file merges board **Section 3** ("Data Architecture: What We Have & What We Build") with board **Section 15** ("Real Data Architecture Revelation"). They were written at different points in the investigation: Section 3 is the initial mental model of the data ("it's an event log we parse via an API"); Section 15 is what querying the actual production table revealed ("it's a version-snapshot table, not an event log"). Section 15 supersedes Section 3's assumptions but doesn't replace its inventory of *which* entities carry signal — so both are kept together as one corrected picture.

## What this section will do

This is the data-reality section. Before any feature can be engineered, the team has to answer: what tables actually exist, what do their columns actually contain, and what garbage is hiding in them. It does three things:

1. Inventories the raw entities that carry lead-scoring signal (Section 3).
2. Flags data-quality traps that would poison a naive model (Section 3).
3. Corrects the team's own initial assumption about the underlying schema, replacing it with a verified, column-by-column map of the real 160-column table (Section 15) — including which of the ~60 planned features can and cannot actually be extracted from it.

**Evidence note for this file:** almost everything below is **[Observed]** — it comes from directly inspecting the real export or querying the real production table, not from the whiteboard's assumptions or any planning estimate (using the taxonomy from [00-overview.md](00-overview.md#evidence-taxonomy)). The one exception is the 3A Data Pipeline subsection, which is a **[Hypothesis]**-tier recommendation — a proposed stage, not something already built. Anywhere that's not the case is called out inline.

## Part A — Raw data sources (Section 3)

> **[Observed] Current data volume:** the database export in hand is **~50,000 leads across 3–4 tenants** (742 distinct `TenantId`s exist in the raw export; the top 4–5 by volume were selected for a legible sample). That's what everything in this file and [04-feature-engineering.md](04-feature-engineering.md) is grounded in. It's still a small fraction of Leadrat's **1,500+ total clients**, so treat the schema and feature findings below as validated on a sample, not as the full production population.

### The four raw input groups

| Group | Contents |
|---|---|
| **Static Lead Fields** | Source, Budget, Location, BHK, PropertyType, EnquiryType, Nationality, UTM params, Campaign |
| **Lead History DTO** | LeadCallLog, Lead Status, Contact Records, Notes, Assignment, Picked Date — all timestamped |
| **Actor Classification** | Human (salesperson), System (routing rules), Integration (portals) — each carries a different signal weight |
| **Tenant Context** | tenant_id, project list, price ranges, geography, historical conversion rates, per-source performance |

### Top-signal entities within the history feed

Ranked by how strong a predictor each is, with the extraction approach already noted at this stage:

| Entity | Signal strength | Extraction approach |
|---|---|---|
| **LeadCallLog** | TOP SIGNAL | Parse direction, outcome, duration, recording URL |
| **Lead Status** | TOP SIGNAL | Track progression: New → Pending → Interested → Booked |
| **Contact Records** | TOP SIGNAL | Channel used: Call / WhatsApp / Visit / Email per event |
| **Picked Date** | TOP SIGNAL | Hours to first pick from creation — critical urgency signal |
| **Lead Source** | TOP SIGNAL | Source *at creation time* — NOT the latest value (re-enquiry adds noise) |
| **Lower/Upper Budget** | TOP SIGNAL | budget_ever_set, range_width, matches_project_price |
| **Projects / Properties** | TOP SIGNAL | has_specific_project — a named project implies a serious buyer |
| **Notes** | MEDIUM | Human-written only — exclude Integration/System authors |
| **Assigned To User** | USE CAREFULLY | Count human reassigns only — ignore System-generated storms |
| **Base/Sub PropertyType** | MEDIUM | Specificity score: Residential → Flat = higher intent |
| **Enquired Cities/Locations** | MEDIUM | location_specificity: country+state+city+locality = 4 |
| **BHKTypes** | MEDIUM | 'Others' = vague (low intent), '2BHK' = specific (high intent) |

### Data quality issues discovered (must handle before ML)

**[Observed]** — these are traps found while inspecting real history data — a model trained without handling them will learn noise:

| Issue | What it looks like | Fix |
|---|---|---|
| **Assignment Storm** | 90+ System reassigns in 98 minutes — a routing bug | Cap count at 10, deduplicate bursts |
| **Re-enquiry Oscillation** | A field is set → cleared → reset within 5 minutes = 1 logical event | Use the latest stable `newValue` per fieldName |
| **Integration Notes** | Auto-note "Re-Enquired From Housing" — not a salesperson insight | Exclude from note counts |
| **Test Lead Contamination** | `updatedBy='Integration'`, name='TestLead24', Currency=BAM/AFN | Exclude from training entirely |
| **Three Actor Types** | Integration = portal push, System = routing noise, Human = gold signal | Tag every event with actor type before deriving anything |
| **Post-Conversion Leakage** | SoldPrice, BookedDate, TotalBrokerage, PaymentMode | Never use as features — label only, never input |

### 3A — Data Pipeline (**[Hypothesis]** — recommended production layer, not on the original board, not yet built)

The board goes straight from "raw data sources" to "feature engineering," as if the feature extractor can read directly off the CRM table. In practice, the data-quality-issues table above is the evidence that it can't: assignment storms, re-enquiry oscillation, test-lead contamination, and multi-actor noise all have to be cleaned *before* any feature derivation runs, or every feature in [04-feature-engineering.md](04-feature-engineering.md) inherits that noise. That cleanup is usually substantial enough to be its own pipeline stage rather than inline logic inside the feature extractor — worth calling out explicitly because it tends to become its own engineering effort once a team moves past initial validation and toward production scale.

```
CRM / production DB
        │
        ▼
   1. Ingestion        — pull new/changed lead rows (the "Data Pipeline (Daily)" Airflow DAG in 06-mlops.md)
        │
        ▼
   2. Validation        — schema checks (Great Expectations, already in the stack per 10-tech-stack-and-deployment.md);
        │                  catches traps like "every BookedDate is a non-null JSON string even when null"
        ▼
   3. Deduplication      — collapse re-enquiry oscillation and assignment-storm bursts into single logical events
        │
        ▼
   4. Missing-value handling — decide defaults per field (e.g. LowerBudget=0 vs. "not stated"; see budget_ever_set in 04)
        │
        ▼
   5. Schema evolution    — the CRM table already changed shape once during this project (Section 3 → Section 15's
        │                   correction from an event-log model to a 160-column version-snapshot table) — a pipeline
        │                   stage that tolerates new/renamed columns without breaking is what prevents that from
        │                   being a manual fire drill next time
        ▼
   Feature Store / Feature Engineering (04-feature-engineering.md)
```

This isn't a new step invented from nothing — Airflow's daily "Data Pipeline" component and the Great Expectations dependency both already exist in [06-mlops.md](06-mlops.md) and [10-tech-stack-and-deployment.md](10-tech-stack-and-deployment.md). The point of calling it out here as its own layer (3A) is that the five responsibilities above — ingestion, validation, deduplication, missing-value handling, schema evolution — are easy to under-scope as "a few lines inside the feature extractor" early on, and expensive to retrofit later once dozens of features depend on ad hoc cleanup logic scattered across the codebase.

## Part B — Section 15: what the real table actually looks like

**[Observed]** — this is a reverse-engineering exercise the team ran directly against the production database, and it overturned the assumption baked into Part A. The open questions in 15F are the exception: those are explicitly unresolved, marked `CLARIFY` rather than asserted as fact.

### 15A — Architecture revelation

| Old assumption (LeadHistoryDto API) | Reality (this DB table) |
|---|---|
| N rows per lead | 1 row per lead |
| Each row = 1 event | 160 columns per row |
| `fieldName` + `oldValue` + `newValue` | Versioned JSON per column: `{version_no: value}` |
| Parsed from an HTTP API response | Direct DB query |
| Sequential event log | Version-snapshot store |

Two columns anchor everything else:

- **`ModifiedDate`** — the timeline key. A JSON dict mapping version number → timestamp, e.g. `{"1":"2026-01-24T12:28Z", "2":"2026-01-25T08:53Z", ..., "12":"2026-02-07T14:11Z"}`. This is the primary anchor for every time-based feature.
- **`CurrentVersion`** — an integer (e.g. `12`) telling you how many versions to iterate through when walking any other JSON-versioned column.

### 15B — Two field types in the table

**Versioned JSON fields** — a dict of `{version: value}`, only storing versions where the value *changed*. To get the value at any version N, find the largest key ≤ N.

| Column | Sample value | What it gives you for ML |
|---|---|---|
| `ModifiedDate` | `{"1":"2026-01-24T12:28Z", "2":"2026-01-25T08:53Z", ..., "12":"2026-02-07T14:11Z"}` | Timestamp of every version — primary timeline anchor for all time features |
| `BaseLeadStatus` | `{"1":"New", "7":"Callback", "11":"Dropped"}` | Status at versions where it changed; missing versions inherit the last change |
| `SubLeadStatus` | `{"1":"", "7":"Follow Up", "11":"Ringing Not Received"}` | Child status; maps to parent via `MasterLeadStatus.OrderRank` |
| `AssignedToUser` | `{"1":"Balmit Lathwal", "2":"Mayank Tiwari", "12":"Balmit Lathwal"}` | Salesperson at each assignment version — human vs System actor detection |
| `AssignedFromUser` | `{"1":"Balmit Lathwal", "12":"Mayank Tiwari"}` | Previous assignee — pair with `AssignedToUser` for reassignment-chain analysis |
| `ContactRecords` | `{"2":1, "3":0, "5":0, "6":0, "9":1}` | Per-version integer — **encoding not yet confirmed** (see 15F, Q1) |
| `Notes` | `{"1":"", "7":"Not answering", "11":"np"}` | Salesperson note at the version it was written; exclude auto-notes from Integration |
| `PickedDate` | `{"1":null, "2":"2026-01-25T08:53:16Z", "12":null}` | When the lead was first picked — v2 timestamp anchors `hours_to_first_pick` |
| `IsPicked` | `{"1":false, "2":true, "12":false}` | Bool per version — 1=call answered, 0=not answered (**CLARIFY exact encoding with CTO**) |
| `IsMeetingDone` | `{"vN": true/false}` | Bool; find the first version where it flips true = meeting-completed timestamp |
| `IsSiteVisitDone` | `{"vN": true/false}` | Bool; strongest pre-booking signal — find the version where it first sets true |
| `BookedDate` | `{"1":null}` — null until booking | LABEL FIELD. Non-null at a version = positive class (label=1) |
| `IsArchived` | `{"vN": true/false}` | LABEL FIELD. True = confirmed lost (label=0 for training) |
| `ScheduledDate` | `{"1":null, "7":"2026-01-27T08:57Z", "11":null}` | Meeting/visit scheduled date at version 7; null again at v11 when dropped |

**Scalar fields** — a single current value, capturing intent data at creation time (no version history):

| Column | Sample value | What it gives you for ML |
|---|---|---|
| `Id` | `ffff8d5c-...` | Lead UUID — primary key for all joins |
| `TenantId` | `cebfe0c2-...` | `tenant_id` feature — which tenant owns this lead |
| `CreatedDate` | `2026-01-24 12:28:46 UTC` | Scalar creation timestamp; use `ModifiedDate["1"]` for precision instead |
| `CurrentVersion` | `12` | How many versions exist — iterate 1..N to walk the timeline |
| `LowerBudget` | `long (0 in sample)` | `budget_ever_set`, `budget_range_width`, `budget_matches_project` |
| `UpperBudget` | `long (0 in sample)` | Pair with `LowerBudget` — both 0 means no budget stated |
| `LeadSource` | `"trehan" in sample` | `source_quality_tier` — encode after EDA on conversion rates |
| `EnquiredFor` | scalar JSON array | `enquiry_type_encoded` — Buy/Rent/Invest. Confirmed present in table |
| `BHKTypes` | scalar JSON array | `bhk_is_specific` — contains "Others" = vague |
| `Projects` | scalar JSON array | `has_specific_project` — non-empty = named project |
| `Properties` | scalar JSON array | A specific unit named = strong intent signal |
| `Nationality` | scalar string | `is_nri_lead` — confirmed present in table |
| `Currency` | `"INR" in sample` | `is_nri_lead` — INR = domestic, USD/AED/GBP = NRI |
| `EnquiredCountry` | scalar string | `location_specificity` (+1), `is_nri_lead` detection |
| `SoldPrice` | scalar — 0 until booked | LABEL. > 0 = booking confirmed; pair with `BookedDate` |
| `BookedBy` | scalar UUID | LABEL. Non-null = positive class (label=1) |
| `UTMSource` | scalar string | `source_quality_tier` refinement — campaign origin |
| `UTMCampaign` | scalar string | `campaign_quality_tier` — map after EDA |
| `IsHotLead` | scalar bool — manual flag | **Interesting:** an existing manual hot flag — compare against the ML score |
| `Rating` | scalar — 0 in sample | Existing salesperson rating — compare against ML output |

### 15C — Reconstructed timeline for a sample lead (`CurrentVersion=12`, ends `label=0`)

| Version | Timestamp (UTC) | BaseLeadStatus | SubLeadStatus | AssignedToUser | ContactRecord | Notes |
|---|---|---|---|---|---|---|
| v1 | 2026-01-24 12:28 | New | — | Balmit Lathwal | — | — |
| v2 | 2026-01-25 08:53 | New | — | Mayank Tiwari | 1 (ans.) | — |
| v3 | 2026-01-25 08:53 | New | — | Mayank Tiwari | 0 | — |
| v4 | 2026-01-25 08:54 | New | — | Mayank Tiwari | — | — |
| v5 | 2026-01-25 08:55 | New | — | Mayank Tiwari | 0 | — |
| v6 | 2026-01-25 08:57 | New | — | Mayank Tiwari | 0 | — |
| v7 | 2026-01-25 08:57 | Callback | Follow Up | Mayank Tiwari | — | Not answering |
| v8 | 2026-01-25 08:59 | Callback | Follow Up | Mayank Tiwari | — | — |
| v9 | 2026-01-28 13:05 | Callback | Follow Up | Mayank Tiwari | 1 (ans.) | — |
| v10 | 2026-01-28 13:05 | Callback | Follow Up | Mayank Tiwari | — | — |
| v11 | 2026-01-28 13:05 | **Dropped** | Ringing Not Received | Mayank Tiwari | — | np |
| v12 | 2026-02-07 14:11 | Dropped | Ringing Not Received | Balmit Lathwal | — | — |

Read alongside the same walk expressed as `IsPicked` transitions: created → picked (first contact, call answered) → several not-answered attempts → status moves to Callback with a note → answered again 3 days later → status moves to Dropped (**label = 0**) → re-assigned 10 days later.

### 15D — How to read versioned fields: the "latest set value" rule

```python
# Step 1 — parse the version timeline
mod_dates = json.loads(row['ModifiedDate'])
# {'1': '2026-01-24T12:28Z', '2': '2026-01-25T08:53Z', ...}
n_versions = row['CurrentVersion']  # = 12
timeline = {int(v): parse_dt(ts) for v, ts in mod_dates.items()}

# Step 2 — get the value of any versioned column at version N
def get_at_version(json_str, version_n):
    d = json.loads(json_str)  # {'1': 'New', '7': 'Callback'}
    keys = [int(k) for k in d if int(k) <= version_n]  # largest key <= version_n
    if not keys:
        return None
    return d[str(max(keys))]

# Step 3 — walk every version to compute features incrementally
for v in range(1, n_versions + 1):
    ts = timeline[v]
    status = get_at_version(row['BaseLeadStatus'], v)
    contact = get_at_version(row['ContactRecords'], v)
    # compute features incrementally

# Step 4 — extract scalar fields (no version parsing needed)
tenant_id  = row['TenantId']
budget_low = row['LowerBudget'] or 0
budget_high= row['UpperBudget'] or 0
lead_source= row['LeadSource']
enq_for    = row['EnquiredFor']
nationality= row['Nationality']
currency   = row['Currency']
utm_source = row['UTMSource']
```

### 15E — Complete feature source map: all 60 features from this single table

This is the reconciliation between the 60-feature plan in [04-feature-engineering.md](04-feature-engineering.md) and what this specific table can actually deliver. `CLARIFY` rows are open questions blocking that feature's implementation.

| Feature | Field type | Column(s) in table | How to extract / derive |
|---|---|---|---|
| total_calls | Versioned | ContactRecords | COUNT versions where ContactRecords is not null/empty |
| answered_calls | Versioned | ContactRecords | COUNT versions where ContactRecords = 1 (answered) |
| disconnected_calls | Versioned | ContactRecords | COUNT versions where ContactRecords = 0 (not answered) |
| answer_rate | Derived | ContactRecords | answered_calls / total_calls |
| total_talk_time_sec | **CLARIFY** | LeadCallLog? Separate table? | Not in this table — ask CTO where call duration is stored |
| max_call_duration_sec | **CLARIFY** | LeadCallLog? Separate table? | Not in this table — ask CTO for the call-log table location |
| has_recording | **CLARIFY** | LeadCallLog? Separate table? | Not in this table — recording URL isn't visible in the 160 columns |
| avg_call_duration | **CLARIFY** | Separate call log table | Depends on resolving the call-log table question |
| calls_last_7_days | Versioned | ContactRecords + ModifiedDate | COUNT ContactRecords versions where ModifiedDate[v] >= now-7days |
| first_call_within_5min | Versioned | PickedDate[v2] vs ModifiedDate[1] | (PickedDate[v2] - ModifiedDate[1]).seconds <= 300 |
| lead_age_days | Scalar | CreatedDate or ModifiedDate["1"] | (scoring_date - ModifiedDate['1']).days |
| days_since_last_activity | Versioned | ModifiedDate | (scoring_date - ModifiedDate[str(CurrentVersion)]).days |
| hours_to_first_pick | Versioned | PickedDate + ModifiedDate | (first non-null PickedDate version timestamp - ModifiedDate['1']) / 3600 |
| active_days_count | Versioned | ModifiedDate | COUNT DISTINCT dates across all ModifiedDate version timestamps |
| activity_velocity | Derived | ModifiedDate version timestamps | versions_in_last_7d / versions_in_first_7d of lead life |
| days_since_last_call | Versioned | ContactRecords + ModifiedDate | (scoring_date - ModifiedDate[last ContactRecords version]).days |
| created_hour | Scalar | ModifiedDate["1"] + UserDetails.TZ | to_local_time(ModifiedDate['1']).hour via DateTimeExtensions |
| created_day_of_week | Scalar | ModifiedDate["1"] + UserDetails.TZ | to_local_time(ModifiedDate['1']).weekday() |
| recency_score | Derived | days_since_last_activity | exp(-0.1 × days_since_last_activity) |
| engagement_streak | Versioned | ModifiedDate version timestamps | Consecutive days with ≥1 version change, walking backwards from today |
| status_change_count | Versioned | BaseLeadStatus | COUNT keys in the BaseLeadStatus JSON dict |
| current_status_encoded ⚠ | Versioned | BaseLeadStatus + MasterLeadStatus | get_at_version(BaseLeadStatus, CurrentVersion) → OrderRank lookup. **Leakage risk:** OrderRank 8/9/10 are the same Booked/NotInterested/Dropped states the label in 15G is derived from — see the caution note in [04-feature-engineering.md](04-feature-engineering.md). Safe only if strictly cutoff-gated. |
| forward_status_moves | Versioned | BaseLeadStatus + MasterLeadStatus | Walk versions: count OrderRank(new) > OrderRank(old) |
| backward_status_moves | Versioned | BaseLeadStatus + MasterLeadStatus | Walk versions: count OrderRank(new) < OrderRank(old) |
| ever_reached_interested | Versioned | BaseLeadStatus | Any version where OrderRank >= 4 |
| ever_site_visit_done | Versioned | IsSiteVisitDone versioned bool | First version where IsSiteVisitDone = true |
| time_in_current_status | Versioned | BaseLeadStatus + ModifiedDate | (scoring_date - ModifiedDate[last status-change version]).days |
| status_progression_rate | Derived | forward_status_moves + lead_age_days | forward_status_moves / lead_age_days |
| last_status_was_positive | Versioned | BaseLeadStatus versions | OrderRank(last change newValue) > OrderRank(previous change oldValue) |
| status_regression_flag | Derived | backward_status_moves | 1 if backward_status_moves > 0 |
| human_touch_count | Versioned | LastModifiedByUser versioned JSON | COUNT versions where LastModifiedByUser is not System/Integration |
| system_event_count | Versioned | LastModifiedByUser versioned JSON | COUNT versions where LastModifiedByUser = 'System' |
| has_human_notes | Versioned | Notes + LastModifiedByUser | Any Notes version where the author is human and it's not an auto-note |
| note_count | Versioned | Notes + LastModifiedByUser | COUNT human-authored, non-empty, non-auto Note versions |
| note_length_avg | Versioned | Notes versioned JSON | AVG(len(Notes[v])) across human-authored note versions |
| channel_variety | Versioned | ContactRecords + LeadCallLog | Distinct contact channels used — **CLARIFY** ContactRecords encoding first |
| whatsapp_ever_used | **CLARIFY** | Not visible in 160 cols | Not seen in this table — may live only in LeadHistoryDto or a separate column |
| email_ever_used | **CLARIFY** | Not visible in 160 cols | Not seen — confirm with CTO if email contact is logged separately |
| visit_completed | Versioned | IsSiteVisitDone versioned bool | Any version where IsSiteVisitDone = true |
| human_reassign_count | Versioned | AssignedToUser + AssignedFromUser | COUNT versions where AssignedToUser changed and it isn't a routing storm |
| source_quality_tier | Scalar | LeadSource | Map LeadSource string → tier 1–5 after EDA (e.g. 'trehan' = direct builder) |
| budget_ever_set | Scalar | LowerBudget, UpperBudget | 1 if LowerBudget > 0 OR UpperBudget > 0 |
| budget_range_width | Scalar | UpperBudget - LowerBudget | float(UpperBudget) - float(LowerBudget); 0 if either null |
| budget_matches_project | Scalar+Join | LowerBudget/UpperBudget + Project | LowerBudget <= Project.MaximumPrice AND UpperBudget >= MinimumPrice |
| requirement_specificity | Scalar | BHKTypes, Projects, EnquiredLocation... | +1 for each of: BHK set, PropertyType, Location, Budget, Project, CarpetArea |
| location_specificity | Scalar | EnquiredCity, State, Location, Country | 0–4 score: +1 per geo level set |
| has_specific_project | Scalar | Projects (scalar array) | 1 if the Projects array is non-empty |
| bhk_is_specific | Scalar | BHKTypes (scalar array) | 1 if BHKTypes doesn't contain 'Others' and is non-empty |
| is_referral_source | Scalar | LeadSource, ReferralName, ReferralContactNo | 1 if any referral field is set OR LeadSource contains 'Referral' |
| is_channel_partner | Scalar | ChannelPartnerName, AgencyName, ChannelPartners | 1 if any channel-partner field is non-empty |
| tenant_id | Scalar | TenantId | Direct read; categorical-encode for XGBoost |
| is_re_enquiry | Scalar | IsIntegrationLead scalar bool | IsIntegrationLead = true → came via portal integration |
| source_changed_flag | Versioned | Not directly visible | **CLARIFY:** does LeadSource change get versioned, or is it scalar-only? |
| routing_instability | Versioned | AssignedToUser + ModifiedDate | >10 System assignment versions within any 60-minute window |
| lead_age_bucket | Derived | lead_age_days | 1=0-3d, 2=4-7d, 3=8-30d, 4=31-90d, 5=90+d |
| activity_per_day | Derived | human_touch_count / lead_age_days | Normalised engagement density |
| campaign_quality_tier | Scalar | Campaigns scalar + UTMCampaign | Pre-compute conversion rate per campaign after EDA → tier 1–5 |
| property_type_encoded | Scalar | SubPropertyType, BasePropertyType | Label-encode: Flat=1, Villa=2, Plot=3, Commercial=4 |
| is_nri_lead | Scalar | Nationality, Currency, EnquiredCountry | 1 if Currency in [USD,AED,GBP] OR Nationality is not Indian |
| enquiry_type_encoded | Scalar | EnquiredFor scalar array | Buy=1, Rent=2, Sale=3, Investment=4 — confirmed scalar column |

**Bottom line:** of the ~60 planned features, roughly 8 (`total_talk_time_sec`, `max_call_duration_sec`, `has_recording`, `avg_call_duration`, `channel_variety`, `whatsapp_ever_used`, `email_ever_used`, `source_changed_flag`) cannot be confirmed from this table alone and are blocked on the open questions below.

### 15F — Three open questions to confirm with the CTO before building the extraction pipeline

1. **`ContactRecords` encoding** — Sample shows `{"2":1, "3":0, "5":0, "6":0, "9":1}`. Is `1` = call answered / `0` = not answered? Or a different enum? Or does it encode channel type (call/whatsapp/visit)? This single answer determines how `total_calls`, `answered_calls`, and `channel_variety` are extracted.
2. **Call duration & direction (`LeadCallLog`)** — The 160-column table has no visible column for call duration, direction, or recording URL. That data appeared in `LeadHistoryDto` as strings like `'Outgoing Call → Answered → 33 sec.'`. Is there a separate CallLog table, a different column, or is it only reachable via the History API?
3. **`IsHotLead` / `IsColdLead` / `IsWarmLead` scalar flags** — Are these set manually by salespeople, or computed automatically by existing rules? If manual, they're a great validation baseline to compare the ML score against. If auto-rule-based, the team needs to understand those rules so the new model doesn't just re-learn (and get credited for) an existing heuristic.

### 15G — Label assignment directly from this table (no LeadHistoryDto needed)

| Positive class (label = 1, Converted) | Negative class (label = 0, Lost/Dropped) |
|---|---|
| `BookedDate` versioned JSON: any version has a non-null value **AND** `SoldPrice` scalar > 0 **AND** `BookedBy` scalar is a non-null UUID. | `BaseLeadStatus` versioned: latest version's value is Dropped / Not Interested / Wrong-Invalid-No. / Purchased From Others **OR** `IsArchived` versioned latest value = true. |
| Sample lead: `BookedDate={"1":null}` → label = None (open lead). | Sample lead: v11 `BaseLeadStatus='Dropped'` → label = 0 ✓ |

**Open lead (label = None — these are what the browser extension scores):** neither positive nor negative — `BookedDate` all null, latest `BaseLeadStatus` not a terminal negative state, and `IsArchived = false`. Never include these in training.

**`DataConverted` (ignore for labelling):** not actually a column in this 160-column table — it was a field on the static lead record meaning "record promoted from the Data/Prospect module to the Lead module." It is `true` for every row here, zero variance, and should be dropped completely. Reserve it for a future Phase-2 prospect-qualification model (see the note in [05-ml-model-training.md](05-ml-model-training.md)).

### Architecture summary (one table to rule them all)

160 columns · 1 row per lead · versioned JSON for behaviour · scalar for intent · walk versions 1→CurrentVersion using `ModifiedDate` timestamps · scalar fields (TenantId, Budget, Source, EnquiredFor, Nationality, UTM, Projects) are a direct read · 3 open questions remain: ContactRecords encoding, the call-duration table, and IsHotLead's origin.
