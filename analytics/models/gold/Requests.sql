{{ config(materialized='table', schema='gold') }}

with base as (
  select *
  from {{ ref('TransactionFact') }}
),

requests as (
  select
    transaction_id,
    customer_id,
    booking_id,
    trip_ts,
    booking_status,
    vehicle_type,
    payment_method,
    booking_value,
    ride_distance,
    driver_rating,
    customer_rating,
    trip_undone_reason,
    trip_undone_reason_type

  from base
  where booking_status != 'Completed'
)

select
  *,
  case
    when booking_value is not null
     and ride_distance is not null
     and ride_distance > 0
      then booking_value / ride_distance
    else null
  end as revenue_per_distance
from requests

