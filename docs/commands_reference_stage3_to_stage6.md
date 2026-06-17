# Commands Reference (Stage 3 to Stage 6)

This document lists the commands used so far and explains why each command is needed.

## 1) Windows host setup (PowerShell)

```powershell
winget install -e --id Microsoft.VisualStudioCode
winget install -e --id Docker.DockerDesktop
winget install -e --id Git.Git
wsl --install -d Ubuntu-22.04
```

Why:
- Installs editor, container runtime, Git, and Linux runtime (WSL2 Ubuntu) required by this project.

---

## 2) WSL verification and defaults (PowerShell)

```powershell
wsl --status
wsl -l -v
wsl --set-default-version 2
wsl --set-default Ubuntu-22.04
```

Why:
- Confirms WSL is available.
- Ensures Ubuntu-22.04 is installed and using WSL2.
- Sets Ubuntu as default distribution.

---

## 3) Create Linux user from root shell (Ubuntu as root)

```bash
adduser robotics
usermod -aG sudo robotics
printf "[user]\ndefault=robotics\n" > /etc/wsl.conf
exit
```

Why:
- Avoids developing as root.
- Grants admin rights through `sudo`.
- Makes `robotics` the default user for future sessions.

Then from PowerShell:

```powershell
wsl --shutdown
wsl -d Ubuntu-22.04
```

Why:
- Restarts WSL so new default user config is applied.

---

## 4) Ubuntu base packages (inside Ubuntu)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg2 lsb-release ca-certificates software-properties-common git build-essential python3-pip python3-venv unzip
```

Why:
- Updates OS packages and installs core build tools and Python tooling.

---

## 5) ROS2 + Gazebo installation (inside Ubuntu)

```bash
sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y ros-humble-desktop ros-humble-gazebo-ros-pkgs ros-dev-tools python3-colcon-common-extensions
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Why:
- Adds ROS2 apt source and key.
- Installs ROS2 Humble, Gazebo plugins, and build tools.
- Auto-loads ROS environment in new terminals.

---

## 6) Move project from Windows path to Linux home (inside Ubuntu)

```bash
mkdir -p ~/robot-telemetry-platform
cp -r "/mnt/c/D Drive/Projects/Robotics_DE/robot-telemetry-platform"/* ~/robot-telemetry-platform/
```

Why:
- Running ROS builds from Linux home is faster and more reliable than `/mnt/c` mount.

---

## 7) Build ROS workspace (inside Ubuntu)

```bash
cd ~/robot-telemetry-platform/robotics/ros2_ws
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

Why:
- Compiles custom ROS packages and exposes them to current shell.

---

## 8) Run simulation and verify topics (inside Ubuntu)

```bash
ros2 launch robot_description sim.launch.py
```

In another terminal:

```bash
source /opt/ros/humble/setup.bash
source ~/robot-telemetry-platform/robotics/ros2_ws/install/setup.bash
ros2 topic list
ros2 topic echo /imu
ros2 topic echo /odom
ros2 topic echo /battery_state
ros2 topic echo /scan
```

Why:
- Starts robot simulation and checks live telemetry topics.

---

## 9) Docker infrastructure for Stage 6 (PowerShell)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose up -d
docker compose ps
```

Why:
- Starts Kafka, MinIO, PostgreSQL, Prometheus, Grafana, and exporters.

---

## 10) Kafka topic commands (PowerShell)

```powershell
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --create --if-not-exists --topic robot.telemetry.v1 --partitions 3 --replication-factor 1
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```

Why:
- Creates telemetry stream topic used by the ROS2-to-Kafka bridge.

---

## 11) PostgreSQL schema verification (PowerShell)

```powershell
docker exec postgres psql -U robot -d robot_ops -c "\dt"
```

Why:
- Confirms `telemetry_operational` and `daily_robot_summary` tables were created.

---

## 12) Service endpoint checks (PowerShell)

```powershell
(Invoke-WebRequest -UseBasicParsing http://localhost:3000).StatusCode
(Invoke-WebRequest -UseBasicParsing http://localhost:9090/-/ready).StatusCode
(Invoke-WebRequest -UseBasicParsing http://localhost:9001).StatusCode
```

Why:
- Verifies Grafana, Prometheus, and MinIO are reachable.

---

## 13) ROS2 daemon recovery (inside Ubuntu)

```bash
unset ROS_MASTER_URI ROS_HOSTNAME ROS_IP
ros2 daemon stop
pkill -f _ros2_daemon
ros2 topic list
```

Why:
- Fixes occasional ROS2 daemon state errors (`!rclpy.ok()`) seen during development.

---

## 14) Optional cleanup commands used during troubleshooting

```bash
pkill -f gzserver || true
pkill -f gzclient || true
```

Why:
- Removes stale Gazebo processes that can block fresh launches.

```powershell
docker rm -f zookeeper kafka minio postgres prometheus grafana kafka-exporter postgres-exporter
```

Why:
- Removes stale container name conflicts from earlier test runs.

---

## Important beginner note
Always run ROS commands in Ubuntu terminals after:

