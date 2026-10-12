-- PostgreSQL operational examples. Replace SESSION_ID with your tv_session cookie value.
-- Fleet monitoring records (replace VEHICLE_ID with one of the five authorised IDs).
SELECT vehicle_id,COUNT(*) AS samples,AVG(temperature) AS average_temperature,MAX(temperature) AS peak_temperature
FROM fleet_readings GROUP BY vehicle_id ORDER BY vehicle_id;
SELECT drive_mode,COUNT(*) AS samples,MAX(temperature) AS peak_temperature
FROM fleet_readings WHERE vehicle_id='VEHICLE_ID' GROUP BY drive_mode;
SELECT severity,status,COUNT(*) AS alerts FROM fleet_alerts WHERE vehicle_id='VEHICLE_ID'
GROUP BY severity,status HAVING COUNT(*)>=1;
SELECT observed_at,temperature,speed FROM fleet_readings
WHERE vehicle_id='VEHICLE_ID' AND observed_at IN
(SELECT updated_at FROM fleet_alerts WHERE vehicle_id='VEHICLE_ID');
EXPLAIN ANALYZE SELECT observed_at,temperature,speed FROM fleet_readings
WHERE vehicle_id='VEHICLE_ID' ORDER BY observed_at DESC LIMIT 120;

-- Automatic readings and alert events are the main application records.
SELECT source,COUNT(*) AS samples,AVG(temperature) AS average_temperature,MAX(temperature) AS peak_temperature
FROM telemetry_readings WHERE session_id='SESSION_ID' GROUP BY source;
SELECT severity,status,COUNT(*) AS alerts FROM thermal_alerts WHERE session_id='SESSION_ID'
GROUP BY severity,status HAVING COUNT(*)>=1;
-- Join a gateway registration with its telemetry, without exposing token hashes.
SELECT c.created_at AS gateway_registered,r.observed_at,r.temperature,r.flow
FROM vehicle_connections c JOIN telemetry_readings r ON c.session_id=r.session_id
WHERE r.session_id='SESSION_ID' AND r.source='gateway' ORDER BY r.observed_at DESC LIMIT 20;
-- Nested query: readings in runs that triggered a critical alert.
SELECT observed_at,temperature,flow FROM telemetry_readings
WHERE session_id='SESSION_ID' AND run_id IN
(SELECT run_id FROM thermal_alerts WHERE session_id='SESSION_ID' AND severity='critical');
EXPLAIN ANALYZE SELECT observed_at,temperature FROM telemetry_readings
WHERE session_id='SESSION_ID' ORDER BY observed_at DESC LIMIT 120;
-- A transaction changes status atomically; rollback leaves the original value.
BEGIN;
UPDATE thermal_alerts SET status='acknowledged' WHERE session_id='SESSION_ID' AND status='active';
ROLLBACK;
-- With a demo_reader role created by your database administrator:
-- GRANT SELECT ON telemetry_readings,thermal_alerts TO demo_reader;
-- REVOKE SELECT ON telemetry_readings,thermal_alerts FROM demo_reader;
