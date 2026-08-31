# POC Code Walkthrough — What Calls What, Start to End

This is a training guide, not architecture or experiment documentation (see [`docs/architecture/`](architecture/README.md) and `specs/001-lead-scoring-platform/poc/` for those). Its only job is: **when you open any file in `backend/src/poc/`, know what calls it and what it calls**, so you can trace a request or a pipeline run end to end.

## The two things you can run, and how they relate

This codebase has **two separate entry points that don't call each other**:

1. **The training pipeline** (`backend/scripts/run_poc_pipeline.py`) — a batch script. Run it once (or whenever you want to retrain). It reads CSVs, builds features, trains a model, evaluates it, and writes everything to disk: a model file, metrics, and a SQLite database of pre-computed scores.
2. **The API server** (`uvicorn poc.api.app:app`) — a live FastAPI process. It **never trains anything**. It only *reads* the files the pipeline already produced (the model file, the parquet dataset, the SQLite DB) and serves them over HTTP to the browser UI.

```
run_poc_pipeline.py  ──writes──▶  backend/data/poc/*.parquet
                                  backend/models/poc/*.json, *.csv
                                  backend/data/poc/poc.db (SQLite)
                                          │
                                          │ (read-only, at request time)
                                          ▼
uvicorn poc.api.app:app  ──serves──▶  browser (ui/poc/index.html)
```

If the server is returning stale or missing data, the fix is almost always "re-run the pipeline," not "restart the server" — the server has no code path that updates these files.

## Directory map

```
backend/
├── config/poc.yaml           # the one config file everything below reads
├── scripts/
│   └── run_poc_pipeline.py   # entry point 1 — batch pipeline
└── src/
    ├── observability/logging.py   # shared setup_logging() helper
    ├── models/entities.py         # SQLAlchemy table definitions (shared by pipeline + API)
    └── poc/
        ├── config.py              # load_poc_config() — reads config/poc.yaml
        ├── feature_spec.py        # the single source of truth for feature/column names
        ├── etl/
        │   ├── load_csv.py        # step 1: read + dedupe raw CSVs
        │   ├── versioned_json.py  # helper: parse the {"1": val, "2": val} JSON columns
        │   ├── features.py        # step 2: raw columns -> model features
        │   ├── label.py           # step 3: raw columns -> converted/not-converted label
        │   └── build_dataset.py   # orchestrates the 3 steps above -> processed_dataset.parquet
        ├── training/
        │   ├── split.py           # load the parquet + train/test split
        │   ├── train.py           # fit XGBoost -> model_poc-v1.json
        │   ├── evaluate.py        # score test set -> metrics.json, thresholds.json
        │   ├── score_all.py       # score every lead -> lead_scores.csv (+ shared helpers used by the API)
        │   └── explain.py         # per-lead SHAP-style explanation logic
        ├── db/
        │   └── seed.py            # writes pipeline output into the SQLite DB via models/entities.py
        └── api/
            ├── app.py             # entry point 2 — FastAPI app object
            ├── deps.py            # shared, cached resources (DB session, loaded model, dataset)
            ├── lead_routes.py     # GET /poc/leads, GET /poc/leads/{id}/score, POST .../explain
            └── tenant_routes.py   # GET /poc/tenants, PATCH /poc/tenants/{id}/scoring-policy
```

---

## Entry point 1: the training pipeline, step by step

Run with `PYTHONPATH=src python scripts/run_poc_pipeline.py` from `backend/`. `run()` in `run_poc_pipeline.py` calls four functions in sequence — nothing runs in parallel, each step reads the previous step's output file from disk (this is a batch pipeline, not one program passing objects in memory).

### Step 0 — config and logging (every step below starts here)
- `poc/config.py`'s `load_poc_config()` reads `backend/config/poc.yaml`, resolves the relative `data_dir`/`model_dir`/`database_url` paths to absolute ones, and returns a plain `dict`. Every other function in the pipeline takes this `config` dict as its first argument — it's the only thing threaded through the whole pipeline.
- `observability/logging.py`'s `setup_logging(config)` calls `logging.basicConfig(level=config["log_level"], format=...)` **once**. This is what makes `logger.info(...)` calls anywhere in the codebase actually print to your terminal. Each pipeline module (`build_dataset.py`, `train.py`, `evaluate.py`, `db/seed.py`) calls this again in its own `if __name__ == "__main__":` block so each script also works stand-alone — but `logging.basicConfig` is a no-op if a handler is already configured, so calling it repeatedly is harmless.

