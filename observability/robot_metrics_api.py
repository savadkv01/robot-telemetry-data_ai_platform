"""Stage 10: Custom robot metrics API for Prometheus.

This service exposes:
- /ingest_event: update custom robot metrics
- /metrics: Prometheus scrape endpoint
- /health: liveness probe
"""

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

app = FastAPI(title="Robot Metrics API", version="1.0.0")

# Event counters
robot_events_total = Counter(
    "robot_events_total",
    "Total robot telemetry events received by custom metrics API",
    ["robot_id", "source_topic"],
)

# Latest value gauges
robot_battery_percentage = Gauge(
    "robot_battery_percentage",
    "Latest robot battery percentage (0 to 1)",
    ["robot_id"],
)

robot_speed_mps = Gauge(
    "robot_speed_mps",
    "Latest robot speed in meters/second",
    ["robot_id"],
)

robot_anomaly_flag = Gauge(
    "robot_anomaly_flag",
    "Latest anomaly flag (0/1)",
    ["robot_id"],
)

# Request latency
ingest_request_seconds = Histogram(
    "robot_ingest_request_seconds",
    "Time spent processing ingest requests",
)


class EventMetricIn(BaseModel):
    robot_id: str
    source_topic: str
    battery_percentage: float | None = None
    speed_mps: float | None = None
    anomaly_flag: int | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest_event")
def ingest_event(payload: EventMetricIn) -> dict[str, bool]:
    with ingest_request_seconds.time():
        robot_events_total.labels(
            robot_id=payload.robot_id, source_topic=payload.source_topic
        ).inc()

        if payload.battery_percentage is not None:
            robot_battery_percentage.labels(robot_id=payload.robot_id).set(
                payload.battery_percentage
            )

        if payload.speed_mps is not None:
            robot_speed_mps.labels(robot_id=payload.robot_id).set(payload.speed_mps)

        if payload.anomaly_flag is not None:
            robot_anomaly_flag.labels(robot_id=payload.robot_id).set(payload.anomaly_flag)

    return {"ok": True}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
