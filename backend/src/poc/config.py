from __future__ import annotations

from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[2]
POC_CONFIG_PATH = BACKEND_DIR / "config" / "poc.yaml"


def load_poc_config(config_path: Path | None = None) -> dict:
    path = config_path or POC_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"POC config file not found: {path}")

    with path.open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)

    if not isinstance(data, dict):
        raise ValueError("POC config file must contain a YAML object")

    data["data_dir"] = str((BACKEND_DIR / data["data_dir"]).resolve())
    data["model_dir"] = str((BACKEND_DIR / data["model_dir"]).resolve())
    if data["database_url"].startswith("sqlite:///"):
        relative_path = data["database_url"].removeprefix("sqlite:///")
        absolute_path = (BACKEND_DIR / relative_path).resolve()
        data["database_url"] = f"sqlite:///{absolute_path.as_posix()}"

    return data
