# Feature Engineering Strategy for Fink API Anomaly Detection and Forecasting

## Objective

Based on the exploratory data analysis conducted in [`02_log_parsing_preprocessing_exploration.ipynb`](../notebooks/02_log_parsing_preprocessing_exploration.ipynb) and the review of existing research on web logs, anomaly detection, and failure prediction, the main principle is to **transform raw logs (now carefully stored in DataFrames) into a temporal representation of API behaviour rather than feeding raw log entries directly into a model**.

Three types of phenomena are relevant to Fink API:

| Phenomenon | Examples investigated in the logs | Objective |
|---|---|---|
| Traffic anomalies | Sudden increases or decreases in request volume, changes in the number of clients | Detect unusual traffic patterns and outliers |
| Reliability anomalies | Increased HTTP 5xx rates, timeouts, interrupted connections | Detect potential service degradation |
| Potential failure precursors | Increasing error counts, rising timeout frequency, sustained traffic changes | Investigate whether failures can be anticipated |

The third category is the most relevant to forecasting, but also the most difficult to validate. An anomaly does not necessarily indicate a failure, and a failure may occur without a detectable precursor in the available logs. At this stage, the dataset contains no labelled incidents that would allow us to reliably train and evaluate a failure prediction model. The initial objective is therefore to build features suitable for **anomaly detection and degradation analysis**, while preparing for future forecasting experiments. Integrating additional observability data, such as system metrics collected through Node Exporter and application logs from the Flask API, could improve our ability to identify failure precursors.

---

## From Raw Logs to Temporal Features

Each access log entry represents an HTTP request, while each Nginx error log entry represents a recorded server side event. These entries must be aggregated into time windows to describe the API's state over time. For the first implementation, we propose using **5-minute windows**. Each row of the resulting dataset will represent one time window, with features describing traffic, HTTP reliability, client activity, geographical distribution, endpoints, and Nginx errors.The features will be calculated independently from the access, geo, and error DataFrames, then merged using their timestamps.

### Choosing the Time Window

5 minutes is the initial working hypothesis, not a final decision.

| Window | Advantage | Limitation |
|---|---|---|
| 1 minute | Captures rapid changes | More noise, particularly in sparse error events |
| 5 minutes | Balances responsiveness and stability | May smooth out short incidents |
| 15 minutes | Produces more stable aggregates | May detect incidents later or hide brief events |

I will compare these three granularities using the same feature definitions and evaluation approach.


### Features groups

Each feature takes a value over the 5-minute window. The groups of features that we are going to construct are as follows:

**Group A - Traffic**

| Feature | Description |
|---|---|
| `request_count` | Total number of HTTP requests |
| `get_count` | Number of GET requests |
| `post_count` | Number of POST requests |


**Group B - HTTP reliability**

| Feature | Description |
|---|---|
| `http_4xx_count` | Number of HTTP 4xx responses (client side errors) |
| `http_5xx_count` | Number of HTTP 5xx responses (server side errors) |
| `http_4xx_rate` | Proportion of requests returning a 4xx response |
| `http_5xx_rate` | Proportion of requests returning a 5xx response |

why rate & count ? because counts capture the absolute volume of errors, while rates measure their relative importance compared with total traffic.

**Group C - Client activity**

| Feature | Description |
|---|---|
| `unique_client_count` | Number of distinct client IPs observed during the window |


**Group D - Response volume**

| Feature | Description |
|---|---|
| `bytes_sent_sum` | Total number of response bytes sent during the window |

This feature provides an indicator of the volume of data served by the API.

**Group E - Geographical distribution**

| Feature | Description |
|---|---|
| `unique_country_count` | Number of distinct countries represented in the requests |
| `top_country_share` | Proportion of requests originating from the most represented country |
| `top_country_share_without_france` | Proportion of non-France requests originating from the most represented non-France country |

These features describe changes in the geographical distribution of traffic. They are exploratory indicators and should only be retained (after testing) if they provide useful information for the anomaly detection.

**Group F - Nginx errors**

| Feature | Description |
|---|---|
| `nginx_error_count` | Total number of Nginx error log entries |
| `nginx_critical_count` | Number of critical (crit) level entries |
| `nginx_timeout_count` | Number of timeout related entries |
| `nginx_connection_reset_count` | Number of connection reset events |
| `nginx_broken_pipe_count` | Number of broken pipe events |

These features describe server side errors independently of HTTP response codes. Error categories is derived from the available error fields, such as `error_level`, `error_code`, and `error_message`.

**Group G - Endpoint activity**

