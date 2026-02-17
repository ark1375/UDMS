ANALYZE silver.TransactionFact;

EXPLAIN ANALYZE
WITH base AS (
    SELECT
        transaction_id,
        customer_id,
        booking_id,
        trip_ts,
        vehicle_type,
        booking_status,
        payment_method,
        booking_value,
        ride_distance,
        driver_rating,
        customer_rating
    FROM silver.TransactionFact
    WHERE trip_ts IS NOT NULL
      AND vehicle_type IS NOT NULL
      AND booking_status = 'Completed'
      AND ride_distance > 0
      AND booking_value >= 10
      AND trip_ts >= TIMESTAMP '2024-09-01 00:00:00'
      AND trip_ts <  TIMESTAMP '2025-01-01 00:00:00'

      AND vehicle_type IN ('Go Sedan', 'Auto')
),
pairs AS (
    SELECT
        a.vehicle_type,
        date_trunc('hour', a.trip_ts) AS hour_bucket,
        a.payment_method,
        COUNT(*) AS pair_rows,
        COUNT(DISTINCT a.transaction_id) AS a_rides,
        COUNT(DISTINCT b.transaction_id) AS b_rides,
        COUNT(DISTINCT a.customer_id) AS uniq_customers_in_a,
        AVG(a.booking_value) AS avg_value_a,
        AVG(b.booking_value) AS avg_value_b,
        AVG(a.driver_rating) AS avg_driver_rating_a,
        AVG(a.customer_rating) AS avg_customer_rating_a,
        AVG(ABS(epoch(a.trip_ts) - epoch(b.trip_ts))) AS avg_time_diff_seconds
    FROM base a
    JOIN base b
      ON a.vehicle_type = b.vehicle_type 
      	AND a.transaction_id <> b.transaction_id
		AND b.trip_ts BETWEEN a.trip_ts - INTERVAL '3 MINUTE' AND a.trip_ts + INTERVAL '3 MINUTE'
		AND ABS(a.booking_value - b.booking_value) <= 10
		GROUP BY 1,2,3
)
SELECT *
FROM pairs
ORDER BY pair_rows DESC, avg_time_diff_seconds ASC;

EXPLAIN ANALYZE
SELECT
    transaction_id,
    customer_id,
    booking_id,
    trip_ts,
    vehicle_type,
    booking_status,
    payment_method,
    booking_value,
    ride_distance,
    driver_rating,
    customer_rating
FROM silver.TransactionFact
WHERE trip_ts IS NOT NULL
  AND vehicle_type IS NOT NULL
  AND booking_status = 'Completed'
  AND ride_distance > 0
  AND booking_value >= 10
  AND trip_ts >= TIMESTAMP '2024-01-01 00:00:00'
  AND trip_ts <  TIMESTAMP '2025-01-01 00:00:00'
  AND vehicle_type IN ('Go Sedan', 'Auto');


CREATE INDEX IF NOT EXISTS tf_idx_vehicle_status_ts
ON silver.TransactionFact (vehicle_type, booking_status, trip_ts);


CREATE INDEX IF NOT EXISTS tf_ts
ON silver.TransactionFact (trip_ts);


SELECT * FROM duckdb_indexes();

DROP INDEX silver.tf_idx_vehicle_status_ts;
DROP INDEX silver.tf_ts;
EXPLAIN ANALYZE
SELECT
    transaction_id,
    customer_id,
    booking_id,
    trip_ts,
    vehicle_type,
    payment_method,
    booking_status,
    booking_value,
    ride_distance,
    driver_rating,
    customer_rating,
    booking_value / ride_distance AS revenue_per_distance,
    date_trunc('hour', trip_ts) AS trip_hour
FROM silver.TransactionFact
WHERE
    booking_status = 'Completed'
    AND (trip_ts >= TIMESTAMP '2024-05-06 09:00:00' AND trip_ts <  TIMESTAMP '2024-05-06 10:00:00')
    AND vehicle_type = 'Auto'
ORDER BY
    revenue_per_distance DESC,
    driver_rating DESC,
    trip_ts ASC
LIMIT 10;
