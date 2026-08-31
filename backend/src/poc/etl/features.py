from __future__ import annotations

import logging

import pandas as pd

from poc.etl.versioned_json import (
    current_value_series,
    success_count,
    transition_count_series,
)
from poc.feature_spec import (
    LEAD_ID_COLUMN,
    MODEL_FEATURES,
    PII_SOURCE_COLUMNS,
    TENANT_ID_COLUMN,
)

logger = logging.getLogger(__name__)


def _to_bool_int(value) -> int:
    return int(bool(value)) if value is not None else 0


def _clean_category(series: pd.Series, default: str = "unknown") -> pd.Series:
    """Fill both real nulls and the blank-string sentinel (`{"1": ""}`) the source data
    uses for "unset", so neither slips through as a literal empty category value."""
    return series.replace("", pd.NA).fillna(default).astype("category")


def build_features(df: pd.DataFrame, run_ts: pd.Timestamp) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out[LEAD_ID_COLUMN] = df["LeadId"]
    out[TENANT_ID_COLUMN] = df["TenantId"].astype("category")

    out["current_status"] = _clean_category(current_value_series(df["BaseLeadStatus"]))
    out["current_sub_status"] = _clean_category(current_value_series(df["SubLeadStatus"]))
    out["lead_source_code"] = _clean_category(
        current_value_series(df["LeadSource"]).fillna(-1).astype(str)
    )
    out["property_type"] = _clean_category(current_value_series(df["BasePropertyType"]))
    out["bhk_type"] = _clean_category(current_value_series(df["BHKType"]))
    out["sale_type"] = _clean_category(
        current_value_series(df["SaleType"]).fillna(-1).astype(str)
    )
    out["enquired_for"] = _clean_category(
        current_value_series(df["EnquiredFor"]).fillna(-1).astype(str)
    )
    out["enquired_city"] = _clean_category(current_value_series(df["EnquiredCity"]))

    out["status_transition_count"] = transition_count_series(df["BaseLeadStatus"])
    out["no_of_bhk"] = pd.to_numeric(current_value_series(df["NoOfBHK"]), errors="coerce").fillna(-1)
    out["lower_budget"] = pd.to_numeric(current_value_series(df["LowerBudget"]), errors="coerce").fillna(0)
    out["upper_budget"] = pd.to_numeric(current_value_series(df["UpperBudget"]), errors="coerce").fillna(0)
    out["contact_attempt_count"] = transition_count_series(df["ContactRecords"])
    out["contact_success_count"] = df["ContactRecords"].apply(success_count)
    out["share_count"] = pd.to_numeric(current_value_series(df["ShareCount"]), errors="coerce").fillna(0)

    created_at = pd.to_datetime(df["CreatedDate"], errors="coerce", utc=True)
    modified_at = pd.to_datetime(current_value_series(df["ModifiedDate"]), errors="coerce", utc=True)
    out["days_since_created"] = (run_ts - created_at).dt.total_seconds() / 86400
    out["days_since_modified"] = (run_ts - modified_at).dt.total_seconds() / 86400
    out["days_since_created"] = out["days_since_created"].fillna(out["days_since_created"].median())
    out["days_since_modified"] = out["days_since_modified"].fillna(out["days_since_modified"].median())

    out["is_picked"] = current_value_series(df["PickedDate"]).notna().astype(int)
    out["has_scheduled_meeting"] = current_value_series(df["ScheduledDate"]).notna().astype(int)
    out["is_meeting_done"] = current_value_series(df["IsMeetingDone"]).apply(_to_bool_int)
    out["is_site_visit_done"] = current_value_series(df["IsSiteVisitDone"]).apply(_to_bool_int)

    for column in PII_SOURCE_COLUMNS:
        assert column not in out.columns, f"PII column leaked into features: {column}"

    missing = set(MODEL_FEATURES) - set(out.columns)
    assert not missing, f"feature_spec.py declares features not built: {missing}"

    logger.info(
        "features: built %d features for %d leads, PII columns present=%s",
        len(MODEL_FEATURES),
        len(out),
        any(col in out.columns for col in PII_SOURCE_COLUMNS),
    )
    return out
