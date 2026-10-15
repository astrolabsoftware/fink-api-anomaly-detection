# Fink API Forecasting & Anomaly Detection

A data-driven project focused on detecting anomalies and forecasting potential outages in the Fink API using log analysis and machine learning.

## Objectives

- Analyze the Nginx logs (the server in front of the API) and potentially the application logs from the API itself (Flask).
- Detect anomalous patterns.
- Identify potential indicators of API service interruptions or outages and send an alert to the operations team so they can intervene well before a failure occurs, by exploring forecasting methods. 

---
## Documentation

The `doc/` directory documents the problem definition, available data, and modeling methodology.

- [Problem Definition](doc/00_problem.md) : Defines the problem, research questions, operational objectives, and some evaluation principles.
- [Data Description](doc/01_data.md) : Describes the available logs, potential data sources, and limitations in term of data.

---

## Modeling Methodology

The [notebooks/](notebooks/) follow the methodology described gradually in the project documentation. They provide an experimental workflow covering data acquisition, preprocessing, exploration, feature engineering, baseline development, model (whether it beats or not the baseline) development and improvement,evaluation and analysis.

---

## Project Status

Early Research & development - data exploration and log pre-processing.