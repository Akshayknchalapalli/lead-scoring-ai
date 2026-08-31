from __future__ import annotations

from functools import lru_cache

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from poc.config import load_poc_config
from poc.feature_spec import MODEL_FEATURES
from poc.training.score_all import load_model, load_thresholds
from poc.training.split import load_dataset


@lru_cache(maxsize=1)
def get_config() -> dict:
    return load_poc_config()


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(get_config()["database_url"])


def get_session():
    session_factory = sessionmaker(bind=get_engine())
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@lru_cache(maxsize=1)
def get_model():
    return load_model(get_config())


@lru_cache(maxsize=1)
def get_thresholds():
    return load_thresholds(get_config())


@lru_cache(maxsize=1)
def get_feature_dataset():
    return load_dataset(get_config())


@lru_cache(maxsize=1)
def get_sorted_probabilities() -> np.ndarray:
    """The same scored population evaluate.py used to derive percentile thresholds.

    Used to turn a raw predicted probability (which is tiny and hard to read given the
    ~0.3% conversion rate) into a 0-100 percentile rank for display, e.g. "Lead Score: 87/100"
    instead of "0.0%".
    """
    dataset = get_feature_dataset()
    model = get_model()
    probabilities = model.predict_proba(dataset[MODEL_FEATURES])[:, 1]
    return np.sort(probabilities)
