# Section 5 — ML Model: Training Pipeline

**Depends on:** [04-feature-engineering.md](04-feature-engineering.md) — the 60-feature vector is Step 4's input.
**Feeds into:** [06-mlops.md](06-mlops.md) (the trained model artifact is what gets served, monitored, retrained, and registered) and [08-scoring-service-architecture.md](08-scoring-service-architecture.md) (the ML Model Service loads exactly what this pipeline produces).

## What this section will do

This section defines the actual training pipeline — the sequence that turns the labelled feature vectors from Section 4 into a calibrated, three-bucket (Hot/Warm/Cold) classifier — and justifies why XGBoost specifically was chosen over the alternatives, on strengths and weaknesses rather than quoted benchmark numbers (see the algorithm comparison below).

**Note on scope:** this file describes the intended training system — the pipeline, the algorithm choice, the promotion gate — and is meant to stay stable across experiment runs. Detailed experimental metrics (AUC, precision/recall, calibration status, leakage investigations) belong in separate, run-specific evaluation records, not here, since those are expected to change with every retrain. Specific hyperparameter values are likewise an experiment-run detail, not an architecture decision — see Step 6 below.

## Training pipeline

**The split happens before feature extraction, not after.** An earlier version of this pipeline computed the feature matrix first and split afterward — that's backwards. Any feature that involves a statistic computed *across leads* (the EDA-derived tiers for `source_quality_tier`/`campaign_quality_tier` in [04-feature-engineering.md](04-feature-engineering.md), or any encoder/imputer/normalizer added later) leaks test-set information into training the moment it's fit before the split. The correct boundary is: split first, then compute every such statistic on the training set only, and apply it unchanged to validation and test.

```
Historical Leads
        │
        ▼
1. Label Assignment  —  Booked=1 / Lost=0 / Open=excluded from training (see 15G)
        │
        ▼
2. Train / Validation / Test Split  —  time-based, not random (see below)
        │
        ├───────────────────┬───────────────────┐
        ▼                   ▼                   ▼
     TRAIN               VALIDATION            TEST
        │                   │                   │
        ▼                   ▼                   ▼
3. Time Travel        3. Time Travel       3. Time Travel      — cutoff applied independently
        │                   │                   │                per split, never shared
        ▼                   ▼                   ▼
4. Feature Extraction & Matrix Construction (per split)
   Any global statistic (EDA tiers, encoders, imputers) is FIT ON TRAIN ONLY,
   then APPLIED — never refit — to validation and test.
        │                   │                   │
        ▼                   │                   │
5. Class Balancing (train only — never applied to validation/test)
        │                   │                   │
        ▼                   ▼                   ▼
6. Model Training  ──────────────────────▶  7. Evaluation  ──────────────────▶  Held-out Test
        │
        ▼
8. Calibration
        │
        ▼
9. Threshold Derivation  (probability → Hot/Warm/Cold, per tenant)
```

### 1 — Label assignment

Booked = 1 (`BookedDate` + `SoldPrice > 0` + `BookedBy` set), Lost = 0, Open = excluded from training entirely (these are what gets scored, not trained on) — the same rule as [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md)'s Section 15G.

### 2 — Train / validation / test split: time-based, not random

Split by **time**, not a random or `tenant_id`-stratified draw: leads created earliest go to train, a middle window to validation, the most recent window to test. This mirrors how the model is actually used — always predicting forward, on leads it has never seen, using history that happened before now. A random split lets a lead from the newest period sit in training while an older lead sits in test, so the model gets evaluated on a temporal distribution it was never really deployed against; a time-based split is what `feature_cutoff_ts` (the anchor this whole pipeline is built around, per [03-data-architecture-and-schema.md](03-data-architecture-and-schema.md) 15A/15D) already implies. If a random or stratified split is ever used instead — e.g. because one tenant's history is too short to support three time-ordered windows — that choice needs to be justified explicitly in the run's evaluation record, not silently substituted.

### 3 — Time travel (per split, independently)

