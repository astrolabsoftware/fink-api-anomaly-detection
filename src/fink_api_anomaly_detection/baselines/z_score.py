"""Classical univariate Z-score anomaly detection."""

import math
from numbers import Real

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
)


class ClassicalZScoreBaseline:
    """Score one feature by its absolute Z-score from a fitted reference period."""

    def __init__(self, feature: str, threshold: float = 3.0) -> None:
        if not isinstance(feature, str) or not feature:
            raise ValueError("feature must be a non-empty string.")
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, Real)
            or not math.isfinite(threshold)
            or threshold <= 0
        ):
            raise ValueError("threshold must be a finite positive number.")

        self.feature = feature
        self.threshold = float(threshold)
        self._mean: float | None = None
        self._std: float | None = None

    def fit(self, reference_df: pd.DataFrame) -> "ClassicalZScoreBaseline":
        """Estimate the feature mean and population standard deviation."""
        data = reference_df.copy()
        if data.empty:
            raise ValueError("reference_df must contain at least one row.")

        values = data[self.feature]
        self._mean = float(values.mean())
        self._std = float(values.std(ddof=0))
        if not math.isfinite(self._std):
            self._mean = None
            self._std = None
            raise ValueError(
                f"{self.feature} has a non-finite standard deviation "
                "in the reference period."
            )
        return self

    def score(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return timestamps and absolute Z-scores for the fitted feature."""
        if self._mean is None or self._std is None:
            raise ValueError("fit must be called with a valid reference period first.")

        data = data_df.copy()
        if self._std == 0:
            scores = (data[self.feature] != self._mean).astype("float64") * (self.threshold + 1)
        else:
            scores = ((data[self.feature] - self._mean) / self._std).abs()
            
        return pd.DataFrame(
            {
                "anomaly_score": scores.reset_index(drop=True).astype("float64"),
            }
        )

    def predict(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return timestamps, absolute Z-scores, and threshold decisions."""
        result = self.score(data_df)
        result["is_anomaly"] = result["anomaly_score"] > self.threshold
        return result[[ "anomaly_score", "is_anomaly"]]
