import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState


class BatteryPublisher(Node):
    """Publishes synthetic battery telemetry on /battery_state."""

    def __init__(self) -> None:
        super().__init__("battery_publisher")
        self.publisher = self.create_publisher(BatteryState, "/battery_state", 10)
        self.level = 1.0
        self.timer = self.create_timer(1.0, self.publish_battery)

    def publish_battery(self) -> None:
        self.level = max(0.0, self.level - 0.003)

        msg = BatteryState()
        msg.percentage = float(self.level)
        msg.voltage = 24.0 * self.level
        msg.current = -2.0
        msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        msg.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION

        self.publisher.publish(msg)
        self.get_logger().info(
            f"Published /battery_state percentage={msg.percentage:.3f} voltage={msg.voltage:.2f}",
            throttle_duration_sec=5.0,
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BatteryPublisher()
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
