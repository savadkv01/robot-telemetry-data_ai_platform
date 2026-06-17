"""Synthetic telemetry injector — pipeline testing.

Produces robot.telemetry.v1 JSON events to Kafka, simulating data across
a configurable date range for 2 robots with deliberately different health
profiles so analytics queries return meaningful, distinguishable results:

  robot-001  Healthy robot.   Battery 92 % → drains ~10 % per day.  Speed 0.2–0.8 m/s.  ~2 % anomalies.
  robot-002  Degrading robot. Battery 92 % → drains ~45 % per day.  Speed 0.1–3.5 m/s. ~12 % anomalies.

Total events: EVENTS_PER_ROBOT_PER_DAY × 2 robots × number_of_days

Environment:
  KAFKA_BOOTSTRAP_SERVERS   default: kafka:29092
  KAFKA_TELEMETRY_TOPIC     default: robot.telemetry.v1
  EVENTS_PER_ROBOT_PER_DAY  default: 500
  START_DATE                default: yesterday (YYYY-MM-DD)
  END_DATE                  default: yesterday (YYYY-MM-DD)
"""

import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
TOPIC     = os.environ.get("KAFKA_TELEMETRY_TOPIC",   "robot.telemetry.v1")
EVENTS_N  = int(os.environ.get("EVENTS_PER_ROBOT_PER_DAY", "500"))

_today     = datetime.now(timezone.utc).date()
_yesterday = _today - timedelta(days=1)

def _parse_date(env_var: str, default) -> "date":
    raw = os.environ.get(env_var, "")
    if raw:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    return default

START_DATE = _parse_date("START_DATE", _yesterday)
END_DATE   = _parse_date("END_DATE",   _yesterday)

# Shift window: spread events evenly across an 8-hour shift
SHIFT_SECONDS = 8 * 3600

ROBOTS = {
    "robot-001": dict(
        battery_start   = 0.92,
        drain_per_event = 0.0002,   # ~10 % battery drop per day
        base_speed      = 0.5,
        speed_jitter    = 0.3,
        anomaly_prob    = 0.02,     # 2 % of events are anomalous
    ),
    "robot-002": dict(
        battery_start   = 0.92,    # starts healthy; degrades faster each day
        drain_per_event = 0.0009,   # ~45 % battery drop per day (failing)
        base_speed      = 0.8,
        speed_jitter    = 0.8,
        anomaly_prob    = 0.12,     # 12 % anomaly rate
    ),
}

TOPIC_CYCLE = ["/imu", "/odom", "/battery_state", "/scan"]


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _build_event(robot_id: str, ts: datetime, cfg: dict, idx: int, battery: float) -> dict:
    topic = TOPIC_CYCLE[idx % len(TOPIC_CYCLE)]

    speed = max(0.0, cfg["base_speed"] + random.uniform(-cfg["speed_jitter"], cfg["speed_jitter"]))
    if random.random() < cfg["anomaly_prob"]:
        speed = random.uniform(2.7, 4.5)   # speed spike — triggers anomaly_flag

    t  = idx * 0.1
    vx = speed * math.cos(t * 0.3)
    vy = speed * math.sin(t * 0.3)
    x  = vx * t * 0.5
    y  = vy * t * 0.5

    if topic == "/imu":
        payload = {
            "ax": round(random.gauss(0, 0.05), 5),
            "ay": round(random.gauss(0, 0.05), 5),
            "az": round(9.81 + random.gauss(0, 0.02), 5),
            "gx": round(random.gauss(0, 0.01), 5),
            "gy": round(random.gauss(0, 0.01), 5),
            "gz": round(vx * 0.05, 5),
        }
    elif topic == "/odom":
        payload = {
            "x":  round(x, 4),
            "y":  round(y, 4),
            "z":  0.0,
            "vx": round(vx, 4),
            "vy": round(vy, 4),
            "vz": 0.0,
        }
    elif topic == "/battery_state":
        payload = {
            "percentage": round(battery, 5),
            "voltage":    round(24.0 * battery, 4),
            "current":    round(-2.0 - random.uniform(0, 0.3), 4),
        }
    else:  # /scan
        min_d = round(max(0.05, random.uniform(0.3, 4.0)), 4)
        payload = {
            "ranges_count": 360.0,
            "min_distance": min_d,
            "max_distance": round(min_d + random.uniform(1.5, 6.0), 4),
        }

    return {
        "robot_id":     robot_id,
        "event_time":   _iso(ts),
        "source_topic": topic,
        "payload":      payload,
    }


def _make_producer() -> KafkaProducer:
    """Connect to Kafka with retry, returning a ready producer."""
    for attempt in range(1, 13):
        try:
            producer = KafkaProducer(
                bootstrap_servers=BOOTSTRAP.split(","),
                value_serializer=lambda v: json.dumps(v).encode(),
                key_serializer=lambda k: k.encode() if k else None,
                acks="all",
                linger_ms=50,
                retries=5,
            )
            print(f"Kafka producer connected to {BOOTSTRAP}")
            return producer
        except NoBrokersAvailable:
            print(f"  Kafka not ready (attempt {attempt}/12), retrying in 5 s ...")
            time.sleep(5)
    print("ERROR: Could not connect to Kafka after 12 retries.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    random.seed(42)   # reproducible data across runs

    producer = _make_producer()

    # Build list of dates in [START_DATE, END_DATE] inclusive
    num_days = (END_DATE - START_DATE).days + 1
    days = [START_DATE + timedelta(days=d) for d in range(num_days)]

    print(f"Date range : {START_DATE}  →  {END_DATE}  ({num_days} day(s))")
    print(f"Robots     : {list(ROBOTS.keys())}")
    print(f"Events/robot/day: {EVENTS_N}")
    print(f"Total events expected: {EVENTS_N * len(ROBOTS) * num_days}\n")

    interval_sec = SHIFT_SECONDS // EVENTS_N   # spacing between events

    total = 0
    for robot_id, cfg in ROBOTS.items():
        battery = cfg["battery_start"]
        for day in days:
            day_start = datetime(day.year, day.month, day.day, 8, 0, 0, tzinfo=timezone.utc)
            for i in range(EVENTS_N):
                battery = max(0.0, battery - cfg["drain_per_event"])
                ts      = day_start + timedelta(seconds=i * interval_sec)
                event   = _build_event(robot_id, ts, cfg, i, battery)
                producer.send(TOPIC, key=robot_id, value=event)
                total += 1

            producer.flush()
            print(f"  {robot_id} | {day} | {EVENTS_N} events sent  (battery={battery:.3f})")

    producer.flush()
    producer.close()
    print(f"\nDone. Total events produced to '{TOPIC}': {total}")


if __name__ == "__main__":
    main()
