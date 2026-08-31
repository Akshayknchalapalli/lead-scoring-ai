from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from sklearn.metrics import precision_recall_curve, roc_auc_score
from xgboost import XGBClassifier

from observability.logging import setup_logging
from poc.config import load_poc_config
from poc.feature_spec import MODEL_FEATURES
from poc.training.split import load_dataset, split_dataset

logger = logging.getLogger(__name__)


def _load_model(config: dict) -> XGBClassifier:
    model_path = Path(config["model_dir"]) / f"model_{config['model_version']}.json"
    model = XGBClassifier(enable_categorical=True, tree_method="hist")
    model.load_model(str(model_path))
    return model


def evaluate(config: dict) -> dict:
    dataset = load_dataset(config)
    _, X_test, _, y_test = split_dataset(dataset)
    model = _load_model(config)

    test_probabilities = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, test_probabilities)

    precision, recall, thresholds_pr = precision_recall_curve(y_test, test_probabilities)
    f1_scores = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros_like(precision),
        where=(precision + recall) > 0,
    )
    best_idx = int(np.argmax(f1_scores))
    best_precision = float(precision[best_idx])
    best_recall = float(recall[best_idx])

    all_probabilities = model.predict_proba(dataset[MODEL_FEATURES])[:, 1]
    hot_min = float(np.quantile(all_probabilities, config["hot_percentile"]))
    warm_min = float(np.quantile(all_probabilities, config["warm_percentile"]))

    hot_count = int((all_probabilities >= hot_min).sum())
    warm_count = int(((all_probabilities >= warm_min) & (all_probabilities < hot_min)).sum())
    cold_count = int(len(all_probabilities) - hot_count - warm_count)

    metrics = {
        "model_version": config["model_version"],
        "auc": auc,
        "test_rows": len(X_test),
        "test_positive": int(y_test.sum()),
        "best_f1_precision": best_precision,
        "best_f1_recall": best_recall,
        "category_counts": {"hot": hot_count, "warm": warm_count, "cold": cold_count},
    }
    thresholds = {
        "model_version": config["model_version"],
        "hot_min": hot_min,
        "warm_min": warm_min,
        "hot_percentile": config["hot_percentile"],
        "warm_percentile": config["warm_percentile"],
    }

    model_dir = Path(config["model_dir"])
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (model_dir / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")

    logger.info(
        "evaluate: AUC=%.4f, best-F1 precision=%.3f recall=%.3f, "
        "categories hot=%d warm=%d cold=%d, thresholds hot_min=%.4f warm_min=%.4f",
        auc,
        best_precision,
        best_recall,
        hot_count,
        warm_count,
        cold_count,
        hot_min,
        warm_min,
    )
    return metrics


if __name__ == "__main__":
    config = load_poc_config()
    setup_logging(config)
    evaluate(config)
