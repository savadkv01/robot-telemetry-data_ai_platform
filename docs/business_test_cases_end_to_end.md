# End-to-End Business Test Cases — Robot Telemetry Data Platform

This document defines **business-level, end-to-end acceptance test cases** for the
Robot Telemetry Data Platform. These tests validate that the platform delivers real
operational value (fleet visibility, failure prevention, performance analytics) — they
are **not** unit tests or code/syntax checks.

Each test case is written from the perspective of a **business stakeholder** (operations
manager, maintenance lead, fleet analyst) and follows a Given / When / Then structure so
it can be executed manually or automated later.

## How to read these tests

- **Persona** — the business role who benefits from the outcome.
- **Business goal** — the real-world problem being verified.
- **Preconditions** — system state before the test.
- **Steps** — the end-to-end actions across the pipeline.
- **Expected business outcome** — what success looks like for the business.
- **Pass / Fail criteria** — the measurable acceptance condition.

## Test environment baseline

| Item | Value |
|------|-------|
| Robot fleet | At least 1 simulated robot (`robot-001`) publishing `/imu`, `/odom`, `/battery_state`, `/scan` |
| Pipeline | ROS2 → Kafka → Spark Streaming → Delta Lake (MinIO) + PostgreSQL |
| Observability | Prometheus + Grafana + custom metrics API |
| Data window | Single shift simulated (continuous telemetry for the duration of the test) |

---

## TC-01 — Fleet operator gains real-time visibility into robot health

| Field | Detail |
|-------|--------|
| **Persona** | Warehouse Operations Manager |
| **Business goal** | Know whether robots are alive and healthy *right now*, without inspecting them physically. |

**Preconditions**
- Infrastructure is running (`docker compose up -d`).
- The robot is publishing telemetry and the ROS2 → Kafka bridge is active.

**Steps**
1. Start the simulated robot and the telemetry bridge.
2. Open the Grafana **Robot Health** dashboard.
3. Observe live battery percentage, speed, and event throughput for `robot-001`.

**Expected business outcome**
- The dashboard reflects the robot's current state within seconds of telemetry being produced.
- Battery, speed, and activity panels update continuously.

**Pass / Fail criteria**
- ✅ **Pass:** Dashboard shows live, changing values for the active robot within ~10 seconds.
- ❌ **Fail:** Panels show "No data", stale values, or never update.

---

## TC-02 — Early warning on battery degradation prevents mid-task failure

| Field | Detail |
|-------|--------|
| **Persona** | Maintenance Lead |
| **Business goal** | Be alerted *before* a robot strands itself due to a depleted/degrading battery. |

**Preconditions**
- Robot is running long enough for battery to discharge meaningfully.

**Steps**
1. Let the simulated robot run so the battery percentage steadily drops.
2. Watch the battery metric in Grafana / the custom metrics API.
3. Identify the point where battery crosses a low-health threshold (e.g. below 20%).

**Expected business outcome**
- The platform surfaces declining battery health as a visible downward trend.
- A low-battery condition is distinguishable well before the battery is empty.

**Pass / Fail criteria**
- ✅ **Pass:** Battery trend is observable and the low-battery state is detectable with lead time (not at 0%).
- ❌ **Fail:** Battery decline is invisible, or only detectable after depletion.

---

## TC-03 — Anomaly detection flags abnormal robot behavior in real time

| Field | Detail |
|-------|--------|
| **Persona** | Operations Manager |
| **Business goal** | Catch unsafe / abnormal behavior (e.g. unexpected speed spikes) while the robot is running. |

**Preconditions**
- Spark Structured Streaming job is running and writing to PostgreSQL.

**Steps**
1. Run the telemetry pipeline through Spark streaming.
2. Allow normal operation, then introduce/observe an abnormal movement condition (e.g. a speed spike beyond expected range).
3. Check the anomaly flag in PostgreSQL and the `robot_anomaly_flag` metric.

**Expected business outcome**
- Normal telemetry is flagged as healthy; the abnormal condition raises the anomaly flag.

**Pass / Fail criteria**
- ✅ **Pass:** Anomaly flag = 0 during normal operation and = 1 when the abnormal condition occurs.
- ❌ **Fail:** Anomalies are missed, or normal behavior is constantly flagged (false positives).

---

## TC-04 — No telemetry is lost when the database is briefly unavailable

| Field | Detail |
|-------|--------|
| **Persona** | Data Platform Owner |
| **Business goal** | Guarantee that robot data is never dropped during a downstream outage (decoupling value of Kafka). |

**Preconditions**
- Full pipeline running and ingesting telemetry.

**Steps**
1. While telemetry is flowing, stop the PostgreSQL service (simulate a downstream outage).
2. Keep the robot and bridge running for a short period.
3. Restart PostgreSQL and resume the Spark streaming job.
4. Compare event counts produced to Kafka vs. events eventually landed downstream.

