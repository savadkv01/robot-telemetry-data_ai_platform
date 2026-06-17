-- =============================================================================
-- Stage 11: Analytics Layer — PostgreSQL Queries
-- Database: robot_ops
-- Tables used:
--   telemetry_operational   (written by Spark Structured Streaming, Stage 7)
--   daily_robot_summary     (written by Spark batch job, Stage 9)
--
-- KPI Definitions:
--   speed_mps               Euclidean speed derived from odom vx/vy/vz (m/s)
--   battery_degradation_score  (1 - battery_pct) * 100; higher = more degraded
--   anomaly_flag            1 when speed > 2.5 m/s, battery < 15%, or
--                           min_distance < 0.20 m; else 0
--   failure_risk_flag       1 when a robot accumulates > 10 anomaly events in
--                           a day (set by batch job, Stage 9)
-- =============================================================================


-- =============================================================================
-- REPORT 1: Fleet Health Snapshot
-- Business use: Operations manager sees current health of every robot at a glance.
-- Shows the most recent telemetry record per robot.
-- =============================================================================
SELECT
    robot_id,
    MAX(event_ts)                                          AS last_seen,
    ROUND(AVG(speed_mps)::numeric, 3)                     AS recent_avg_speed_mps,
    ROUND(MIN(battery_degradation_score)::numeric, 1)     AS best_battery_score,
    ROUND(MAX(battery_degradation_score)::numeric, 1)     AS worst_battery_score,
    SUM(anomaly_flag)                                     AS anomaly_count,
    COUNT(*)                                              AS total_events
FROM telemetry_operational
WHERE event_ts >= NOW() - INTERVAL '1 hour'
GROUP BY robot_id
ORDER BY anomaly_count DESC, last_seen DESC;


-- =============================================================================
-- REPORT 2: Battery Degradation Trend (last 24 hours, 30-minute buckets)
-- Business use: Maintenance lead tracks battery drain curve per robot.
-- A steep curve indicates a failing battery cell.
-- =============================================================================
SELECT
    robot_id,
    DATE_TRUNC('minute', event_ts) - 
        INTERVAL '1 minute' * MOD(
            EXTRACT(MINUTE FROM event_ts)::int, 30
        )                                                  AS bucket_30m,
    ROUND(AVG(battery_degradation_score)::numeric, 2)    AS avg_degradation_score,
    COUNT(*)                                              AS samples
FROM telemetry_operational
WHERE event_ts >= NOW() - INTERVAL '24 hours'
  AND battery_degradation_score IS NOT NULL
GROUP BY robot_id, bucket_30m
ORDER BY robot_id, bucket_30m;


-- =============================================================================
-- REPORT 3: Anomaly Events Detail
-- Business use: Safety review — list every event where the robot behaved
-- abnormally (speed spike, near-collision, low battery).
-- =============================================================================
SELECT
    robot_id,
    event_ts,
    source_topic,
    ROUND(speed_mps::numeric, 3)                         AS speed_mps,
    ROUND(battery_degradation_score::numeric, 2)         AS battery_degradation_score
FROM telemetry_operational
WHERE anomaly_flag = 1
ORDER BY event_ts DESC
LIMIT 500;


-- =============================================================================
-- REPORT 4: Robots At Failure Risk Today
-- Business use: Maintenance planner sees which robots need attention today.
-- Failure risk flag is set when anomaly_events > 10 in a day.
-- =============================================================================
SELECT
    robot_id,
    event_date,
    anomaly_events,
    ROUND(avg_battery_degradation::numeric, 2)           AS avg_battery_degradation,
    ROUND(min_battery_pct::numeric * 100, 1)             AS min_battery_pct,
    ROUND(avg_speed_mps::numeric, 3)                     AS avg_speed_mps,
    ROUND(max_speed_mps::numeric, 3)                     AS max_speed_mps,
    events_count
FROM daily_robot_summary
WHERE failure_risk_flag = 1
ORDER BY event_date DESC, anomaly_events DESC;


-- =============================================================================
-- REPORT 5: Daily Fleet Performance KPIs
-- Business use: Operations director reviews fleet-wide daily performance summary.
-- =============================================================================
SELECT
    event_date,
    COUNT(DISTINCT robot_id)                              AS active_robots,
    SUM(events_count)                                     AS total_events,
    ROUND(AVG(avg_speed_mps)::numeric, 3)                AS fleet_avg_speed_mps,
    ROUND(MAX(max_speed_mps)::numeric, 3)                AS fleet_max_speed_mps,
    SUM(anomaly_events)                                   AS fleet_anomaly_events,
    SUM(failure_risk_flag)                                AS robots_at_risk,
    ROUND(AVG(min_battery_pct)::numeric * 100, 1)        AS fleet_avg_min_battery_pct
FROM daily_robot_summary
GROUP BY event_date
ORDER BY event_date DESC
LIMIT 30;


