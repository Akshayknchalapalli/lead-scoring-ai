from __future__ import annotations

LEAD_ID_COLUMN = "lead_id"
TENANT_ID_COLUMN = "tenant_id"
LABEL_COLUMN = "converted"

NUMERIC_FEATURES = [
    "status_transition_count",
    "no_of_bhk",
    "lower_budget",
    "upper_budget",
    "contact_attempt_count",
    "contact_success_count",
    "days_since_created",
    "days_since_modified",
    "share_count",
]

BOOLEAN_FEATURES = [
    "is_picked",
    "has_scheduled_meeting",
    "is_meeting_done",
    "is_site_visit_done",
]

CATEGORICAL_FEATURES = [
    TENANT_ID_COLUMN,
    "lead_source_code",
    "property_type",
    "bhk_type",
    "sale_type",
    "enquired_for",
    "enquired_city",
]

# Built by features.py and useful for API/UI display, but NOT fed to the model: the lead's
# current status text is derived from (and near-synonymous with, e.g. "Booked"/"Invoiced") the
# same BaseLeadStatus field the conversion label is built from. Including it as a model input
# is target leakage in disguise, not a real predictive signal (see poc/data-findings.md).
DISPLAY_ONLY_FEATURES = [
    "current_status",
    "current_sub_status",
]

MODEL_FEATURES = NUMERIC_FEATURES + BOOLEAN_FEATURES + CATEGORICAL_FEATURES

# Raw source columns that must never appear in the feature table or explanation text (POC-FR-010).
PII_SOURCE_COLUMNS = [
    "Name",
    "Email",
    "ContactNo",
    "AlternateContactNo",
    "ReferralContactNo",
    "ReferralName",
    "ReferralEmail",
    "LandLine",
    "DateOfBirth",
    "ConfidentialNotes",
    "Notes",
]
