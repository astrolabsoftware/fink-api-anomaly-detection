# Lightweight Nginx Log Exporter (client)

The client is a lightweight Python program using only the standard library. It runs directly on the Nginx host, reads Nginx access, geo, and error logs, selects the raw log lines corresponding to a UTC-aligned 5-minute window, and sends that window to the existing inference API.

## Client directory

```text
client/
├── README.md
└── nginx-log-exporter/
    ├── config.json
    ├── nginx_log_exporter.py
    └── nginx-log-exporter.service
```

The script loads `config.json` from its own directory. The systemd unit, configuration, and executable are grouped together in `client/nginx-log-exporter/`.

The agent does not create local log or state directories, nor does it persist payloads.

## API contract and log formats

The API source of truth is `PredictionRequest` and `/predict` in `src/fink_api_anomaly_detection/api.py`.

The client sends an HTTP `POST` request with the `X-API-Token` header and a JSON payload containing:

- `source_id`
- `window_id`, which must match `window_start`
- `window_start` and `window_end`, as UTC ISO-8601 timestamps ending in `Z`
- `access_logs`, `geo_logs`, and `error_logs`, as arrays of original log lines

Access and geo timestamps use `%d/%b/%Y:%H:%M:%S %z`. Error timestamps use `%Y/%m/%d %H:%M:%S` and are interpreted as UTC.

The client uses these formats only to select log lines; it does not transform the log entries.

## Scheduling and delivery

At startup, the agent selects the current UTC-aligned 5-minute window. It does not process earlier windows or recover a backlog.

It waits until the selected window ends, plus a 15-second grace period, then collects the log lines for which:

`window_start <= timestamp < window_end`

It then sends the payload to the API.

Each window has at most two HTTP attempts. If the first request fails, the agent waits 15 seconds and retries once. It also checks that a successful response is valid and corresponds to the submitted source and window.

After success or failure, the agent calculates the next window based on the current UTC clock.

The agent streams files line by line and keeps small byte cursors in memory while running, allowing it to read appended content without rescanning the active files. Cursors are discarded on restart.

It reads the configured active log files and matching rotated files whose modification times are recent enough for the current window. Gzip rotations are supported.

Missing or unreadable log categories make collection incomplete. In that case, the window is logged and skipped rather than being sent with partial data.

Malformed lines are logged and ignored, while empty categories are sent as empty arrays. Original Nginx log files are read-only.

## Configuration and manual run

Edit `client/nginx-log-exporter/config.json` before installing the agent.

Set the following values:

- `api_url` to the inference API's `/predict` endpoint.
- `api_token` to the server's `API_TOKEN`. Do not commit the real token to Git.
- `source_id` to a 1–128 character identifier using letters, digits, `.`, `_`, or `-`. The default value is `"nginx.log.ztf.api.fink-portal"`.
- `log_files` to the active access, geo, and error log paths on the host.
- `request_timeout_seconds` to a positive HTTP timeout (default: 10 seconds).

No additional Python packages are required. Python 3.10 or later is recommended.

From the repository root, run:

```bash
python3 client/nginx-log-exporter/nginx_log_exporter.py
```

Logs are written to stdout and stderr.

## systemd installation (recommended)

Create the dedicated system user and install the three runtime files from the client subdirectory into `/opt/nginx-log-exporter/`:

```bash
sudo useradd --system --user-group --no-create-home \
  --shell /usr/sbin/nologin nginx-log-exporter

# Add the user to the group that provides access to the logs.
sudo usermod -aG root nginx-log-exporter

sudo install -d -o root -g nginx-log-exporter -m 750 \
  /opt/nginx-log-exporter

sudo install -o root -g nginx-log-exporter -m 640 \
  client/nginx-log-exporter/config.json \
  client/nginx-log-exporter/nginx_log_exporter.py \
  /opt/nginx-log-exporter/

sudo install -o root -g root -m 644 \
  client/nginx-log-exporter/nginx-log-exporter.service \
  /etc/systemd/system/nginx-log-exporter.service
```

Update the installed configuration securely with the real API token and host log paths:

```bash
sudoedit /opt/nginx-log-exporter/config.json
```

The service runs as the dedicated unprivileged user. It assumes that the Nginx logs are readable through the configured supplementary group and restricts log access to `/var/log/nginx`. Adjust the unit if the logs are stored elsewhere.

Enable and inspect the service with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nginx-log-exporter
sudo systemctl status nginx-log-exporter
sudo journalctl -u nginx-log-exporter -f
```

To stop and disable the service:

```bash
sudo systemctl disable --now nginx-log-exporter
```

## Few Resource usage

Memory usage is proportional to the collected window payload, + a small in-memory cursor map.

Files are streamed rather than loaded entirely into memory. The process sleeps between window deadlines and does not write payloads, state, or log files to disk. Systemd/journald receives its logs.

The agent does not start additional workers, databases, or message queues.