```bash
source /opt/ros/humble/setup.bash
source ~/robot-telemetry-platform/robotics/ros2_ws/install/setup.bash
```

If these are missing, many ROS commands will fail or show empty results.

---

## Stage 7–12 Commands (Spark, Analytics, Grafana)

### 15) Build the Spark Docker image (PowerShell — one-time, ~5 min)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose --profile spark build
```

Why:
- Builds a custom Python + OpenJDK 21 + PySpark image.
- All 9 required JARs (Kafka, Delta Lake, PostgreSQL JDBC, Hadoop S3A, etc.) are downloaded via `wget` during the build and baked into the image.
- Must be run before any `spark` profile services.

---

### 16) Inject synthetic telemetry for pipeline testing (PowerShell)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose --profile spark run --rm injector
```

Why:
- Sends 2000 synthetic events (2 robots × 2 days × 500 events) to Kafka topic `robot.telemetry.v1`.
- Use this to populate the pipeline without needing ROS2/Gazebo running.
- robot-001 = healthy profile, robot-002 = degrading battery + higher anomaly rate.

---

### 17) Run Spark Structured Streaming job (PowerShell)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose --profile spark run --rm spark-streaming
```

Why:
- Reads telemetry events from Kafka.
- Computes `speed_mps`, `battery_degradation_score`, `anomaly_flag`.
- Writes to Delta Lake (`s3a://robot-lake/processed/telemetry_events/`) and PostgreSQL (`telemetry_operational`).
- Runs in trigger-once mode by default — exits cleanly after processing all available messages.

Verify results:
```powershell
docker exec postgres psql -U robot -d robot_ops -c "SELECT robot_id, COUNT(*) FROM telemetry_operational GROUP BY robot_id;"
```

---

### 18) Run Spark batch aggregation job (PowerShell)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose --profile spark run --rm spark-batch
```

Why:
- Reads processed telemetry from Delta Lake.
- Aggregates daily KPIs per robot (avg speed, min battery, anomaly count, failure risk flag).
- Writes to curated Delta (`s3a://robot-lake/curated/daily_robot_summary/`) and PostgreSQL (`daily_robot_summary`).

Verify results:
```powershell
docker exec postgres psql -U robot -d robot_ops -c "SELECT * FROM daily_robot_summary ORDER BY event_date DESC;"
```

---

### 19) Run DuckDB analytics reports (PowerShell)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
docker compose --profile spark run --rm duckdb-analytics
```

Why:
- Runs 7 analytical reports directly on Delta Lake files via DuckDB — no Spark required at query time.
- Reports include fleet health, battery trend, anomaly summary, daily KPIs, maintenance priority, speed percentiles, topic throughput.

---

### 20) Run PostgreSQL analytical reports (PowerShell)

```powershell
docker exec postgres psql -U robot -d robot_ops -f /dev/stdin < "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\sql\analytics_postgresql.sql"
```

Or connect interactively:
```powershell
docker exec -it postgres psql -U robot -d robot_ops
```

Then paste individual queries from `sql/analytics_postgresql.sql`.

Why:
- 10 business reports: fleet snapshot, battery trend, anomaly detail, failure risk, daily KPIs, per-robot history, topic throughput, anomaly hotspots, availability %, maintenance ranking.

---

### 21) Open Grafana dashboards (browser)

```
http://localhost:3000
```

Login: `admin` / `admin`

Dashboards (under Robotics folder):
- **Robot Telemetry Health** — Prometheus-backed live metrics
- **Robot Fleet Analytics** — PostgreSQL-backed business analytics

Why:
- Both dashboards are auto-provisioned from `infra/grafana/dashboards/` on container start.
- Robot Fleet Analytics has a Robot ID variable for multi-robot filtering.

---

### 22) Full pipeline end-to-end run (PowerShell — all steps in order)

```powershell
cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"

# Start core infrastructure
docker compose up -d

# Build Spark image (first time only)
docker compose --profile spark build

# Step 1: inject test data
docker compose --profile spark run --rm injector

# Step 2: stream to Delta + PostgreSQL
docker compose --profile spark run --rm spark-streaming

# Step 3: daily aggregation
docker compose --profile spark run --rm spark-batch

# Step 4: analytics reports (stdout)
docker compose --profile spark run --rm duckdb-analytics

# Step 5: open Grafana
Start-Process "http://localhost:3000"
```

---

### 23) Start the FastAPI observability API (Ubuntu — optional)

```bash
cd ~/robot-telemetry-platform
source .venv/bin/activate
pip install -r observability/requirements.txt
uvicorn observability.robot_metrics_api:app --host 0.0.0.0 --port 8000
```

Why:
- Exposes custom robot metrics (`robot_battery_percentage`, `robot_speed_mps`, `robot_anomaly_flag`, etc.) to Prometheus.
- Without this, 3/4 Prometheus targets are UP — this completes the fourth (`robot_metrics_api`).
- Must be started manually from Ubuntu (it is not in Docker Compose to allow WSL ROS2 integration).
