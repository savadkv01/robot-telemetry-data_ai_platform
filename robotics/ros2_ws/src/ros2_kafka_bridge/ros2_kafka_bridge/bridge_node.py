"""Stage 5: ROS2 -> Kafka telemetry bridge.

Subscribes to ROS2 telemetry topics (`/imu`, `/odom`, `/battery_state`, `/scan`),
normalizes each message into the `robot.telemetry.v1` JSON event format, and
publishes it to a Kafka topic.

Event format (see robotics/schemas/robot_telemetry_v1.schema.json):
    {
        "robot_id": "robot-001",
        "event_time": "2026-06-17T12:00:00.000000+00:00",
        "source_topic": "/imu",
        "payload": { ... topic-specific fields ... }
    }

Environment overrides:
    ROBOT_ID                  default: robot-001
    KAFKA_BOOTSTRAP_SERVERS   default: localhost:9092
    KAFKA_TELEMETRY_TOPIC     default: robot.telemetry.v1
"""

import json
import os
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Imu, LaserScan

from kafka import KafkaProducer


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class Ros2KafkaBridge(Node):
    """Bridges ROS2 telemetry topics to a Kafka topic as JSON events."""

    def __init__(self) -> None:
        super().__init__("ros2_kafka_bridge")

        self.robot_id = os.environ.get("ROBOT_ID", "robot-001")
        self.bootstrap_servers = os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.telemetry_topic = os.environ.get(
            "KAFKA_TELEMETRY_TOPIC", "robot.telemetry.v1"
        )

        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
            acks="all",
            linger_ms=20,
            retries=5,
        )

        self.create_subscription(Imu, "/imu", self.on_imu, 20)
        self.create_subscription(Odometry, "/odom", self.on_odom, 20)
        self.create_subscription(BatteryState, "/battery_state", self.on_battery, 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, 10)

        self.published = 0

        self.get_logger().info(
            f"ros2_kafka_bridge started | robot_id={self.robot_id} "
            f"| brokers={self.bootstrap_servers} | topic={self.telemetry_topic}"
        )

    def _publish(self, source_topic: str, payload: dict) -> None:
        """Build the telemetry event envelope and send it to Kafka."""
        event = {
            "robot_id": self.robot_id,
            "event_time": _now_iso(),
            "source_topic": source_topic,
            "payload": payload,
        }
        try:
            self.producer.send(self.telemetry_topic, key=self.robot_id, value=event)
        except Exception as exc:  # noqa: BLE001 - log and keep the node alive
            self.get_logger().error(f"Kafka publish failed for {source_topic}: {exc}")
            return

        self.published += 1
        if self.published % 50 == 0:
            self.get_logger().info(
                f"Published {self.published} telemetry events "
                f"(last source={source_topic})"
            )

    def on_imu(self, msg: Imu) -> None:
        payload = {
            "ax": float(msg.linear_acceleration.x),
            "ay": float(msg.linear_acceleration.y),
            "az": float(msg.linear_acceleration.z),
            "gx": float(msg.angular_velocity.x),
            "gy": float(msg.angular_velocity.y),
            "gz": float(msg.angular_velocity.z),
        }
        self._publish("/imu", payload)

    def on_odom(self, msg: Odometry) -> None:
        position = msg.pose.pose.position
        linear = msg.twist.twist.linear
        payload = {
            "x": float(position.x),
            "y": float(position.y),
            "z": float(position.z),
            "vx": float(linear.x),
            "vy": float(linear.y),
            "vz": float(linear.z),
        }
        self._publish("/odom", payload)

    def on_battery(self, msg: BatteryState) -> None:
        payload = {
            "percentage": float(msg.percentage),
            "voltage": float(msg.voltage),
            "current": float(msg.current),
        }
        self._publish("/battery_state", payload)

    def on_scan(self, msg: LaserScan) -> None:
        finite = [
            float(r)
            for r in msg.ranges
            if r is not None and r == r and r != float("inf")
        ]
        payload = {
            "ranges_count": float(len(msg.ranges)),
            "min_distance": min(finite) if finite else None,
            "max_distance": max(finite) if finite else None,
        }
        self._publish("/scan", payload)

    def destroy_node(self) -> bool:
        """Flush and close the Kafka producer on shutdown."""
        try:
            self.producer.flush(timeout=5)
            self.producer.close(timeout=5)
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup
            self.get_logger().warning(f"Error closing Kafka producer: {exc}")
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Ros2KafkaBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
