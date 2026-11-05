# Data

The dataset consists of Nginx logs collected from the Fink API (ztf). The raw data is stored locally in `data/ztf/nginx_history_logs/`. It contains **42 compressed `.gz` files**: 14 files per category, with filename dates from **October 4 to October 17, 2026**.

The filenames are dated one day after the events they contain. Parsed event timestamps range from **October 3, 2026 at 00:00 UTC** to **October 17, 2026 at 00:00 UTC**. This covers 14 days, with six records in the final partial day. 

## Data Privacy and Repository Policy

The raw logs are excluded from git through the project`.gitignore` file and are not intended to be published on GitHub.Depending on their format and content, these logs contain sensitive information, including client IP addresses. Don't worry; the repository is designed to focus also on analysis data (via .ipynb notebooks), giving you a comprehensive view of the raw data. If data sharing is required in the future, an appropriate anonymization process and the necessary permissions must be established before publication.

---

## Dataset Structure

The dataset `data/ztf/nginx_history_logs` is organized into three categories:

- `access-logs/`: HTTP full request logs recorded by Nginx.
- `error-logs/`: Nginx error logs.
- `geo-logs/`: geographical ( user country) information associated with requests.

Each category contains one compressed log file per filename date.

```
data/
└── nginx_history_logs
    ├── access-logs
    │   ├── access.log-20261004.gz
    │   ├── access.log-20261005.gz
    │   ├── access.log-20261006.gz
    │   ├── access.log-20261007.gz
    │   ├── access.log-20261008.gz
    │   ├── access.log-20261009.gz
    │   ├── access.log-20261010.gz
    │   ├── access.log-20261011.gz
    │   ├── access.log-20261012.gz
    │   ├── access.log-20261013.gz
    │   ├── access.log-20261014.gz
    │   ├── access.log-20261015.gz
    │   ├── access.log-20261016.gz
    │   └── access.log-20261017.gz
    ├── error-logs
    │   ├── error.log-20261004.gz
    │   ├── error.log-20261005.gz
    │   ├── error.log-20261006.gz
    │   ├── error.log-20261007.gz
    │   ├── error.log-20261008.gz
    │   ├── error.log-20261009.gz
    │   ├── error.log-20261010.gz
    │   ├── error.log-20261011.gz
    │   ├── error.log-20261012.gz
    │   ├── error.log-20261013.gz
    │   ├── error.log-20261014.gz
    │   ├── error.log-20261015.gz
    │   ├── error.log-20261016.gz
    │   └── error.log-20261017.gz
    └── geo-logs
        ├── geo.log-20261004.gz
        ├── geo.log-20261005.gz
        ├── geo.log-20261006.gz
        ├── geo.log-20261007.gz
        ├── geo.log-20261008.gz
        ├── geo.log-20261009.gz
        ├── geo.log-20261010.gz
        ├── geo.log-20261011.gz
        ├── geo.log-20261012.gz
        ├── geo.log-20261013.gz
        ├── geo.log-20261014.gz
        ├── geo.log-20261015.gz
        ├── geo.log-20261016.gz
        └── geo.log-20261017.gz
```
---

## Potentially Useful Information

Depending on the actual log formats, the data provide information about:

- Request volumes and traffic patterns.
- HTTP status codes and error rates.
- Request timestamps and temporal variations.
- Client IP_addresse/country & client agent.
- Nginx errors and upstream communication failures.

The exact fields, formats, and level of detail will be detailed during data exploration -- through jupyter notebook's.

---

## Future Data Sources

Flask application logs may be integrated in a later stage. Also, if needed, additional infrastructure metrics such as CPU usage, memory consumption could help explain degradation and outages that cannot be identified reliably from Nginx logs alone.

--- 

##  Current Limitations

The initial dataset has limitation:
- **Unknown incident labels:** historical outage timestamps have not been established as part of the dataset.

--- 

# Note for Lsst 

We still collect data just like ztf (data/lsst/nginx_history_logs/)