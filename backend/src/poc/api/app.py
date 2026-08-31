from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from observability.logging import setup_logging
from poc.api import lead_routes, tenant_routes
from poc.config import load_poc_config

REPO_ROOT = Path(__file__).resolve().parents[4]
UI_DIR = REPO_ROOT / "ui" / "poc"


def create_app() -> FastAPI:
    setup_logging(load_poc_config())

    app = FastAPI(title="Lead Scoring POC")
    app.include_router(lead_routes.router)
    app.include_router(tenant_routes.router)

    if UI_DIR.exists():
        app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")

    return app


app = create_app()
