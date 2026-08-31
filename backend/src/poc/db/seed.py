from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.entities import (
    Base,
    Lead,
    LeadFeatureSnapshot,
    LeadLifecycleState,
    LeadScore,
    ModelScope,
    ModelStatus,
    ModelVersion,
    ScoreCategory,
    TenantScoringPolicy,
)
from observability.logging import setup_logging
from poc.config import load_poc_config
from poc.feature_spec import LEAD_ID_COLUMN, MODEL_FEATURES, TENANT_ID_COLUMN
from poc.training.score_all import score_all
from poc.training.split import load_dataset

logger = logging.getLogger(__name__)

_CATEGORY_MAP = {
    "cold": ScoreCategory.COLD,
    "warm": ScoreCategory.WARM,
    "hot": ScoreCategory.HOT,
}


def _json_safe(value):
    return value.item() if hasattr(value, "item") else value


def _clear_existing(session: Session) -> None:
    session.query(LeadScore).delete()
    session.query(LeadFeatureSnapshot).delete()
    session.query(TenantScoringPolicy).delete()
    session.query(ModelVersion).delete()
    session.query(Lead).delete()
    session.commit()


def seed_database(config: dict) -> None:
    dataset = load_dataset(config)
    scores_df = score_all(config)

    feature_cutoff_ts = pd.to_datetime(dataset["feature_cutoff_ts"].iloc[0], utc=True).to_pydatetime()
    metrics = json.loads((Path(config["model_dir"]) / "metrics.json").read_text(encoding="utf-8"))
    thresholds = json.loads((Path(config["model_dir"]) / "thresholds.json").read_text(encoding="utf-8"))

    by_lead = dataset.set_index(LEAD_ID_COLUMN)
    feature_records = {
        lead_id: {col: _json_safe(value) for col, value in row.items()}
        for lead_id, row in by_lead[MODEL_FEATURES].to_dict(orient="index").items()
    }
    days_since_created = by_lead["days_since_created"]
    days_since_modified = by_lead["days_since_modified"]

    engine = create_engine(config["database_url"])
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        _clear_existing(session)

        session.add(
            ModelVersion(
                model_version=config["model_version"],
                model_scope=ModelScope.GLOBAL,
                scope_key=None,
                trained_at=feature_cutoff_ts,
                status=ModelStatus.ACTIVE,
                training_window={"cutoff": feature_cutoff_ts.isoformat()},
                metrics=metrics,
                artifact_uri=str(Path(config["model_dir"]) / f"model_{config['model_version']}.json"),
            )
        )
        for tenant_id in config["top_tenants"]:
            session.add(
                TenantScoringPolicy(
                    tenant_id=tenant_id,
                    scoring_enabled=True,
                    threshold_cold_max=thresholds["warm_min"],
                    threshold_hot_min=thresholds["hot_min"],
                    override_enabled=False,
                    policy_version=config["model_version"],
                )
            )
        session.commit()

        lead_rows = []
        snapshot_rows = []
        score_rows = []
        for row in scores_df.itertuples(index=False):
            tenant_id = getattr(row, TENANT_ID_COLUMN)
            lead_id = getattr(row, LEAD_ID_COLUMN)
            created_at = feature_cutoff_ts - timedelta(days=float(days_since_created.get(lead_id, 0)))
            updated_at = feature_cutoff_ts - timedelta(days=float(days_since_modified.get(lead_id, 0)))

            lead_rows.append(
                Lead(
                    tenant_id=tenant_id,
                    lead_id=lead_id,
                    lifecycle_state=LeadLifecycleState.OPEN,
                    current_score_ts=feature_cutoff_ts,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
            snapshot_rows.append(
                LeadFeatureSnapshot(
                    tenant_id=tenant_id,
                    lead_id=lead_id,
                    feature_cutoff_ts=feature_cutoff_ts,
                    feature_vector=feature_records.get(lead_id, {}),
                    feature_schema_version=config["model_version"],
                    is_leakage_validated=True,
                )
            )
            score_rows.append(
                LeadScore(
                    tenant_id=tenant_id,
                    lead_id=lead_id,
                    score_probability=float(row.score_probability),
                    score_category=_CATEGORY_MAP[row.score_category],
                    threshold_policy_version=config["model_version"],
                    score_ts=feature_cutoff_ts,
                    model_version=config["model_version"],
                    feature_cutoff_ts=feature_cutoff_ts,
                    is_cold_start=False,
                    is_stale=False,
                    staleness_seconds=0,
                )
            )

        session.bulk_save_objects(lead_rows)
        session.commit()
        session.bulk_save_objects(snapshot_rows)
        session.commit()
        session.bulk_save_objects(score_rows)
        session.commit()

    logger.info(
        "seed: wrote %d leads, %d feature snapshots, %d scores, %d tenant policies to %s",
        len(lead_rows),
        len(snapshot_rows),
        len(score_rows),
        len(config["top_tenants"]),
        config["database_url"],
    )


if __name__ == "__main__":
    config = load_poc_config()
    setup_logging(config)
    seed_database(config)
