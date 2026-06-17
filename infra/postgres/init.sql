CREATE TABLE IF NOT EXISTS telemetry_operational (
  robot_id TEXT,
  event_ts TIMESTAMP,
  source_topic TEXT,
  speed_mps DOUBLE PRECISION,
  battery_degradation_score DOUBLE PRECISION,
  anomaly_flag INT
);

CREATE INDEX IF NOT EXISTS idx_telemetry_operational_robot_ts
  ON telemetry_operational (robot_id, event_ts);

CREATE TABLE IF NOT EXISTS daily_robot_summary (
  robot_id TEXT,
  event_date DATE,
  events_count BIGINT,
  avg_speed_mps DOUBLE PRECISION,
  max_speed_mps DOUBLE PRECISION,
  avg_battery_degradation DOUBLE PRECISION,
  anomaly_events BIGINT,
  min_battery_pct DOUBLE PRECISION,
  failure_risk_flag INT
);

CREATE INDEX IF NOT EXISTS idx_daily_robot_summary_robot_date
  ON daily_robot_summary (robot_id, event_date);