For each labelled lead, extract features only from before its outcome date, using that lead's own `feature_cutoff_ts` — this is the guardrail that prevents leakage, and it's applied separately within each of train/validation/test, never computed once and shared. This is exactly the guardrail `current_status_encoded` depends on for safety — see the leakage caution in [04-feature-engineering.md](04-feature-engineering.md).

### 4 — Feature extraction & matrix construction

Renamed from "feature matrix" / "join" — that undersold what this step actually does, per [04-feature-engineering.md](04-feature-engineering.md):

- **Version walking** — walking each versioned-JSON column via `get_at_version()` up to the split-specific cutoff.
- **Feature derivation** — the ~60 GROUP 1–6 derivations (counts, ratios, status transitions, etc.).
- **Categorical encoding** — `tenant_id`, `property_type_encoded`, and similar, encoded consistently across splits.
- **Missing-value handling** — the per-feature defaults specified throughout Section 4 (e.g. `LowerBudget` null → 0).
- **Placeholder handling** — features Section 4 marks **Placeholder** (unconfirmed value encoding, e.g. `answered_calls`) are still extracted and included, but flagged in the feature schema (see the model-artifact contents below) so nothing downstream treats them as validated. Features marked **CLARIFY** (not derivable at all) are excluded from the matrix entirely, not silently zero-filled.
- **Confidence-aware extraction** — the Confirmed/Placeholder/CLARIFY tiering from [04-feature-engineering.md](04-feature-engineering.md) is carried through into this step's output, not dropped at the feature-engineering boundary.

Any statistic that needs to look across leads (EDA-derived tiers, encoders, imputers) is fit here on the training split only, then applied — never refit — to validation and test, per the ordering note above.

### 5 — Class balancing (train only)

Real-estate lead conversion is a heavily imbalanced problem — expect well under the "~5%" planning-time rule of thumb. Handle the imbalance using an appropriate strategy — `scale_pos_weight`, class weights, or SMOTE are all valid choices, and enterprise XGBoost deployments frequently use `scale_pos_weight` alone rather than SMOTE — and **record which approach was chosen, and the exact imbalance ratio it was tuned against, in the run's evaluation record.** This is a run-level decision, not a fixed architecture rule; applied to the training split only, never to validation or test.

### 6 — Model training

XGBoost (see the algorithm comparison below for why). Specific hyperparameters (tree depth, estimator count, early-stopping rounds, etc.) are selected through validation for a given run and tracked with that run's model artifact — they are experiment detail, not an architecture decision, and are deliberately not fixed here so this file doesn't go stale the next time they're retuned.

### 7 — Evaluation

Score the held-out test split (never touched until this point) and report against the promotion criteria below.

### 8 — Calibration

Platt scaling (or an equivalent) for probability calibration, fit on train/validation, verified on test with a reliability diagram and a Brier-score target agreed per run.

### 9 — Threshold derivation

Per-tenant — Hot/Warm/Cold cut points derived from score percentiles, because conversion baselines differ across the 3–4 tenants (FR3, NFR5, [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md)). See "From probability to business action" below for how this cut point relates to what the extension actually displays.

### From probability to business action

A model produces a **probability**. A tenant's configured **threshold** turns that probability into a **category**. A product decision turns that category into a **business action**. These are three distinct steps, not one:

```
Model probability (e.g. 0.82)
        │
        ▼
Per-tenant threshold cut  →  category (Hot / Warm / Cold)
        │
        ▼
Business action  →  badge color, sort order, next-best-action copy (Section 7), notification rules
```

`0.82` is not "Hot" until a threshold says so, and "Hot" is not "call this lead first" until a product rule says so. Keeping these separate matters because each can change independently: a tenant's threshold can be re-tuned without retraining the model, and the business action tied to "Hot" can change (e.g. adding an auto-notification) without touching either the model or the threshold.

## Model evaluation & promotion gate (making Steps 7–9 explicit)

The pipeline above already contains evaluation, calibration, and thresholding — but it's worth pulling those into an explicit gate, because "does this new model actually get deployed" should never be a judgment call made by reading a single AUC number. Crucially, clearing the model's own accuracy bar is **not sufficient on its own** — a candidate can have a great offline AUC and still be unsafe to promote if the data it was trained on has drifted from what's currently live, or if its feature schema doesn't match what the serving path expects. The gate a candidate model has to clear, in order:

