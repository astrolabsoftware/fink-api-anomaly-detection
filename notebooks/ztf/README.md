# Notebooks for data exploring, analysis and modeling methodology - ztf.api.fink-portal

In the notebooks in this folder, we aim to explore the data, perform analyses, detect useful patterns, identify one or more baselines, and finally demonstrate model training and evaluation.

## Notebooks

- [01 - Raw Data Exploration](01_raw_data_exploration.ipynb): Understand the dataset structure and available log sources, inspect the number, size, distribution of files, examine representative samples from each log category.
- [02 - Log Parsing, Preprocessing, data exploration & features selection](02_log_parsing_preprocessing_exploration.ipynb): Explore parsed logs, storage in dataframes, exploring data patterns in each category of logs, assess data quality, and select relevant features for our probleme (anomaly detection).
- [03 - Feature Engineering](03_feature_enginering.ipynb): Parse the three Nginx log sources, build and validate the 5-minute temporal features, and prepare the experiment feature subsets.
- [04 - Baselines evaluation](04_baselines_evaluation.ipynb): Here we test some baselines (statistical methods) for anomaly detections .
- [05 - Isolation forest model evaluation](05_isoforest_model.ipynb): Here we test a ML Model: Isolation forest for anomaly detections .
- [06 - deep learning model evaluation](06_autoencoder_model.ipynb): autoencoder-based anomaly detection.
- [07 - Autoencoder inference](07_autoencoder_inference_test.ipynb): Run inference with the trained autoencoder.

