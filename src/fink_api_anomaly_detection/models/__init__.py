"""Models (ML/deep)anomaly detectors"""
from .ae import Autoencoder
from .isof import IsolationForestDetector

__all__ = ["Autoencoder", "IsolationForestDetector"]