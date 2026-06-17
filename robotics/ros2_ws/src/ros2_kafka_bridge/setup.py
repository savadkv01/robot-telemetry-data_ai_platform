from setuptools import setup

package_name = "ros2_kafka_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/ros2_kafka_bridge"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools", "kafka-python"],
    zip_safe=True,
    maintainer="robotics-de",
    maintainer_email="you@example.com",
    description="Bridge ROS2 telemetry topics to Kafka JSON events.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "bridge_node = ros2_kafka_bridge.bridge_node:main",
        ],
    },
)
