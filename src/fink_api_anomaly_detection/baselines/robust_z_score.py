"""Robust univariate Z-score anomaly detection."""

import math
from numbers import Real

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_numeric_dtype,
)

_NORMAL_SCALE = 0.6745


class RobustZScoreBaseline:
    """Score one feature by its median and median absolute deviation."""

    def __init__(self, feature: str, threshold: float = 3.5) -> None:
        if not isinstance(feature, str) or not feature:
            raise ValueError("feature must be a non-empty string.")
        if (isinstance(threshold, bool) or not isinstance(threshold, Real) or not math.isfinite(threshold) or threshold <= 0):
            raise ValueError("threshold must be a finite positive number.")

        self.feature = feature
        self.threshold = float(threshold)
        self._median: float | None = None
        self._mad: float | None = None

    def fit(self, reference_df: pd.DataFrame) -> "RobustZScoreBaseline":
        """Estimate the feature median and median absolute deviation."""
        data = reference_df.copy()
        if data.empty: raise ValueError("reference_df must contain at least one row.")

        values = data[self.feature]
        self._median = float(values.median())
        self._mad = float((values - self._median).abs().median())
        if not math.isfinite(self._mad):
            self._median = None
            self._mad = None
            raise ValueError(
                f"{self.feature} has a non-finite MAD in the reference period."
            )
        return self

    def score(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return timestamps and absolute robust Z-scores."""
        
        if self._median is None or self._mad is None:
            raise ValueError("fit must be called with a valid reference period first.")

        data = data_df.copy()
        if self._mad == 0:
            scores = (data[self.feature] != self._median).astype("float64") * (
                self.threshold + 1
            )
        else:
            scores = (
                _NORMAL_SCALE * (data[self.feature] - self._median) / self._mad
            ).abs()

        return pd.DataFrame(
            {
                "timestamp": data["timestamp"].reset_index(drop=True),
                "anomaly_score": scores.reset_index(drop=True).astype("float64"),
            }
        )

    def predict(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return timestamps, robust Z-scores, and threshold decisions."""
        result = self.score(data_df)
        result["is_anomaly"] = result["anomaly_score"] > self.threshold
        return result[["timestamp", "anomaly_score", "is_anomaly"]]