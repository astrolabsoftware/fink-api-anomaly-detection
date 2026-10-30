"""Operational threshold rules for anomaly detection."""

from dataclasses import dataclass, fields
import math
from numbers import Real

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_complex_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
)


@dataclass(frozen=True)
class OperationalThresholds:
    """Maximum values used by the operational threshold baseline.

    A rule is triggered when its feature value is strictly greater than its
    corresponding maximum. Rate thresholds must be between 0 and 1; all
    thresholds must be finite and non-negative.
    """

    http_5xx_rate_max: float
    http_4xx_rate_max: float
    request_count_max: float
    nginx_error_count_max: float

    def __post_init__(self) -> None:
        for threshold in fields(self):
            value = getattr(self, threshold.name)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError(f"{threshold.name} must be a number.")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{threshold.name} must be finite and non-negative.")

        if self.http_5xx_rate_max > 1:
            raise ValueError("http_5xx_rate_max must be between 0 and 1.")
        if self.http_4xx_rate_max > 1:
            raise ValueError("http_4xx_rate_max must be between 0 and 1.")


class OperationalThresholdBaseline:
    """Score feature data using explicit operational thresholds."""

    _FEATURE_COLUMNS = (
        "http_5xx_rate",
        "http_4xx_rate",
        "request_count",
        "nginx_error_count",
    )
    def __init__(self, thresholds: OperationalThresholds) -> None:
        if not isinstance(thresholds, OperationalThresholds):
            raise TypeError("thresholds must be an OperationalThresholds instance.")
        self.thresholds = thresholds

    def score(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return each index and the count of thresholds exceeded."""

        if data_df.empty:
            return pd.DataFrame(
                {
                    "anomaly_score": pd.Series(index=data_df.index, dtype="float64"),
                }
            )

        data = data_df.loc[:, self._FEATURE_COLUMNS]
        triggered_rules = pd.DataFrame(
            {
                "high_http_5xx_rate": (
                    data["http_5xx_rate"] > self.thresholds.http_5xx_rate_max
                ),
                "high_http_4xx_rate": (
                    data["http_4xx_rate"] > self.thresholds.http_4xx_rate_max
                ),
                "high_request_count": (
                    data["request_count"] > self.thresholds.request_count_max
                ),
                "high_nginx_error_count": (
                    data["nginx_error_count"] > self.thresholds.nginx_error_count_max
                ),
            }
        )

        return pd.DataFrame(
            {
                "anomaly_score": triggered_rules.sum(axis=1).astype("float64"),
            }
        )

    def predict(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """Return threshold-exceedance scores and decisions, indexed like the input."""

        result = self.score(data_df)
        result["is_anomaly"] = result["anomaly_score"] > 0
        return result[["anomaly_score", "is_anomaly"]]
