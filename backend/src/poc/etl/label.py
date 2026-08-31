from __future__ import annotations

import logging

import pandas as pd

from poc.etl.versioned_json import current_value_series

logger = logging.getLogger(__name__)

# Current-status substrings (case-insensitive) that indicate a cancelled/reverted booking.
# Per FR-011/FR-019, a cancelled or reverted booking is non-converted unless a later valid
# booking occurred. This dataset only exposes the *current* (last) status per lead, not a full
# per-version timeline, so "later valid booking" cannot be reconstructed directly — instead, if
# the lead's current status is itself a cancellation/revert state, that is by definition the
# final outcome (no later valid booking exists), so it is excluded from the converted label even
# when a stale BookedDate/SoldPrice value remains from before the cancellation.
_CANCEL_STATUS_MARKERS = ("cancel", "revert")


def build_labels(df: pd.DataFrame) -> pd.Series:
    booked_date = current_value_series(df["BookedDate"])
    sold_price = pd.to_numeric(current_value_series(df["SoldPrice"]), errors="coerce")
    current_status = current_value_series(df["BaseLeadStatus"]).fillna("").str.lower()

    has_signal = booked_date.notna() | (sold_price > 0)
    is_cancelled = current_status.str.contains("|".join(_CANCEL_STATUS_MARKERS), regex=True)

    converted = has_signal & ~is_cancelled
    converted = converted.astype(int)

    logger.info(
        "label: %d positive labels out of %d (%.4f%%), %d excluded as cancelled/reverted",
        converted.sum(),
        len(converted),
        100 * converted.mean(),
        int((has_signal & is_cancelled).sum()),
    )
    return converted
