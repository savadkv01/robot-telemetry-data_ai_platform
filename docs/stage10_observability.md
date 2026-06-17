# Stage 10 — Observability & Monitoring

This stage wires monitoring for robotics telemetry and infrastructure.

## Implemented artifacts

- Custom metrics API:
  - [observability/robot_metrics_api.py](observability/robot_metrics_api.py)
  - [observability/requirements.txt](observability/requirements.txt)
- Prometheus scrape config:
  - [infra/prometheus/prometheus.yml](infra/prometheus/prometheus.yml)
- Grafana dashboard + provisioning:
  - [infra/grafana/dashboards/robot_health.json](infra/grafana/dashboards/robot_health.json)
  - [infra/grafana/provisioning/datasources/datasource.yml](infra/grafana/provisioning/datasources/datasource.yml)

## What is monitored

### Robot custom metrics
From `robot_metrics_api`:
- `robot_events_total{robot_id,source_topic}`
- `robot_battery_percentage{robot_id}`
- `robot_speed_mps{robot_id}`
- `robot_anomaly_flag{robot_id}`
- `robot_ingest_request_seconds`

### Kafka metrics
From `kafka-exporter`:
- broker status
- topic partition metrics
- consumer lag (when consumer groups exist)

### PostgreSQL metrics
From `postgres-exporter`:
- connections
- transactions
- database-level runtime metrics

### Prometheus self metrics
From `prometheus` target:
- scrape health
- TSDB runtime metrics

---

## Run the custom metrics API (Ubuntu)

```bash
cd ~/robot-telemetry-platform
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -r observability/requirements.txt
uvicorn observability.robot_metrics_api:app --host 0.0.0.0 --port 8000
```

Health check:
```bash
curl http://localhost:8000/health
```

Prometheus metrics endpoint:
```bash
curl http://localhost:8000/metrics
```

---

## Push sample metrics events

```bash
curl -X POST http://localhost:8000/ingest_event \
  -H "Content-Type: application/json" \
  -d '{
    "robot_id": "robot-001",
    "source_topic": "/battery_state",
    "battery_percentage": 0.88,
    "speed_mps": 0.42,
    "anomaly_flag": 0
  }'
```

---

## Prometheus verification

Open: http://localhost:9090/targets

Expected targets:
- `prometheus` = UP
- `kafka_exporter` = UP
- `postgres_exporter` = UP
- `robot_metrics_api` = UP (after running API)

---

## Grafana usage

Open: http://localhost:3000 (admin/admin)

Dashboards available (auto-provisioned from `infra/grafana/dashboards/`):

| Dashboard | UID | Source | Description |
|-----------|-----|--------|-------------|
| **Robot Telemetry Health** | `robot-telemetry-health` | Prometheus | Live battery %, event throughput, exporter health |
| **Robot Fleet Analytics** | `robot-fleet-analytics` | PostgreSQL | Fleet snapshot, battery trends, anomaly hotspots, daily KPIs, maintenance priority, availability gauges |

Both dashboards are provisioned automatically when the Grafana container starts. No manual import is needed.

Main panels:
- Robot Battery Percentage
- Telemetry Events Per Second
- Exporter Health
- Operational Events per Minute (PostgreSQL)

---

## Spark UI note

When Spark streaming job is running, UI is typically at:
- http://localhost:4040

Use it for:
- input rows/sec
- processing time per micro-batch
- failed stages/tasks

---

## Common troubleshooting

### `robot_metrics_api` target is DOWN
- Ensure API is running on port 8000.
- Ensure Prometheus has target `host.docker.internal:8000`.

### Grafana panel no data
- Check Prometheus query first in Prometheus UI.
- Send sample events to `/ingest_event`.

### Kafka exporter initially DOWN
- Wait for Kafka startup; restart exporter if needed.

### No Spark UI
- Spark job must be actively running.
