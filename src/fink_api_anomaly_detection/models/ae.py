"""
Autoencoder for anomaly detection.

The model learns to reconstruct candidate-normal traffic windows.
Anomaly detection is based on reconstruction Mean Squared Error (MSE).
"""

from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler


class Autoencoder:
    """Dense autoencoder for reconstruction-based anomaly detection"""

    def __init__(
        self,
        code_dim: int = 8,
        hidden_dims: Sequence[int] = (32, 16),
        optimizer: str = "adam",
        epochs: int = 100,
        batch_size: int = 32,
        patience: int = 10,
        random_state: int = 42,
        verbose: int = 0,
        checkpoint_path: str = "artifacts/ae/checkpoints/ae_best.weights.h5",
    ):

        self.code_dim = code_dim
        self.hidden_dims = tuple(hidden_dims)
        self.optimizer = optimizer
        self.epochs = epochs
        self.batch_size = batch_size
        self.patience = patience
        self.random_state = random_state
        self.verbose = verbose
        self.checkpoint_path = Path(checkpoint_path)

        self.model = None
        self.scaler = None
        self.feature_names_ = None
        self.history_ = None

    def _check_feature_order(self, X):
        """Check feature names and their order"""

        if self.feature_names_ is None:
            return

        if list(X.columns) != self.feature_names_:
            raise ValueError(
                "Feature names or order do not match training data.\n"
                f"Expected: {self.feature_names_}\n"
                f"Received: {list(X.columns)}"
            )

    def _check_is_fitted(self):
        """Check whether the model has been trained"""

        if self.model is None or self.scaler is None or self.feature_names_ is None:
            raise RuntimeError("Autoencoder has not been fitted or loaded.")

    def _build_model(self, n_features):
        """Build the dense autoencoder architecture"""

        try:
            import tensorflow as tf
            from tensorflow.keras import Model, layers
        except ImportError as exc:
            raise ImportError("TensorFlow installation is required.") from exc

        tf.keras.utils.set_random_seed(self.random_state)

        inputs = layers.Input(shape=(n_features,), name="input")

        # Encoder
        x = inputs
        for i, units in enumerate(self.hidden_dims):
            x = layers.Dense(units, activation="relu", name=f"encoder_{i + 1}")(x)

        # Bottleneck (code)
        latent = layers.Dense(self.code_dim, activation="relu", name="latent")(x)

        # Decoder
        x = latent
        for i, units in enumerate(reversed(self.hidden_dims)):
            x = layers.Dense(units, activation="relu", name=f"decoder_{i + 1}")(x)

        # Output layer
        outputs = layers.Dense(n_features, activation="linear", name="output")(x)

        model = Model(inputs=inputs, outputs=outputs, name="anomalydetection")
        model.compile(optimizer=self.optimizer, loss="mse")

        return model

    def fit(self, X, X_val=None):
        """
        Train the autoencoder.

        Parameters
        ----------
        X : DataFrame
            Candidate-normal training windows.

        X_val : DataFrame, optional
            Chronologically later candidate-normal validation windows.

        Returns
        -------
        self
        """

        from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

        self.feature_names_ = list(X.columns)

        # Fit scaler only on training data
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X.to_numpy(dtype=float))

        # Build autoencoder
        self.model = self._build_model(n_features=X_scaled.shape[1])

        # Create checkpoint directory
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                mode="min",
                patience=self.patience,
                restore_best_weights=True,
                verbose=self.verbose,
            ),
            ModelCheckpoint(
                filepath=str(self.checkpoint_path),
                monitor="val_loss",
                mode="min",
                save_best_only=True,
                save_weights_only=True,
                verbose=self.verbose,
            ),
        ]

        fit_kwargs = {}

        if X_val is not None:
            self._check_feature_order(X_val)

            if len(X_val) == 0:
                raise ValueError("Validation data cannot be empty.")

            X_val_scaled = self.scaler.transform(X_val.to_numpy(dtype=float))
            fit_kwargs["validation_data"] = (X_val_scaled, X_val_scaled)

        else:
            if len(X_scaled) < 5:
                raise ValueError("At least 5 training samples are required.")

            fit_kwargs["validation_split"] = 0.2

        # Autoencoder target = input
        self.history_ = self.model.fit(
            X_scaled, X_scaled,
            epochs=self.epochs,
            batch_size=self.batch_size,
            shuffle=(X_val is None),
            callbacks=callbacks,
            verbose=self.verbose,
            **fit_kwargs
        )

        # Reload best checkpoint
        self.model.load_weights(self.checkpoint_path)

        return self

    def decision_function(self, X):
        """
        Calculate reconstruction MSE for each observation.

        Higher values indicate more anomalous observations.
        """

        self._check_is_fitted()
        self._check_feature_order(X)

        X_scaled = self.scaler.transform(X.to_numpy(dtype=float))
        reconstructed = self.model.predict(X_scaled, verbose=0)

        errors = np.mean(np.square(X_scaled - reconstructed), axis=1)

        return pd.Series(errors, index=X.index, name="ae_score")

    def predict(self, X, threshold):
        """
        Predict anomalies using a user-defined threshold

        True : anomaly
        False : normal
        """

        scores = self.decision_function(X)
        predictions = scores > threshold

        return pd.Series(predictions, index=scores.index, name="is_anomaly")

    def save(self, path):
        """Save model, scaler and metadata."""

        self._check_is_fitted()

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        self.model.save(path / "autoencoder.keras")
        joblib.dump(self.scaler, path / "scaler.joblib")

        metadata = {
            "code_dim": self.code_dim,
            "hidden_dims": self.hidden_dims,
            "optimizer": self.optimizer,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "patience": self.patience,
            "random_state": self.random_state,
            "verbose": self.verbose,
            "feature_names": self.feature_names_,
            "checkpoint_path": str(self.checkpoint_path),
        }

        joblib.dump(metadata, path / "metadata.joblib")

    @classmethod
    def load(cls, path):
        """Load a previously saved autoencoder."""

        from tensorflow.keras.models import load_model

        path = Path(path)
        metadata = joblib.load(path / "metadata.joblib")

        instance = cls(
            code_dim=metadata["code_dim"],
            hidden_dims=metadata["hidden_dims"],
            optimizer=metadata["optimizer"],
            epochs=metadata["epochs"],
            batch_size=metadata["batch_size"],
            patience=metadata["patience"],
            random_state=metadata["random_state"],
            verbose=metadata["verbose"],
            checkpoint_path=metadata["checkpoint_path"],
        )

        instance.model = load_model(path / "autoencoder.keras")
        instance.scaler = joblib.load(path / "scaler.joblib")
        instance.feature_names_ = metadata["feature_names"]

        return instance