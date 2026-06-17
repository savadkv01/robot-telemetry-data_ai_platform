from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    gazebo_ros_pkg = get_package_share_directory("gazebo_ros")
    robot_desc_pkg = get_package_share_directory("robot_description")

    urdf_file = os.path.join(robot_desc_pkg, "urdf", "telemetry_bot.urdf.xacro")

    with open(urdf_file, "r", encoding="utf-8") as f:
        robot_description_content = f.read()

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros_pkg, "launch", "gazebo.launch.py")
        )
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description_content}],
    )

    spawn_entity = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        arguments=["-entity", "telemetry_bot", "-topic", "robot_description"],
        output="screen",
    )

    battery_pub = Node(
        package="telemetry_sim",
        executable="battery_publisher",
        name="battery_publisher",
        output="screen",
    )

    imu_odom_pub = Node(
        package="telemetry_sim",
        executable="imu_odom_publisher",
        name="imu_odom_publisher",
        output="screen",
    )

    return LaunchDescription([
        gazebo,
        robot_state_publisher,
        spawn_entity,
        battery_pub,
        imu_odom_pub,
    ])
