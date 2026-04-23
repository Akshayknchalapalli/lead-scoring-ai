# Lead Intelligence Platform - Detailed Blueprint

This is the detailed text companion to `docs/lead_ai_score_docs.excalidraw`.
It mirrors the same sections and adds implementation-level detail for Data, ML, Backend, Product, and QA.

---

## SECTION 1 - PROBLEM STATEMENT

### Business Context
- Data scale: ~1,00,000 leads across 3-4 tenants.
- Typical conversion baseline: ~3-8%.
- Current pain: leads are not consistently prioritized.
- Sales reps waste cycles on low-intent leads.

### Why this matters
- Better prioritization increases call-to-meeting rate.
- Faster follow-up improves conversion.
- Tenant stickiness improves with measurable lift.

### Target Product Outcome
- Real-time lead scoring (`Hot/Warm/Cold`) on CRM UI.
- Actionable guidance on-demand.
- Multi-tenant, low-cost, high-margin add-on capability.

---

## SECTION 2 - REQUIREMENTS & USE CASES

### Functional Requirements
- FR1: Auto-score all open leads as Hot/Warm/Cold.
- FR2: Recompute scores in real-time when lead history changes.
- FR3: Tenant isolation in data + scoring behavior.
- FR4: Explain score on-demand.
- FR5: Suggest next best action.
- FR6: Browser extension integration; no deep CRM rewrite.
- FR7: Tenant-level enable/disable toggle.
- FR8: Scale for 1L+ leads with fast rendering.

### Non-Functional Requirements
- NFR1: Inference latency target under 2ms/lead.
- NFR2: Badge render target under 500ms (cache path).
- NFR3: AUC target > 0.80.
- NFR4: 99.9% API uptime.
- NFR5: Zero cross-tenant leakage.
- NFR6: Privacy/compliance guardrails for LLM calls.
- NFR7: Horizontal scale for 10x growth.
- NFR8: Monthly retrain with safe deployment.

### Core Use Cases
- UC1 Rep sees hot leads first and acts faster.
- UC2 Manager sees team-wise quality distribution.
- UC3 Admin enables/disables scoring.
- UC4 Re-enquiry triggers score refresh quickly.
- UC5 New tenant gets day-1 scores.
- UC6 Rep clicks “Why?” to get explanation and next action.

---

## SECTION 3 - DATA ARCHITECTURE (WHAT WE HAVE / WHAT WE BUILD)

### Existing Data Sources
- `LeadHistories`
- `LeadCallLogs`
- `IVRCallLogs`
- `ServetelCallLogs`
- `Leads`

### Build Layer
- Unified event normalization.
- Tenant-scoped feature extraction keyed by `tenant_id + lead_id`.
- Time-bounded snapshots for scoring.
- Score-serving cache and model version metadata.

### CSV Reality (Important Clarification)

This blueprint output is **not from one CSV**.  
It is built from **two CSV files**:

1) **Scoring/Feature CSV** (derived features + label/eval fields)  
2) **LeadHistory Raw CSV** (full raw history column set used for feature derivation and audits)

The two files are merged using:

- `tenant_id` + `lead_id` (feature CSV)
- `TenantId` + `LeadId` (LeadHistory CSV)

### Top signal families from blueprint
- LeadCallLog outcomes + durations + recordings.
- Lead status progression sequence.
- Contact channel behavior.
- Picked-date urgency.
- Source quality and campaign quality.
- Budget/project specificity.

---

## SECTION 4 - FEATURE ENGINEERING (RAW -> ML VECTOR)

### Source CSV #1 - Derived Scoring/Feature Header

```text
tenant_id,lead_id,total_calls_from_logs,calls_with_duration,total_talk_time_sec,max_call_duration_sec,avg_call_duration_sec,has_recording,contact_events_total,call_events,whatsapp_events,email_events,channel_variety,whatsapp_ever_used,email_ever_used,source_changed_flag,enquiry_type_variety,total_calls_for_status,answered_calls,disconnected_calls,answer_rate,first_contact_at,last_contact_at,contact_span_hours,recency_days,response_time_sec,meeting_done_flag,site_visit_done_flag,booked_flag,time_to_meeting_hours,time_to_site_visit_hours,time_to_booked_hours,lead_stage_progression_score,agent_assigned_latest,agent_total_assigned_leads,agent_total_converted_leads,agent_conversion_rate,first_action_type,second_action_type,third_action_type,call_then_whatsapp_flag,whatsapp_then_meeting_flag,call_then_meeting_flag,call_whatsapp_meeting_pattern_flag,time_between_action1_action2_sec,events_in_first_48h,lead_source_value,utm_source_value,source_conversion_rate,utm_source_conversion_rate,campaign_quality_score,lead_created_at,feature_cutoff_ts,converted_label,first_booked_at
```

