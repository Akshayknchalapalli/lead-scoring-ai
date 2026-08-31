from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xgboost as xgb

from poc.config import load_poc_config
from poc.feature_spec import LEAD_ID_COLUMN, MODEL_FEATURES, TENANT_ID_COLUMN
from poc.training.score_all import categorize, load_model, load_thresholds, percentile_rank
from poc.training.split import load_dataset

logger = logging.getLogger(__name__)

TOP_N_SIGNALS = 3

_DEFAULT_ACTIONS = {
    "hot": "Prioritize immediate outreach — this lead shows strong intent signals.",
    "warm": "Follow up within 24-48 hours to keep momentum.",
    "cold": "Add to the nurture sequence; revisit if engagement increases.",
}

_FEATURE_ACTION_HINTS = {
    "has_scheduled_meeting": "A meeting is already scheduled — confirm details and prepare for it.",
    "is_site_visit_done": "A site visit has been completed — follow up on their decision.",
    "is_picked": "This lead hasn't been contacted yet — reach out promptly.",
    "is_meeting_done": "A meeting has taken place — send a personalized follow-up.",
    "status_transition_count": "This lead has had frequent status changes — review recent notes before contacting.",
    "contact_success_count": "Previous contact attempts succeeded — continue the conversation.",
}


def _recommended_action(category: str, top_feature: str) -> str:
    base = _DEFAULT_ACTIONS[category]
    hint = _FEATURE_ACTION_HINTS.get(top_feature)
    return f"{base} {hint}" if hint else base


# Each builder turns a raw (value, contributed-positively) pair into a business-readable
# sentence — the engineered feature name and number never surface directly in the UI.
def _status_transition_count(value, positive):
    count = int(value)
    if positive:
        return (
            f"This lead has progressed through multiple sales stages ({count} status "
            "transitions), indicating sustained engagement."
        )
    return (
        f"This lead has seen little movement through the sales stages so far ({count} status "
        "transitions), suggesting limited progress."
    )


def _contact_attempt_count(value, positive):
    count = int(value)
    if positive:
        return (
            f"The sales team has engaged with this lead multiple times ({count} contact "
            "attempts), suggesting ongoing interaction."
        )
    return f"This lead has only been contacted {count} time(s) so far, suggesting limited outreach."


def _contact_success_count(value, positive):
    count = int(value)
    if positive:
        return (
            f"The sales team has successfully connected with this lead {count} time(s), "
            "a sign of a responsive, engaged prospect."
        )
    return (
        f"Successful contact with this lead has been rare so far ({count} time(s)), "
        "which may indicate low responsiveness."
    )



# Boolean templates always account for both the raw value (what happened) AND the
# contribution direction (how it's affecting THIS lead's score) — a feature can contribute
# negatively even when "present" due to interactions with other features, and asserting
# "strong positive signal" regardless of direction produces contradictory-sounding
# explanations (e.g. a COLD lead described by a seemingly strong positive signal).
def _has_scheduled_meeting(value, positive):
    if value:
        if positive:
            return "A meeting has already been scheduled with this lead, a strong signal of buying intent."
        return "A meeting has been scheduled with this lead, though other factors are currently outweighing that signal."
    if positive:
        return "No meeting is scheduled yet, but other signals are still keeping this lead's score up."
    return "No meeting has been scheduled with this lead yet, which is limiting its score."


def _is_meeting_done(value, positive):
    if value:
        if positive:
            return "This lead has already had a meeting, a strong indicator of serious interest."
        return "This lead has had a meeting, though other factors are currently pulling its score down."
    if positive:
        return "This lead hasn't had a meeting yet, but other signals are still supporting a positive score."
    return "This lead has not yet had a meeting, which typically correlates with lower intent."


def _is_site_visit_done(value, positive):
    if value:
        if positive:
            return "This lead has completed a site visit, one of the strongest signals of purchase intent."
        return "This lead completed a site visit, though other factors are currently outweighing that signal."
    if positive:
        return "This lead hasn't completed a site visit yet, but other signals are still supporting a positive score."
    return "This lead has not completed a site visit yet, a stage most converting leads pass through."


def _is_picked(value, positive):
    if value:
        if positive:
            return "This lead has been picked up and is being actively worked by an agent."
        return "This lead has been picked up, though other factors are currently pulling its score down."
    if positive:
        return "This lead hasn't been picked up yet, but other signals are still supporting a positive score."
    return "This lead has not yet been picked up by an agent, which may be delaying engagement."


def _tenant_id(value, positive):
    trend = "stronger" if positive else "weaker"
    return f"This lead belongs to the '{value}' portfolio, which historically shows {trend} conversion performance."


def _lead_source_code(value, positive):
    trend = "higher" if positive else "lower"
    return f"This lead came through source channel '{value}', which tends to bring in {trend}-intent leads."


def _property_type(value, positive):
    trend = "more" if positive else "less"
    return f"This lead is enquiring about {value} property, a category that converts {trend} often historically."


def _enquired_city(value, positive):
    trend = "stronger" if positive else "weaker"
    return f"This lead is enquiring in {value}, a location with a {trend} conversion history."