-- =============================================================================
-- REPORT 6: Per-Robot Performance History (7-day trend)
-- Business use: Analyst compares a specific robot's week-over-week health.
-- Replace 'robot-001' with the target robot_id as needed.
-- =============================================================================
SELECT
    robot_id,
    event_date,
    events_count,
    ROUND(avg_speed_mps::numeric, 3)                     AS avg_speed_mps,
    ROUND(max_speed_mps::numeric, 3)                     AS max_speed_mps,
    ROUND(avg_battery_degradation::numeric, 2)           AS avg_battery_degradation,
    anomaly_events,
    ROUND(min_battery_pct::numeric * 100, 1)             AS min_battery_pct,
    failure_risk_flag
FROM daily_robot_summary
WHERE robot_id = 'robot-001'
  AND event_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY event_date;


-- =============================================================================
-- REPORT 7: Topic Throughput Breakdown
-- Business use: Data platform owner validates data completeness — confirms all
-- sensor topics (/imu, /odom, /battery_state, /scan) are flowing.
-- =============================================================================
SELECT
    robot_id,
    source_topic,
    COUNT(*)                                              AS event_count,
    MIN(event_ts)                                         AS first_event,
    MAX(event_ts)                                         AS last_event,
    ROUND(
        COUNT(*) / GREATEST(
            EXTRACT(EPOCH FROM (MAX(event_ts) - MIN(event_ts))), 1
        )::numeric, 2
    )                                                     AS events_per_second
FROM telemetry_operational
GROUP BY robot_id, source_topic
ORDER BY robot_id, source_topic;


-- =============================================================================
-- REPORT 8: Anomaly Hotspot Windows (rolling 5-minute windows, last 4 hours)
-- Business use: Identify *when* anomalies cluster — useful for diagnosing
-- environmental causes (e.g. a specific route segment causing near-collisions).
-- =============================================================================
SELECT
    robot_id,
    DATE_TRUNC('minute', event_ts) -
        INTERVAL '1 minute' * MOD(
            EXTRACT(MINUTE FROM event_ts)::int, 5
        )                                                  AS window_5m,
    SUM(anomaly_flag)                                     AS anomaly_events,
    COUNT(*)                                              AS total_events,
    ROUND(
        100.0 * SUM(anomaly_flag) / COUNT(*), 1
    )                                                     AS anomaly_rate_pct
FROM telemetry_operational
WHERE event_ts >= NOW() - INTERVAL '4 hours'
GROUP BY robot_id, window_5m
HAVING SUM(anomaly_flag) > 0
ORDER BY anomaly_events DESC, window_5m DESC;


-- =============================================================================
-- REPORT 9: Robot Operational Availability
-- Business use: Measures what % of expected time each robot was actively
-- sending telemetry — a proxy for uptime.
-- Assumes a 28,800-second shift (8 hours), 1 event/second expected baseline.
-- Adjust SHIFT_SECONDS to match actual operational window.
-- =============================================================================
WITH constants AS (
    SELECT 28800.0 AS shift_seconds
),
robot_active AS (
    SELECT
        robot_id,
        event_date,
        EXTRACT(EPOCH FROM (MAX(event_ts) - MIN(event_ts))) AS active_seconds
    FROM telemetry_operational
    GROUP BY robot_id, event_date
)
SELECT
    ra.robot_id,
    ra.event_date,
    ROUND(ra.active_seconds::numeric, 0)                 AS active_seconds,
    ROUND(c.shift_seconds, 0)                            AS expected_shift_seconds,
    ROUND(
        LEAST(100.0 * ra.active_seconds / c.shift_seconds, 100.0)::numeric, 1
    )                                                    AS availability_pct
FROM robot_active ra
CROSS JOIN constants c
ORDER BY ra.event_date DESC, ra.robot_id;


-- =============================================================================
-- REPORT 10: Maintenance Priority Ranking
-- Business use: Maintenance planner ranks all robots from most to least urgent
-- based on a weighted score combining recent anomalies and battery degradation.
-- Score = (anomaly_events * 2) + avg_battery_degradation
-- Higher score = higher maintenance priority.
-- =============================================================================
SELECT
    robot_id,
    SUM(anomaly_events)                                   AS total_anomalies_7d,
    ROUND(AVG(avg_battery_degradation)::numeric, 2)      AS avg_degradation_7d,
    ROUND(AVG(min_battery_pct)::numeric * 100, 1)        AS avg_min_battery_pct_7d,
    SUM(failure_risk_flag)                                AS high_risk_days,
    ROUND(
        (SUM(anomaly_events) * 2.0
         + AVG(avg_battery_degradation))::numeric, 2
    )                                                    AS maintenance_priority_score
FROM daily_robot_summary
WHERE event_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY robot_id
ORDER BY maintenance_priority_score DESC;
