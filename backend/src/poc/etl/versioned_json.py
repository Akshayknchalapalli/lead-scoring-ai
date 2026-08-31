from __future__ import annotations

import json
from typing import Any

import pandas as pd


def _parse(cell: Any) -> dict | None:
    if not isinstance(cell, str):
        return None
    try:
        parsed = json.loads(cell)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def current_value(cell: Any) -> Any:
    """Return the value at the last key of a versioned-JSON cell, e.g.
    '{"1": "New", "2": "Pending"}' -> "Pending". Returns None for
    missing/malformed/empty cells."""
    parsed = _parse(cell)
    if not parsed:
        return None
    last_key = list(parsed.keys())[-1]
    return parsed[last_key]


def transition_count(cell: Any) -> int:
    """Number of versions recorded for this field. 0 for missing/malformed cells."""
    parsed = _parse(cell)
    if not parsed:
        return 0
    return len(parsed)


def success_count(cell: Any) -> int:
    """For ContactRecords-style cells mapping version -> 0/1 outcome, count the 1s."""
    parsed = _parse(cell)
    if not parsed:
        return 0
    return sum(1 for value in parsed.values() if value == 1 or value is True)


def current_value_series(series: pd.Series) -> pd.Series:
    return series.apply(current_value)


def transition_count_series(series: pd.Series) -> pd.Series:
    return series.apply(transition_count)
