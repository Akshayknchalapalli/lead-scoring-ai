from pathlib import Path
import os

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from interview_demo.agent import run_agent

app = FastAPI(title="Lead Advisor — Interview Demo")
router = APIRouter(prefix="/demo", tags=["interview advisor"])
EVIDENCE_DIR = Path(os.getenv("DEMO_EVIDENCE_DIR", "artifacts/demo-runs"))

class RunRequest(BaseModel):
    tenant_id: str = Field(default="demo-a", min_length=1, max_length=80)
    lead_id: str = Field(default="hot-1", min_length=1, max_length=80)
    request: str = Field(default="Explain the next step", max_length=1000)

@router.post("/run")
def run(body: RunRequest):
    return run_agent(body.tenant_id, body.lead_id, body.request, evidence_dir=EVIDENCE_DIR)

@router.get("", response_class=HTMLResponse)
def home():
    return (Path(__file__).with_name("index.html")).read_text(encoding="utf-8")


app.include_router(router)
app.add_api_route("/", home, response_class=HTMLResponse, include_in_schema=False)
