import os

from config.loader import load_config

_CONFIG = None


def get_config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        env = os.getenv("APP_ENV", "dev").lower()
        if env not in ("dev", "prod"):
            raise ValueError(f"Invalid APP_ENV: {env}")
        _CONFIG = load_config(env)
    return _CONFIG
