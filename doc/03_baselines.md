# Statistical baselines for anomaly detection

## 1. Objective

We define 4 baseline methods to evaluate future anomaly detectors on Nginx logs. We will try to implement all these baselines with dedicated code. Each baseline is simple, reproducible, and independent of the detection model that will be studied later (whether or not it outperforms these baselines). The objective is therefore to measure whether a more elaborate method detects unusual behavior better than explainable statistical references. In the absence of incident/anomaly labels, the results describe the ability to detect atypical observations/outliers. The different baselines are:

| Baseline | Method | Type |
| --- | --- | --- |
| B1 | Operational rules and thresholds | Univariate, explicit rules |
| B2 | Classical Z-score | Univariate, parametric |
| B3 | Robust Z-score based on the median and MAD | Univariate, robust |
| B4 | Conditional temporal reference | Univariate, temporal context |

## 2. Baseline conventions

### 2.1 Input

Each baseline receives a temporal feature table built by the `03_feature_engineering.ipynb` pipeline.

Expected format: a `pandas.DataFrame` containing:

- a unique `timestamp` column, ordered chronologically;
- the numeric feature columns used by the method;

### 2.2 Output

Each baseline returns a table aligned with the input timestamps:

| Column | Type | Meaning |
| --- | --- | --- |
| `timestamp` | datetime | Window being analyzed |
| `anomaly_score` | float | The higher the score, the more atypical the window |
| `is_anomaly` | bool | Decision after applying the threshold |

### 2.3 Fitting and scoring

Methods that learn a reference follow this conceptual contract:

- `fit(reference_df)`: estimates parameters on the reference period;
- `score(data_df)`: calculates scores for a period to be evaluated;
- `predict(data_df, threshold)`: converts scores into decisions.

The reference period and the evaluation period must not overlap in the main experiment. Parameters learned on the reference remain fixed during evaluation, unless a separate experiment explicitly studies online adaptation.

## 3. Available features

The 23 current (+ Timestamps) features are grouped as follows:

- **Traffic:** `request_count`, `get_count`, `post_count`
- **HTTP reliability:** `http_4xx_count`, `http_5xx_count`, `http_4xx_rate`, `http_5xx_rate`
- **Clients:** `unique_client_count`
- **Volume:** `bytes_sent_sum`
- **Geography:** `unique_country_count`, `top_country_share`, `top_country_share_without_france`
- **Nginx errors:** `nginx_error_count`, `nginx_critical_count`, `nginx_timeout_count`, `nginx_connection_reset_count`, `nginx_broken_pipe_count`
- **Endpoints:** `endpoint_api_count`, `endpoint_unrecognized_count`, `unique_endpoint_count`
- **Temporal deltas:** `request_count_delta`, `http_5xx_rate_delta`, `nginx_error_count_delta`

The notebook (03) provides five feature subsets: `baseline` (9 features), `baseline_nginx` (14), `baseline_nginx_geography` (17), `baseline_nginx_geography_endpoints` (20), and `all` (23). B1-B4 use only the features relevant to them.

## 4. Baselines

### B1 - Operational rules and thresholds

**Principle.** Trigger an alert when at least one explicit rule is satisfied: high 5xx rate, abnormally high or low volume, high timeouts, nonzero critical errors, or high total number of Nginx errors.

The rules are combined with a logical OR:

$$
is\_anomaly_t = \bigvee_j \mathbb{1}[\text{rule}_j(X_t)]
$$

The shared score can be the maximum of the normalized scores for each rule or the number of triggered rules.

The implementation uses explicitly configured limits: maximum `http_5xx_rate`, minimum and maximum `request_count`, maximum `nginx_timeout_count`, and maximum `nginx_error_count`. Any nonzero `nginx_critical_count` triggers its own rule. Limits are exceeded strictly; a request count strictly below its minimum triggers the low-volume rule. The anomaly score is the number of triggered rules, and an observation is anomalous when that score is greater than zero. Configure and validate these limits before the evaluation period; the baseline does not learn or tune them on the data being scored.

**Limitations:** interpretable, but does not capture complex interactions well. Fixed thresholds can trigger during normal variations.

