# Section 4 — Feature Engineering (+ Section 14 appendix)

**Depends on:** [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md) — every feature below is extracted from a column documented there; several rows are marked `CLARIFY` because that file's Section 15E flags them as unconfirmed in the real table. Also depends on that file's 3A Data Pipeline layer having already cleaned and deduplicated the raw rows.
**Feeds into:** [05-ml-model-training.md](05-ml-model-training.md), which trains on the 60-feature vector this section produces.

> This file merges board **Section 4** ("Feature Engineering: Raw Data → ML Input Vector") with board **Section 14** ("Feature Derivation Guide"). Section 4 is the *what* — a taxonomy of 60 features grouped by category. Section 14 is the *how* — the exact source field, parsing logic, and edge case for each one. Read Section 4's table for orientation, then Section 14 for the implementation recipe of any specific feature.

## What this section will do

This is where raw CRM history gets turned into a fixed-length numeric vector a model can actually train on. Every lead becomes one row of ~60 numbers, built by combining scalar lead fields with versioned-JSON columns walked version-by-version (per [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md)'s 15D). This section's job is to enumerate exactly which 60 numbers, group them by what kind of behaviour they capture, and — critically — document the leakage traps that would make an offline model look great and a production model fail.

**Evidence note:** the derivation logic in Part B (source field, parsing rule, edge case per feature) is **[Observed]** — read directly from the codebase, not assumed. The two features tagged EDA-pending below (`source_quality_tier`, `campaign_quality_tier`) are **[Hypothesis]** — their tier boundaries can't be set until conversion-rate analysis actually runs on the data. The leakage caution on `current_status_encoded` is now backed by a real **[Experiment]** finding, not just a theoretical concern — see below.

## Part A — Feature taxonomy (Section 4)

The 60 features are organized into six behavioural groups. Each group corresponds 1:1 to a `GROUP` in the Section 14 derivation guide below.

| Call Features (from ContactRecords) | Time Features (from ModifiedDate) | Status Features (from BaseLeadStatus) | Engagement Features (from ContactRecords/Notes) | Intent Features (from scalar fields) | Tenant/Contextual Features |
|---|---|---|---|---|---|
| total_calls: int | lead_age_days: int | status_change_count: int | human_touch_count: int | source_quality_tier: int 1-5 | tenant_id: category encoded |
| answered_calls: int | days_since_last_activity: int | current_status_encoded: int ⚠ | system_event_count: int | budget_ever_set: bool 0/1 | is_re_enquiry: bool 0/1 |
| disconnected_calls: int | hours_to_first_pick: float | forward_status_moves: int | has_human_notes: bool 0/1 | budget_range_width: float | source_changed_flag: bool |
| answer_rate: float 0-1 | active_days_count: int | backward_status_moves: int | note_count: int | budget_matches_project: bool | routing_instability: bool |
| total_talk_time_sec: int | activity_velocity: float | ever_reached_interested: bool | note_length_avg: float | requirement_specificity: int 0-5 | lead_age_bucket: int 1-5 |
| max_call_duration_sec: int | days_since_last_call: int | ever_site_visit_done: bool | channel_variety: int 1-4 | location_specificity: int 0-4 | activity_per_day: float |
| has_recording: bool 0/1 | created_day_of_week: int | time_in_current_status: int | whatsapp_ever_used: bool | has_specific_project: bool | campaign_quality_tier: int |
| avg_call_duration: float | created_hour: int | status_progression_rate: float | email_ever_used: bool | bhk_is_specific: bool | property_type_encoded: int |
| calls_last_7_days: int | recency_score: float 0-1 | last_status_was_positive: bool | visit_completed: bool | is_referral_source: bool | is_nri_lead: bool 0/1 |
| first_call_within_5min: bool | engagement_streak: int | status_regression_flag: bool | human_reassign_count: int | is_channel_partner: bool | enquiry_type_encoded: int |

### Leakage warning — never use as features

`SoldPrice` · `BookedDate` · `TotalBrokerage` · `NetBrokerageAmount` · `TokenType` · `PaymentMode` · `BookedUnderName` · `EarnedBrokerage` · `RemainingAmount`

These are all post-conversion outcomes. Using them as inputs means the model is being fed the answer — it will show excellent offline metrics and then fail in production, where these fields are empty for every lead being scored.

### ⚠ Leakage caution — `current_status_encoded` (marked ⚠ in the taxonomy table above)

`current_status_encoded` maps a lead's *latest* status to `MasterLeadStatus.OrderRank` (1–10, see the reference map below). The problem: OrderRank 8/9/10 are literally **Booked / Not Interested / Dropped** — the exact same three states the label in [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md)'s Section 15G is derived from. If this feature is snapshotted at or after the outcome, the model isn't learning a predictive signal, it's reading the label off a different column with extra steps — the classic "target leakage via a near-duplicate of the label" trap.

**Whether it's actually safe depends on two things, exactly as with any other conditional-leakage feature in this pipeline:**

1. **When it's captured.** It's only safe if it's extracted strictly before `feature_cutoff_ts`, using the same "time travel" discipline as Step 2 in [05-ml-model-training.md](05-ml-model-training.md). If the cutoff logic has a bug (or isn't applied consistently for this field), it silently becomes a leak.
2. **What values it can take at that cutoff.** Because scoring only ever runs on *open* leads (label=None per Section 15G), a lead being scored live can never actually be at OrderRank 8/9/10 — so in production the value is always non-terminal. The risk is specifically at **training time**: if the cutoff for a historical Booked/Dropped lead is applied even slightly late, the terminal status leaks in through this field even though every other feature was correctly time-bounded.

