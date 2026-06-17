# Stage 6 — Kafka Infrastructure (Docker Compose)

This stage provisions local infrastructure with Docker Compose:
- Kafka + ZooKeeper
- MinIO (S3 compatible)
- PostgreSQL
- Prometheus
- Grafana
- Kafka Exporter
- Postgres Exporter

## Implemented files

- `infra/docker-compose.yml`
- `infra/spark/Dockerfile` — custom Spark image (python:3.11-slim + OpenJDK 21 + pyspark 3.5.1 + all 9 JARs baked in)
- `infra/prometheus/prometheus.yml`
- `infra/postgres/init.sql`
- `infra/grafana/provisioning/datasources/datasource.yml`
- `infra/grafana/provisioning/dashboards/dashboard.yml`
- `infra/grafana/dashboards/robot_health.json`

## Service explanation

- **zookeeper**: coordination backend for this Kafka image.
- **kafka**: telemetry event bus. Has a healthcheck so dependent services wait for it.
- **minio**: object storage for Delta Lake data.
- **postgres**: operational and summary SQL tables.
- **prometheus**: metrics scraping and storage.
- **grafana**: dashboard visualization. Auto-provisions datasources and dashboards from `grafana/provisioning/`.
- **kafka-exporter**: Kafka metrics endpoint for Prometheus. Waits for Kafka to be healthy before starting.
- **postgres-exporter**: PostgreSQL metrics endpoint for Prometheus.

### Spark pipeline services (profile: `spark`)

These services share the custom `infra/spark/Dockerfile` image and are only started when the `spark` profile is active:

- **injector** (`scripts/inject_telemetry.py`): injects synthetic telemetry (2000 events across 2 robots) into Kafka for testing.
- **spark-streaming** (`streaming/spark_streaming.py`): Structured Streaming job — Kafka → Delta Lake + PostgreSQL.
- **spark-batch** (`streaming/spark_batch_daily.py`): daily KPI aggregation job — Delta Lake → curated Delta + PostgreSQL.
- **duckdb-analytics** (`sql/analytics_duckdb.py`): 7 analytical reports scanning Delta Lake directly via DuckDB.

```powershell
# Build Spark image (one-time, ~5 min)
cd "robot-telemetry-platform\infra"
docker compose --profile spark build

# Run pipeline steps
docker compose --profile spark run --rm injector
docker compose --profile spark run --rm spark-streaming
docker compose --profile spark run --rm spark-batch
docker compose --profile spark run --rm duckdb-analytics
```

## Start infrastructure

```bash
cd ~/robot-telemetry-platform/infra
docker compose up -d
```

## Verify containers

```bash
docker compose ps
```

## Access UIs

- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

## Create MinIO bucket for Delta

Create bucket `robot-lake` in MinIO console.

## Kafka topic setup

```bash
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --create --topic robot.telemetry.v1 --partitions 3 --replication-factor 1
```

## Stop infrastructure

```bash
cd ~/robot-telemetry-platform/infra
docker compose down
```
