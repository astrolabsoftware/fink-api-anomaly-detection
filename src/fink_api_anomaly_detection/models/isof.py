"""Isolation Forest model for unsupervised anomaly detection in API logs"""

from typing import Any
from pathlib import Path
import inspect
import joblib
from datetime import datetime, timezone

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
        self.metadata_ = None 
        self.n_samples_fit_ = None 

    def fit(self, X: pd.DataFrame) -> "IsolationForestDetector":
        """Fit Isolation Forest on numerical features extracted from log windows"""

        self.feature_names_ = list(X.columns)
        self.model.fit(X)
        self.is_fitted_ = True
        self.n_samples_fit_ = X.shape[0]

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
        self.n_samples_fit_ = None

        return self

    def save(self, path: str | Path) -> None:
        """Save the fitted model and its metadata to disk."""
        if not self.is_fitted_:
            raise RuntimeError("The detector must be fitted before saving.")

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        artifact = {
            "model": self.model,
            "is_fitted": self.is_fitted_,
            "feature_names": self.feature_names_,
            "hyperparameters": self.get_params(),
            "n_features": len(self.feature_names_),
            "n_training_samples": int(self.n_samples_fit_),
            "training_date_utc": datetime.now(timezone.utc).isoformat(),
        }

        joblib.dump(artifact, destination)


    @classmethod
    def load(cls, path: str | Path) -> "IsolationForestDetector":
        """Load the fitted model and its metadata from disk."""
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"No saved detector found at {source}")

        artifact = joblib.load(source)

        signature = inspect.signature(cls.__init__)
        valid_params = set(signature.parameters) - {"self"}

        hyperparameters = {
            key: value
            for key, value in artifact["hyperparameters"].items()
            if key in valid_params
        }

        detector = cls(**hyperparameters)
        detector.model = artifact["model"]
        detector.is_fitted_ = artifact["is_fitted"]
        detector.feature_names_ = artifact["feature_names"]
        detector.metadata_ = {
            key: value
            for key, value in artifact.items()
            if key not in {"model", "is_fitted", "feature_names"}
        }

        return detector