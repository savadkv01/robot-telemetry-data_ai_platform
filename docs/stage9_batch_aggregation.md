# Stage 9 — Batch Aggregation Job

This stage computes daily robot performance summaries from processed telemetry.

## Implemented file
- [streaming/spark_batch_daily.py](streaming/spark_batch_daily.py)

## Input
- Delta processed table: `s3a://robot-lake/processed/telemetry_events`

## Output
1. Curated Delta table:
   - `s3a://robot-lake/curated/daily_robot_summary`
2. PostgreSQL table:
   - `daily_robot_summary`

---

## Aggregation logic

Grouped by:
- `robot_id`
- `event_date`

Computed metrics:
- `events_count`
- `avg_speed_mps`
- `max_speed_mps`
- `avg_battery_degradation`
- `anomaly_events`
- `min_battery_pct`
- `failure_risk_flag` where `anomaly_events > 10`

---

## Run command

The batch job runs inside the same Docker image as the streaming job. From PowerShell (inside `robot-telemetry-platform/infra/`):

```powershell
# Build image first if not already done
docker compose --profile spark build

# Run batch aggregation (reads processed Delta, writes curated Delta + PostgreSQL)
docker compose --profile spark run --rm spark-batch
```

The job reads the latest processed telemetry from MinIO, computes daily KPIs, and overwrites the curated Delta table and PostgreSQL `daily_robot_summary` table.

---

## Validate results

### PostgreSQL
In PowerShell:
```powershell
docker exec postgres psql -U robot -d robot_ops -c "SELECT * FROM daily_robot_summary ORDER BY event_date DESC, robot_id LIMIT 20;"
```

### MinIO
Open MinIO console at http://localhost:9001 and confirm:
- `robot-lake/curated/daily_robot_summary/` has files

---

## Common issues

### No rows generated
- Ensure Stage 7 stream has written records to processed Delta.

### Delta path not found
- Verify bucket `robot-lake` exists.
- Verify Spark streaming job ran successfully.

### PostgreSQL write failed
- Check Postgres container status and credentials.

---

## Beginner explanation

Streaming (Stage 7) gives event-by-event records.
Batch (Stage 9) creates one row per robot per day.
This makes dashboard/report queries faster and easier.