| Feature | Description |
|---|---|
| `endpoint_api_count` | Number of requests to `/api/v1/*` |
| `endpoint_unrecognized_count` | Number of requests to endpoints outside `/api/v1/*` |
| `unique_endpoint_count` | Number of distinct endpoints requested during the window |

These features help distinguish normal API traffic from requests to unexpected or less common paths, which may indicate unusual activity or automated probing.

**Group H - features for temporal changes**

| Feature | Description |
|---|---|
| `request_count_delta` | Difference in request count compared with the previous window |
| `http_5xx_rate_delta` | Difference in HTTP 5xx rate compared with the previous window |
| `nginx_error_count_delta` | Difference in Nginx error count compared with the previous window |

For each delta, the calculation is: `Delta x_t = x_t - x_{t-1}`. These features capture changes in API behaviour rather than only its current state. A positive value indicates an increase, while a negative value indicates a decrease.

---

## Example of the Final Temporal Dataset

**#features =**23 (with timestamp = 24)

After aggregating the three DataFrames independently and merging the results by time window, the dataset will contain one row per 5-minute interval. The following table illustrates the proposed structure. **All values are illustrative.**

| timestamp | request_count | get_count | post_count | http_4xx_count | http_5xx_count | http_4xx_rate | http_5xx_rate | unique_client_count | bytes_sent_sum | unique_country_count | top_country_share | top_country_share_without_france | nginx_error_count | nginx_critical_count | nginx_timeout_count | nginx_connection_reset_count | nginx_broken_pipe_count | endpoint_api_count | endpoint_unrecognized_count | unique_endpoint_count | request_count_delta | http_5xx_rate_delta | nginx_error_count_delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10:00 | 420 | 30 | 390 | 12 | 3 | 0.0286 | 0.0071 | 35 | 8400000 | 8 | 0.42 | 0.55 | 1 | 0 | 0 | 1 | 0 | 390 | 30 | 45 | 20 | 0.0021 | 0 |
| 10:05 | 510 | 38 | 472 | 18 | 6 | 0.0353 | 0.0118 | 42 | 9100000 | 9 | 0.39 | 0.49 | 4 | 1 | 1 | 2 | 1 | 475 | 35 | 51 | 90 | 0.0047 | 3 |
| 10:10 | 1250 | 82 | 1168 | 45 | 106 | 0.0360 | 0.0848 | 68 | 21000000 | 14 | 0.31 | 0.38 | 17 | 3 | 6 | 5 | 3 | 1150 | 100 | 88 | 740 | 0.0730 | 13 |
| 10:15 | 390 | 27 | 363 | 8 | 2 | 0.0205 | 0.0051 | 31 | 7800000 | 7 | 0.45 | 0.58 | 0 | 0 | 0 | 0 | 0 | 360 | 30 | 39 | -860 | -0.0797 | -17 |
| 10:20 | 405 | 29 | 376 | 9 | 2 | 0.0222 | 0.0049 | 33 | 8000000 | 8 | 0.43 | 0.54 | 1 | 0 | 0 | 1 | 0 | 375 | 30 | 41 | 15 | -0.0002 | 1 |

#### Details (for features implemntation)

- Rates are represented as proportions between 0 and 1. For example, `0.01` corresponds to 1%.
- Delta features are calculated after aggregating the underlying features and sorting the data chronologically. 
- Windows without HTTP requests or Nginx errors must remain in the dataset. Missing event counts in these windows should be set to 0 where appropriate.
- Nginx error features are calculated independently from the error logs. An Nginx error does not necessarily correspond to an HTTP 5xx response.
- `endpoint_unrecognized_count` counts requests to endpoints outside `/api/v1/*`. The term *unrecognized* refers to paths outside the expected API prefix; it does not automatically mean that these requests are invalid or malicious.
- `endpoint_api_count` and `endpoint_unrecognized_count` should sum to `request_count` when every request has a classifiable endpoint. Requests with missing endpoints must be counted as unrecognized.
- `unique_endpoint_count` counts all distinct endpoints requested during each window, including endpoints inside and outside `/api/v1/*`.
- `top_country_share` is calculated as the number of requests from the most represented country divided by the total number of requests with available country information in that window. 
- `top_country_share_without_france` uses only requests with available country information outside France; it is 0 when no such requests exist.
- The 3 log sources must be aggregated independently and then merged using their time-window timestamps. **The DataFrames must not be joined row by row.**
- All temporal calculations must use past and current observations only. Future information must not be used to calculate features intended for real time anomaly detection or forecasting.

