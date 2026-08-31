from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.entities import TenantScoringPolicy
from poc.api.deps import get_session

router = APIRouter(prefix="/poc", tags=["tenants"])


class ScoringPolicyUpdate(BaseModel):
    scoring_enabled: bool


@router.get("/tenants")
def list_tenants(session: Session = Depends(get_session)):
    policies = session.query(TenantScoringPolicy).all()
    return [
        {
            "tenant_id": policy.tenant_id,
            "scoring_enabled": policy.scoring_enabled,
            "threshold_cold_max": policy.threshold_cold_max,
            "threshold_hot_min": policy.threshold_hot_min,
        }
        for policy in policies
    ]


@router.patch("/tenants/{tenant_id}/scoring-policy")
def update_scoring_policy(
    tenant_id: str,
    update: ScoringPolicyUpdate,
    session: Session = Depends(get_session),
):
    policy = session.get(TenantScoringPolicy, tenant_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Tenant policy not found")
    policy.scoring_enabled = update.scoring_enabled
    session.commit()
    return {"tenant_id": tenant_id, "scoring_enabled": policy.scoring_enabled}