**Recommendation:** prefer the behavioural/progression features that already exist in this taxonomy over the raw terminal-status snapshot — they describe *how* a lead moved, not *where it ended up*, which is inherently harder to leak the label through:

- `status_change_count` (the board's version of "status transition count" — total versions recorded in `BaseLeadStatus`, forward + backward moves combined)
- `forward_status_moves`
- `backward_status_moves`
- `time_in_current_status`

If `current_status_encoded` is kept at all, treat it the same as the conditional-leakage fields noted in the older companion doc (`booked_flag`, `time_to_booked_hours`, `meeting_done_flag`, `site_visit_done_flag`): safe only if the version it's read at has `ModifiedDate[v] <= feature_cutoff_ts`, and worth a dedicated leakage-checklist test (train a model with it, confirm AUC doesn't jump implausibly, and check its SHAP importance isn't suspiciously dominant) before it ships.

**This is not a hypothetical risk; it already happened.** An early training pass included the lead's current status text (`BaseLeadStatus`/`current_status` — the same underlying signal `current_status_encoded` is built from, just categorical rather than OrderRank-encoded) as a feature, and it produced exactly the leakage pattern warned about above. It was caught, removed, and the field is now kept as a *display-only* field for the API/UI rather than a model input. Full experimental details (the AUC swing, SHAP feature-importance breakdown, and the fix) belong in separate evaluation records, not repeated here — this file's job is the standing rule the incident confirms, not the incident report itself.

### Correction — `DataConverted` is not a conversion signal

`DataConverted` means the record was promoted from the Data/Prospect module into the Lead module — it is `true` for every lead in the table and carries zero variance. Drop it from features entirely. The only valid conversion signals are `BookedDate` (versioned) + `SoldPrice > 0` (scalar) + `BookedBy` non-null (scalar) — see 15G — used as the **label**, never as an input feature. This same field is flagged as a *label candidate for a different, future model* in [05-ml-model-training.md](05-ml-model-training.md)'s Phase-2 note.

### Future evolution — a Feature Store (not on the original board, but worth flagging)

The current design computes these 60 features in **two separate places**: once offline in the training pipeline (Pandas, [05-ml-model-training.md](05-ml-model-training.md) Step 4), and again live in the "Feature Extractor" component inside the backend ([08-scoring-service-architecture.md](08-scoring-service-architecture.md)). That's two independent implementations of the same derivation logic in this file — e.g. `answer_rate = answered_calls / total_calls` has to be written and kept in sync twice. If those two implementations ever drift (a rounding difference, an edge-case fix applied to one but not the other, a timezone bug fixed only in the live path), the model sees different feature values at training time than at serving time — **training-serving skew** — and accuracy silently degrades in a way that's hard to detect because both paths still "work," they just disagree.

A **feature store** (e.g. Feast, Tecton, SageMaker Feature Store, or Vertex AI Feature Store) solves this by making the feature *definition* the single source of truth: one piece of derivation code, computed once, with an offline store for training (historical point-in-time correct joins) and an online store for serving (the sub-millisecond lookup the badge needs) reading from the same definitions. Today's Redis cache in [06-mlops.md](06-mlops.md) is a simple online store already — it just isn't backed by a shared definition layer yet.

**This is not a v1 requirement.** At 50,000 leads and ~60 features, keeping the two implementations manually in sync (with the shared feature-derivation table in this file as the spec both are built against) is manageable. It's worth planning for once feature count or team size grows — the tell is usually the first time a bug report says "the badge and the training notebook disagree on this lead's score."

## Part B — Section 14: the derivation guide (how each feature is actually calculated)

**Terminology note:** Section 14's original derivation guide was written under the *pre-Section-15* assumption — that the source was an event log (`LeadHistoryDto`, `fieldName`/`oldValue`/`newValue`, `updatedBy`, `auditActionType`) reached via an API. [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md)'s Section 15 corrected that: the real source is a 160-column **version-snapshot table** — versioned-JSON columns like `BaseLeadStatus` and `ContactRecords`, walked with `get_at_version()` (15D), not a stream of timestamped events. The tables below have been rewritten to match that model: every **Column(s) in table** entry names an actual versioned or scalar column from 15B, cross-referenced against 15E's per-feature mapping, rather than an event-log field that no longer describes the real schema.

### Feature implementation confidence

Every row in every GROUP table below carries a **Confidence** value, one of three tiers. This is a separate axis from **Type** (which just says whether the column is versioned, scalar, or derived) — Confidence says how much you should trust the derivation as written:

- **Confirmed** — the source column, encoding, and derivation are verified against the real 160-column schema (15A–15E). Safe to implement as written.
- **Placeholder** — the source column exists and the derivation pipeline is known, but one or more value encodings remain unconfirmed (for example, `ContactRecords`' 1/0 meaning, or which `LastModifiedByUser` values represent a human vs. a system actor — 15F Q1, and the actor-classification gap below). These features are computable today, but **should not be relied upon or shipped as validated** until the outstanding question is resolved — the number they produce today might mean something other than its name implies.
- **CLARIFY** — the required source data has not been located anywhere in the 160-column schema (15E/15F). Not derivable at all today, regardless of implementation effort, until that's resolved.

Confirmed answers baked into the derivation logic below:

- **Status ranks:** `MasterLeadStatus.OrderRank` is used directly — New=1, Pending=2, Callback=3, MeetingScheduled=4, SiteVisitScheduled=5, MeetingDone=6, VisitDone=7, Booked=8, NotInterested=9, Dropped=10. Children inherit their parent's rank (15B: `SubLeadStatus` maps to parent via this same OrderRank).
- **Budget–project join:** `LowerBudget (long) <= Project.MaximumPrice (double?)` AND `UpperBudget (long) <= Project.MinimumPrice`, casting both to float at query time — the one feature in this file that legitimately joins to a separate `Project` table rather than reading a column on the same row (15E: `budget_matches_project`, "Scalar+Join").
- **Timezone:** Priority 1 = `UserDetails.TimeZoneInfo`, Priority 2 = `CountryInfo.TimeZoneId`, Priority 3 = IST hardcoded fallback — gated by `GlobalSettings.IsTimeZoneEnabled`. Applied to `ModifiedDate['1']` (the versioned creation timestamp), not a separate `created_at` event.
- **Actor classification is an open gap, not a confirmed column.** Several groups below (originally Group 4's `updatedBy=human/System/Integration` split) assumed a clean actor-type field. 15B only confirms `LastModifiedByUser` (a versioned JSON of salesperson *names* per version) — there is no confirmed boolean "is this a System/Integration action" column. Rows that depend on this distinction are marked provisional below; resolving it is effectively a fourth open question alongside 15F's three.

### GROUP 1 — Call Features

*Source: the `ContactRecords` versioned column (15B). Call duration, direction, and recording URL are **not** visible anywhere in the 160-column table (15F Q2) — the four rows marked CLARIFY below are blocked on that open question, not derivable today regardless of implementation effort.*

| Feature | Confidence | Type | Column(s) in table | How to derive | Notes & edge cases |
|---|---|---|---|---|---|
| total_calls | Confirmed | Versioned | `ContactRecords` | COUNT versions where `ContactRecords` has any entry (value irrelevant) | Only needs an attempt to exist, not what its value means. Counts contact attempts across any channel, not calls specifically (15F Q1 hasn't confirmed `ContactRecords` is call-only). |
| answered_calls | **Placeholder** | Versioned | `ContactRecords` | COUNT versions where `ContactRecords` = 1, *if* 1 means "answered" | The value meaning is unconfirmed (15F Q1) — could instead mean a different outcome or channel entirely. Don't ship this as a validated "answered calls" count yet. |
| disconnected_calls | **Placeholder** | Versioned | `ContactRecords` | COUNT versions where `ContactRecords` = 0, *if* 0 means "not answered" | Same unconfirmed assumption as `answered_calls` (15F Q1). |
| answer_rate | **Placeholder** | Derived | answered_calls / total_calls | Same; if total_calls = 0 → set 0.0 | Inherits `answered_calls`'s open question — only meaningful once 15F Q1 resolves. |
| total_talk_time_sec | **CLARIFY** | — | Not in this table | Not derivable — call duration isn't a visible column in the 160-column table (15F Q2: separate CallLog table?) | Do not implement against `ContactRecords`; it has no duration field. |
| max_call_duration_sec | **CLARIFY** | — | Not in this table | Same blocker as `total_talk_time_sec`. | |
| has_recording | **CLARIFY** | — | Not in this table | Recording URL isn't visible in the 160 columns — blocked on 15F Q2. | |
| avg_call_duration | **CLARIFY** | — | Depends on total_talk_time_sec | Blocked until the call-log-table question in 15F Q2 resolves. | |
| calls_last_7_days | Confirmed | Versioned | `ContactRecords` + `ModifiedDate` | COUNT `ContactRecords` versions where `ModifiedDate[v]` >= (scoring_date - 7 days) | Walk both dicts together by matching version key — see 15D's `get_at_version()` pattern. |
| first_call_within_5min | Confirmed | Versioned | `PickedDate` + `ModifiedDate` | 1 if (first non-null `PickedDate` version timestamp − `ModifiedDate['1']`) <= 300 seconds | `ModifiedDate['1']` is the lead-creation timestamp (15A) — there is no separate "Created" event to anchor to. |

### GROUP 2 — Time Features

*Source: the `ModifiedDate` versioned column — the timeline key for every other versioned field in the table (15A) — plus `PickedDate` and `CurrentVersion`.*

| Feature | Confidence | Type | Column(s) in table | How to derive | Notes & edge cases |
|---|---|---|---|---|---|
| lead_age_days | Confirmed | Scalar/Versioned | `CreatedDate` or `ModifiedDate['1']` | (scoring_date − `ModifiedDate['1']`).days | `ModifiedDate['1']` is more precise than the scalar `CreatedDate` (15E) — prefer it. |
| days_since_last_activity | Confirmed | Versioned | `ModifiedDate` | (scoring_date − `ModifiedDate[str(CurrentVersion)]`).days | Includes every version, not just human-driven ones — there's no confirmed actor-type column to filter by (see the actor-classification note above), but the feature as specified doesn't need that filter to be valid. |
| hours_to_first_pick | Confirmed | Versioned | `PickedDate` + `ModifiedDate` | (first non-null `PickedDate` version timestamp − `ModifiedDate['1']`) / 3600 | 9999.0 if `PickedDate` never sets across any version. < 0.083 hrs (5 min) = very hot signal. |
| active_days_count | Confirmed | Versioned | `ModifiedDate` | COUNT(DISTINCT date) across all `ModifiedDate` version timestamps | Calendar days with any version change — spread across history implies an engaged lead. |
| activity_velocity | Confirmed | Derived | `ModifiedDate` version timestamps | versions_in_last_7d / versions_in_first_7d of the lead's life | > 1.0 = accelerating (warming up). < 1.0 = slowing down. |
| days_since_last_call | Confirmed | Versioned | `ContactRecords` + `ModifiedDate` | (scoring_date − `ModifiedDate`[last `ContactRecords` version]).days | 999 if no `ContactRecords` version exists at all. Only needs an entry to exist, same as `total_calls`. |
| created_day_of_week | Confirmed | Scalar/Versioned | `ModifiedDate['1']` + `UserDetails.TZ` | to_local_time(`ModifiedDate['1']`).weekday(), 0=Mon..6=Sun | Gated by `GlobalSettings.IsTimeZoneEnabled`. Fallback: IST. |
| created_hour | Confirmed | Scalar/Versioned | `ModifiedDate['1']` + `UserDetails.TZ` | to_local_time(`ModifiedDate['1']`).hour; priority `UserDetails.TimeZoneInfo` → `CountryInfo.TimeZoneId` → IST | A 22:00 IST lead has a different conversion pattern than a 10:00 one. |
| recency_score | Confirmed | Derived | days_since_last_activity | math.exp(-0.1 × days_since_last_activity) — decay formula, 1.0 if active today | Approaches 0 as the lead goes stale. |
| engagement_streak | Confirmed | Versioned | `ModifiedDate` version timestamps | Consecutive calendar days with ≥1 version change, counting backwards from scoring_date | As specified, this counts *any* version change, not just human-driven ones — there's no confirmed actor-type column to narrow it further (see the actor-classification note above), but that's a scope note, not a blocker. |

### GROUP 3 — Status Features

*Source: the `BaseLeadStatus` versioned column (+ `SubLeadStatus` for child status), mapped through `MasterLeadStatus.OrderRank` (15B).*

| Feature | Confidence | Type | Column(s) in table | How to derive | Notes & edge cases |
|---|---|---|---|---|---|
| status_change_count | Confirmed | Versioned | `BaseLeadStatus` | COUNT keys in the `BaseLeadStatus` JSON dict | Both forward and backward moves counted. High count with no forward progress = churning. |
| current_status_encoded ⚠ | Confirmed | Versioned | `BaseLeadStatus` + `MasterLeadStatus` | `get_at_version(BaseLeadStatus, CurrentVersion)` → OrderRank lookup (New=1 ... Dropped=10) | Data-wise this is Confirmed (column and encoding both exist) — its ⚠ is a separate **leakage** concern, not a data-availability one. OrderRank 8/9/10 *are* the label states (Booked/NotInterested/Dropped); see the caution note in Part A. Only safe if strictly cutoff-gated. |
| forward_status_moves | Confirmed | Versioned | `BaseLeadStatus` + `MasterLeadStatus` | Walk versions in order: count transitions where OrderRank(new) > OrderRank(old) | Requires the OrderRank map (see Reference table below). |
| backward_status_moves | Confirmed | Versioned | `BaseLeadStatus` + `MasterLeadStatus` | Walk versions in order: count transitions where OrderRank(new) < OrderRank(old) | Any backward move is a negative signal. New→Pending then Pending→New = 1 backward move. |
| ever_reached_interested | Confirmed | Versioned | `BaseLeadStatus` | 1 if any version has OrderRank >= 4 (Meeting Scheduled or later) | OrderRank 4=MeetingScheduled, 5=SiteVisitSched, 6=MeetingDone, 7=VisitDone, 8=Booked. |
| ever_site_visit_done | Confirmed | Versioned | `IsSiteVisitDone` | 1 if any version of `IsSiteVisitDone` is true | The old "OR Contact Records = 'Visit'" fallback path is dropped here — `ContactRecords`' channel type isn't a confirmed encoding (15F Q1), so `IsSiteVisitDone` is the one reliable, Confirmed source. |
| time_in_current_status | Confirmed | Versioned | `BaseLeadStatus` + `ModifiedDate` | (scoring_date − `ModifiedDate`[last status-change version]).days | Long time in a low-rank status = stalling. Long time in a high-rank status = close to booking. |
| status_progression_rate | Confirmed | Derived | forward_status_moves / lead_age_days | Same; if lead_age_days = 0 → set 0.0 | Normalises progression speed by lead age. |
| last_status_was_positive | Confirmed | Versioned | `BaseLeadStatus` | 1 if OrderRank(latest version) > OrderRank(previous version) | If only 1 status version exists: 1 if rank > 1. If the dict is empty: 0. |
| status_regression_flag | Confirmed | Derived | backward_status_moves | 1 if backward_status_moves > 0 at any point in the lead's history | One-time flag — never resets once tripped. |

### GROUP 4 — Engagement Features

*Source: `ContactRecords`, `Notes`, `AssignedToUser`/`AssignedFromUser`, and `LastModifiedByUser` versioned columns (15B). Every "human vs. System" distinction below inherits the actor-classification gap flagged above — `LastModifiedByUser` gives a salesperson **name** per version, not a confirmed System/Integration/Human enum, so "is this a real person" is a name-pattern heuristic, not a guaranteed field.*

| Feature | Confidence | Type | Column(s) in table | How to derive | Notes & edge cases |
|---|---|---|---|---|---|
| human_touch_count | **Placeholder** | Versioned | `LastModifiedByUser` | COUNT versions where `LastModifiedByUser` is a real person's name (not 'System' or blank) | The column exists and names are readable, but "is this name a human vs. a system label" is a pattern heuristic, not a confirmed enum — see the actor-classification note above. Otherwise the single most important feature. |
| system_event_count | **Placeholder** | Versioned | `LastModifiedByUser` | COUNT versions where `LastModifiedByUser` = 'System' exactly | Same actor-classification caveat as `human_touch_count`. |
| has_human_notes | **Placeholder** | Versioned | `Notes` + `LastModifiedByUser` | 1 if any `Notes` version has a human-pattern author AND doesn't start with 'Re-Enquired From' | Inherits the actor-classification caveat via the author check. Auto-notes from portals start with 'Re-Enquired From Housing' — exclude these regardless. |
| note_count | **Placeholder** | Versioned | `Notes` + `LastModifiedByUser` | COUNT `Notes` versions with a human-pattern author, excluding portal auto-notes | Same exclusion and caveat as has_human_notes. |
| note_length_avg | **Placeholder** | Versioned | `Notes` | AVG(len(value)) across human-authored `Notes` versions | Inherits the same author-detection caveat — "human-authored" is a pattern match. 0.0 if no human notes at all. |
| channel_variety | **CLARIFY** | — | `ContactRecords` | Blocked — `ContactRecords`' channel-type encoding (Call/WhatsApp/Email/Visit) isn't confirmed (15F Q1); the column may only encode a 0/1 answered flag, not channel identity. | Do not implement a 4-channel count against `ContactRecords` until 15F Q1 resolves. |
| whatsapp_ever_used | **CLARIFY** | — | Not visible in 160 cols | Not seen in this table — may not be captured anywhere in this schema (15E/15F). | |
| email_ever_used | **CLARIFY** | — | Not visible in 160 cols | Same as above. | |
| visit_completed | Confirmed | Versioned | `IsSiteVisitDone` | 1 if any version of `IsSiteVisitDone` is true | Same column and same Confirmed status as `ever_site_visit_done` in Group 3 — the two features are currently identical pending a distinct signal. |
| human_reassign_count | **Placeholder** | Versioned | `AssignedToUser` + `AssignedFromUser` | COUNT versions where `AssignedToUser` changed to a human-pattern name, deduplicating 5+ changes within 10 minutes as 1 | Inherits the actor-classification caveat. Burst dedup removes routing-storm noise regardless (see the Assignment Storm row in Part A's data-quality table). |

### GROUP 5 — Intent Features

*Source: scalar columns on the same 160-column lead row — `LowerBudget`, `UpperBudget`, `Projects`, `BHKTypes`, `EnquiredFor`, `LeadSource`, etc. (15B) — not a separate `LeadEnquiry`/`LeadFilter` entity. `budget_matches_project` is the one exception that legitimately joins to a separate `Project` table.*

| Feature | Confidence | Type | Column(s) in table | How to derive | Notes & edge cases |
|---|---|---|---|---|---|
| source_quality_tier | Confirmed* | Scalar + EDA | `LeadSource` | Pre-compute conversion rate per source from historical data → rank 1–5 | *The column and its raw values are Confirmed (15B); the tier *mapping* is a business-tuning decision, not a data-confidence question — see the [Hypothesis] evidence note at the top of this file. Requires EDA first. Placeholder value = 3 until then. |
| budget_ever_set | Confirmed | Scalar | `LowerBudget`, `UpperBudget` | 1 if `LowerBudget` > 0 OR `UpperBudget` > 0 | Budget set = the lead has researched prices — a strong intent signal vs. zero budget. |
| budget_range_width | Confirmed | Scalar | `UpperBudget`, `LowerBudget` | float(`UpperBudget`) − float(`LowerBudget`); cast long → float; 0.0 if either is null | Narrow range = a decisive buyer. Wide range = still browsing. |
| budget_matches_project | Confirmed | Scalar + Join | `LowerBudget`/`UpperBudget` + `Project` table | Confirmed join: `LowerBudget` <= `Project.MaximumPrice` AND `UpperBudget` >= `Project.MinimumPrice`, casting to float | The one feature here that reaches outside the 160-column row. Watch the long/double type mismatch. |
| requirement_specificity | Confirmed | Scalar | `BHKTypes`, `NoOfBHK`, `BasePropertyType`, `Projects`, `EnquiredLocation`, `CarpetArea` | +1 each for: BHK set (not 'Others'), PropertyType set, Location set, Budget set, non-empty Projects list, CarpetArea > 0 | Score 0–5. Higher = the buyer knows exactly what they want. |
| location_specificity | Confirmed | Scalar | `EnquiredCountry`, `EnquiredState`, `EnquiredCity`, `EnquiredLocation` | +1 per geo level set | 0 = no location preference stated. 4 = country+state+city+locality all set. |
| has_specific_project | Confirmed | Scalar | `Projects` (scalar array) | 1 if `Projects` array is non-empty | A named project implies the buyer visited a site or saw an ad for it specifically. |
| bhk_is_specific | Confirmed | Scalar | `BHKTypes` (scalar array) | 1 if `BHKTypes` doesn't contain 'Others' and is non-empty | 'Others' = vague. '2BHK' = specific. |
| is_referral_source | Confirmed | Scalar | `LeadSource`, `ReferralName`, `ReferralContactNo` | 1 if any referral field is set OR `LeadSource` contains 'Referral' | Referral leads convert 3–5× better — gives the highest source_quality_tier. |
| is_channel_partner | Confirmed | Scalar | `AgencyName`, `ChannelPartnerName`, `ChannelPartners` | 1 if any channel-partner field is non-empty | CP leads have a different conversion journey — consider a separate model segment in v2. |

### GROUP 6 — Tenant / Contextual Features

*Source: scalar columns (`TenantId`, `IsIntegrationLead`) plus versioned columns already covered above, reused for a tenant/context lens.*

| Feature | Confidence | Type | Column(s) in table | How to derive | Notes & edge cases |
|---|---|---|---|---|---|
| tenant_id | Confirmed | Scalar | `TenantId` | Direct read; categorical-encode for XGBoost | Lets the model learn tenant-specific patterns without separate models. |
| is_re_enquiry | Confirmed | Scalar | `IsIntegrationLead` | 1 if `IsIntegrationLead` = true | Portal re-enquiry (Housing.com etc.) merges into the existing lead — a strong positive signal that the lead searched again. |
| source_changed_flag | **CLARIFY** | — | Not directly visible | Blocked — unconfirmed whether a `LeadSource` change is versioned at all, or only ever stored as the single current scalar value (15E/15F). | Do not assume a versioned history exists for `LeadSource` until this resolves. |
| routing_instability | **Placeholder** | Versioned | `AssignedToUser` + `ModifiedDate` | 1 if >10 `AssignedToUser` version changes fall within any 60-minute window | The change-count itself is Confirmed-derivable, but whether those reassigns are System-driven (vs. legitimate human reassignment) is provisional pending the actor-classification gap above — hence Placeholder overall. Real example seen in this data: 90+ reassigns in 98 minutes (see Part A's Assignment Storm row). |
| lead_age_bucket | Confirmed | Derived | lead_age_days | 1=0–3 days, 2=4–7 days, 3=8–30 days, 4=31–90 days, 5=90+ days | Buckets handle non-linear age effects. |
| activity_per_day | **Placeholder** | Derived | human_touch_count / lead_age_days | Same; if lead_age_days = 0 → use human_touch_count | Inherits Group 4's actor-classification caveat via human_touch_count. |
| campaign_quality_tier | Confirmed* | Scalar + EDA | `Campaigns`, `UTMCampaign` | Pre-compute conversion rate per campaign from EDA → tier 1–5; no history → tier 3 (neutral default) | *Same caveat as `source_quality_tier` — column Confirmed, tier mapping is EDA-pending, not a data-confidence gap. |
| property_type_encoded | Confirmed | Scalar | `SubPropertyType` (primary), `BasePropertyType` (fallback) | Map to integer: ResidentialFlat=1, Villa=2, Plot=3, Commercial=4, Office=5 | Unknown/missing → 0. One-hot encode if cardinality is below 10 types. |
| is_nri_lead | Confirmed | Scalar | `Nationality`, `Currency`, `EnquiredCountry` | 1 if `Currency` IN [USD,AED,GBP,EUR] OR `Nationality` is not Indian | NRI leads follow a different journey — needs a separate scoring track in v2. |
| enquiry_type_encoded | Confirmed | Scalar | `EnquiredFor` (scalar array) | Map the first value: Buy=1, Rent=2, Sale=3, Investment=4 | Buy intent converts at 3× the rate of Rent — a strong prior before any engagement is even observed. |

### Reference — MasterLeadStatus order-rank map

*From `MasterLeadStatusSeeds.json` + `MasterLeadStatus.cs`'s `OrderRank` field. Parent statuses drive the progression chain; child statuses inherit their parent's rank.*

| OrderRank | Status Name | Meaning for ML | Terminal? |
|---|---|---|---|
| 1 | New | Entry point — lead just created | No |
| 2 | Pending | Assigned, not yet contacted | No |
| 3 | Callback | Contact attempted, callback needed | No |
| 4 | Meeting Scheduled | Meeting date confirmed with lead | No |
| 5 | Site Visit Scheduled | Site visit date confirmed | No |
| 6 | Meeting Done | Meeting completed | No |
| 7 | Visit Done | Site visit completed — strongest pre-book signal | No |
| 8 | Booked | **LABEL = 1** (positive class for training) | Yes (positive) |
| 9 | Not Interested | **LABEL = 0** (negative class for training) | Yes (negative) |
| 10 | Dropped | **LABEL = 0** (negative class for training) | Yes (negative) |

Selected child statuses and the parent rank they inherit: Not Answered / Busy / Not Reachable / Need More Info / To Schedule A Meeting / To Schedule Site Visit → inherit **Callback (3)**. Unmatched Budget / Different Location / Different Requirements / Plan Postponed → inherit **Not Interested (9)**. Wrong/Invalid No. / Purchased From Others → inherit **Dropped (10)**.

### Label assignment rule (as used by the derivation guide)

Restated here in the same versioned-column terms as 15G, not the event-log field names (`BookedByIds`/`ArchivedByIds`) an earlier draft of this section used — those aren't confirmed columns in the real table:

- **Positive class (label=1):** `BookedDate` versioned JSON has a non-null value at any version, AND `SoldPrice` scalar > 0, AND `BookedBy` scalar is a non-null UUID.
- **Negative class (label=0):** `BaseLeadStatus` versioned latest value is Dropped / Not Interested / Wrong-Invalid-No. / Purchased From Others, OR `IsArchived` versioned latest value is true.
- **Open lead (label=None):** neither of the above — these are scored, not trained on.

This is the same schema-level label rule from [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md)'s Section 15G, restated here for convenience — that file is the source of truth if the two ever drift. `DataConverted` is true for every lead and zero-variance — never use it as a label or feature; it's reserved for a future Phase-2 prospect-qualification model.