### Source CSV #2 - LeadHistory Raw Header

```text
Id,CreatedDate,ModifiedDate,AssignedTo,AssignmentType,IsDeleted,CreatedBy,LastModifiedBy,EnquiredFor,SaleType,BasePropertyType,SubPropertyType,BHKType,NoOfBHK,Name,Email,ContactNo,LowerBudget,UpperBudget,Area,AreaUnit,Notes,EnquiredCity,EnquiredState,EnquiredLocation,LeadSource,Rating,BaseLeadStatus,SubLeadStatus,ScheduledDate,LeadNumber,ChosenProject,ChosenProperty,BookedUnderName,RevertDate,SoldPrice,IsHighlighted,IsEscalated,IsAboutToConvert,IsIntegrationLead,ShareCount,IsHotLead,CurrentVersion,TenantId,AssignedToUser,AssignedFromUser,ContactRecords,IsColdLead,IsWarmLead,Documents,LastModifiedByUser,IsMeetingDone,IsSiteVisitDone,MeetingLocation,SiteLocation,IsArchived,Projects,Properties,ArchivedBy,ArchivedDate,RestoredBy,RestoredDate,SubSource,ReferralContactNo,ReferralName,AgencyName,CompanyName,CarpetArea,PossessionDate,CarpetAreaUnit,ConversionFactor,AlternateContactNo,ChildLeadsCount,DuplicateLeadVersion,LeadId,UserId,CustomerLocation,ClosingManager,CustomerState,Profession,SourcingManager,SourcingManagerUser,ChannelPartnerContactNo,ChannelPartnerExecutiveName,ChannelPartnerName,ClosingManagerUser,CustomerCity,ChannelPartners,ConfidentialNotes,PickedDate,IsPicked,SecondaryUser,SecondaryUserId,BookedDate,BookedBy,BookedByUser,CustomFlags,UploadType,UploadTypeName,BHKTypes,BHKs,EnquiredCities,EnquiredLocations,EnquiredStates,EnquiryTypes,Agencies,LeadAssignmentType,Designation,BulkCategory,SecondaryFromUser,Links,Baths,Beds,EnquiredCommunity,EnquiredSubCommunity,EnquiredTowerName,Floors,Furnished,OfferType,BuiltUpArea,BuiltUpAreaConversionFactor,BuiltUpAreaUnit,SaleableArea,SaleableAreaConversionFactor,SaleableAreaUnit,ReferralEmail,CustomerCommunity,CustomerCountry,CustomerSubCommunity,CustomerTowerName,EnquiredCountry,Currency,NetArea,NetAreaConversionFactor,NetAreaUnit,PropertyArea,PropertyAreaConversionFactor,PropertyAreaUnit,UnitName,ClusterName,Nationality,Campaigns,Purpose,PossesionType,LandLine,DateOfBirth,Gender,MaritalStatus,AppointmentDoneOn,AnniversaryDate,UnitTypes,Buyer,PaymentPlans,UTMCampaign,UTMContent,UTMId,UTMMedium,UTMSource,UTMTerm,UTMURL
```

Note: Source CSV #2 is raw history inventory and should not be treated as direct model-ready features without transformation and leakage controls.

### Feature Taxonomy

#### A) Call Interaction Features
- `total_calls_from_logs`
- `calls_with_duration`
- `total_talk_time_sec`
- `max_call_duration_sec`
- `avg_call_duration_sec`
- `has_recording`
- `answered_calls`, `disconnected_calls`, `answer_rate`

#### B) Contact Channel Features
- `contact_events_total`
- `call_events`, `whatsapp_events`, `email_events`
- `channel_variety`
- `whatsapp_ever_used`, `email_ever_used`

#### C) Time Behavior Features
- `first_contact_at`, `last_contact_at`
- `contact_span_hours`
- `recency_days`
- `response_time_sec`

#### D) Funnel Features
- `meeting_done_flag`
- `site_visit_done_flag`
- `booked_flag`
- `time_to_meeting_hours`
- `time_to_site_visit_hours`
- `time_to_booked_hours`
- `lead_stage_progression_score`

#### E) Agent/Assignment Features
- `agent_assigned_latest`
- `agent_total_assigned_leads`
- `agent_total_converted_leads`
- `agent_conversion_rate`

#### F) Sequence Features
- `first_action_type`, `second_action_type`, `third_action_type`
- `call_then_whatsapp_flag`
- `whatsapp_then_meeting_flag`
- `call_then_meeting_flag`
- `call_whatsapp_meeting_pattern_flag`
- `time_between_action1_action2_sec`
- `events_in_first_48h`

