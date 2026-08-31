# Section 10 — Implementation Stack & Delivery Pipeline (+ Section 11: CI/CD)

**Depends on:** every prior section — this is the concrete tooling that implements Sections 3–9.
**Feeds into:** [12-delivery-timeline-and-ask.md](12-delivery-timeline-and-ask.md) — the 8-week plan is essentially "build and ship each column below, in order."

> This file merges board **Section 10** (the tech stack) with board **Section 11** (CI/CD). Section 10 lists *what* is used; Section 11 is *how it ships*. Since the deployment pipeline exists to ship exactly the six stacks below, they're kept as one document. Renamed from "Complete Tech Stack" — by the time deployment, CI/CD, infrastructure, and release engineering are all in scope, "tech stack" undersold what this file actually covers.

## What this section will do

Section 10 is the concrete tooling choice behind every architectural component described so far, organized into the same six tracks used throughout the board (ML, data pipeline/MLOps, backend, LLM/RAG, browser extension, infrastructure). Section 11 defines the pipeline that takes a code push and turns it into a live, versioned, zero-downtime deployment across both the backend and four browser extension stores.

**Technologies are implementations of contracts, not the architecture itself.** Every table below answers "what do we use *today*" for a logical component that Sections 3–9 already defined independent of any specific tool. That distinction matters in both directions already established elsewhere in this blueprint: the **Online Feature Cache** ([06-mlops.md](06-mlops.md)) is Redis today and could become Feast tomorrow without changing what "online feature cache" means architecturally; the **LLM Adapter** ([07-llm-rag-layer.md](07-llm-rag-layer.md)) is GPT-4o-mini today and could become Claude, Gemini, or a local model tomorrow without changing the Explanation Service's contract. Reading the tables below as "the current answer to a question the architecture already asked" — not as the architecture itself — is the right frame for all of them.

**Evidence note:** most of this table is **[Hypothesis]** — planned tooling, not yet adopted. A meaningful subset is already **[Observed]** in `backend/pyproject.toml`'s real dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `redis`, `alembic`, `pandas`, `xgboost`, `scikit-learn`. Everything else in the table below — LangChain, pgvector, MLflow, Airflow, Evidently, SHAP, Terraform, and the entire CI/CD pipeline in the next section — has not been added to the codebase yet.

## Tech stack by track

