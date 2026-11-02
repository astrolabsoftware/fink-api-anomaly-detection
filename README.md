# Fink API Forecasting & Anomaly Detection

A data-driven project focused on detecting anomalies and forecasting potential outages in the Fink API using Nginx **log/system-log** analysis and machine learning.

## Objectives

Analyze `Nginx logs` (the server in front of the Fink API) and, where available, `system logs` (from node-exporter) and the `API Flask application logs` to **detect anomalous patterns with `anomaly-detection` methods and identify potential indicators of service interruptions or outages**, by exploring `forecasting` methods to alert the ops team early enough to intervene before a failure occurs.

---
## Documentation

The `doc/` directory documents the problem definition, available data, and modeling methodology.

- [Problem Definition](doc/00_problem.md) : Defines the problem, research questions, operational objectives, and some evaluation principles.
- [Data Description](doc/01_data.md) : Describes the available logs, potential data sources, and limitations in term of data.
- [Feature Engineering Strategy](doc/02_feature_engineering_strategy.md) : Feature Engineering Strategy (doc) for Fink API anomaly detection and forecasting.
- [Baselines definition](doc/03_baselines.md) : Defines the statistical baselines for anomaly detection.
- [Candidate machine/deep-learning models](doc/04_models.md): describes candidate ml/dl models to compare with the statistical baselines.

---

## Modeling Methodology

The [notebooks/](notebooks/) follow the methodology described gradually in the project documentation. They provide an experimental workflow covering data acquisition, preprocessing, exploration, feature engineering, baseline development, model (whether it beats or not the baseline) development and improvement,evaluation and analysis.

---

## setup 

requires-python = ">=3.13,<3.14"

## Project Status

Research & development - think about an app to deploy (FastApi OR api) for inference