"""Isolation Forest model for unsupervised anomaly detection in API logs"""

from typing import Any
from pathlib import Path
import joblib

import pandas as pd
from sklearn.ensemble import IsolationForest


class IsolationForestDetector:
    """Detect anomalous time windows using Isolation Forest"""

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float | str = "auto",
        max_features: float = 1.0,
        random_state: int = 42,
        n_jobs: int = -1,
    ) -> None:
        """Initialize the detector and configure its hyperparameters"""

        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            max_features=max_features,
            random_state=random_state,
            n_jobs=n_jobs,
        )
        self.is_fitted_ = False
        self.feature_names_: list[str] = []

    def fit(self, X: pd.DataFrame) -> "IsolationForestDetector":
        """Fit Isolation Forest on numerical features extracted from log windows"""

        self.feature_names_ = list(X.columns)
        self.model.fit(X)
        self.is_fitted_ = True

        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Predict whether each window is normal (1) or anomalous (-1)"""

        if not self.is_fitted_:
            raise RuntimeError("The detector must be fitted before making predictions.")

        predictions = self.model.predict(X)

        return pd.Series(predictions, index=X.index, name="anomaly_label")

    def decision_function(self, X: pd.DataFrame) -> pd.Series:
        """Return anomaly scores, where lower values indicate more anomalous samples."""
        if not self.is_fitted_:
            raise RuntimeError("The detector must be fitted before making predictions.")
        scores = self.model.decision_function(X)

        return pd.Series(
            scores,
            index=X.index,
            name="anomaly_score",
        )

    def detect_anomalies(self, X: pd.DataFrame) -> pd.DataFrame:
        """Return the input features with anomaly predictions and anomaly scores."""
        if not self.is_fitted_:
            raise RuntimeError("The detector must be fitted before making predictions.")

        results = X.copy()
        results["anomaly_label"] = self.model.predict(X)
        results["anomaly_score"] = self.model.decision_function(X)
        results["is_anomaly"] = results["anomaly_label"].eq(-1)

        return results

    def get_params(self) -> dict[str, Any]:
        """Return the detector's current hyperparameters."""
        return self.model.get_params(deep=False)

    def set_params(self, **params: Any) -> "IsolationForestDetector":
        """Update the detector's hyperparameters."""
                
        self.model.set_params(**params)
        self.feature_names_ = None
        self.is_fitted_ = False

        return self


    def save(self, path: str) -> None:
        """Persist the fitted detector to disk."""
        if not self.is_fitted_:
            raise RuntimeError("The detector must be fitted before making predictions.")

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(self, destination)

    @classmethod
    def load(cls, path: str) -> "IsolationForestDetector":
        """Load a previously saved detector from disk."""
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"No saved detector found at {source}")

        return joblib.load(source)
