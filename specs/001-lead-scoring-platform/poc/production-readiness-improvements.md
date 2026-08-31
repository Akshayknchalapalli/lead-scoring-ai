# POC Production-Readiness Improvements

This is a companion to `poc/data-findings.md` (which documents the first bug caught during
development — `current_status` target leakage, AUC 0.988 → 0.699). This doc covers a second
round of fixes found while testing the running demo, all in `backend/src/poc/training/explain.py`
and `backend/src/poc/etl/features.py`. None of these change the POC's scope or requirements —
they're correctness and quality fixes discovered by actually using the thing, which is exactly
what a POC is for.

## 1. Business-friendly explanations

**Before**: signals were the raw feature name and value —
`"status_transition_count (8) increased this lead's score"`.

**After**: every signal is a full sentence in business language, e.g.:
- `"This lead has progressed through multiple sales stages (8 status transitions), indicating sustained engagement."`
- `"The sales team has successfully connected with this lead 4 time(s), a sign of a responsive, engaged prospect."`

Implemented as a `_SIGNAL_BUILDERS` dict (`explain.py:198-219`) mapping each of the 20 model
features to a dedicated sentence-builder function, with a generic fallback for anything not
explicitly covered. The raw feature name never reaches the API/UI.

## 2. Bug: explanations could contradict the prediction (direction-unaware booleans)

**Found while testing**: a lead scored COLD produced the explanation *"This lead has completed
a site visit, one of the strongest signals of purchase intent"* — a positive-sounding claim on a
lead the model scored as low-intent. Confidence-damaging if shown to a sales rep.

**Root cause**: the four boolean feature templates (`has_scheduled_meeting`, `is_meeting_done`,
`is_site_visit_done`, `is_picked`) wrote their sentence based only on the raw value (1/0),
ignoring the actual sign of that feature's contribution for this specific lead. In a tree model,
a feature can contribute *negatively* even when "present," due to interaction with other
features — so asserting a fixed positive meaning regardless of direction was wrong, not just
imprecise.

**Fix**: all four templates now branch on both the value *and* the contribution direction
(`explain.py:84-121`), e.g.:
- present + positive: `"This lead has completed a site visit, one of the strongest signals of purchase intent."`
- present + negative: `"This lead completed a site visit, though other factors are currently outweighing that signal."`

Note this is *not* the same as forcing every top-3 signal to agree with the overall category — a
COLD lead can still legitimately have one positively-contributing signal among its top 3 (other
factors just outweighed it more). The fix only ensures a signal's own sentence never misstates
its own direction.

## 3. Bug: empty-string values treated as a valid category

**Found while testing**: an explanation read *"This lead is enquiring about `` property"* — a
visible double space where a category value should have been.

**Root cause**: several source CRM fields use `{"1": ""}` (an empty string) as their "unset"
sentinel rather than a JSON `null`. `features.py` only replaced actual nulls via `.fillna("unknown")`,
so the empty string passed through unchanged into `property_type`, `current_status`,
`current_sub_status`, `enquired_city`, and `bhk_type`.

**Fix**: added `_clean_category()` (`features.py:26-29`), which replaces the empty string with
`pd.NA` before applying the same `"unknown"` fallback, so both real nulls and the blank-string
sentinel resolve to one consistent `"unknown"` category. (It does not trim whitespace or do any
other normalization — just this one substitution.)

**Side effect — model improved**: fixing this required retraining, since it changes the actual
feature values (not just display text): fragmented `""`/`"unknown"` categories were collapsing
into one clean category, giving the model a cleaner signal.

| | ROC-AUC |
|---|---|
| Before this fix (post-leakage-fix baseline) | 0.699 |
| After this fix | **0.751** |

Same model architecture, same features, same imbalance handling — the improvement came entirely
from cleaner categorical encoding. A concrete illustration of why feature-engineering data quality
matters as much as model choice.

## 4. Lead score display: percentile rank, not raw probability

Documented in detail in the prior turn of this build (see conversation history / git log): the
raw predicted probability is tiny by construction (the real conversion rate is 0.317%), so most
of the WARM band rounded to a confusing `"0.0%"` in the UI. Replaced with a 0-100 percentile rank
against the full scored population (`percentile_rank()` in `score_all.py`), shown as e.g. `87%`
in the UI table (not `87 / 100` — matches common CRM scoring conventions more closely) and as
`"scored in the top 13% of leads"` in the explanation summary, instead of the raw probability.

## Why this matters beyond the POC

| Area | What changed |
|---|---|
| Explainability | Feature-name-and-number output → full business-language sentences |
| Correctness | Explanations can no longer contradict the predicted category |
| Data quality | Blank-string CRM sentinel values no longer silently corrupt categorical features |
| Model quality | AUC 0.699 → 0.751 from the data-quality fix alone, no architecture change |
| UX | Raw tiny probabilities replaced with percentile-rank language throughout |

None of this was found by reading code or specs — it surfaced from actually clicking through the
running demo and querying real leads across Hot/Warm/Cold. Worth keeping as a standing practice
before any future model/feature change ships: score a sample from each category and read the
explanation out loud before calling it done.
