{{ config(materialized='table', schema='gold') }}

with base as (
  select *
  from {{ ref('TransactionFact') }}
),

travels as (
  select
    transaction_id,
    customer_id,
    booking_id,
    trip_ts,
    vehicle_type,
    payment_method,
    booking_value,
    ride_distance,
    driver_rating,
    customer_rating

  from base
  where booking_status = 'Completed'
)

select
  *,
  case
    when ride_distance is not null and ride_distance > 0
      then booking_value / ride_distance
    else null
  end as revenue_per_distance
from travels