#### G) Source Quality Features
- `lead_source_value`, `utm_source_value`
- `source_conversion_rate`
- `utm_source_conversion_rate`
- `campaign_quality_score`

#### H) Label/Evaluation Fields
- `converted_label` (target only)
- `first_booked_at` (evaluation context)

### I) Raw Source Coverage (LeadHistories 160 columns)

Feature taxonomy above is derived output. Raw table coverage is explicit below:

| Raw Column Group | Example Columns | Feature Group Mapping | Status |
|---|---|---|---|
| Identity/Contact | `Name`, `Email`, `ContactNo`, `AlternateContactNo` | data quality + context | selective |
| Status/Journey | `BaseLeadStatus`, `SubLeadStatus`, `CurrentVersion` | status + sequence + time | used now |
| Assignment | `AssignedTo`, `AssignedToUser`, `ClosingManager` | agent features | used now |
| Engagement | `ContactRecords`, `Notes`, `ConfidentialNotes` | contact + engagement + future NLP | used now / phase 2 |
| Funnel | `IsMeetingDone`, `IsSiteVisitDone`, `BookedDate` | funnel features | cutoff-conditional |
| Outcome | `SoldPrice`, `BookedDate`, `BookedBy` | labels/evaluation only | leakage-sensitive |
| Intent | `EnquiryTypes`, `LeadSource`, `SubSource`, `Purpose` | intent + source quality | used now |
| Budget/Fit | `LowerBudget`, `UpperBudget`, area fields | intent fit features | used now |
| Attribution | `UTMSource`, `UTMMedium`, `UTMCampaign` | campaign quality features | used now |
| Tenant Controls | `TenantId`, `IsDeleted` | filtering/partitioning | used now |

### J) LeadHistory Segregation by Taxonomy Sections

This is the same section-wise segregation style, but explicitly for `LeadHistories` raw fields.

#### J1) LeadHistory -> A. Call Interaction Features

Primary raw columns:

- `ContactRecords` (channel events)
- `ModifiedDate` (event timing anchor by version)
- `Notes` / `ConfidentialNotes` (contains communication context in some flows)
- `PickedDate`, `IsPicked` (first-contact/response-adjacent urgency)

Derived examples:

- call count proxies, channel mix, response-time approximations
- call activity windows when joined with call-log tables

#### J2) LeadHistory -> B. Contact Channel Features

Primary raw columns:

- `ContactRecords`
- `Notes`
- `ConfidentialNotes`
- `Documents` (engagement artifact)

Derived examples:

- `contact_events_total`, `call_events`, `whatsapp_events`, `email_events`
- `channel_variety`, channel-ever-used flags

#### J3) LeadHistory -> C. Time Behavior Features

Primary raw columns:

- `CreatedDate`
- `ModifiedDate`
- `PickedDate`
- `CurrentVersion`

Derived examples:

- lead age, recency, time since last activity, time to first pick
- event-gap and cadence features

#### J4) LeadHistory -> D. Funnel Features

Primary raw columns:

- `IsMeetingDone`
- `IsSiteVisitDone`
- `MeetingLocation`
- `SiteLocation`
- `BookedDate`
- `BookedBy`
- `BookedByUser`

Derived examples:

- stage completion flags
- stage progression score
- stage elapsed-time metrics

Leakage note:

- `BookedDate`-based derivatives are target-side / leakage-sensitive unless strictly cutoff-bounded.

#### J5) LeadHistory -> E. Agent/Assignment Features

Primary raw columns:

- `AssignedTo`
- `AssignedToUser`
- `AssignedFromUser`
- `ClosingManager`
- `ClosingManagerUser`
- `SourcingManager`
- `SourcingManagerUser`
- `SecondaryUserId`
- `SecondaryUser`
- `SecondaryFromUser`

Derived examples:

- latest assigned owner
- reassignment frequency and assignment stability
- downstream agent-conversion aggregate joins

#### J6) LeadHistory -> F. Sequence Features

Primary raw columns:

- `ModifiedDate` (event ordering backbone)
- `ContactRecords`
- `BaseLeadStatus`, `SubLeadStatus`
- `IsMeetingDone`, `IsSiteVisitDone`
- `LeadSource` updates

Derived examples:

- first/second/third action type
- transition patterns (call -> whatsapp -> meeting etc.)
- action spacing and short-horizon event density

#### J7) LeadHistory -> G. Source Quality Features

Primary raw columns:

- `LeadSource`
- `SubSource`
- `UTMSource`, `UTMMedium`, `UTMCampaign`, `UTMContent`, `UTMTerm`, `UTMId`, `UTMURL`
- `Campaigns`

Derived examples:

- source conversion rates
- campaign quality score/tier
- source-flip reliability flags

