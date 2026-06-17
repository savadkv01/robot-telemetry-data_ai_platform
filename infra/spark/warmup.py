"""
Spark JAR warmup — runs at Docker image build time.
Downloads all required JARs (Delta, Kafka, PostgreSQL JDBC, hadoop-aws)
into /opt/ivy2 so containers never need internet access at runtime.
"""
import os
os.environ.setdefault("PYSPARK_PYTHON", "python3")

from pyspark.sql import SparkSession  # noqa: E402

PACKAGES = ",".join([
    "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
    "io.delta:delta-spark_2.12:3.2.0",
    "org.postgresql:postgresql:42.7.3",
    "org.apache.hadoop:hadoop-aws:3.3.4",
])

spark = (
    SparkSession.builder
    .appName("jar-warmup")
    .config("spark.jars.packages", PACKAGES)
    .config("spark.jars.ivy", "/opt/ivy2")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    )
    .getOrCreate()
)

spark.stop()
print("JAR warmup complete — all JARs cached at /opt/ivy2")
