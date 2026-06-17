"""Stage 11: Analytics Layer — DuckDB queries on Delta Lake (MinIO).

Connects to MinIO via the DuckDB httpfs + delta extensions, runs analytical
queries directly on the Delta Lake parquet files without needing a running
Spark session, and prints formatted performance reports to stdout.

Delta Lake paths (MinIO):
    Processed zone:  s3://robot-lake/processed/telemetry_events/
    Curated zone:    s3://robot-lake/curated/daily_robot_summary/

Usage:
    python sql/analytics_duckdb.py

Optional environment overrides:
    MINIO_ENDPOINT    default: http://localhost:9000
    MINIO_ACCESS_KEY  default: minioadmin
    MINIO_SECRET_KEY  default: minioadmin
"""

import os
import textwrap

import duckdb


# ---------------------------------------------------------------------------
# MinIO / S3 connection settings
# ---------------------------------------------------------------------------
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

PROCESSED_PATH = "s3://robot-lake/processed/telemetry_events"
CURATED_PATH = "s3://robot-lake/curated/daily_robot_summary"


def configure_duckdb(con: duckdb.DuckDBPyConnection) -> None:
    """Install and configure DuckDB extensions for MinIO Delta Lake access."""
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    con.execute("INSTALL delta;")
    con.execute("LOAD delta;")

    # Use CREATE SECRET (DuckDB 1.x recommended approach) instead of SET s3_*
    # so credentials are applied to delta_scan S3 calls as well.
    endpoint = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
    use_ssl = "true" if MINIO_ENDPOINT.startswith("https") else "false"
    con.execute(f"""
        CREATE OR REPLACE SECRET minio_secret (
            TYPE S3,
            KEY_ID '{MINIO_ACCESS_KEY}',
            SECRET '{MINIO_SECRET_KEY}',
            ENDPOINT '{endpoint}',
            URL_STYLE 'path',
            USE_SSL {use_ssl},
            REGION 'us-east-1'
        );
    """)


def print_report(title: str, result: duckdb.DuckDBPyRelation) -> None:
    """Print a labeled, formatted report to stdout."""
    separator = "=" * 72
    print(f"\n{separator}")
    print(f"  {title}")
    print(separator)
    df = result.df()
    if df.empty:
        print("  (no data)")
    else:
        print(df.to_string(index=False))
    print()


def run_fleet_health_snapshot(con: duckdb.DuckDBPyConnection) -> None:
    """REPORT 1: Current health of every robot — latest metrics summary.

    Business use: Operations manager identifies unhealthy robots at a glance.
    """
    result = con.execute(f"""
        SELECT
            robot_id,
            MAX(event_ts)                                  AS last_seen,
            ROUND(AVG(speed_mps), 3)                       AS avg_speed_mps,
            ROUND(MAX(battery_degradation_score), 2)       AS max_degradation,
            SUM(anomaly_flag)                              AS anomaly_count,
            COUNT(*)                                       AS total_events
        FROM delta_scan('{PROCESSED_PATH}')
        GROUP BY robot_id
        ORDER BY anomaly_count DESC
    """)
    print_report("REPORT 1: Fleet Health Snapshot (All Time)", result)


def run_battery_degradation_trend(con: duckdb.DuckDBPyConnection) -> None:
    """REPORT 2: Battery degradation over time per robot (hourly buckets).

    Business use: Maintenance lead tracks battery drain curve.
    A steep positive slope suggests a failing battery.
    """
    result = con.execute(f"""
        SELECT
            robot_id,
            DATE_TRUNC('hour', event_ts)                   AS hour_bucket,
            ROUND(AVG(battery_degradation_score), 2)       AS avg_degradation_score,
            COUNT(*)                                        AS samples
        FROM delta_scan('{PROCESSED_PATH}')
        WHERE battery_degradation_score IS NOT NULL
        GROUP BY robot_id, hour_bucket
        ORDER BY robot_id, hour_bucket
    """)
    print_report("REPORT 2: Battery Degradation Trend (Hourly)", result)


def run_anomaly_summary(con: duckdb.DuckDBPyConnection) -> None:
    """REPORT 3: Anomaly breakdown by robot and topic.

    Business use: Safety review — how often does each robot misbehave,
    and which sensor type most commonly triggers the anomaly flag?
    """
    result = con.execute(f"""
        SELECT
            robot_id,
            source_topic,
            SUM(anomaly_flag)                              AS anomaly_events,
            COUNT(*)                                       AS total_events,
            ROUND(100.0 * SUM(anomaly_flag) / COUNT(*), 1) AS anomaly_rate_pct,
            ROUND(AVG(speed_mps), 3)                       AS avg_speed_mps,
            ROUND(AVG(battery_degradation_score), 2)       AS avg_degradation
        FROM delta_scan('{PROCESSED_PATH}')
        GROUP BY robot_id, source_topic
        ORDER BY robot_id, anomaly_events DESC
    """)
    print_report("REPORT 3: Anomaly Summary by Robot and Topic", result)


