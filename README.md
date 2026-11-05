# Fink API's Anomaly Detection

A data-driven project aimed at detecting anomalies and identifying potential failure signals within Fink APIs through the analysis of Nginx logs and machine learning.

## Objectives

By leveraging **logs from Nginx** a server positioned in front of the Fink APIs (for LSST and ZTF); the objective is to **detect anomalies in the API** using anomaly detection methods, in order to alert the operations team via Slack so that they can intervene if necessary.

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

The [notebooks/](notebooks/) follow the methodology described gradually in the project documentation. They provide -- for the two log sources / two Fink APIs (LSST and ZTF) -- an experimental workflow covering data acquisition, preprocessing, exploration, feature engineering, baseline development, model (whether it beats or not the baseline) development and improvement,evaluation and analysis.

---

# Inference API (FastAPI)

**Source code:** `src/fink_api_anomaly_detection/api.py`

The FastAPI application exposes two endpoints, `/health` and `/predict`, and serves as the inference interface for the anomaly detection system.

A client (nginx log exporter installed in each api.server) submits raw Nginx log lines (access, geo, and error logs) corresponding to a complete 5-minute time window. The API processes these logs, builds the corresponding features, and runs inference using the trained Autoencoder model stored in `artifacts/ae/[ZTF/LSST]`.

If an anomaly is detected, the API generates an alert containing relevant information, such as the alert severity and anomaly score, and sends it to the configured Slack channel.

The HTTP response also indicates whether an anomaly was detected and provides the corresponding inference results.

The inference server exposes exactly two application routes:

- `GET /health`: unauthenticated liveness check.
- `POST /predict`: accepts one complete 5-minute raw log window and requires the `X-API-Token` header.


### Server configuration and Docker Compose setup

Docker Compose reads the service configuration from `.env.ztf` and, when the
LSST service is enabled, `.env.lsst`.

| Variable | Default | Purpose |
|---|---|---|
| `AE_MODEL_PATH` | ZTF: `artifacts/ae/ztf`; LSST: `artifacts/ae/lsst` | Path to the trained Autoencoder and scaler inside the image. |
| `ANOMALY_THRESHOLD` | ZTF: `0.3608`; LSST: set after training | Reconstruction error threshold used for anomaly detection. |
| `API_TOKEN` | Required | Shared secret used to authenticate client requests. Replace the example value with a strong secret. |
| `SLACK_WEBHOOK_URL` | Optional | Slack webhook URL used for anomaly notifications. |

Create the ZTF environment file expected by the active Compose service and set
its token before starting the API:

```bash
cp .env.ztf.example .env.ztf
```

Edit `.env.ztf` and replace `API_TOKEN` (and, if needed, set
`SLACK_WEBHOOK_URL`). The `.env.*.example` files are templates; Compose does
not load them directly.

The Compose file starts only the ZTF service by default. It pulls
`gitlab-registry.in2p3.fr/astrolabsoftware/fink/api.fink-portal.log-anomaly-detection-api`, maps host port 8000 to
container port 8000, and reads `.env.ztf`.

```bash
docker compose -f docker-compose.api.yml up
```

Open the ZTF API documentation at **http://127.0.0.1:8000/docs**.

Stop the service with `Ctrl+C`, then remove its container with:

```bash
docker compose -f docker-compose.api.yml down
```

The LSST service is commented out in `docker-compose.api.yml`. To enable it,
first create `.env.lsst` from `.env.lsst.example`, set its `API_TOKEN` and a
trained model's `ANOMALY_THRESHOLD`, then uncomment the LSST service in the
Compose file. It maps host port 8001 to container port 8000, so its
documentation will be available at **http://127.0.0.1:8001/docs**.


## Example API execution (ZTF)

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

# deployment in prod

[deploy/](deploy/) contain configuration and kube manifest to deploy each api in k3s single node cluster (server) -- comming soon

---

# Nginx log exporter client

The client is designed to run directly on the Nginx server of each api.

Its role is to collect raw Nginx access, geo, and error log lines, organize them into 5-minute windows, and send these windows to the inference API through requests to `POST /predict` (for inference)

For installation and configuration instructions, see the [client README](client/README.md).