---

## Feature Selection Strategy and Evaluation

We have complete temporal dataset `df` containing 23 technical features, and `timestamp`, which will serve as the temporal index. Rather than using all features from the beginning, we will start with a compact baseline. We will then progressively add other feature groups to evaluate their impact on anomaly detection performance. The objective is to identify which features provide useful information and whether adding/removing features improves the results.

### Comparing Feature Subsets

We will compare the following configurations:

1. **Baseline:** Traffic, reliability, client activity, and response volume.
2. **Baseline + Nginx errors:** Add server-side error indicators.
3. **Baseline + Nginx errors + geography:** Add geographical distribution indicators.
4. **Baseline + Nginx errors + geography + endpoints:** Add endpoint activity indicators.
5. **All features:** Add temporal-change indicators to the previous configuration.

the feature subsets will be defined as follows:
``` 
traffic_ft = ["request_count", "get_count", "post_count"]

reliability_ft = ["http_4xx_count", "http_5xx_count", "http_4xx_rate", "http_5xx_rate"]

client_volume_ft = ["unique_client_count", "bytes_sent_sum"]

nginx_ft = ["nginx_error_count", "nginx_critical_count", "nginx_timeout_count", "nginx_connection_reset_count", "nginx_broken_pipe_count"]

geography_ft = ["unique_country_count", "top_country_share", "top_country_share_without_france"]

endpoint_ft = ["endpoint_api_count", "endpoint_unrecognized_count", "unique_endpoint_count"]

temporal_ft = ["request_count_delta", "http_5xx_rate_delta", "nginx_error_count_delta"]

# Baseline
b_ft = traffic_ft + reliability_ft + client_volume_ft

# Baseline + Nginx errors
bn_ft = b_ft + nginx_ft

# Baseline + Nginx errors + geographical features
bng_ft = bn_ft + geography_ft

# Baseline + Nginx errors + geographical features + endpoint features
bnge_ft = bng_ft + endpoint_ft

# All features (23)
all_ft = bnge_ft + temporal_ft

df_b = df[b_ft].copy()
df_bn = df[bn_ft].copy()
df_bng = df[bng_ft].copy()
df_bnge = df[bnge_ft].copy()
df_all = df[all_ft].copy()
```

The implementation is available through the `features` package:

```python
from src.fink_api_anomaly_detection.features import (
    build_feature_subsets,
    build_temporal_features,
)

df = build_temporal_features(access_df, geo_df, errors_df)
feature_sets = build_feature_subsets(df)
```

The three arguments are the DataFrames returned by the access-, geo-, and
error-log preprocessing functions. The result contains `timestamp` and the 23
features above, with one UTC row for every 5-minute (modifiable in src code) interval between the
earliest and latest timestamp in the input data. Intervals without events are
retained with zero-valued aggregates; the first temporal deltas are zero
because there is no previous window. `build_feature_subsets` returns the five
documented experiment configurations as separate DataFrames, without the
`timestamp` column. These configurations will be evaluated using the same model and evaluation procedure to isolate the contribution of each feature group. We will then repeat the comparisons across different baseline/models. Since the dataset does not contain labelled incidents, evaluation will focus on the consistency and interpretability of detected anomalies. 

---
## Other possible experiences - Comparing Current Behaviour with Recent History

After evaluating the initial feature sets, I will investigate additional features that compare the current window with recent observations.

Possible indicators include:

- The mean of the previous six windows.
- The median of the previous six windows.
- The difference between the current value and the historical median.

These features can be useful for detecting deviations from recent behaviour. However, **all historical reference values must be calculated using past observations only**, without incorporating future data.



# References

- **Benova & Hudec (2024)** — [*Comprehensive Analysis and Evaluation of Anomalous User Activity in Web Server Logs*](https://pmc.ncbi.nlm.nih.gov/articles/PMC10856912/). Investigates NGINX log features, temporal aggregation, user behaviour, and Isolation Forest-based anomaly detection.

- **Denaro et al. (2024)** — [*Predicting Failures of Autoscaling Distributed Applications*](https://doi.org/10.1145/3660794). Explores statistical representations of system indicators for failure-related analysis.

- **IBM Research (2024)** — [*InstantOps: A Joint Approach to System Failure Prediction and Root Cause Identification in Microservices Cloud-Native Applications*](https://research.ibm.com/publications/instantops-a-joint-approach-to-system-failure-prediction-and-root-cause-identification-in-microservices-cloud-native-applications). Investigates combining observability signals to predict and diagnose failures in distributed applications.