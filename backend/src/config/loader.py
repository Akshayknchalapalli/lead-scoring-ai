from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"


def load_config(env: str) -> dict:
    if env not in ("dev", "prod"):
        raise ValueError(f"Invalid environment: {env}")

    config_path = CONFIG_DIR / f"{env}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML object")

    return data
