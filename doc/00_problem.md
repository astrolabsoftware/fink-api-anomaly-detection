# Problem Definition

## Context

The Fink API (a Flask/Python application) is exposed through Nginx. Its access and error logs provide information about incoming requests, HTTP responses, and potential server-side issues. Flask application logs may also be integrated in the future to provide additional information about application-level failures.

**The objective of this project is to investigate whether these logs can be used to detect abnormal API behavior and anticipate service degradation or outages.**



## Problem Statement

**How can we leverage API logs to automatically identify anomalous behavior and anticipate incidents that may lead to service degradation or unavailability?**

The main challenge is that an anomaly does not necessarily correspond to a failure, and a failure does not necessarily produce an obvious anomaly in access logs.

For example:

- A sudden increase in request volume may result from a legitimate event, automated ligitim scraping, or a potential attack.
- An increase in HTTP 5xx responses may indicate application, server Errors or infrastructure problems.
- An increase in response times may indicate resource (CPU,RAM) saturation.
- A concentration of requests from a single IP address may reflect legitimate usage or suspicious activity.
- Since the Fink API is used worldwide, traffic patterns may vary across time zones and local usage periods. For example, working hours in France (8:00 AM–6:00 PM) do not necessarily coincide with peak usage periods in the Americas or Australia. Therefore, traffic variations must be interpreted in a global context before being classified as anomalies.
- A sudden decrease in traffic may be normal during quiet periods, but may also indicate service unavailability.

Therefore, the project will investigate multiple definitions of anomalous behavior rather than assume that a single definition is available from the beginning.

## Research Questions

The project will investigate the following questions:

1. Which indicators best characterize normal API behavior?
2. Can unusual traffic patterns and error rates be detected reliably?
3. Can anomalies be detected without labeled historical incidents? (Since, at the moment, we have no labels indicating whether an anomaly is present or not)
4. Which signals consistently precede API outages?
5. How far in advance can an outage realistically be anticipated?
6. How can models be evaluated when incidents are rare?
7. How can false alarms be limited while retaining useful detection
   sensitivity?

---

## Detection vs. Forecasting

The project distinguishes between two related but different tasks.

### Anomaly Detection

Identify unusual API behavior using historical patterns and observed log data. Examples include abnormal request volumes, unusual HTTP error rates,
or unexpected changes in traffic composition.

### Outage Forecasting

Estimate whether an API outage is likely to occur within a future time window, using only information available at prediction time.This task requires reliable historical outage timestamps or another defensible way to identify outage periods. An anomaly may be useful for monitoring without necessarily being predictive of an outage.

---

## The Decision

The project will initially investigate two possible outputs -- An anomaly alert based on unusual observed behavior -- and an outage risk estimate for a defined future time window.The exact alerting policy and prediction horizon remain to be defined based on data and evaluation results.

---

## Evaluation Principles

The initial datasets does not contain labeled anomalies or confirmed outage timestamps. The project will therefore initially focus on unsupervised anomaly detection and exploratory evaluation. So, the evaluation strategy will distinguish between the detection of unusual behavior and the prediction of future service outages.

### For unsupervised Anomaly Detection

In the absence of ground-truth labels, conventional supervised classification metrics such as accuracy, precision, and recall cannot be directly computed in a reliable way.

The initial evaluation will focus on:

- **Anomaly characteristics:** Investigate the traffic patterns, HTTP status codes, and error indicators associated with detected anomalies.
- **Detection stability:** Assess how sensitive the detected anomalies are to changes in model parameters and detection thresholds.
- **Method agreement:** Compare the results obtained with different statistical and machine learning approaches.
- **Temporal consistency:** Determine whether detected anomalies reflect unusual behavior after accounting for temporal variations, including time of day and day of the week, where the available data supports such analysis.
- **Alert frequency:** Measure how often anomalies are detected and investigate whether the resulting alert volume could be operationally manageable.


### Validation and Reference Data

Whenever possible, detected anomalies will be compared against independent sources of evidence, such as historical incident records
(if available), monitoring alerts, application logs, and infrastructure metrics (e.g., CPU and memory usage of Host machine). A sample of detected anomalies may also be manually reviewed in collaboration with the ops team to assess their relevance and identify potential incidents. If reliable labels can be established, for example by consulting fink team members who can recall when specific failures occurred and annotating the corresponding periods in the dataset, supervised evaluation metrics such as precision, recall, and false positive rate can then be computed.


### For outage Forecasting

Outage forecasting requires reliable information about confirmed outages and their timestamps. If such information becomes available, the project will investigate whether signals observed before an outage provide useful early warnings. The evaluation may then consider:

- **Precision and recall:** Assess the quality and coverage of outage-related alerts.
- **False alarm rate:** Measure the frequency of alerts that are not associated with relevant incidents.
- **Lead time:** Measure the time between an alert and a subsequent confirmed outage.
- **Detection horizon:** Evaluate performance over explicitly defined prediction windows.

---

## Temporal Validation and Data Limitations

All evaluations must respect temporal order to avoid information leakage. When sufficient data is available, models will be evaluated on periods that occur after the periods used for model development. The current observation period covers 14 days [see doc/01_data.md](/doc/01_data.md), providing only two weekly cycles. This remains a limitation for identifying recurring traffic patterns, like evaluating mounthly seasonality. The availability of longer historical logs and confirmed incident records will determine which evaluation methods can be applied.
