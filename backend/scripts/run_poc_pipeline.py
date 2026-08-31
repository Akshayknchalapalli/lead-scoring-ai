from __future__ import annotations

import logging

from observability.logging import setup_logging
from poc.config import load_poc_config
from poc.db.seed import seed_database
from poc.etl.build_dataset import build_dataset
from poc.training.evaluate import evaluate
from poc.training.train import train_model

logger = logging.getLogger(__name__)


def run() -> None:
    config = load_poc_config()
    setup_logging(config)

    logger.info("run_poc_pipeline: starting full run (ETL -> train -> evaluate -> score -> seed)")
    build_dataset(config)
    train_model(config)
    evaluate(config)
    seed_database(config)  # scores every lead internally before seeding
    logger.info("run_poc_pipeline: complete")


if __name__ == "__main__":
    run()
