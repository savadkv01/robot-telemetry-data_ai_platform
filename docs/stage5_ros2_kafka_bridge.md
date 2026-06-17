# Stage 5 — ROS2 → Kafka Bridge

This stage implements a Python ROS2 subscriber node that converts telemetry messages to JSON and writes to Kafka topic `robot.telemetry.v1`.

## Implemented files

- `robotics/ros2_ws/src/ros2_kafka_bridge/ros2_kafka_bridge/bridge_node.py`
- `robotics/schemas/robot_telemetry_v1.schema.json`

## 1) Build ROS2 workspace

```bash
cd ~/robot-telemetry-platform/robotics/ros2_ws
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

## 2) Kafka topic creation commands

```bash
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --create --topic robot.telemetry.v1 --partitions 3 --replication-factor 1

docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list
```

## 3) Start simulation and ROS2 telemetry

Terminal A:
```bash
cd ~/robot-telemetry-platform/robotics/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch robot_description sim.launch.py
```

## 4) Run ROS2->Kafka bridge

Terminal B:
```bash
cd ~/robot-telemetry-platform/robotics/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

# Optional overrides
export ROBOT_ID=robot-001
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_TELEMETRY_TOPIC=robot.telemetry.v1

ros2 run ros2_kafka_bridge bridge_node
```

## 5) Validate Kafka payloads

Terminal C:
```bash
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic robot.telemetry.v1 --from-beginning
```

You should see JSON events with fields:
- `robot_id`
- `event_time`
- `source_topic`
- `payload`

## 6) Testing procedure checklist

- [ ] `ros2 topic echo /imu` returns messages
- [ ] Bridge logs startup with topic and broker
- [ ] Kafka consumer prints telemetry JSON lines
- [ ] `/battery_state` and `/scan` records appear in Kafka

## Event schema

Schema file: `robotics/schemas/robot_telemetry_v1.schema.json`
