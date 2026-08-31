from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from poc.config import load_poc_config
from poc.etl.features import build_features
from poc.etl.label import build_labels
from poc.etl.load_csv import load_raw
from poc.feature_spec import LABEL_COLUMN, TENANT_ID_COLUMN
from observability.logging import setup_logging

logger = logging.getLogger(__name__)


def build_dataset(config: dict, run_ts: pd.Timestamp | None = None) -> pd.DataFrame:
    run_ts = run_ts or pd.Timestamp.now(tz="UTC")

    raw = load_raw(config["csv_files"])
    features = build_features(raw, run_ts)
    labels = build_labels(raw)

    dataset = features.copy()
    dataset[LABEL_COLUMN] = labels.values
    # A single batch cutoff for every lead: this is a historical-snapshot pipeline, not a stream,
    # so there is one feature_cutoff_ts per run rather than one per event (see design.md §5).
    dataset["feature_cutoff_ts"] = run_ts.isoformat()

    data_dir = Path(config["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "processed_dataset.parquet"
    dataset.to_parquet(output_path, index=False)

    logger.info(
        "build_dataset: wrote %d rows, %d positive labels, tenants=%d, to %s",
        len(dataset),
        int(dataset[LABEL_COLUMN].sum()),
        dataset[TENANT_ID_COLUMN].nunique(),
        output_path,
    )
    return dataset


if __name__ == "__main__":
    config = load_poc_config()
    setup_logging(config)
    build_dataset(config)
