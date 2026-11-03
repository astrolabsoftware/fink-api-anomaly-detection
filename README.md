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

# Inference API (FastAPI)

**Source code:** `src/fink_api_anomaly_detection/api.py`

The FastAPI application exposes two endpoints, `/health` and `/predict`, and serves as the inference interface for the anomaly detection system.

A client submits raw Nginx log lines (access, geo, and error logs) corresponding to a complete 5-minute time window. The API processes these logs, builds the corresponding features, and runs inference using the trained Autoencoder model stored in `artifacts/ae`.

If an anomaly is detected, the API generates an alert containing relevant information, such as the alert severity and anomaly score, and sends it to the configured Slack channel.

The HTTP response also indicates whether an anomaly was detected and provides the corresponding inference results.

The inference server exposes exactly two application routes:

- `GET /health`: unauthenticated liveness check.
- `POST /predict`: accepts one complete 5-minute raw log window and requires the `X-API-Token` header.

## There is 2 setup mode (manual and docker):

### Setup (Manual)

On the inference host, install only the runtime dependencies and configure the root `.env` file.

The repository includes a `.env.example` file containing the default configuration. Copy it to `.env` and replace the example `API_TOKEN` with a strong secret before starting the server.

The `.env` file is ignored by Git, while `.env.example` serves as a configuration template.

```bash
python -m pip install -r requirements.api.txt

cp .env.example .env

# Edit .env and set API_TOKEN (and optionally SLACK_WEBHOOK_URL).

python -m uvicorn fink_api_anomaly_detection.api:app \
    --app-dir src \
    --env-file .env \
    --host 0.0.0.0 \
    --port 8000
```

### Server configuration

The following environment variables configure the inference server (in .env):

| Variable | Default | Purpose |
|---|---|---|
| `AE_MODEL_PATH` | `artifacts/ae` | Path to the trained Autoencoder and scaler. |
| `ANOMALY_THRESHOLD` | `0.3608` | Reconstruction error threshold used for anomaly detection. |
| `API_TOKEN` | Required | Shared secret used to authenticate client requests. |
| `SLACK_WEBHOOK_URL` | Empty | Optional Slack webhook URL used for anomaly notifications. |

### Setup (Docker)

*Docker deployment : coming soon.*

## Example execution

### Accessing the API documentation

Once the server is running, open the following URL in your browser:

**http://127.0.0.1:8000/docs**

The Swagger UI displays the two available endpoints and their documentation.

To test the inference endpoint manually:

1. Open `POST /predict`.
2. Click **Try it out**.
3. Copy the example JSON payload below into the request body.
4. Provide the required `X-API-Token` header.
5. Click **Execute**.


### Example request

The `POST /predict` endpoint receives:

- `source_id`: identifier of the Nginx log source.
- `window_id`: identifier of the window, equal to its UTC `window_start`.
- `window_start` and `window_end`: UTC boundaries of the 5-minute window.
- `access_logs`: raw Nginx access log lines.
- `geo_logs`: raw geographical log lines.
- `error_logs`: raw Nginx error log lines.

Example payload:

**Note:** The log data below is simulated. IP addresses, HTTP statuses, countries, and other values are fictitious. This example also contains no Nginx error logs.

```json
{
  "source_id": "nginx.log.ztf.api.fink-portal",
  "window_id": "2026-11-03T13:15:00Z",
  "window_start": "2026-11-03T13:15:00Z",
  "window_end": "2026-11-03T13:20:00Z",
  "access_logs": [
    "192.0.2.147 - - [03/Nov/2026:13:15:01 +0000] \"POST /api/v1/conesearch HTTP/1.1\" 200 364 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "192.0.2.146 - - [03/Nov/2026:13:15:20 +0000] \"POST /api/v1/objects HTTP/1.1\" 200 742 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "192.0.2.147 - - [03/Nov/2026:13:16:04 +0000] \"GET /api/v1/conesearch HTTP/1.1\" 200 2 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "198.51.100.38 - - [03/Nov/2026:13:16:10 +0000] \"GET /api/v1/latests HTTP/1.1\" 200 41256 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "198.51.100.38 - - [03/Nov/2026:13:16:30 +0000] \"POST /api/v1/objects HTTP/1.1\" 500 37 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "198.51.100.38 - - [03/Nov/2026:13:17:11 +0000] \"POST /api/v1/latests HTTP/1.1\" 200 46265 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "198.51.100.38 - - [03/Nov/2026:13:17:12 +0000] \"POST /api/v1/latests HTTP/1.1\" 200 31937 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "203.0.113.91 - - [03/Nov/2026:13:18:12 +0000] \"POST /api/v1/conesearch HTTP/1.1\" 200 2 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "198.51.100.38 - - [03/Nov/2026:13:19:12 +0000] \"POST /api/v1/latests HTTP/1.1\" 200 36189 \"-\" \"python-httpx/0.28.1\" \"-\"",
    "203.0.113.91 - - [03/Nov/2026:13:19:30 +0000] \"POST /api/v1/latests HTTP/1.1\" 200 16711 \"-\" \"python-httpx/0.28.1\" \"-\""
  ],
  "geo_logs": [
    "03/Nov/2026:13:15:01 +0000@France@200@/api/v1/conesearch",
    "03/Nov/2026:13:15:20 +0000@France@200@/api/v1/objects",
    "03/Nov/2026:13:16:04 +0000@France@200@/api/v1/conesearch",
    "03/Nov/2026:13:16:10 +0000@Taiwan@200@/api/v1/latests",
    "03/Nov/2026:13:16:30 +0000@Taiwan@500@/api/v1/objects",
    "03/Nov/2026:13:17:11 +0000@Taiwan@200@/api/v1/latests",
    "03/Nov/2026:13:17:12 +0000@Taiwan@200@/api/v1/latests",
    "03/Nov/2026:13:18:12 +0000@Australia@200@/api/v1/conesearch",
    "03/Nov/2026:13:19:12 +0000@Taiwan@200@/api/v1/latests",
    "03/Nov/2026:13:19:30 +0000@Taiwan@200@/api/v1/latests"
  ],
  "error_logs": []
}
```

### Example response

For the example request above, the API returns the following response:

```json
{
  "source_id": "nginx.log.ztf.api.fink-portal",
  "window_start": "2026-11-03T13:15:00Z",
  "window_end": "2026-11-03T13:20:00Z",
  "reconstruction_error": 0.03167640499672337,
  "threshold": 0.3608,
  "is_anomaly": false,
  "severity": "None",
  "alert_status": "not_an_anomaly",
  "parse_warnings": []
}
```

### Interpreting the response

In this example, the reconstruction error is:

`0.03167640499672337`

It is lower than the configured anomaly threshold:

`0.3608`

Therefore, the window is classified as **normal** (`is_anomaly: false`).

As no anomaly is detected:

- The severity is set to `None`.
- The alert status is `not_an_anomaly`.
- No Slack notification is sent.

This is expected for this simulated example, which contains only a small number of requests within the 5-minute window.

---

# Nginx log exporter client

The client is designed to run directly on the Nginx server.

Its role is to collect raw Nginx access, geo, and error log lines, organize them into 5-minute windows, and send these windows to the inference API through requests to `POST /predict` (for inference)

For installation and configuration instructions, see the [client README](client/README.md).