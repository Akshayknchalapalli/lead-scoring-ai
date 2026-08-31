from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.entities import Lead, LeadScore, TenantScoringPolicy
from poc.api.deps import (
    get_feature_dataset,
    get_model,
    get_session,
    get_sorted_probabilities,
    get_thresholds,
)
from poc.training.explain import explain_lead
from poc.training.score_all import percentile_rank

router = APIRouter(prefix="/poc", tags=["leads"])


def _scoring_enabled(session: Session, tenant_id: str) -> bool:
    policy = session.get(TenantScoringPolicy, tenant_id)
    return bool(policy and policy.scoring_enabled)


def _lead_score(probability, sorted_probabilities) -> int | None:
    if probability is None:
        return None
    return percentile_rank(float(probability), sorted_probabilities)


@router.get("/leads")
def list_leads(
    tenant_id: str = Query(...),
    limit: int = Query(200, ge=1, le=2000),
    session: Session = Depends(get_session),
):
    enabled = _scoring_enabled(session, tenant_id)

    rows = session.execute(
        select(Lead.lead_id, LeadScore.score_probability, LeadScore.score_category)
        .join(
            LeadScore,
            (LeadScore.tenant_id == Lead.tenant_id) & (LeadScore.lead_id == Lead.lead_id),
            isouter=True,
        )
        .where(Lead.tenant_id == tenant_id)
        .order_by(LeadScore.score_probability.desc())
        .limit(limit)
    ).all()

    sorted_probabilities = get_sorted_probabilities()
    leads = [
        {
            "lead_id": lead_id,
            "score_probability": float(probability) if enabled and probability is not None else None,
            "score_category": category.value if enabled and category is not None else None,
            "lead_score": _lead_score(probability, sorted_probabilities) if enabled else None,
        }
        for lead_id, probability, category in rows
    ]
    return {"tenant_id": tenant_id, "scoring_enabled": enabled, "leads": leads}


@router.get("/leads/{lead_id}/score")
def get_lead_score(
    lead_id: str,
    tenant_id: str = Query(...),
    session: Session = Depends(get_session),
):
    if not _scoring_enabled(session, tenant_id):
        raise HTTPException(status_code=404, detail="Scoring is disabled for this tenant")

    score = session.execute(
        select(LeadScore)
        .where(LeadScore.tenant_id == tenant_id, LeadScore.lead_id == lead_id)
        .order_by(LeadScore.score_ts.desc())
        .limit(1)
    ).scalar_one_or_none()
    if score is None:
        raise HTTPException(status_code=404, detail="Lead score not found")

    return {
        "lead_id": lead_id,
        "tenant_id": tenant_id,
        "score_probability": score.score_probability,
        "score_category": score.score_category.value,
        "lead_score": _lead_score(score.score_probability, get_sorted_probabilities()),
        "model_version": score.model_version,
        "score_ts": score.score_ts.isoformat(),
        "is_stale": score.is_stale,
    }


@router.post("/leads/{lead_id}/explain")
def explain(
    lead_id: str,
    tenant_id: str = Query(...),
    session: Session = Depends(get_session),
):
    if not _scoring_enabled(session, tenant_id):
        raise HTTPException(status_code=404, detail="Scoring is disabled for this tenant")

    try:
        return explain_lead(
            get_model(),
            get_thresholds(),
            get_feature_dataset(),
            tenant_id,
            lead_id,
            get_sorted_probabilities(),
        )
    except LookupError:
        return {
            "summary": "Explanation is not available for this lead right now.",
            "top_signals": [],
            "recommended_action": "Use standard follow-up guidance until more data is available.",
        }