### B2 - Classical Z-score

**Principle.** Measure the deviation of a feature from its reference mean:

$$
z_t = \frac{x_t-\mu}{\sigma}, \qquad S_t=|z_t|
$$

where $\mu$ and $\sigma$ are estimated on the reference period. An initial two-sided threshold of `3` ($z_t>3$) can be tested, without considering it a guarantee of the false alert rate.

**Features to test:** test `request_count`, `http_5xx_count`, `http_5xx_rate`, and `nginx_error_count` separately.

**Edge case:** if `std` is zero or non-finite, for example, flag values that differ from the constant or declare the feature unusable. Do not silently produce infinite values.

**Limitations:** sensitive to extreme values in the reference; the mean and standard deviation may be unsuitable for asymmetric distributions.

### B3 - Robust Z-score (median and MAD)

**Principle.** Replace the mean and standard deviation with the median and the median absolute deviation (*Median Absolute Deviation*, MAD):

$$
m = \mathrm{median}(x), \quad MAD = \mathrm{median}(|x-m|)
$$

$$
z_t^{robuste} = \frac{0.6745(x_t-m)}{MAD}, \qquad S_t=|z_t^{robuste}|
$$

An initial threshold of `3.5` can be tested and then calibrated.

**Features:** the same univariate features as B2, to isolate the effect of the robust calculation.

**Edge case:** if the MAD is zero, for example, assign a zero score to values equal to the median and a high score to different values; keep the same rule in all experiments.

**Limitations:** does not correct for seasonality or temporal drift; discrete features can have a zero MAD.

### B4 - Conditional temporal reference

**Principle.** Compare an observation with the history of a comparable context rather than with a global mean. The context $C_t$ can represent the time slot or day of the week.

For the reference group $G(C_t)$, calculate a center $m(C_t)$ and a robust dispersion:

$$
S_t = \frac{|x_t-m(C_t)|}{1.4826\,MAD(C_t)}
$$

The factor `1.4826` converts the MAD into a robust estimate of the standard deviation under a normality assumption. If the dispersion is zero, apply the policy defined for B3.

**Comparison window:** with 5-minute windows, start with wider time slots, for example 30 or 60 minutes.

**Calibration:** learn parameters and thresholds on the reference only; an evaluated observation must not contribute to its own reference.

**Limitations:** depends on the amount of historical data and may handle special days poorly, such as lasting changes in traffic.

## 5. Evaluation protocol (unsupervised learning)

### 5.1 Temporal split

1. Split the reference (train) and evaluation (test) chronologically (temporally); do not randomly shuffle the windows.
2. Fit parameters on the reference only. Do not use the evaluation set to calculate means, medians, covariances, expected rates, or thresholds (avoid leakage).

### 5.2 Metrics to report

Without incident labels, precision, recall, or F1 cannot be presented as available metrics. At minimum, report:

- **Number and rate of alerted windows.**
- **Number of alert sequences**, with a predefined grouping rule.
- **Sequence duration**, total and median.
- **Temporal concentration**, by day and period.
- **Signal consistency**, with the features that explain the alerts.
- **Stability**, variation in scores and alert rate between reference periods.
- **Computational cost**, if relevant.


### 5.3 Evaluation with synthetic perturbations

Create copies of the windows and apply controlled perturbations without modifying the original data. Possible scenarios:

- spike or drop in `request_count`;
- increase in `http_5xx_count` and the corresponding rate;
- increase in `nginx_timeout_count`;
- gradual drift over several windows;
- combined anomaly through moderate variations in several features.

The modified windows are known by construction. Report the proportion detected, the detection delay for sequential perturbations, and alerts outside the perturbed windows, by type and intensity.

Preserve the constraints between features as much as possible: `http_5xx_count` must not exceed `request_count`,….

### 5.4 Interpretation

Without labels, the number of detected anomaly windows, response to synthetic perturbations, persistence of alerts, stability, and cost can be compared. These measures alone cannot support the conclusion that a method detects real incidents better. Later validation using known incidents, operational logs, or human review is necessary.

## 6. References

- NIST/SEMATECH, *e-Handbook of Statistical Methods*, “Detection of Outliers”: https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm
