FROM python:3.11-slim

# Install OpenJDK 21 + wget
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    procps \
    wget \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# Install Python packages (pyspark pip package includes the full Spark distribution)
RUN pip install --no-cache-dir \
    pyspark==3.5.1 \
    delta-spark==3.2.0 \
    kafka-python==2.0.2 \
    psycopg2-binary==2.9.10 \
    pyarrow==18.1.0 \
    duckdb==1.1.3 \
    pandas==2.2.3

# Symlink spark-submit onto PATH
RUN find /usr/local/lib -maxdepth 6 -name "spark-submit" -type f | head -1 | \
    xargs -I{} ln -sf {} /usr/local/bin/spark-submit

ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3

# Download all required extension JARs directly into PySpark's jars/ directory.
# They are on Spark's classpath at startup with no spark.jars.packages resolution needed.
RUN PYSPARK_JARS=$(python3 -c "import pyspark,os; print(os.path.join(os.path.dirname(pyspark.__file__),'jars'))") && \
    wget -q -P "$PYSPARK_JARS" \
        "https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.1/spark-sql-kafka-0-10_2.12-3.5.1.jar" \
        "https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.1/spark-token-provider-kafka-0-10_2.12-3.5.1.jar" \
        "https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar" \
        "https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.12.0/commons-pool2-2.12.0.jar" \
        "https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.0/delta-spark_2.12-3.2.0.jar" \
        "https://repo1.maven.org/maven2/io/delta/delta-storage/3.2.0/delta-storage-3.2.0.jar" \
        "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar" \
        "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar" \
        "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar" && \
    echo "--- Extension JARs installed ---" && \
    ls "$PYSPARK_JARS" | grep -E "kafka|delta|postgresql|hadoop-aws|aws-java-sdk"