| ML & Data Science | Data Pipeline & MLOps | Backend API | LLM & RAG | Browser Extension | Infrastructure & Deployment |
|---|---|---|---|---|---|
| Python 3.11 | Apache Airflow 2.x | FastAPI (Python) | OpenAI GPT-4o-mini | Vanilla JS (no framework) | AWS ECS Fargate |
| XGBoost 2.0 | Redis (ElastiCache) | Uvicorn ASGI server | LangChain framework | Webpack 5 bundler | AWS RDS PostgreSQL |
| LightGBM (alt) | Evidently AI (drift) | SQLAlchemy ORM | pgvector (embeddings) | WebExtensions API | AWS ElastiCache Redis |
| Scikit-learn | Great Expectations | PostgreSQL 15 | text-embedding-3-small | Manifest V3 (Chrome/Edge) | AWS S3 (model storage) |
| Pandas / NumPy | Docker containers | Pydantic v2 | FAISS (local vector search) | Manifest V2 (Firefox compatibility layer) | AWS CloudWatch |
| Feature-engine (shared feature transformation library — [04](04-feature-engineering.md)/[08](08-scoring-service-architecture.md)'s Feature Extractor, not a standalone product) | GitHub Actions CI/CD | python-jose (JWT) | tiktoken (token counting) | Xcode (Safari conversion) | Route53 + ACM SSL |
| SHAP (explainability) | AWS S3 (artefact store) | Celery (async tasks) | Instructor (structured output) | chrome.storage.local | Terraform (IaC) |
| Imbalanced-learn (SMOTE) | Pytest (model tests) | Redis pub/sub | Redis (LLM response cache) | MutationObserver API | Docker + ECR |
| MLflow (model registry) | Alembic (DB migrations) | Nginx reverse proxy | Tenacity (retry logic) | Fetch API (batch calls) | GitHub Actions deploy |
| Optuna (hyperparameter tuning) | Prometheus + Grafana | OpenTelemetry tracing | LangSmith (LLM tracing) | CSS custom properties | AWS Secrets Manager |

Cross-reference: MLflow, Redis (ElastiCache), Evidently AI, and the Airflow DAG here are the exact same tools named with their monthly costs in [06-mlops.md](06-mlops.md). FastAPI, Nginx, and Postgres here are the same three backend components diagrammed in [08-scoring-service-architecture.md](08-scoring-service-architecture.md). LangChain, pgvector, and GPT-4o-mini here implement the RAG pipeline described in [07-llm-rag-layer.md](07-llm-rag-layer.md).

**Where Great Expectations fits:** it sits between ingestion and feature computation — `Airflow → Great Expectations → Feature Extraction` — validating the raw data 3A's pipeline pulls in ([03-data-architecture-and-schema.md](03-data-architecture-and-schema.md)) before any of Section 4's feature derivations run against it. It's the concrete tool behind 3A's "Validation" stage, not a separate concern.

**Configuration and secrets:** `Configuration → AWS Secrets Manager → Runtime`. API keys (OpenAI, database credentials, JWT signing keys) are injected into the running services at startup from Secrets Manager, not committed to config files or baked into container images — one sentence's worth of a rule, but worth stating rather than leaving implicit given how many credentials this stack actually has (LLM API key, DB connection strings, auth signing keys).

## Deployment pipeline & CI/CD (Section 11)

A single code push to `main` fans out into two parallel delivery tracks — the backend/model track and the browser-extension track. **These two tracks are independently releasable, not just parallel.** Backend v12 running against Extension v8 is a perfectly valid production state — the API contract in [08-scoring-service-architecture.md](08-scoring-service-architecture.md) is what makes that safe, and it's a direct consequence of that contract being stable that these two pipelines don't need to ship in lockstep. A backend fix doesn't wait for extension store review; an extension UI change doesn't wait for a backend deploy.

| Stage | Detail |
|---|---|
| 1. **Code push** (GitHub main) | Developer pushes → GitHub Actions triggers the workflow → full test suite runs |
| 2. **Test suite + promotion gate evaluation** (pytest) | Unit tests for feature engineering, integration tests for the API, extension end-to-end tests, and — for a model change — the full promotion gate from [05-ml-model-training.md](05-ml-model-training.md) (AUC, precision/recall, calibration, drift/schema compatibility), not just an isolated AUC number |
| 3. **Docker build** (ECR push) | Dockerfile builds the API + ML service, tags the image with the commit SHA, pushes to ECR |
| 4. **Staging deploy** (ECS Fargate) | Blue/green deploy to staging first, smoke tests run, then a load test at 1K leads |
| 5. **Model validate** (shadow test) | New model vs. old model at a limited traffic split — operational checks only (latency, errors, prediction/calibration stability); auto-provisional-promote or auto-rollback based on those, *not* on AUC (see below) |
| 6. **Prod deploy** (zero downtime) | ECS rolling update with health-check gates, a rollback threshold, and a Slack notification on completion. For a model change specifically: the Model Registry's version pointer updates, and the ML Model Service picks it up via the atomic-reload mechanism in [08-scoring-service-architecture.md](08-scoring-service-architecture.md) — deployment and runtime model-loading are the same mechanism, not two separate ones. |
| 7a. **Extension → store submit** | `webpack build` for all targets → Chrome Web Store, Firefox Add-ons, Edge Add-ons |
| 7b. **Safari → App Store** | `xcrun` convert → Xcode archive → App Store Connect → ~2 week Apple review |

Stage 2's promotion gate evaluation renaming reflects that this is no longer a single "model AUC check" — it's the full gate [05-ml-model-training.md](05-ml-model-training.md) defines, evaluated here as the CI enforcement point. Stage 5 is the CI/CD-level enforcement of the same shadow-test safety gate described in [06-mlops.md](06-mlops.md) — it's not a separate mechanism, it's this pipeline calling that mechanism automatically on every retrain. Note Stage 2's promotion-gate evaluation and Stage 5's shadow test are two different things: Stage 2 runs against the held-out historical test split (labels already exist) as part of the promotion criteria in [05-ml-model-training.md](05-ml-model-training.md); Stage 5's shadow test runs against live, unlabelled traffic and can only validate *operational* health, not accuracy — the actual business-metrics confirmation happens later, once real outcomes arrive, per 06-mlops.md's delayed Accuracy Tracker evaluation. Stages 7a/7b are the automated version of the manual store-submission steps walked through in [09-browser-extension.md](09-browser-extension.md).

This pipeline is what makes NFR8 ("monthly auto-retraining with zero-downtime deployment") from [02-requirements-and-use-cases.md](02-requirements-and-use-cases.md) an operational reality rather than a manual process — a model that fails its shadow test never even reaches provisional promotion, let alone Stage 6.

## Six contracts, converged

Looking back across Sections 3–9, this blueprint has converged on six stable contracts, each with today's implementation choice living in the tables above:

```
Data Contract (03) → Feature Contract (04) → Model Contract (05) → Service Contract (06)
      → API Contract (08) → Client Contract (09)
```

Section 10's job is exactly "here are today's implementation choices for each of those six" — Redis for the online feature cache, XGBoost for the model, MLflow for the registry, FastAPI for the API, GPT-4o-mini behind the LLM Adapter, a Manifest V3/compatibility-layer extension for the client. None of those tool choices are the architecture; the six contracts are. That's the separation this whole file has been building toward, and it's the reason a technology swap anywhere in the tables above is a Section 10 update, not a Sections 3–9 rewrite.