def run_daily_kpi_report(con: duckdb.DuckDBPyConnection) -> None:
    """REPORT 4: Daily KPI summary for every robot from the curated layer.

    Business use: Operations director reviews fleet-wide daily performance.
    """
    result = con.execute(f"""
        SELECT
            event_date,
            robot_id,
            events_count,
            ROUND(avg_speed_mps, 3)                        AS avg_speed_mps,
            ROUND(max_speed_mps, 3)                        AS max_speed_mps,
            ROUND(avg_battery_degradation, 2)              AS avg_battery_degradation,
            anomaly_events,
            ROUND(min_battery_pct * 100, 1)                AS min_battery_pct,
            failure_risk_flag
        FROM delta_scan('{CURATED_PATH}')
        ORDER BY event_date DESC, anomaly_events DESC
    """)
    print_report("REPORT 4: Daily Robot KPI Summary (Curated Layer)", result)


def run_maintenance_priority_ranking(con: duckdb.DuckDBPyConnection) -> None:
    """REPORT 5: Maintenance priority score per robot.

    Business use: Maintenance planner ranks robots by urgency.
    Score = (total_anomalies * 2) + avg_battery_degradation.
    Higher score = schedule maintenance sooner.
    """
    result = con.execute(f"""
        SELECT
            robot_id,
            SUM(anomaly_events)                            AS total_anomalies,
            ROUND(AVG(avg_battery_degradation), 2)         AS avg_degradation,
            ROUND(AVG(min_battery_pct) * 100, 1)           AS avg_min_battery_pct,
            SUM(failure_risk_flag)                         AS high_risk_days,
            ROUND(
                SUM(anomaly_events) * 2.0
                + AVG(avg_battery_degradation), 2
            )                                              AS maintenance_priority_score
        FROM delta_scan('{CURATED_PATH}')
        GROUP BY robot_id
        ORDER BY maintenance_priority_score DESC
    """)
    print_report("REPORT 5: Maintenance Priority Ranking", result)


def run_speed_percentiles(con: duckdb.DuckDBPyConnection) -> None:
    """REPORT 6: Speed distribution percentiles per robot.

    Business use: Fleet analyst understands normal vs. extreme speed behaviour.
    p95/p99 help tune anomaly detection thresholds.
    """
    result = con.execute(f"""
        SELECT
            robot_id,
            ROUND(MIN(speed_mps), 3)                        AS min_speed,
            ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP
                  (ORDER BY speed_mps), 3)                  AS p50_speed,
            ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP
                  (ORDER BY speed_mps), 3)                  AS p90_speed,
            ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP
                  (ORDER BY speed_mps), 3)                  AS p95_speed,
            ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP
                  (ORDER BY speed_mps), 3)                  AS p99_speed,
            ROUND(MAX(speed_mps), 3)                        AS max_speed
        FROM delta_scan('{PROCESSED_PATH}')
        WHERE speed_mps IS NOT NULL
        GROUP BY robot_id
        ORDER BY robot_id
    """)
    print_report("REPORT 6: Speed Distribution Percentiles per Robot", result)


def run_topic_throughput(con: duckdb.DuckDBPyConnection) -> None:
    """REPORT 7: Events per second per topic — data completeness check.

    Business use: Data platform owner verifies all sensor topics are flowing
    and none are silently dropped.
    """
    result = con.execute(f"""
        SELECT
            robot_id,
            source_topic,
            COUNT(*)                                        AS total_events,
            MIN(event_ts)                                   AS first_event,
            MAX(event_ts)                                   AS last_event,
            ROUND(
                COUNT(*) / GREATEST(
                    EPOCH(MAX(event_ts) - MIN(event_ts)), 1
                ), 2
            )                                               AS events_per_second
        FROM delta_scan('{PROCESSED_PATH}')
        GROUP BY robot_id, source_topic
        ORDER BY robot_id, source_topic
    """)
    print_report("REPORT 7: Topic Throughput Breakdown", result)


if __name__ == "__main__":
    print(textwrap.dedent(f"""
    =========================================================
      Stage 11 — DuckDB Analytics on Delta Lake
      MinIO endpoint : {MINIO_ENDPOINT}
      Processed path : {PROCESSED_PATH}
      Curated path   : {CURATED_PATH}
    =========================================================
    Connecting to DuckDB and configuring MinIO access...
    """))

    con = duckdb.connect()
    configure_duckdb(con)
    print("Connected. Running reports...\n")

    run_fleet_health_snapshot(con)
    run_battery_degradation_trend(con)
    run_anomaly_summary(con)
    run_daily_kpi_report(con)
    run_maintenance_priority_ranking(con)
    run_speed_percentiles(con)
    run_topic_throughput(con)

    con.close()
    print("All reports completed.")
