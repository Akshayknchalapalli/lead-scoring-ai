from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from observability.logging import setup_logging
from poc.config import load_poc_config
from poc.feature_spec import (
    DISPLAY_ONLY_FEATURES,
    LEAD_ID_COLUMN,
    MODEL_FEATURES,
    TENANT_ID_COLUMN,
)
from poc.training.split import load_dataset

logger = logging.getLogger(__name__)


def load_model(config: dict) -> XGBClassifier:
    model_path = Path(config["model_dir"]) / f"model_{config['model_version']}.json"
    model = XGBClassifier(enable_categorical=True, tree_method="hist")
    model.load_model(str(model_path))
    return model


def load_thresholds(config: dict) -> dict:
    thresholds_path = Path(config["model_dir"]) / "thresholds.json"
    return json.loads(thresholds_path.read_text(encoding="utf-8"))


def categorize(probability: float, thresholds: dict) -> str:
    if probability >= thresholds["hot_min"]:
        return "hot"
    if probability >= thresholds["warm_min"]:
        return "warm"
    return "cold"


def percentile_rank(probability: float, sorted_probabilities: np.ndarray) -> int:
    """0-100 rank of `probability` against the full scored population.

    This is what actually drives Hot/Warm/Cold (see categorize()), so it's a far more readable
    number to show a user than the raw probability, which is tiny given the real conversion rate
    and rounds to "0.0%" for much of the Warm band.
    """
    rank = np.searchsorted(sorted_probabilities, probability, side="right")
    return int(round(rank / len(sorted_probabilities) * 100))


def score_all(config: dict) -> pd.DataFrame:
    dataset = load_dataset(config)
    model = load_model(config)
    thresholds = load_thresholds(config)

    probabilities = model.predict_proba(dataset[MODEL_FEATURES])[:, 1]

    result = dataset[[TENANT_ID_COLUMN, LEAD_ID_COLUMN] + DISPLAY_ONLY_FEATURES].copy()
    result["score_probability"] = probabilities
    result["score_category"] = [categorize(p, thresholds) for p in probabilities]
    result["model_version"] = config["model_version"]

    output_path = Path(config["model_dir"]) / "lead_scores.csv"
    result.to_csv(output_path, index=False)

    logger.info(
        "score_all: scored %d leads -> hot=%d warm=%d cold=%d, wrote %s",
        len(result),
        int((result["score_category"] == "hot").sum()),
        int((result["score_category"] == "warm").sum()),
        int((result["score_category"] == "cold").sum()),
        output_path,
    )
    return result


if __name__ == "__main__":
    config = load_poc_config()
    setup_logging(config)
    score_all(config)