def _bhk_type(value, positive):
    qualifier = "common" if positive else "less common"
    return f"This lead's preferred configuration ({value}) is {qualifier} among converting leads."


def _no_of_bhk(value, positive):
    trend = "aligns with" if positive else "is atypical for"
    return f"This lead is enquiring about a {int(value)}-BHK property, which {trend} typical converting leads."


def _sale_type(value, positive):
    trend = "more" if positive else "less"
    return f"This lead's sale type ({value}) converts {trend} often historically."


def _enquired_for(value, positive):
    trend = "more" if positive else "less"
    return f"This lead's enquiry type ({value}) converts {trend} often historically."


def _budget_signal(label):
    def _builder(value, positive):
        trend = "aligning with stronger buying intent" if positive else "which is atypical for converting leads"
        return f"This lead's {label} is {value:,.0f}, {trend}."

    return _builder


def _days_since_created(value, positive):
    days = int(value)
    if positive:
        return f"This lead was created {days} days ago — its age fits the typical pattern of converting leads."
    return f"This lead was created {days} days ago, longer than most converting leads typically take to close."


def _days_since_modified(value, positive):
    days = int(value)
    if positive:
        return f"This lead was last updated {days} days ago, suggesting relatively recent activity."
    return f"This lead hasn't been updated in {days} days, suggesting it may be going cold."


def _share_count(value, positive):
    count = int(value)
    if positive:
        return f"This lead has been shared internally {count} time(s), suggesting team interest."
    return f"This lead has rarely been shared internally ({count} time(s) so far)."


def _default_signal(feature, value, positive):
    direction = "increased" if positive else "decreased"
    return f"{feature.replace('_', ' ')} ({value}) {direction} this lead's score."


_SIGNAL_BUILDERS = {
    "status_transition_count": _status_transition_count,
    "contact_attempt_count": _contact_attempt_count,
    "contact_success_count": _contact_success_count,
    "has_scheduled_meeting": _has_scheduled_meeting,
    "is_meeting_done": _is_meeting_done,
    "is_site_visit_done": _is_site_visit_done,
    "is_picked": _is_picked,
    "tenant_id": _tenant_id,
    "lead_source_code": _lead_source_code,
    "property_type": _property_type,
    "enquired_city": _enquired_city,
    "bhk_type": _bhk_type,
    "no_of_bhk": _no_of_bhk,
    "sale_type": _sale_type,
    "enquired_for": _enquired_for,
    "lower_budget": _budget_signal("lower stated budget"),
    "upper_budget": _budget_signal("upper stated budget"),
    "days_since_created": _days_since_created,
    "days_since_modified": _days_since_modified,
    "share_count": _share_count,
}


def _build_signal(feature: str, value, positive: bool) -> str:
    builder = _SIGNAL_BUILDERS.get(feature)
    if builder:
        return builder(value, positive)
    return _default_signal(feature, value, positive)


def explain_lead(
    model,
    thresholds: dict,
    dataset: pd.DataFrame,
    tenant_id: str,
    lead_id: str,
    sorted_probabilities: np.ndarray | None = None,
) -> dict:
    mask = (dataset[TENANT_ID_COLUMN] == tenant_id) & (dataset[LEAD_ID_COLUMN] == lead_id)
    row = dataset.loc[mask, MODEL_FEATURES]
    if row.empty:
        raise LookupError(f"lead not found: tenant={tenant_id} lead={lead_id}")

    probability = float(model.predict_proba(row)[0, 1])
    category = categorize(probability, thresholds)

    booster = model.get_booster()
    dmatrix = xgb.DMatrix(row, enable_categorical=True)
    contributions = booster.predict(dmatrix, pred_contribs=True)[0][:-1]  # drop bias term

    ranked = sorted(
        zip(MODEL_FEATURES, contributions), key=lambda pair: abs(pair[1]), reverse=True
    )
    top_signals = [
        _build_signal(feature, row.iloc[0][feature], contribution > 0)
        for feature, contribution in ranked[:TOP_N_SIGNALS]
    ]

    if sorted_probabilities is not None:
        rank = percentile_rank(probability, sorted_probabilities)
        if rank >= 50:
            top_percent = max(1, 100 - rank)
            headline = f"scored in the top {top_percent}% of leads"
        else:
            headline = f"scored higher than {rank}% of leads"
    else:
        headline = f"{probability:.1%} predicted conversion likelihood"

    top_feature = ranked[0][0]
    summary = f"This lead is scored {category.upper()} ({headline}). {top_signals[0]}"

    return {
        "summary": summary,
        "top_signals": top_signals,
        "recommended_action": _recommended_action(category, top_feature),
    }


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    config = load_poc_config()
    dataset = load_dataset(config)
    model = load_model(config)
    thresholds = load_thresholds(config)
    sorted_probabilities = np.sort(model.predict_proba(dataset[MODEL_FEATURES])[:, 1])
    sample = dataset.iloc[0]
    result = explain_lead(
        model,
        thresholds,
        dataset,
        sample[TENANT_ID_COLUMN],
        sample[LEAD_ID_COLUMN],
        sorted_probabilities,
    )
    for key, value in result.items():
        print(f"{key}: {value}")
