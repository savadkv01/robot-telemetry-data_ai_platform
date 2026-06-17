from setuptools import setup

package_name = "telemetry_sim"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/telemetry_sim"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="robotics-de",
    maintainer_email="you@example.com",
    description="ROS2 helper nodes for telemetry simulation.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "battery_publisher = telemetry_sim.battery_publisher:main",
            "imu_odom_publisher = telemetry_sim.imu_odom_publisher:main",
        ],
    },
)
