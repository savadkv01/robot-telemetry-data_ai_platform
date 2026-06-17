# Stage 12 — Grafana Analytics Dashboard

This stage adds a full analytical Grafana dashboard powered by PostgreSQL, providing business-level fleet insights without requiring SQL knowledge.

---

## Implemented files

| File | Description |
|------|-------------|
| `infra/grafana/dashboards/robot_analytics.json` | 22-panel analytics dashboard |

The dashboard is auto-provisioned alongside the existing `robot_health.json` dashboard. No manual Grafana import needed.

---

## Accessing the dashboard

1. Ensure Docker infra is running:
   ```powershell
   cd "c:\D Drive\Projects\Robotics_DE\robot-telemetry-platform\infra"
   docker compose up -d
   ```

2. Open Grafana: http://localhost:3000 (login: `admin` / `admin`)

3. Go to **Dashboards → Robotics → Robot Fleet Analytics**

> The dashboard requires data in PostgreSQL. Run the full pipeline first (see Stage 11 commands).

---

## Dashboard structure

### Row 1 — Fleet Overview

**Fleet Health Snapshot** (table)

Source: `telemetry_operational`

Shows the most recent telemetry record aggregated per robot within the selected time window. Columns:
- **Anomaly Count** — red ≥ 10, yellow ≥ 3
- **Worst Battery Score** — red ≥ 80, yellow ≥ 50
- **Avg Speed (m/s)** — red ≥ 2.5, yellow ≥ 1.5

---

### Row 2 — Today's Key Metrics (6 stat panels)

All panels query `daily_robot_summary` at the latest `event_date`.

| Panel | Threshold colours |
|-------|------------------|
| Total Events | Blue |
| Robots at Failure Risk | Green → Yellow (≥1) → Red (≥2) |
| Fleet Anomaly Events | Green → Yellow (≥10) → Red (≥25) |
| Fleet Avg Min Battery % | Red → Yellow (≥20%) → Green (≥40%) |
| Active Robots | Green |
| Fleet Avg Speed (m/s) | Green → Yellow (≥1.5) → Red (≥2.5) |

---

### Row 3 — Battery & Performance Trends

**Battery Degradation Trend** (timeseries)

Source: `telemetry_operational`

- 30-minute time buckets
- One line per robot (pivoted in SQL)
- Threshold line at score 80 (danger level)
- Steep rising curve = failing battery

**Topic Throughput Breakdown** (table)

Source: `telemetry_operational`

- One row per robot × topic combination
- **Events/sec** column: red = 0, yellow ≥ 0.1, green ≥ 0.5
- Validates all 4 sensor topics (`/imu`, `/odom`, `/battery_state`, `/scan`) are flowing

---

### Row 4 — Anomaly Analysis

**Anomaly Hotspot Windows** (bar chart timeseries)

Source: `telemetry_operational`

- 5-minute aggregation windows
- One bar series per robot
- Identifies *when* anomalies cluster in time — useful for diagnosing route-specific or environmental causes

**Recent Anomaly Events** (table)

Source: `telemetry_operational`

- Last 100 anomaly events sorted newest-first
- **Speed (m/s)** column: red ≥ 2.5, yellow ≥ 1.5
- **Battery Degradation** column: red ≥ 80, yellow ≥ 50
- Filterable by robot using the template variable

---

### Row 5 — Daily Fleet KPIs

**Daily Fleet KPIs — Last 30 Days** (table)

Source: `daily_robot_summary`

Fleet-wide aggregates per day. Columns with thresholds:
- **Robots at Risk** — red ≥ 2, yellow ≥ 1
- **Anomaly Events** — red ≥ 25, yellow ≥ 10
- **Avg Min Battery %** — red < 20, yellow < 40

---

### Row 6 — Maintenance & Reliability

**Maintenance Priority Ranking** (table with inline gauge)

Source: `daily_robot_summary` — last 7 days

Score formula: `(total_anomalies × 2) + avg_battery_degradation`

Columns:
- **Priority Score** — rendered as an inline LCD gauge (green → yellow at 20 → red at 50)
- **High-Risk Days** — days where `failure_risk_flag = 1`

**Operational Availability %** (gauge panel)

Source: `telemetry_operational`

Formula: `active_seconds / 28800 × 100` (baseline: 8-hour shift = 28,800 seconds)

- Red < 60%, Yellow < 80%, Green ≥ 80%
- One gauge arc per robot

---

### Row 7 — Per-Robot History

**Per-Robot 7-Day Performance History** (table)

Source: `daily_robot_summary`

Filtered by the `$robot_id` template variable. Columns:
- **Failure Risk** — value-mapped to `OK` (green) or `AT RISK` (red)
- **Avg Battery Degradation** — red ≥ 70, yellow ≥ 40
- **Anomaly Events** — red ≥ 10, yellow ≥ 5

---

## Template variable

The dashboard has a **Robot ID** variable (`$robot_id`) populated dynamically from:

```sql
SELECT DISTINCT robot_id FROM telemetry_operational ORDER BY 1
```

- Multi-select enabled
- "All" option included
- Refreshes on time range change
- Used in the Per-Robot History panel; other panels aggregate across all robots

---

## Datasource

The dashboard uses the **PostgresRobotOps** datasource (uid: `postgres_robot_ops`) provisioned in `infra/grafana/provisioning/datasources/datasource.yml`:

```yaml
- name: PostgresRobotOps
  uid: postgres_robot_ops
  type: postgres
  url: postgres:5432
  user: robot
  jsonData:
    database: robot_ops
    sslmode: disable
```

No DuckDB plugin is needed — the curated data written by Spark to PostgreSQL is equivalent to the Delta Lake data queried by DuckDB.

---

## Dashboard refresh and time range

| Setting | Value |
|---------|-------|
| Auto-refresh | 30 seconds |
| Default time range | Last 24 hours |
| Schema version | Grafana 39 (compatible with Grafana 11.x) |
| Dashboard UID | `robot-fleet-analytics` |

---

## Common issues

### Dashboard shows "No data"
- Ensure the Spark streaming and batch jobs have run and PostgreSQL has rows.
- Check the time range — default is last 24 hours. If test data is older, widen the range.

### "PostgresRobotOps" datasource not found
- Check `infra/grafana/provisioning/datasources/datasource.yml` exists and contains the `postgres_robot_ops` entry.
- Restart the Grafana container: `docker compose restart grafana`

### Dashboard not appearing in Grafana
- Grafana scans `provisioning/dashboards/` every 15 seconds.
- If it still doesn't appear after 30 seconds: `docker compose restart grafana`

### Robot ID variable is empty
- The variable queries `telemetry_operational`. If the table is empty, the dropdown will be empty.
- Run the injector and streaming job first.
