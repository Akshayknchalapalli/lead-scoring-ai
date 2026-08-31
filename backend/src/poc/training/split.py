from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from poc.feature_spec import LABEL_COLUMN, MODEL_FEATURES

RANDOM_STATE = 42
TEST_SIZE = 0.2


def load_dataset(config: dict) -> pd.DataFrame:
    path = Path(config["data_dir"]) / "processed_dataset.parquet"
    return pd.read_parquet(path)


def split_dataset(dataset: pd.DataFrame):
    X = dataset[MODEL_FEATURES]
    y = dataset[LABEL_COLUMN]
    return train_test_split(X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE)
