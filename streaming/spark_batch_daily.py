"""Stage 9: Daily batch aggregation job.

Reads processed telemetry Delta data from MinIO, computes daily robot KPIs,
and writes results to:
1) Curated Delta table in MinIO
2) PostgreSQL summary table
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    col,
    count,
    max as smax,
    min as smin,
    sum as ssum,
    to_date,
)

import os

# ---------------------------------------------------------------------------
# Runtime config — overridable via environment variables.
# ---------------------------------------------------------------------------
POSTGRES_URL      = os.environ.get("POSTGRES_URL",     "jdbc:postgresql://localhost:5432/robot_ops")
POSTGRES_USER     = os.environ.get("POSTGRES_USER",    "robot")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD","robot")
MINIO_ENDPOINT    = os.environ.get("MINIO_ENDPOINT",   "http://localhost:9000")
MINIO_ACCESS_KEY  = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY  = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
PROCESSED_PATH    = os.environ.get("DELTA_PROCESSED_PATH", "s3a://robot-lake/processed/telemetry_events")
CURATED_PATH      = os.environ.get("DELTA_CURATED_PATH",   "s3a://robot-lake/curated/daily_robot_summary")


def create_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("robot-daily-summary-batch")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


if __name__ == "__main__":
    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    processed_path = PROCESSED_PATH
    curated_path = CURATED_PATH

    df = (
        spark.read.format("delta")
        .load(processed_path)
        .withColumn("event_date", to_date(col("event_ts")))
    )

    # Daily KPI aggregation
    daily = (
        df.groupBy("robot_id", "event_date")
        .agg(
            count("*").alias("events_count"),
            avg("speed_mps").alias("avg_speed_mps"),
            smax("speed_mps").alias("max_speed_mps"),
            avg("battery_degradation_score").alias("avg_battery_degradation"),
            ssum("anomaly_flag").alias("anomaly_events"),
            smin("payload.percentage").alias("min_battery_pct"),
        )
        .withColumn("failure_risk_flag", (col("anomaly_events") > 10).cast("int"))
    )

    # Write curated Delta table
    (
        daily.write.format("delta")
        .mode("overwrite")
        .partitionBy("event_date")
        .save(curated_path)
    )

    # Write serving summary to PostgreSQL
    (
        daily.write.mode("append")
        .format("jdbc")
        .option("url", POSTGRES_URL)
        .option("dbtable", "daily_robot_summary")
        .option("user", POSTGRES_USER)
        .option("password", POSTGRES_PASSWORD)
        .option("driver", "org.postgresql.Driver")
        .save()
    )

    print("Daily batch summary completed successfully")
    spark.stop()