### Step 1 — `poc/etl/build_dataset.py`'s `build_dataset(config)`
Called from `run_poc_pipeline.py:20`. Internally:
1. `poc/etl/load_csv.py`'s `load_raw(config["csv_files"])` — reads all 5 CSVs with `pandas.read_csv`, concatenates them, then **deduplicates by `LeadId`**, keeping whichever row has the latest `ModifiedDate` (parsed via `versioned_json.current_value_series`, since `ModifiedDate` is itself one of those `{"1": ts, "2": ts}` version-keyed JSON columns). Logs `"load_csv: loaded N files, N raw rows"` then `"...deduped to N unique leads"`.
2. `poc/etl/features.py`'s `build_features(raw, run_ts)` — turns raw CRM columns into the ~19 model features (`current_status`, `status_transition_count`, `lower_budget`, `days_since_created`, etc.), using `poc/etl/versioned_json.py`'s helpers (`current_value_series` — last value in the version dict; `transition_count_series` — how many versions exist; `success_count` — count of `1`/`True` values, used for `ContactRecords`). It asserts no PII column and no missing declared feature slipped through, using the column lists in `poc/feature_spec.py`. Logs `"features: built N features for N leads..."`.
3. `poc/etl/label.py`'s `build_labels(raw)` — computes the `converted` label from `BookedDate`/`SoldPrice`/`BaseLeadStatus`, excluding cancelled/reverted bookings. Logs `"label: N positive labels out of N (%.4f%%)..."`.
4. `build_dataset()` merges features + label + a single `feature_cutoff_ts` (one timestamp for the whole batch, since this is a historical snapshot, not a live stream) into one DataFrame, writes it to `data/poc/processed_dataset.parquet`, and logs `"build_dataset: wrote N rows, N positive labels..."`.

### Step 2 — `poc/training/train.py`'s `train_model(config)`
Called from `run_poc_pipeline.py:21`.
1. `poc/training/split.py`'s `load_dataset(config)` reads back the parquet file, and `split_dataset(dataset)` does a stratified 80/20 train/test split using `MODEL_FEATURES`/`LABEL_COLUMN` from `feature_spec.py`.
2. Computes `scale_pos_weight` from the real class imbalance in the training split (not a hardcoded guess), fits an `XGBClassifier`, and saves it to `models/poc/model_poc-v1.json`.
3. Logs `"train: fit on N rows (N positive / N negative, scale_pos_weight=X), saved to ..."`.

### Step 3 — `poc/training/evaluate.py`'s `evaluate(config)`
Called from `run_poc_pipeline.py:22`.
1. Reloads the same parquet + does the identical split (same `RANDOM_STATE`, so it's the same held-out test set `train.py` didn't train on), reloads the model file `train.py` just saved.
2. Computes AUC (`roc_auc_score`) and a precision/recall curve, picks the best F1 threshold.
3. Separately, scores **every** lead (not just the test set) to derive the Hot/Warm/Cold cut points at the `hot_percentile`/`warm_percentile` from `poc.yaml` (0.90/0.60 — i.e. top 10% hot, next 30% warm, bottom 60% cold).
4. Writes `models/poc/metrics.json` and `models/poc/thresholds.json`. Logs one line with AUC, precision, recall, and the three category counts.

