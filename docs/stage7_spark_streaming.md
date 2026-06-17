# Stage 7 — Spark Structured Streaming

This stage reads telemetry events from Kafka, computes features, and writes to Delta Lake (MinIO) and PostgreSQL.

## Implemented file
- [streaming/spark_streaming.py](streaming/spark_streaming.py)

## What this pipeline does
1. Read JSON telemetry events from Kafka topic `robot.telemetry.v1`
2. Parse event schema
3. Compute features:
   - `speed_mps`
   - `battery_degradation_score`
4. Detect anomaly with rule:
   - speed > 2.5 m/s OR battery < 15% OR min distance < 0.2m
5. Write to:
   - Delta table: `s3a://robot-lake/processed/telemetry_events`
   - Postgres table: `telemetry_operational`

---

## Prerequisites
- Stage 6 infra running:
  - Kafka
  - MinIO
  - PostgreSQL
- Kafka topic exists: `robot.telemetry.v1`
- MinIO bucket exists: `robot-lake`

### Quick checks
In PowerShell:
```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose ps
```

Create topic if missing:
```powershell
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --create --if-not-exists --topic robot.telemetry.v1 --partitions 3 --replication-factor 1
```

---

## Run Spark streaming job

The Spark job runs inside Docker using the custom `infra/spark/Dockerfile` image. All required JARs (Kafka, Delta Lake, PostgreSQL JDBC, Hadoop S3A, etc.) are baked into the image at build time — no internet access needed at runtime.

From PowerShell (inside `robot-telemetry-platform/infra/`):

```powershell
# First-time image build (~5 min)
docker compose --profile spark build

# Run the streaming job (trigger-once mode: processes all available Kafka offsets then exits)
docker compose --profile spark run --rm spark-streaming
```

The job runs in `availableNow` (trigger-once) mode by default. It exits cleanly after processing all available Kafka messages. To run in continuous streaming mode, set `SPARK_TRIGGER_ONCE=false` in the service environment.

---

## Generate telemetry events for testing

### Option A: ROS2 bridge path (recommended)
Run ROS2 simulation + bridge so Kafka receives real telemetry JSON.

### Option B: quick Kafka test event
In PowerShell:
```powershell
docker exec kafka bash -lc "echo '{\"robot_id\":\"robot-test\",\"event_time\":\"2026-02-15T00:00:00Z\",\"source_topic\":\"/battery_state\",\"payload\":{\"percentage\":0.50,\"min_distance\":0.5,\"vx\":0.0,\"vy\":0.0,\"vz\":0.0}}' | kafka-console-producer --bootstrap-server localhost:9092 --topic robot.telemetry.v1"
```

---

## Validate outputs

### 1) PostgreSQL rows
In PowerShell:
```powershell
docker exec postgres psql -U robot -d robot_ops -c "SELECT COUNT(*) FROM telemetry_operational;"
```

### 2) MinIO objects
Open MinIO console: http://localhost:9001
- Bucket: `robot-lake`
- Path should contain:
  - `processed/telemetry_events/`
  - `checkpoints/stream_telemetry/`

---

## Common errors and fixes

### Error: S3A classes not found
- Rebuild the Docker image: `docker compose --profile spark build --no-cache`
- All JARs are fetched via `wget` during `docker build`, not at runtime.

### Error: bucket does not exist
- Create `robot-lake` in MinIO UI.

### Error: JDBC/Postgres connection
- Verify Postgres container is up and credentials are:
  - user: `robot`
  - password: `robot`
  - db: `robot_ops`

### Error: no input data
- Confirm Kafka topic receives messages (`kafka-console-consumer`).

---

## Beginner note
This is your first real data-engineering layer in the project:
- Kafka = input stream
- Spark = processing engine
- Delta = long-term lakehouse storage
- PostgreSQL = fast operational analytics table