```
Training (Step 6)
      │
      ▼
Evaluation (Step 7 — held-out test split)
      │
      ▼
Promotion Criteria
  AUC             > 0.80   (NFR3)
  Precision (Hot) — target set from business tolerance for false positives
  Recall (Hot)    — target set from business tolerance for missed conversions
  Calibration     — Brier score below an agreed threshold
      │
      ▼
Drift & Compatibility Checks  —  not just "is the model good," but "is it safe to swap in right now"
  Feature drift        — has the training-data feature distribution shifted vs. what's currently live?
                          (same PSI mechanism as the Drift Monitor in 06-mlops.md)
  Prediction drift      — does the candidate's score distribution differ substantially from the
                          live model's, on the same current population?
  Data quality          — did this run's input pass the same validation checks 3A's pipeline enforces
                          (03-data-architecture-and-schema.md) — no silent schema or null-rate regressions?
  Schema compatibility   — does the candidate's feature schema (see the model artifact below) match
                          what the Feature Extractor / Scoring API currently produces and expects?
      │
      ▼
Shadow Traffic — operational validation only (latency, errors, prediction/calibration
  stability vs. the live model) — see 06-mlops.md for why this stage cannot compute AUC:
  there's no ground-truth outcome yet for leads scored during a live trial.
  (this is Stage 5 of the CI/CD pipeline in 10-tech-stack-and-deployment.md)
      │
      ▼
Provisional promotion — candidate takes a limited slice of live traffic; the AUC/precision/
  recall check above (computed on historical held-out test data) already passed, but the
  *business-metrics* confirmation against current live performance has to wait for real
  outcomes, per 06-mlops.md's delayed Accuracy Tracker evaluation
      │
      ▼
Approve — auto-confirm the promotion if operational shadow checks pass now and the delayed
  accuracy comparison holds up once outcomes arrive; auto-rollback + retrain trigger otherwise.
  Only confirmed models remain in production long-term.
      │
      ▼
Model Registry (see 06-mlops.md) — the promoted model artifact (see below) is versioned, logged,
      │                             and becomes what the Scoring API loads
      ▼
Deploy (Stage 6, 10-tech-stack-and-deployment.md) — zero-downtime rolling update
```

This is the same promotion mechanism already scattered across [06-mlops.md](06-mlops.md) (which has the full two-phase — immediate operational shadow validation, then delayed accuracy confirmation once labels exist — spelled out in detail) and [10-tech-stack-and-deployment.md](10-tech-stack-and-deployment.md) (CI/CD Stage 5, "Model validate") — it's written out here as one continuous gate so it reads as a single evaluation contract rather than several independent mentions of a shadow test. The AUC/precision/recall/calibration criteria above are evaluated on the held-out test split (Step 7), which already has historical ground truth — that part of the gate is immediate. The drift, compatibility, and shadow-traffic checks are what make this an *enterprise* promotion gate rather than a pure offline-accuracy check — a model can clear its offline AUC bar and still turn out unsafe to fully trust, either because production has drifted since the test split was built, or because its *live* performance (only knowable once real outcomes arrive) doesn't match its offline promise. Current experimental results against these criteria belong in separate, run-specific evaluation records, not here — this gate is designed to block promotion of any model that doesn't clear it, whatever the current numbers happen to be.

### What a promoted model artifact actually contains

"Model Registry" (06-mlops.md) is often read as "a `.pkl`/`.json` file with a version number." That undersells what actually has to be versioned together for the registry to be useful. A promoted artifact is a **bundle**, not a single file:

