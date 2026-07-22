from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKeyConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Index, Integer, PrimaryKeyConstraint, String, UniqueConstraint, desc
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LeadLifecycleState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ModelScope(str, Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    SEGMENT = "segment"


class ModelStatus(str, Enum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"
    RETIRED = "retired"


class ScoreCategory(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class Lead(Base):
    __tablename__ = "leads"

    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    lead_id: Mapped[str] = mapped_column(String, nullable=False)
    lifecycle_state: Mapped[LeadLifecycleState] = mapped_column(
        SQLEnum(
            LeadLifecycleState,
            name="lead_lifecycle_state",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    current_score_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "lead_id"),
    )


class LeadEvent(Base):
    __tablename__ = "lead_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    lead_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    event_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    event_version: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.lead_id"],
            name="fk_lead_events_lead",
        ),
        Index("ix_lead_events_tenant_lead_event_ts", "tenant_id", "lead_id", "event_ts"),
    )


class LeadFeatureSnapshot(Base):
    __tablename__ = "lead_feature_snapshots"

    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    lead_id: Mapped[str] = mapped_column(String, nullable=False)
    feature_cutoff_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feature_vector: Mapped[dict] = mapped_column(JSON, nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String, nullable=False)
    is_leakage_validated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feature_snapshot_ref: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "lead_id", "feature_cutoff_ts"),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.lead_id"],
            name="fk_feature_snapshots_lead",
        ),
        Index(
            "ix_feature_snapshots_tenant_lead_cutoff_desc",
            "tenant_id",
            "lead_id",
            desc("feature_cutoff_ts"),
        ),
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    model_version: Mapped[str] = mapped_column(String, primary_key=True)
    model_scope: Mapped[ModelScope] = mapped_column(
        SQLEnum(
            ModelScope,
            name="model_scope",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    scope_key: Mapped[str | None] = mapped_column(String)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ModelStatus] = mapped_column(
        SQLEnum(
            ModelStatus,
            name="model_status",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    training_window: Mapped[dict] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(model_scope = 'global' AND scope_key IS NULL) OR "
            "(model_scope IN ('tenant', 'segment') AND scope_key IS NOT NULL)",
            name="ck_model_versions_scope_key",
        ),
        Index(
            "ix_model_versions_scope_scope_key",
            "model_scope",
            "scope_key",
        ),
        Index(
            "uq_model_versions_active_per_scope",
            "model_scope",
            "scope_key",
            unique=True,
            postgresql_where=(status == "active"),
        ),
    )


class LeadScore(Base):
    __tablename__ = "lead_scores"

    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    lead_id: Mapped[str] = mapped_column(String, nullable=False)
    score_probability: Mapped[float] = mapped_column(Float, nullable=False)
    score_category: Mapped[ScoreCategory] = mapped_column(
        SQLEnum(
            ScoreCategory,
            name="score_category",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    threshold_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    score_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    feature_cutoff_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feature_snapshot_ref: Mapped[str | None] = mapped_column(String)
    is_cold_start: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False)
    staleness_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "lead_id",
            "feature_cutoff_ts",
            "model_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.lead_id"],
            name="fk_lead_scores_lead",
        ),
        ForeignKeyConstraint(
            ["model_version"],
            ["model_versions.model_version"],
            name="fk_lead_scores_model_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id", "feature_cutoff_ts"],
            [
                "lead_feature_snapshots.tenant_id",
                "lead_feature_snapshots.lead_id",
                "lead_feature_snapshots.feature_cutoff_ts",
            ],
            name="fk_lead_scores_feature_snapshot",
        ),
        CheckConstraint(
            "score_probability >= 0.0 AND score_probability <= 1.0",
            name="ck_lead_scores_probability_range",
        ),
        Index("ix_lead_scores_tenant_lead", "tenant_id", "lead_id"),
        Index(
            "ix_lead_scores_tenant_lead_score_ts_desc",
            "tenant_id",
            "lead_id",
            desc("score_ts"),
        ),
        Index("ix_lead_scores_tenant_score_ts_desc", "tenant_id", desc("score_ts")),
        Index("ix_lead_scores_tenant_stale_score_ts", "tenant_id", "is_stale", "score_ts"),
    )

    def __repr__(self) -> str:
        return (
            f"<LeadScore tenant={self.tenant_id} lead={self.lead_id} "
            f"score={self.score_probability}>"
        )


class TenantScoringPolicy(Base):
    __tablename__ = "tenant_scoring_policies"

    tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    scoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    threshold_cold_max: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_hot_min: Mapped[float] = mapped_column(Float, nullable=False)
    override_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "threshold_cold_max < threshold_hot_min",
            name="ck_tenant_scoring_policy_threshold_order",
        ),
    )


class ScoreExplanation(Base):
    __tablename__ = "score_explanations"

    explanation_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    lead_id: Mapped[str] = mapped_column(String, nullable=False)
    score_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    top_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.lead_id"],
            name="fk_score_explanations_lead",
        ),
        UniqueConstraint(
            "tenant_id",
            "lead_id",
            "score_ts",
            name="uq_score_explanations_tenant_lead_score_ts",
        ),
    )