### Step 4 — `poc/db/seed.py`'s `seed_database(config)`
Called from `run_poc_pipeline.py:23`.
1. Calls `poc/training/score_all.py`'s `score_all(config)` first — this reloads the model + parquet + `thresholds.json`, scores every lead, categorizes each into hot/warm/cold via `categorize()`, and writes `models/poc/lead_scores.csv`. Logs `"score_all: scored N leads -> hot=N warm=N cold=N..."`.
2. `seed_database` then opens the SQLite DB at `config["database_url"]`, creates all tables from `models/entities.py`'s `Base.metadata` if they don't exist, **wipes existing rows** (`_clear_existing`), and bulk-inserts fresh `ModelVersion`, `TenantScoringPolicy` (one per tenant in `poc.yaml`'s `top_tenants`), `Lead`, `LeadFeatureSnapshot`, and `LeadScore` rows built from the scored dataset.
3. Logs `"seed: wrote N leads, N feature snapshots, N scores, N tenant policies to ..."`.

`models/entities.py` defines 7 tables total, but the POC pipeline only ever writes 5 of them (`Lead`, `LeadFeatureSnapshot`, `LeadScore`, `ModelVersion`, `TenantScoringPolicy`). `LeadEvent` and `ScoreExplanation` are part of the *future production* schema and are currently unused by any POC code — don't expect data in those tables.

**After all four steps, nothing is "running" anymore.** The pipeline is a script, not a service — it produces files and exits. The API server below is what serves those files.

---

## Entry point 2: the API server, request by request

Started with `uvicorn poc.api.app:app --reload` from `backend/`. Unlike the pipeline, this *stays running* and handles one HTTP request at a time.

### Startup (`poc/api/app.py`)
`create_app()` runs once, at process start:
1. Builds a `FastAPI()` instance.
2. `app.include_router(lead_routes.router)` and `app.include_router(tenant_routes.router)` — this is what makes the `/poc/...` endpoints exist at all. If a route isn't showing up, check it's registered in one of these two router files.
3. Mounts `ui/poc/` as static files at `/` — this is why opening `http://127.0.0.1:8000/` in a browser serves `ui/poc/index.html` instead of a 404.
4. The module-level `app = create_app()` (line 25) is the object `uvicorn poc.api.app:app` imports and runs.

### Shared resources (`poc/api/deps.py`)
Every route handler below takes one or more of these as a `Depends(...)` argument. Each is wrapped in `@lru_cache(maxsize=1)`, meaning **it only actually runs once per server process**, the first time it's requested — not once per HTTP request:
- `get_config()` → `poc.config.load_poc_config()`
- `get_engine()` → a SQLAlchemy engine for the SQLite DB
- `get_session()` → a fresh DB `Session` **per request** (this one is not cached — it's a generator dependency that opens and closes a session for each call)
- `get_model()` → `poc.training.score_all.load_model()` — loads `model_poc-v1.json` into memory once
- `get_thresholds()` → `thresholds.json`
- `get_feature_dataset()` → the same `processed_dataset.parquet` the pipeline built
- `get_sorted_probabilities()` → scores the whole dataset once (with the cached model) and sorts the probabilities, so any individual lead's raw probability can be turned into a readable 0–100 percentile rank instantly

This is the concrete reason the server needs the pipeline's output files to already exist on disk before it starts — `get_model()`/`get_thresholds()`/`get_feature_dataset()` will raise a file-not-found error on first request if the pipeline hasn't run yet.

### Browser opens `http://127.0.0.1:8000/`
Static file mount serves `ui/poc/index.html`. Its JS then makes the calls below.

### `GET /poc/tenants` (`tenant_routes.py:list_tenants`)
Queries every row in `TenantScoringPolicy` and returns tenant id, whether scoring is enabled, and the two threshold values. Populates the tenant dropdown in the UI.

### `GET /poc/leads?tenant_id=X` (`lead_routes.py:list_leads`)
1. `_scoring_enabled()` checks that tenant's `TenantScoringPolicy.scoring_enabled` flag.
2. Joins `Lead` with `LeadScore` for that tenant, ordered by score descending.
3. For each row, calls `_lead_score()` → `score_all.percentile_rank()` against `get_sorted_probabilities()` to compute the 0–100 display score.
4. If scoring is disabled for the tenant, scores are nulled out in the response (the UI shows leads but no scores).

### `GET /poc/leads/{lead_id}/score` (`lead_routes.py:get_lead_score`)
Same idea as above but for one lead — 404s if scoring is disabled or no score row exists.

### `POST /poc/leads/{lead_id}/explain` (`lead_routes.py:explain`)
1. Same `_scoring_enabled()` gate.
2. Calls `poc/training/explain.py`'s `explain_lead(model, thresholds, dataset, tenant_id, lead_id, sorted_probabilities)`:
   - Looks up that lead's feature row in the in-memory dataset.
   - Re-predicts its probability and category.
   - Calls `model.get_booster().predict(dmatrix, pred_contribs=True)` — XGBoost's built-in per-feature contribution values (the same idea as SHAP) for *this one lead's* prediction.
   - Ranks features by `abs(contribution)`, takes the top 3, and turns each into a human sentence via the `_SIGNAL_BUILDERS` dict (a hand-written template per feature name — e.g. `_has_scheduled_meeting`, `_contact_success_count` — falling back to `_default_signal` for any feature without a custom template).
   - Returns `{summary, top_signals, recommended_action}`.
3. If the lead isn't found in the dataset (`LookupError`), returns a generic fallback message instead of a 500 error.

### `PATCH /poc/tenants/{tenant_id}/scoring-policy` (`tenant_routes.py:update_scoring_policy`)
Flips `TenantScoringPolicy.scoring_enabled` for one tenant and commits. This is what the UI's enable/disable toggle calls.

---

## Config reference — `backend/config/poc.yaml`

| Key | Read by | Meaning |
|---|---|---|
| `csv_files` | `load_csv.py` | Absolute paths to the 5 raw lead-export CSVs (not in git) |
| `data_dir` | `build_dataset.py`, `split.py`, `deps.py` | Where `processed_dataset.parquet` lives |
| `model_dir` | `train.py`, `evaluate.py`, `score_all.py`, `deps.py` | Where the model file, `metrics.json`, `thresholds.json`, `lead_scores.csv` live |
| `database_url` | `seed.py`, `deps.py` | SQLite connection string |
| `top_tenants` | `seed.py` | Which tenants get a `TenantScoringPolicy` row seeded |
| `hot_percentile` / `warm_percentile` | `evaluate.py` | The 0.90 / 0.60 cut points used to derive Hot/Warm/Cold thresholds |
| `model_version` | everywhere | String tag (`"poc-v1"`) used in filenames and DB rows |
| `log_level` | `observability/logging.py` | Passed to `logging.basicConfig(level=...)` |

Don't confuse this with `backend/src/config/loader.py` / `runtime.py` — that's a **separate, unrelated** config system for the *future production app* (reads `config/dev.yaml` / `config/prod.yaml`), not used anywhere in the POC pipeline or API above.

---

## Why your added logs weren't showing up (and the fix)

`setup_logging()` (which is what actually attaches a handler so `logger.info(...)` prints anywhere) was only ever called inside the **pipeline** scripts — `build_dataset()`, `train_model()`, `evaluate()`, `seed_database()` each call it in their own `if __name__ == "__main__":` block, or `run_poc_pipeline.py` calls it once at the top of `run()`.

**`poc/api/app.py` never called it.** When you run `uvicorn poc.api.app:app`, Python's root logger has no handler attached by your code at all. Uvicorn configures its *own* named loggers (`uvicorn`, `uvicorn.error`, `uvicorn.access`) — which is why you see uvicorn's own startup/request logs — but any `logger = logging.getLogger(__name__)` you add inside `lead_routes.py`, `deps.py`, etc. has nothing attached anywhere in its logger hierarchy. Python's logging module silently drops anything below WARNING in that situation (its "handler of last resort" only ever prints WARNING and above), so your `logger.info(...)` calls were not broken — they were going to a logger with no output configured.

**I've fixed this**: `create_app()` in `poc/api/app.py` now calls `setup_logging()` too, so any logger anywhere in the `poc.*` package will print once you restart the server. See the diff below.

Two other things worth knowing for next time:
- `--reload` runs your app in a **subprocess**; if you only ever add a `print()` at *import time* (module top-level) rather than inside a function, it can be easy to miss because it only prints once at startup, not per-request.
- To see a specific module's logs more precisely without changing the global level, you can always do `logging.getLogger("poc.api.lead_routes").setLevel(logging.DEBUG)` right where you need it.
