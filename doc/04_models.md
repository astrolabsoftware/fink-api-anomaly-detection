# Machine-learning models for anomaly detection

This document describes candidate machine-learning models to compare with the statistical baselines in [03_baselines.md](./03_baselines.md).

---

## 1. Isolation Forest

Isolation Forest is an unsupervised anomaly detection method for tabular data. It identifies observations that are easier to isolate from the rest of the data. It is a candidate for detecting unusual combinations of Nginx features
that independent univariate baselines may not identify.

### Principle

The method builds an ensemble of isolation trees. Each tree repeatedly **selects a feature and a split value** (between the min and max of that feature) at random, partitioning the observations until a window is isolated or a stopping condition is reached. An observation isolated in fewer splits than typical observations is considered more anomalous.

The anomaly score is based on the **average path length across the trees**: shorter average paths indicate greater anomaly. Implementations may expose scores with different signs or conventions. For comparisons in this project, the reported `anomaly_score` must consistently increase with anomaly.

### Proposed application to this project

- Treat each timestamped 5-minute window as one observation.
- Use numeric features from the feature table in notebook 03; evaluate feature subsets separately where useful, rather than assuming that including every feature improves detection.
- Exclude `timestamp` from the model input. Preserve it to align each score and decision with its original window.
- Fit the model on the chronological reference period only. Score the later evaluation period without refitting on it.
- Return one anomaly score per evaluation window and a binary decision derived from a threshold calibrated using the reference period only.

### Parameters to evaluate (from sklearn.sklearn.ensemble.IsolationForest)

The experiment should record the selected values and rationale for:

- **n_estimators**: Number of trees (more = better, slower)
- **contamination**:(helps calibrate threshold) Expected % of anomalies -- % unkonwn with unlabled data 
- **max_samples**: # of samples used per tree (default = 'auto')
- **Subsample size:** controls the number of observations considered by each
- **Random seed:** should be fixed for reproducibility


### Strengths and limitations

**Potential strengths**

- Uses several features jointly and can detect multivariate outliers.
- Does not require anomaly labels during fitting.
- Tree-based splits generally do not require feature standardization solely to
  put numeric variables on a common scale.

**Limitations**

- Does not use temporal order, so a window's context and recurring daily
  patterns are not modeled explicitly.
- Results depend on the selected features, hyperparameters, random seed, and
  threshold.
- Correlated, redundant, or differently distributed features can affect which
  observations are isolated.

### Evaluation protocol

Use the chronological reference/evaluation split described in [03_baselines.md](./03_baselines.md).Compare Isolation Forest with B1-B4 using the same windows and relevant feature sets. Report the existing alert-volume, alert-sequence, duration, temporal concentration, and signal-consistency measures, as well as the chosen
parameters.

Evaluate sensitivity with controlled synthetic perturbations, such as isolated
spikes or drops, gradual drift, and coordinated changes in related features.
Record detection of the perturbed windows and alerts outside them. Preserve
logical constraints between related features when constructing perturbations.

---



# References 

1- Isolation forest (sklearn implemntation) [doc](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)