#### J8) LeadHistory -> H. Label/Evaluation Fields

Primary raw columns:

- `BookedDate`
- `SoldPrice`
- `BookedBy`
- `BookedByUser`
- `BookedUnderName`

Derived examples:

- `converted_label`
- conversion timestamp anchors for evaluation

Strict rule:

- Keep these fields out of training input features unless explicitly used as labels/evaluation-only metadata.

#### J9) Additional LeadHistory Context Columns (Used Selectively)

Intent and profile:

- `EnquiryTypes`, `EnquiredFor`, `Purpose`, `Buyer`, `Profession`, `Nationality`

Budget/fit:

- `LowerBudget`, `UpperBudget`, `Area`, `CarpetArea`, `BuiltUpArea`, `SaleableArea`, `PropertyArea`, `NetArea`

Project/unit specificity:

- `Projects`, `Properties`, `UnitName`, `ClusterName`, `UnitTypes`

Geo context:

- `EnquiredCity`, `EnquiredState`, `EnquiredLocation`, `EnquiredCountry`
- `CustomerCity`, `CustomerState`, `CustomerLocation`, `CustomerCountry`
- `CustomerCommunity`, `CustomerSubCommunity`, `CustomerTowerName`

Lifecycle/control:

- `IsArchived`, `ArchivedBy`, `ArchivedDate`, `RestoredBy`, `RestoredDate`
- `IsHighlighted`, `IsEscalated`, `IsAboutToConvert`, `IsIntegrationLead`
- `DuplicateLeadVersion`, `LeadAssignmentType`, `BulkCategory`

---

## DATA LEAKAGE (CRITICAL)

### Hard leakage (never features)
- `converted_label`
- `first_booked_at`
- `BookedDate`
- `SoldPrice`
- post-conversion financial fields (brokerage/payment artifacts)

### Conditional leakage
- `booked_flag`
- `time_to_booked_hours`
- `meeting_done_flag`
- `site_visit_done_flag`

Safe only if `event_time <= feature_cutoff_ts`.

### Leakage checklist
1. All feature events timestamped and bounded by cutoff.
2. Target computed independently of feature window.
3. Post-conversion fields excluded from training matrix.

Ignoring this causes fake high offline accuracy and poor production performance.

---

## SECTION 5 - ML MODEL (TRAINING PIPELINE)

### Pipeline steps
1. Data cleanup and contamination exclusion.
2. Time-travel extraction before outcome boundary.
3. Label creation (`BookedDate` / `SoldPrice > 0` policy).
4. Feature matrix join (static + history + call + sequence).
5. Model train/validate/test with tenant-safe splitting.
6. Calibration and thresholding for class buckets.

### Model options and rationale
- XGBoost: primary choice for tabular performance and speed.
- LightGBM: strong alternate.
- Random Forest / Logistic: baselines for sanity and explainability.
- LLM: never bulk score engine.

---

## SECTION 6 - MLOPS

### Serving + lifecycle
- Fast scoring API (single + batch).
- Redis cache for score retrieval.
- Model registry/version tracking.
- Monthly retraining and staged rollout.
- Drift monitoring (feature drift + quality drift).

### Cost discipline
- Keep ML scoring always-on and cheap.
- Keep LLM usage strictly on-demand explanations.

---

## SECTION 7 - LLM + RAG (ENTERPRISE TIER)

### Usage boundary
- ML handles scoring continuously.
- LLM handles explanations only when rep clicks “Why?”.

### Explanation output
- why score moved
- top intent signals
- next best action
- best call time suggestion
- optional script guidance

---

## SECTION 8 - SCORING SERVICE ARCHITECTURE

### API surface
- `POST /api/scores/batch`
- `GET /api/score/:lead_id`
- `GET /api/explain/:id`
- tenant feature-flag update endpoint

### Runtime behavior
- cache-first read path
- live compute fallback
- version-aware responses

---

## SECTION 9 - BROWSER EXTENSION IMPLEMENTATION

### Components
- content script badge injection on CRM rows
- popup controls and tenant state
- CSS badge classes for hot/warm/cold
- build pipeline for Chrome/Edge/Firefox/Safari

### User flow
1. Admin enables scoring.
2. Extension checks tenant scoring status.
3. Batch score fetch for visible rows.
4. Mutation observer updates badges while scrolling.
5. Rep clicks badge for explanation (enterprise).

---

## ROLLOUT PLAN (8-WEEK SHAPE)

- Week 1-2: data prep + feature engineering + initial model.
- Week 3: scoring API + cache + toggles.
- Week 4: MLOps + registry + CI/CD.
- Week 5-6: extension implementation.
- Week 7: explanation layer.
- Week 8: pilot launch + KPI validation + iteration.

---

