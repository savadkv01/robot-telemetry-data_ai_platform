# Stage 11 — Analytics Layer

This stage adds two analytical query layers on top of the data written by Stages 7–9:

1. **PostgreSQL queries** — 10 business-focused SQL reports against `telemetry_operational` and `daily_robot_summary`
2. **DuckDB on Delta Lake** — 7 analytical reports scanning Delta Lake files directly, without starting Spark

---

## Implemented files

| File | Description |
|------|-------------|
| `sql/analytics_postgresql.sql` | 10 PostgreSQL business reports |
| `sql/analytics_duckdb.py` | 7 DuckDB analytical reports on Delta Lake |
| `scripts/inject_telemetry.py` | Synthetic telemetry injector for testing (2000 events) |
| `docs/business_test_cases_end_to_end.md` | 8 business-level E2E acceptance test cases |

---

## Prerequisites

- Stage 7 streaming job has run → `telemetry_operational` has rows
- Stage 9 batch job has run → `daily_robot_summary` has rows
- MinIO bucket `robot-lake` has Delta files in `processed/telemetry_events/` and `curated/daily_robot_summary/`

Quick check:
```powershell
docker exec postgres psql -U robot -d robot_ops -c "SELECT COUNT(*) FROM telemetry_operational;"
docker exec postgres psql -U robot -d robot_ops -c "SELECT COUNT(*) FROM daily_robot_summary;"
```

If tables are empty, run the injector first (see commands below).

---

## Inject test data (if needed)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose --profile spark run --rm injector
docker compose --profile spark run --rm spark-streaming
docker compose --profile spark run --rm spark-batch
```

The injector produces:
- **robot-001** — healthy profile: battery drain ~10%/day, anomaly rate ~2%
- **robot-002** — degrading profile: battery drain ~45%/day, anomaly rate ~12%
- 500 events × 2 robots × 2 days = **2000 total events**

---

## PostgreSQL reports (10 reports)

Run from PowerShell:
```powershell
docker exec -it postgres psql -U robot -d robot_ops
```

Then paste queries from `sql/analytics_postgresql.sql`, or run individual sections.

### Report summary

| # | Report | Source table | Business use |
|---|--------|-------------|--------------|
| 1 | Fleet Health Snapshot | `telemetry_operational` | Operations manager sees current state of every robot |
| 2 | Battery Degradation Trend (30-min buckets) | `telemetry_operational` | Maintenance lead tracks battery drain curve |
| 3 | Anomaly Events Detail | `telemetry_operational` | Safety review — every event where robot behaved abnormally |
| 4 | Robots At Failure Risk Today | `daily_robot_summary` | Maintenance planner sees which robots need attention today |
| 5 | Daily Fleet Performance KPIs | `daily_robot_summary` | Operations director reviews fleet-wide daily summary |
| 6 | Per-Robot Performance History (7-day) | `daily_robot_summary` | Analyst compares week-over-week health for one robot |
| 7 | Topic Throughput Breakdown | `telemetry_operational` | Validates all 4 sensor topics (/imu, /odom, /battery_state, /scan) are flowing |
| 8 | Anomaly Hotspot Windows (5-min) | `telemetry_operational` | Identifies *when* anomalies cluster |
| 9 | Operational Availability % | `telemetry_operational` | % of expected 8-hr shift where robot was sending telemetry |
| 10 | Maintenance Priority Ranking | `daily_robot_summary` | Score = (anomaly_events × 2) + avg_battery_degradation |

### KPI definitions

| KPI | Definition |
|-----|-----------|
| `speed_mps` | Euclidean speed from odom vx/vy/vz (m/s) |
| `battery_degradation_score` | `(1 - battery_pct) × 100` — higher = more degraded |
| `anomaly_flag` | `1` when speed > 2.5 m/s OR battery < 15% OR min_distance < 0.20 m |
| `failure_risk_flag` | `1` when a robot accumulates > 10 anomaly events in a day |

---

## DuckDB analytics (7 reports)

Run from PowerShell:
```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose --profile spark run --rm duckdb-analytics
```

Reports print to stdout. DuckDB reads Delta Lake files directly from MinIO using `delta_scan()` — no Spark session required.

### Report summary

| # | Report | Delta path |
|---|--------|-----------|
| 1 | Fleet Health (latest record per robot) | `processed/telemetry_events/` |
| 2 | Battery Degradation Trend (1-hr buckets) | `processed/telemetry_events/` |
| 3 | Anomaly Summary | `processed/telemetry_events/` |
| 4 | Daily KPI Summary | `curated/daily_robot_summary/` |
| 5 | Maintenance Priority Ranking | `curated/daily_robot_summary/` |
| 6 | Speed Percentiles (p50/p90/p99) | `processed/telemetry_events/` |
| 7 | Topic Throughput | `processed/telemetry_events/` |

### DuckDB MinIO connection

DuckDB connects to MinIO using the `CREATE SECRET` syntax (not `SET s3_*`, which would attempt to connect to AWS EC2 metadata):

```python
conn.execute("""
    CREATE OR REPLACE SECRET minio_secret (
        TYPE S3,
        KEY_ID 'minioadmin',
        SECRET 'minioadmin',
        ENDPOINT 'minio:9000',
        URL_STYLE 'path',
        USE_SSL false
    )
""")
delta_scan("s3://robot-lake/processed/telemetry_events/")
```

---

## Common issues

### PostgreSQL: no rows returned
- Check that the Spark streaming job has run: `docker exec postgres psql -U robot -d robot_ops -c "SELECT COUNT(*) FROM telemetry_operational;"`
- If 0, run the injector and streaming job first.

### DuckDB: `Invalid Configuration Error: No credentials provided`
- This happens if `CREATE SECRET` is not used and DuckDB tries to fetch credentials from AWS EC2 metadata.
- Ensure `sql/analytics_duckdb.py` uses `CREATE OR REPLACE SECRET` with explicit KEY_ID and ENDPOINT. Do not use `SET s3_*` variables.

### DuckDB: `delta_scan path not found`
- Ensure the Spark streaming job has run and written files to `s3://robot-lake/processed/telemetry_events/`.
- Check MinIO at http://localhost:9001 (minioadmin/minioadmin).

---

## Beginner explanation

- **PostgreSQL reports** are fast because Spark already wrote clean, indexed rows.
- **DuckDB on Delta Lake** lets you run analytical queries *on the raw files* — useful for ad-hoc analysis or when you want to bypass the operational database entirely.
- Both layers query the same underlying data — they complement each other.
