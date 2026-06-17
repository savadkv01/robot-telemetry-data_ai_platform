"""Stage 7: Spark Structured Streaming pipeline.

Reads telemetry JSON events from Kafka topic `robot.telemetry.v1`,
computes features/anomaly flags, writes to:
1) Delta Lake in MinIO (processed zone)
2) PostgreSQL operational table
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    coalesce,
    from_json,
    lit,
    pow,
    sqrt,
    to_date,
    to_timestamp,
    when,
)
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

import os

# ---------------------------------------------------------------------------
# Runtime config — all values overridable via environment variables.
# Docker defaults use service names; local defaults use localhost.
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP   = os.environ.get("KAFKA_BOOTSTRAP_SERVERS",  "localhost:9092")
KAFKA_TOPIC       = os.environ.get("KAFKA_TELEMETRY_TOPIC",    "robot.telemetry.v1")
KAFKA_OFFSETS     = os.environ.get("KAFKA_STARTING_OFFSETS",   "earliest")
POSTGRES_URL      = os.environ.get("POSTGRES_URL",             "jdbc:postgresql://localhost:5432/robot_ops")
POSTGRES_USER     = os.environ.get("POSTGRES_USER",            "robot")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD",        "robot")
MINIO_ENDPOINT    = os.environ.get("MINIO_ENDPOINT",           "http://localhost:9000")
MINIO_ACCESS_KEY  = os.environ.get("MINIO_ACCESS_KEY",         "minioadmin")
MINIO_SECRET_KEY  = os.environ.get("MINIO_SECRET_KEY",         "minioadmin")
TRIGGER_ONCE      = os.environ.get("SPARK_TRIGGER_ONCE",       "false").lower() == "true"
PROCESSED_PATH    = os.environ.get("DELTA_PROCESSED_PATH",     "s3a://robot-lake/processed/telemetry_events")
CHECKPOINT_DELTA  = os.environ.get("CHECKPOINT_DELTA",         "s3a://robot-lake/checkpoints/stream_telemetry")
CHECKPOINT_PG     = os.environ.get("CHECKPOINT_PG",            "s3a://robot-lake/checkpoints/stream_postgres")


def create_spark() -> SparkSession:
    """Create Spark session with Delta, MinIO, and Postgres dependencies."""
    return (
        SparkSession.builder.appName("robot-telemetry-stream")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # MinIO S3A config
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def telemetry_schema() -> StructType:
    """JSON schema of events produced by ROS2->Kafka bridge."""
    payload_schema = StructType(
        [
            StructField("ax", DoubleType(), True),
            StructField("ay", DoubleType(), True),
            StructField("az", DoubleType(), True),
            StructField("gx", DoubleType(), True),
            StructField("gy", DoubleType(), True),
            StructField("gz", DoubleType(), True),
            StructField("x", DoubleType(), True),
            StructField("y", DoubleType(), True),
            StructField("z", DoubleType(), True),
            StructField("vx", DoubleType(), True),
            StructField("vy", DoubleType(), True),
            StructField("vz", DoubleType(), True),
            StructField("percentage", DoubleType(), True),
            StructField("voltage", DoubleType(), True),
            StructField("current", DoubleType(), True),
            StructField("ranges_count", DoubleType(), True),
            StructField("min_distance", DoubleType(), True),
            StructField("max_distance", DoubleType(), True),
        ]
    )

    return StructType(
        [
            StructField("robot_id", StringType(), False),
            StructField("event_time", StringType(), False),
            StructField("source_topic", StringType(), False),
            StructField("payload", payload_schema, True),
        ]
    )


def write_postgres(batch_df, batch_id: int) -> None:
    """Write each micro-batch into PostgreSQL operational table."""
    if batch_df.rdd.isEmpty():
        return

    (
        batch_df.select(
            "robot_id",
            "event_ts",
            "source_topic",
            "speed_mps",
            "battery_degradation_score",
            "anomaly_flag",
        )
        .write.mode("append")
        .format("jdbc")
        .option("url", POSTGRES_URL)
        .option("dbtable", "telemetry_operational")
        .option("user", POSTGRES_USER)
        .option("password", POSTGRES_PASSWORD)
        .option("driver", "org.postgresql.Driver")
        .save()
    )


if __name__ == "__main__":
    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    schema = telemetry_schema()

    kafka_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", KAFKA_OFFSETS)
        .load()
    )

    parsed = (
        kafka_df.select(from_json(col("value").cast("string"), schema).alias("e"))
        .select("e.*")
        .withColumn("event_ts", to_timestamp(col("event_time")))
        .withColumn("event_date", to_date(col("event_time")))
        .withColumn(
            "speed_mps",
            sqrt(
                pow(coalesce(col("payload.vx"), lit(0.0)), 2)
                + pow(coalesce(col("payload.vy"), lit(0.0)), 2)
                + pow(coalesce(col("payload.vz"), lit(0.0)), 2)
            ),
        )
        .withColumn(
            "battery_degradation_score",
            when(
                col("payload.percentage").isNotNull(),
                (lit(1.0) - col("payload.percentage")) * lit(100.0),
            ).otherwise(None),
        )
        .withColumn(
            "anomaly_flag",
            when(col("speed_mps") > lit(2.5), lit(1))
            .when(col("payload.percentage") < lit(0.15), lit(1))
            .when(col("payload.min_distance") < lit(0.20), lit(1))
            .otherwise(lit(0)),
        )
    )

    trigger_kwargs = {"availableNow": True} if TRIGGER_ONCE else {}

    # Delta sink (processed zone)
    delta_query = (
        parsed.writeStream.format("delta")
        .queryName("delta_sink_processed_telemetry")
        .outputMode("append")
        .partitionBy("event_date")
        .option("checkpointLocation", CHECKPOINT_DELTA)
        .trigger(**trigger_kwargs)
        .start(PROCESSED_PATH)
    )

    # PostgreSQL sink (operational store)
    postgres_query = (
        parsed.writeStream.queryName("postgres_sink_operational")
        .outputMode("append")
        .foreachBatch(write_postgres)
        .option("checkpointLocation", CHECKPOINT_PG)
        .trigger(**trigger_kwargs)
        .start()
    )

    # In trigger-once mode both queries process available data and self-terminate.
    # In continuous mode, await until manually stopped.
    if TRIGGER_ONCE:
        delta_query.awaitTermination()
        postgres_query.awaitTermination()
    else:
        spark.streams.awaitAnyTermination()
