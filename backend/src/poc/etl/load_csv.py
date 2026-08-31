from __future__ import annotations

import logging

import pandas as pd

from poc.etl.versioned_json import current_value_series

logger = logging.getLogger(__name__)


def load_raw(csv_files: list[str]) -> pd.DataFrame:
    frames = [pd.read_csv(path, low_memory=False) for path in csv_files]
    raw = pd.concat(frames, ignore_index=True)
    logger.info("load_csv: loaded %d files, %d raw rows", len(csv_files), len(raw))

    raw["_modified_at"] = pd.to_datetime(
        current_value_series(raw["ModifiedDate"]), errors="coerce", utc=True
    )
    raw = raw.sort_values("_modified_at", na_position="first")
    deduped = raw.drop_duplicates(subset="LeadId", keep="last").reset_index(drop=True)
    logger.info("load_csv: deduped to %d unique leads", len(deduped))

    return deduped
