# Stage 8 — Data Lake Design (MinIO + Delta)

This document defines the robotics lakehouse structure used in this project.

## 1) Zone model

### Raw zone
Purpose:
- Store near-original telemetry events for replay and audit.
- Minimal transformation.

Example path:
- `s3a://robot-lake/raw/telemetry_json/`

Typical columns:
- `ingest_time`
- `raw_value` (JSON string)
- `kafka_topic`
- `kafka_partition`
- `kafka_offset`

### Processed zone
Purpose:
- Typed schema, cleaned fields, feature columns.

Current table:
- `processed/telemetry_events`

Example path:
- `s3a://robot-lake/processed/telemetry_events/`

Typical columns:
- `robot_id`, `event_ts`, `event_date`, `source_topic`
- `payload.*`
- `speed_mps`
- `battery_degradation_score`
- `anomaly_flag`

### Curated zone
Purpose:
- Business-ready aggregate datasets for dashboards/reports.

Current table:
- `curated/daily_robot_summary`

Example path:
- `s3a://robot-lake/curated/daily_robot_summary/`

Typical columns:
- `robot_id`, `event_date`
- `events_count`, `avg_speed_mps`, `max_speed_mps`
- `avg_battery_degradation`, `anomaly_events`, `failure_risk_flag`

---

## 2) Delta table strategy

Use Delta Lake for all processed/curated tables because it provides:
- ACID transactions
- schema enforcement/evolution
- reliable streaming + batch interoperability
- checkpoint-compatible pipeline behavior

---

## 3) Partition strategy

### Processed table
Partition by:
- `event_date`

Reason:
- Fast day-based queries
- Good balance between partition count and file size

### Curated table
Partition by:
- `event_date`

Reason:
- Daily reporting and dashboard filters are date-first.

---

## 4) Recommended MinIO folder layout

```text
s3a://robot-lake/
  raw/
    telemetry_json/
  processed/
    telemetry_events/
  curated/
    daily_robot_summary/
  checkpoints/
    stream_telemetry/
    stream_postgres/
```

---

## 5) Naming conventions

- Bucket: `robot-lake`
- Zone names: `raw`, `processed`, `curated`
- Table names use snake_case
- Kafka topic versioning: `robot.telemetry.v1`

---

## 6) Beginner notes

- Raw = source of truth
- Processed = cleaned event-level data
- Curated = report-ready data

Think of flow as:
`Kafka events -> processed Delta -> curated daily summary`