| Component | What it is | Why it has to travel with the model |
|---|---|---|
| **Model** | The trained XGBoost booster itself | The prediction function. |
| **Feature schema** | The ordered list of features the model expects, each tagged with its Section-4 Confidence tier (Confirmed/Placeholder/CLARIFY) | Without this, nothing downstream knows whether a feature value is trustworthy, or whether the serving path is even producing the columns this model version expects (this is what "schema compatibility" above checks). |
| **Encoders / imputers** | Whatever was fit on the training split in Step 4 (categorical encoders, EDA-derived tier maps, missing-value defaults) | Must be applied identically at serving time — refitting them live would reintroduce the exact leakage Step 4's train-only-fitting rule exists to prevent. |
| **Calibration model** | The Step 8 Platt-scaling (or equivalent) transform | Needed to turn a raw model score back into a calibrated probability at serving time. |
| **Thresholds** | The Step 9 per-tenant Hot/Warm/Cold cut points | Needed to turn a probability into a category — see "From probability to business action" above. |
| **Training metadata** | Training window, data snapshot reference, hyperparameters actually used, class-balancing strategy chosen (Step 5) | Reproducibility — answers "what exactly produced this artifact" without needing the training code's git history. |
| **Metrics** | AUC, precision/recall, calibration score, drift-check results — everything the promotion gate evaluated | The audit trail for *why* this specific version was promoted. |
| **Version** | A unique identifier tying all of the above together | What the Model Registry and Scoring API actually key off of. |

[06-mlops.md](06-mlops.md) covers the registry's *lifecycle* (versioning, rollback, lineage, reproducibility) — this table is what Section 5 hands that registry each time a model is promoted, so the two sections describe the same handoff from complementary sides.

## Phase 2 opportunity (noted here, deferred)

`DataConverted` — the field flagged as useless for lead-scoring in [04-feature-engineering.md](04-feature-engineering.md) because it's `true` for every row — is actually the perfect **label** for a different, future model: predicting which Data/Prospect-module records should be promoted to Leads at all. Same ML infrastructure (XGBoost, same MLOps pipeline), different input population. Build this after Phase 1 (the lead-scoring model) ships.

## Algorithm comparison — why XGBoost wins for this use case

This used to be a table with an AUC column quoting numbers like "0.87" per algorithm. Removed — those numbers implied a precision that doesn't exist. They read as benchmark results even with a caveat attached, and no bake-off comparing all five algorithms on Leadrat's own data has actually been run (only XGBoost has — see the promotion gate above for where that result belongs). Comparing algorithm classes on their structural strengths and weaknesses is a stronger, more honest argument than quoting a generic figure that was never measured here:

| Algorithm | Strengths | Weaknesses | Decision |
|---|---|---|---|
| **XGBoost** | Excellent for tabular/mixed-type data · handles missing values natively · gives feature importance (needed for Section 7's explanation layer) · mature, well-understood ecosystem · fast inference | Needs careful tuning to avoid overfitting on a small positive class; less interpretable than logistic regression | **Chosen** |
| LightGBM | Similar strengths to XGBoost; faster training on very large datasets | Slightly less mature tooling for this team; marginal benefit at current data volume | Viable alternate — revisit if training time becomes a bottleneck |
| Random Forest | Strong overfitting resistance; good interpretability | Slower inference than boosted trees at comparable accuracy; larger model artifacts | Reasonable baseline, not chosen — no clear advantage over XGBoost here |
| Neural Network | Can model complex interactions given enough data | Needs far more data than currently available; black-box output works against Section 7's explanation requirement; expensive to train and serve for no demonstrated benefit on tabular data | Overkill for this problem shape |
| Logistic Regression | Maximally interpretable; trivial to serve; a useful sanity-check baseline | Misses non-linear feature interactions; needs feature scaling; historically the weakest of this group on tabular problems with interaction effects | Good baseline to report alongside the chosen model, not a production candidate |
| GPT-4 / any LLM | None, for this specific job — see the cost math and correctness argument in [07-llm-rag-layer.md](07-llm-rag-layer.md) | Orders of magnitude slower and more expensive per lead than a trained classifier; not deterministic; not a scoring model in any meaningful sense | **Wrong tool** — kept as a row specifically to preempt "why not just use GPT to score leads" before it's asked |

This satisfies NFR1 (< 2ms inference) from [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) structurally — XGBoost's inference cost is a property of the algorithm class, not of any single tuning run. NFR3 (AUC > 0.80) is a different kind of claim — it's a promotion-gate criterion evaluated per run (see above), not something this comparison can or should assert in advance.
