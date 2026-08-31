from __future__ import annotations

import logging
from pathlib import Path

from xgboost import XGBClassifier

from observability.logging import setup_logging
from poc.config import load_poc_config
from poc.training.split import load_dataset, split_dataset

logger = logging.getLogger(__name__)


def train_model(config: dict) -> XGBClassifier:
    dataset = load_dataset(config)
    X_train, X_test, y_train, y_test = split_dataset(dataset)

    positive_count = int(y_train.sum())
    negative_count = int(len(y_train) - positive_count)
    scale_pos_weight = negative_count / positive_count if positive_count else 1.0

    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        tree_method="hist",
        enable_categorical=True,
        eval_metric="auc",
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    model_dir = Path(config["model_dir"])
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"model_{config['model_version']}.json"
    model.save_model(str(model_path))

    logger.info(
        "train: fit on %d rows (%d positive / %d negative, scale_pos_weight=%.1f), saved to %s",
        len(X_train),
        positive_count,
        negative_count,
        scale_pos_weight,
        model_path,
    )
    return model


if __name__ == "__main__":
    config = load_poc_config()
    setup_logging(config)
    train_model(config)
