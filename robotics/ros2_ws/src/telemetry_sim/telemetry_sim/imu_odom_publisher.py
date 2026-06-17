import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Quaternion
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu


class ImuOdomPublisher(Node):
    """Publishes synthetic /imu and /odom messages for local telemetry testing."""

    def __init__(self) -> None:
        super().__init__("imu_odom_publisher")
        self.imu_pub = self.create_publisher(Imu, "/imu", 20)
        self.odom_pub = self.create_publisher(Odometry, "/odom", 20)

        self.t = 0.0
        self.dt = 0.1
        self.timer = self.create_timer(self.dt, self.publish_tick)

    def publish_tick(self) -> None:
        self.t += self.dt

        x = 0.2 * self.t
        y = 0.5 * math.sin(self.t / 2.0)
        vx = 0.2
        vy = 0.25 * math.cos(self.t / 2.0)
        yaw = 0.1 * math.sin(self.t / 3.0)

        imu = Imu()
        imu.header.stamp = self.get_clock().now().to_msg()
        imu.header.frame_id = "base_link"
        imu.linear_acceleration.x = 0.05 * math.cos(self.t)
        imu.linear_acceleration.y = 0.03 * math.sin(self.t)
        imu.linear_acceleration.z = 9.81
        imu.angular_velocity.z = 0.1 * math.cos(self.t / 3.0)

        odom = Odometry()
        odom.header.stamp = imu.header.stamp
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.pose.pose.position.x = x
        odom.pose.pose.position.y = y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation = self.yaw_to_quaternion(yaw)
        odom.twist.twist.linear.x = vx
        odom.twist.twist.linear.y = vy
        odom.twist.twist.angular.z = imu.angular_velocity.z

        self.imu_pub.publish(imu)
        self.odom_pub.publish(odom)

    @staticmethod
    def yaw_to_quaternion(yaw: float) -> Quaternion:
        q = Quaternion()
        q.w = math.cos(yaw / 2.0)
        q.z = math.sin(yaw / 2.0)
        return q


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ImuOdomPublisher()
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
