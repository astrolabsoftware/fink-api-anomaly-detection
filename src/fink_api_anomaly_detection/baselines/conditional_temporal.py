"""Conditional temporal reference anomaly detection."""

import math
from numbers import Real

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
)

_MAD_TO_STD = 1.4826


class ConditionalTemporalBaseline:
    """Score one feature against robust statistics for its time-of-day slot."""

    def __init__(self, feature: str, threshold: float = 3.5, context_minutes: int = 30) -> None:
        if not isinstance(feature, str) or not feature:
            raise ValueError("feature must be a non-empty string.")
        if ( isinstance(threshold, bool) or not isinstance(threshold, Real) or not math.isfinite(threshold)or threshold <= 0):
            raise ValueError("threshold must be a finite positive number.")
        if ( isinstance(context_minutes, bool) or not isinstance(context_minutes, int) or context_minutes <= 0 or 60 % context_minutes != 0):
            raise ValueError("context_minutes must be a positive divisor of 60.")

        self.feature = feature
        self.threshold = float(threshold)
        self.context_minutes = context_minutes
        self._context_statistics: dict[int, tuple[float, float]] | None = None

    def fit(self, reference_df: pd.DataFrame) -> "ConditionalTemporalBaseline":
        """Fit a median and MAD for each time-of-day context in the reference."""
        self._context_statistics = None
        data = reference_df.copy()
        if data.empty: raise ValueError("reference_df must contain at least one row.")

        contexts = self._context_slots(data["timestamp"])
        grouped_values = data[self.feature].groupby(contexts)
        medians = grouped_values.median()
        deviations = (data[self.feature] - contexts.map(medians)).abs()
        mads = deviations.groupby(contexts).median()
        self._context_statistics = {
            int(context): (float(medians[context]), float(mads[context]))
            for context in medians.index
        }

        if any(
            not math.isfinite(center) or not math.isfinite(mad)
            for center, mad in self._context_statistics.values()
        ):
            self._context_statistics = None
            raise ValueError(
                f"{self.feature} has a non-finite MAD in a reference context."
            )

        return self

    def score(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return timestamps and absolute, context-adjusted robust scores."""
        if self._context_statistics is None:
            raise ValueError("fit must be called with a valid reference period first.")

        data = data_df.copy()
        contexts = self._context_slots(data["timestamp"])
        missing_contexts = sorted(set(contexts).difference(self._context_statistics))
        if missing_contexts:
            descriptions = ", ".join(self._describe_context(context) for context in missing_contexts)
            raise ValueError("Reference period has no observations for time-of-day context(s): "+ descriptions)

        medians = contexts.map({context: stats[0] for context, stats in self._context_statistics.items()})
        mads = contexts.map({context: stats[1] for context, stats in self._context_statistics.items()})
        deviations = (data[self.feature] - medians).abs()
        zero_mad = mads == 0
        scores = (deviations / (_MAD_TO_STD * mads)).where(
            ~zero_mad,
            (deviations != 0).astype("float64") * (self.threshold + 1),
        )

        return pd.DataFrame(
            {
                "timestamp": data["timestamp"],
                "anomaly_score": scores.astype("float64"),
            }
        )

    def predict(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return timestamps, conditional scores, and anomaly decisions."""
        result = self.score(data_df)
        result["is_anomaly"] = result["anomaly_score"] > self.threshold
        return result[["timestamp", "anomaly_score", "is_anomaly"]]


    def _context_slots(self, timestamps: pd.Series) -> pd.Series:
        if timestamps.dt.tz is not None:
            timestamps = timestamps.dt.tz_convert("UTC")
        minutes_since_midnight = timestamps.dt.hour * 60 + timestamps.dt.minute
        return (minutes_since_midnight // self.context_minutes).astype("int64")

    def _describe_context(self, context: int) -> str:
        minutes = context * self.context_minutes
        hour, minute = divmod(minutes, 60)
        return f"{hour:02d}:{minute:02d}"