**Expected business outcome**
- Telemetry continues to be captured in Kafka during the outage and is processed once the database recovers — no permanent data loss.

**Pass / Fail criteria**
- ✅ **Pass:** Events buffered during the outage are recoverable and processed after recovery; no gap in the captured stream.
- ❌ **Fail:** Telemetry generated during the outage is permanently lost.

---

## TC-05 — Historical telemetry is retained for audit and replay

| Field | Detail |
|-------|--------|
| **Persona** | Fleet Analyst |
| **Business goal** | Investigate "what happened" after an incident using a reliable historical record. |

**Preconditions**
- Streaming job has written processed telemetry to the Delta Lake (MinIO) processed zone.

**Steps**
1. Run the pipeline for a defined period.
2. Browse the MinIO bucket and confirm Delta files exist in the processed zone.
3. Query the historical data (PostgreSQL or DuckDB on Delta) for the test window.

**Expected business outcome**
- All telemetry from the test window is queryable later, partitioned by date/robot for efficient lookup.

**Pass / Fail criteria**
- ✅ **Pass:** Historical events for the test window are present and queryable after the fact.
- ❌ **Fail:** Data is missing, unqueryable, or not retained.

---

## TC-06 — Daily fleet performance summary supports management reporting

| Field | Detail |
|-------|--------|
| **Persona** | Operations Director |
| **Business goal** | Get per-robot daily KPIs (activity, average battery, anomalies) for decision-making. |

**Preconditions**
- At least one day's worth of telemetry exists in the data lake.

**Steps**
1. Run the daily batch aggregation job.
2. Inspect the resulting summary table.
3. Review KPIs per robot: total events, average/min battery, anomaly count, active time.

**Expected business outcome**
- A concise per-robot, per-day summary is produced that management can use for reporting and maintenance planning.

**Pass / Fail criteria**
- ✅ **Pass:** Summary table contains one row per robot per day with correct, non-empty KPI values.
- ❌ **Fail:** Summary is missing, empty, or KPIs are clearly wrong (e.g. zero events for an active robot).

---

## TC-07 — Platform scales to multiple robots without losing per-robot identity

| Field | Detail |
|-------|--------|
| **Persona** | Fleet Operations Manager |
| **Business goal** | Operate a *fleet*, not a single robot — each robot's data stays correctly attributed. |

**Preconditions**
- Ability to run more than one robot identity (e.g. `robot-001` and `robot-002` via `ROBOT_ID`).

**Steps**
1. Launch two telemetry sources with distinct robot IDs.
2. Let both stream through the pipeline.
3. Filter dashboards and query results by `robot_id`.

**Expected business outcome**
- Each robot's metrics and history are independently visible and never mixed together.

**Pass / Fail criteria**
- ✅ **Pass:** Data for each robot is correctly attributed and separable by `robot_id`.
- ❌ **Fail:** Robot data is merged, mislabeled, or one robot's data overwrites another's.

---

## TC-08 — Operational metrics enable proactive maintenance scheduling

| Field | Detail |
|-------|--------|
| **Persona** | Maintenance Planner |
| **Business goal** | Move from reactive repair to scheduled, data-driven maintenance. |

**Preconditions**
- Several test runs / days of summary data exist.

**Steps**
1. Review battery trend and anomaly counts across multiple runs from the summary tables.
2. Identify robots trending toward degraded health.
3. Decide a maintenance action based on the data.

**Expected business outcome**
- The data clearly differentiates a healthy robot from a degrading one, enabling a maintenance decision *before* failure.

**Pass / Fail criteria**
- ✅ **Pass:** Degrading robots are distinguishable from healthy ones using platform data alone.
- ❌ **Fail:** The data provides no actionable signal to plan maintenance.

---

## Traceability matrix

| Test case | Business value verified | Primary stage(s) exercised |
|-----------|-------------------------|----------------------------|
| TC-01 | Real-time fleet visibility | 4, 5, 6, 10 |
| TC-02 | Failure prevention (battery) | 4, 5, 7, 10 |
| TC-03 | Real-time anomaly detection | 5, 7, 10 |
| TC-04 | Zero data loss / decoupling | 5, 6, 7 |
| TC-05 | Historical audit & replay | 7, 8, 11 |
| TC-06 | Management KPI reporting | 9, 11 |
| TC-07 | Fleet scalability | 5, 7, 10 |
| TC-08 | Proactive maintenance | 9, 11 |

## Execution notes

- These tests are **outcome-focused**: they pass or fail based on observable business
  results, not on internal implementation details.
- Run them in order on a clean environment for a full end-to-end acceptance pass.
- Capture screenshots of Grafana panels and query outputs as evidence for each test.
